"""Voice loop: PTT -> ASR -> brain -> streaming TTS -> repeat.

Key UX move: we speak the reply sentence-by-sentence as the brain streams,
instead of waiting for the whole response. First audio lands within a
second of the brain producing its first sentence, which is the difference
between "alive" and "chatbot".

State transitions:
    idle -> listening (PTT press)
    listening -> idle (no speech detected)
    listening -> thinking (after transcription)
    thinking -> speaking (first sentence ready)
    speaking -> idle (playback drained + brain done)
"""

from __future__ import annotations

import asyncio

from rich.console import Console

import numpy as np

from sabrina.brain.protocol import Brain, CancelToken, Done, Image, Message, TextDelta
from sabrina.bus import EventBus
from sabrina.config import Settings
from sabrina.events import (
    AssistantReply,
    BargeInDetected,
    SpeakFinished,
    SpeakStarted,
    ThinkingFinished,
    ThinkingStarted,
    UserMessage,
)
from sabrina.listener.protocol import Listener
from sabrina.listener.ptt import PushToTalk
from sabrina.listener.vad import AudioMonitor, SileroVAD
from sabrina.logging import get_logger
from sabrina.memory.embed import Embedder, build_embedder
from sabrina.memory.store import MemoryStore, SearchHit, new_session_id
from sabrina.speaker.protocol import Speaker
from sabrina.state import StateMachine

log = get_logger(__name__)

_SYSTEM = (
    "You are Sabrina, a helpful, concise personal assistant speaking to the user "
    "through a voice interface. Reply in 1-3 short sentences. Don't use markdown, "
    "bullet lists, or code blocks -- your reply will be spoken aloud. If the user "
    "asks for something you can't do yet (e.g. control apps), say so briefly."
)


def _format_retrieved(hits: list[SearchHit], max_chars_per_hit: int = 180) -> str:
    """Turn search hits into a compact block the brain sees as system context.

    One line per hit, "[date role] snippet". Distance is hidden from the brain
    (not useful) but logged for tuning.
    """
    lines = ["Earlier in our conversations you might find relevant:"]
    for h in hits:
        stamp = h.message.ts.strftime("%Y-%m-%d")
        snippet = h.message.content.strip().replace("\n", " ")
        if len(snippet) > max_chars_per_hit:
            snippet = snippet[: max_chars_per_hit - 1] + "\u2026"
        lines.append(f"- [{stamp} {h.message.role}] {snippet}")
    return "\n".join(lines)


# Characters that terminate a sentence for the streaming TTS buffer.
# Newlines too, so paragraph-ish replies still flow.
_TERMINATORS = ".!?\n"


def _split_off_sentence(buf: str) -> tuple[str | None, str]:
    """If `buf` contains a sentence terminator, split at the first one.

    Returns (sentence_to_speak, remainder). If no terminator, returns
    (None, buf). Ignores terminators inside tight decimal numbers
    ("3.14") by requiring whitespace or end-of-buffer after the terminator.
    """
    for i, ch in enumerate(buf):
        if ch in _TERMINATORS:
            # Require the next char to be whitespace/EOS to avoid "3.14" splits.
            nxt = buf[i + 1 : i + 2]
            if nxt == "" or nxt.isspace():
                sentence = buf[: i + 1].strip()
                remainder = buf[i + 1 :].lstrip()
                return (sentence or None, remainder)
    return (None, buf)


def _make_barge_in_vad(settings: Settings | None) -> SileroVAD | None:
    """Construct and eagerly warm up a Silero VAD for barge-in, or None.

    Returns None when barge-in is disabled OR the silero-vad package
    can't be loaded (broken install, missing wheel, etc). The voice loop
    then runs without barge-in rather than crashing on first speaking
    phase. Mirrors memory/store.py:_try_enable_vec graceful-degrade.

    Lives at module scope so `test_smoke.py` can exercise the degrade
    path without spinning up the full voice loop.
    """
    if settings is None or not settings.barge_in.enabled:
        return None
    candidate = SileroVAD(
        threshold=settings.barge_in.threshold,
        min_speech_ms=settings.barge_in.min_speech_ms,
    )
    try:
        candidate._ensure_loaded()
    except Exception as exc:  # noqa: BLE001
        log.warning("vad.unavailable", error=str(exc))
        return None
    return candidate


async def run_voice_loop(
    brain: Brain,
    listener: Listener,
    speaker: Speaker,
    bus: EventBus,
    sm: StateMachine,
    console: Console,
    hotkey: str = "shift_r",
    input_device: int | str | None = None,
    memory: MemoryStore | None = None,
    load_recent: int = 20,
    settings: Settings | None = None,
) -> None:
    history: list[Message] = []
    session_id = new_session_id()

    if memory is not None and load_recent > 0:
        loaded = memory.load_recent(load_recent)
        history.extend(m.to_message() for m in loaded)
        if loaded:
            console.print(
                f"[dim](loaded {len(loaded)} message(s) from memory; "
                f"session={session_id})[/]"
            )

    # -- semantic memory wiring (optional) -----------------------------------
    # Enabled when config says so AND the vec table came up successfully in the
    # MemoryStore. Falls back to plain rolling-context if anything's missing.
    semantic_enabled = (
        settings is not None
        and memory is not None
        and settings.memory.enabled
        and settings.memory.semantic.enabled
        and memory.vec_enabled
    )
    embedder: Embedder | None = None
    warmup_task: asyncio.Task | None = None
    if semantic_enabled:
        try:
            embedder = build_embedder(settings.memory.semantic.embedding_model)
        except Exception as exc:  # noqa: BLE001 - degrade to text-only
            console.print(f"[yellow]semantic memory disabled ({exc})[/]")
            semantic_enabled = False
            embedder = None
    if semantic_enabled and embedder is not None:
        # Warm the model off the hot path so the first user turn isn't the
        # one paying the 1-2s torch/ONNX load.
        async def _warm() -> None:
            try:
                await asyncio.to_thread(embedder.warmup)
                log.info("embedder.ready", model=embedder.model_name, dim=embedder.dim)
            except Exception as exc:  # noqa: BLE001
                log.warning("embedder.warmup_failed", error=str(exc))

        warmup_task = asyncio.create_task(_warm())

    # --- barge-in wiring (optional) -----------------------------------------
    # When enabled, a Silero VAD monitors the mic during each speaking phase.
    # If the user starts talking mid-reply, the CancelToken trips, the brain
    # stream exits early, the speaker is stopped, and (if continue_on_interrupt)
    # the captured audio becomes the next user turn without a PTT press.
    vad: SileroVAD | None = _make_barge_in_vad(settings)

    ptt = PushToTalk(hotkey, input_device=input_device)
    ptt.start()

    # --- vision wiring (optional) -------------------------------------------
    # `settings` carries the [vision] config and the api key. If it's None,
    # vision stays off regardless of the toml settings. Keeps the old
    # signature usable for minimal tests.
    vision_hotkey = None
    vision_enabled = (
        settings is not None
        and settings.vision.trigger != "off"
        and settings.anthropic_api_key is not None
    )
    vision_voice_phrase = vision_enabled and settings.vision.trigger in {
        "voice_phrase",
        "both",
    }
    vision_hotkey_mode = vision_enabled and settings.vision.trigger in {
        "hotkey",
        "both",
    }
    if vision_hotkey_mode:
        from sabrina.vision.hotkey import VisionHotkey

        vision_hotkey = VisionHotkey(settings.vision.hotkey)
        try:
            vision_hotkey.start()
        except Exception as exc:  # noqa: BLE001
            console.print(
                f"[yellow]vision hotkey not available ({exc}); "
                "voice-phrase trigger still works.[/]"
            )
            vision_hotkey = None

    console.print(
        f"[bold green]Sabrina[/] voice loop ready. "
        f"Hold [bold]{hotkey}[/] to talk. Ctrl+C to quit."
    )
    console.print(
        f"[dim]brain={brain.name}  listener={listener.name}  speaker={speaker.name}[/]"
    )
    if vision_enabled:
        trig = settings.vision.trigger
        pieces = []
        if vision_voice_phrase:
            pieces.append("say 'look at my screen'")
        if vision_hotkey_mode and vision_hotkey is not None:
            pieces.append(f"press {settings.vision.hotkey}")
        if pieces:
            console.print(f"[dim]vision: {' or '.join(pieces)} (trigger={trig})[/]")

    # Audio buffered from a barge-in that will feed the next turn instead
    # of waiting for a PTT press. Set at end of speaking when cancel fired.
    pending_barge_audio: np.ndarray | None = None

    try:
        while True:
            # ---- 1. listen --------------------------------------------------
            if pending_barge_audio is not None and pending_barge_audio.size > 0:
                audio = pending_barge_audio
                pending_barge_audio = None
                console.print("[dim](barge-in audio captured; re-transcribing...)[/]")
            else:
                pending_barge_audio = None
                await sm.transition("listening", reason="ptt_wait")
                console.print("[dim](hold to talk)[/]", end="\r")
                audio = await ptt.record_while_held()
            if audio.size == 0:
                console.print("[dim](no audio captured)[/]                  ")
                await sm.transition("idle", reason="empty_audio")
                continue

            # ---- 2. transcribe ---------------------------------------------
            console.print("[dim](transcribing ...)[/]                 ", end="\r")
            transcript = await listener.transcribe(audio)
            user_text = transcript.text.strip()
            if not user_text:
                console.print("[dim](no speech detected)[/]              ")
                await sm.transition("idle", reason="no_speech")
                continue
            console.print(f"[bold cyan]you>[/] {user_text}                ")

            await sm.transition("thinking", reason="user_message")

            # --- vision? -------------------------------------------------
            # Decide if this turn attaches a screenshot. Two ways in: the
            # user said a trigger phrase, or they pre-armed the turn with
            # the vision hotkey. Hotkey consumes the flag here (one turn
            # only); voice-phrase is stateless.
            use_vision = False
            if vision_enabled:
                from sabrina.vision.triggers import should_trigger_vision

                hotkey_armed = vision_hotkey is not None and vision_hotkey.consume()
                phrase_matched = vision_voice_phrase and should_trigger_vision(
                    user_text
                )
                use_vision = hotkey_armed or phrase_matched

            turn_brain: Brain = brain
            turn_system = _SYSTEM
            turn_user_msg = Message(role="user", content=user_text)

            if use_vision:
                try:
                    from sabrina.brain.claude import ClaudeBrain
                    from sabrina.vision.see import (
                        DEFAULT_VISION_SYSTEM_PROMPT,
                        capture as capture_screen,
                    )

                    console.print("[dim](capturing screen ...)[/]          ", end="\r")
                    shot = await asyncio.to_thread(capture_screen, settings)
                    console.print(
                        f"[dim](screen {shot.source_width}x{shot.source_height} "
                        f"-> {shot.width}x{shot.height}, "
                        f"{len(shot.data)/1024:.0f} KB)[/]            "
                    )
                    turn_user_msg = Message(
                        role="user",
                        content=user_text,
                        images=(Image(data=shot.data, media_type=shot.media_type),),
                    )
                    api_key = settings.anthropic_api_key.get_secret_value()
                    vision_model = (
                        settings.vision.model or settings.brain.claude.fast_model
                    )
                    turn_brain = ClaudeBrain(
                        api_key=api_key,
                        model=vision_model,
                        max_tokens=settings.brain.claude.max_tokens,
                    )
                    turn_system = DEFAULT_VISION_SYSTEM_PROMPT
                except Exception as exc:  # noqa: BLE001 - fall back to text
                    console.print(
                        f"[yellow]vision failed ({exc}); answering without screen.[/]"
                    )
                    use_vision = False

            history.append(turn_user_msg)
            user_msg_id: int | None = None
            if memory is not None:
                # We store just the text in long-term memory — images are
                # ephemeral and would bloat the SQLite file fast.
                user_msg_id = memory.append(session_id, "user", user_text)
            await bus.publish(UserMessage(text=user_text))
            await bus.publish(ThinkingStarted(tier=turn_brain.name))

            # --- semantic retrieval ---------------------------------------
            # Embed the user's turn, pull top-k relevant older turns, and
            # append them to the system prompt as a compact "Earlier..."
            # block. Everything async-safe: model calls live on a thread.
            retrieved_block: str | None = None
            user_embedding: list[float] | None = None
            if semantic_enabled and embedder is not None and memory is not None:
                try:
                    user_embedding = await asyncio.to_thread(embedder.embed, user_text)
                    sem_cfg = settings.memory.semantic
                    exclude = set(memory.recent_ids(sem_cfg.min_age_turns))
                    if user_msg_id is not None:
                        exclude.add(user_msg_id)

                    def _do_search(vec: list[float]) -> list[SearchHit]:
                        return memory.search(
                            vec,
                            k=sem_cfg.top_k,
                            max_distance=sem_cfg.max_distance,
                            exclude_ids=exclude,
                        )

                    hits = await asyncio.to_thread(_do_search, user_embedding)
                    if hits:
                        retrieved_block = _format_retrieved(hits)
                        log.info(
                            "semantic.hits",
                            count=len(hits),
                            top_distance=round(hits[0].distance, 3),
                        )
                except Exception as exc:  # noqa: BLE001 - never fail the turn
                    log.warning("semantic.retrieval_failed", error=str(exc))

            if retrieved_block:
                turn_system = f"{turn_system}\n\n{retrieved_block}"
                console.print(
                    f"[dim](memory: {retrieved_block.count(chr(10))} "
                    f"earlier turn(s) attached)[/]"
                )

            # Persist the user turn's embedding now that search is done
            # (order doesn't matter; this just avoids a redundant embed call).
            if (
                user_embedding is not None
                and user_msg_id is not None
                and memory is not None
                and memory.vec_enabled
            ):
                try:
                    await asyncio.to_thread(
                        memory.insert_embedding, user_msg_id, user_embedding
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("semantic.insert_user_failed", error=str(exc))

            # ---- 3. stream reply + speak sentence-by-sentence ---------------
            console.print("[bold magenta]sabrina>[/] ", end="")
            reply_parts: list[str] = []
            buf = ""
            speak_queue: asyncio.Queue[str | None] = asyncio.Queue()
            in_tok: int | None = None
            out_tok: int | None = None

            # Per-turn cancel machinery. The token threads through brain.chat
            # and speaker.speak; the monitor starts on first spoken sentence
            # so its dead-zone timer aligns with actual TTS onset.
            cancel_token = CancelToken()
            monitor: AudioMonitor | None = None
            if vad is not None and settings is not None:
                monitor = AudioMonitor(
                    vad,
                    cancel_token,
                    device=input_device,
                    dead_zone_ms=settings.barge_in.dead_zone_ms,
                )

            async def _speaker_worker() -> None:
                """Consume sentences from the queue, speak them in order.

                On cancel, drain remaining queue items without speaking them.
                Start the barge-in monitor when the first sentence goes out so
                its dead-zone aligns with real TTS onset (not with thinking).
                """
                first_sentence = True
                while True:
                    item = await speak_queue.get()
                    if item is None:
                        return
                    if cancel_token.cancelled:
                        continue  # drain remaining queued sentences silently
                    if first_sentence:
                        await sm.transition("speaking", reason="first_sentence")
                        if monitor is not None:
                            monitor.start()
                        first_sentence = False
                    await bus.publish(SpeakStarted(engine=speaker.name, text=item))
                    result = await speaker.speak(item, cancel_token=cancel_token)
                    await bus.publish(
                        SpeakFinished(engine=speaker.name, duration_s=result.duration_s)
                    )

            speaker_task = asyncio.create_task(_speaker_worker())

            try:
                async for ev in turn_brain.chat(
                    history, system=turn_system, cancel_token=cancel_token
                ):
                    if isinstance(ev, TextDelta):
                        console.print(ev.text, end="", highlight=False, soft_wrap=True)
                        reply_parts.append(ev.text)
                        buf += ev.text
                        while True:
                            sentence, buf = _split_off_sentence(buf)
                            if sentence is None:
                                break
                            await speak_queue.put(sentence)
                    elif isinstance(ev, Done):
                        in_tok, out_tok = ev.input_tokens, ev.output_tokens
            except Exception as exc:  # noqa: BLE001 - loop must survive
                console.print(f"\n[red]brain error:[/] {exc}")
                await speak_queue.put(None)
                await speaker_task
                if monitor is not None:
                    monitor.stop()
                if sm.state != "idle":
                    await sm.transition("idle", reason="brain_error")
                continue

            # Flush any trailing text that never hit a terminator (unless
            # cancelled — we want to stop speaking, not queue more).
            tail = buf.strip()
            if tail and not cancel_token.cancelled:
                await speak_queue.put(tail)
            await speak_queue.put(None)
            await speaker_task

            # Stop the monitor and grab whatever audio it captured. Returns
            # None unless VAD actually fired.
            barge_audio = monitor.stop() if monitor is not None else None

            # --- barge-in path -------------------------------------------
            if cancel_token.cancelled:
                # Belt-and-suspenders: ensure speaker is quiet. The poll
                # task inside speaker.speak should already have called
                # stop(), but calling it again is harmless.
                try:
                    await speaker.stop()
                except Exception as exc:  # noqa: BLE001
                    log.debug("speaker.stop_failed", err=str(exc))
                await bus.publish(BargeInDetected())
                log.info("bargein.handled", captured_samples=int(barge_audio.size) if barge_audio is not None else 0)
                console.print("\n[yellow](interrupted)[/]")
                # Drop the partial reply — don't add to history or memory.
                # Stale partials are bad context for the next turn.
                if (
                    settings is not None
                    and settings.barge_in.continue_on_interrupt
                    and barge_audio is not None
                    and barge_audio.size > 0
                ):
                    pending_barge_audio = barge_audio
                if sm.state == "speaking":
                    await sm.transition("idle", reason="barge_in")
                # Skip the rest of the normal end-of-turn bookkeeping
                # (history/memory writes, token log). Loop continues.
                continue

            console.print()  # newline after stream
            reply = "".join(reply_parts)
            history.append(Message(role="assistant", content=reply))
            if memory is not None:
                reply_msg_id = memory.append(session_id, "assistant", reply)
                if (
                    semantic_enabled
                    and embedder is not None
                    and memory.vec_enabled
                    and reply.strip()
                ):
                    try:
                        reply_embedding = await asyncio.to_thread(embedder.embed, reply)
                        await asyncio.to_thread(
                            memory.insert_embedding, reply_msg_id, reply_embedding
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.warning("semantic.insert_assistant_failed", error=str(exc))
            await bus.publish(AssistantReply(text=reply, tier=turn_brain.name))
            await bus.publish(
                ThinkingFinished(
                    tier=turn_brain.name, input_tokens=in_tok, output_tokens=out_tok
                )
            )
            if sm.state != "idle":
                await sm.transition("idle", reason="reply_done")
            if in_tok is not None or out_tok is not None:
                console.print(f"[dim](tokens in={in_tok} out={out_tok})[/]")
    except (KeyboardInterrupt, asyncio.CancelledError):
        console.print("\n[dim]bye.[/]")
    finally:
        ptt.stop()
        if vision_hotkey is not None:
            vision_hotkey.stop()
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
