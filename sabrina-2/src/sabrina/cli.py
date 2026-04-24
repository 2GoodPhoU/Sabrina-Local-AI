"""Top-level CLI.

Flat command surface. Each subsystem gets one primary verb:
  sabrina chat                  -- text REPL against a brain
  sabrina voice                 -- push-to-talk voice loop (ASR + brain + TTS)
  sabrina tts "hello"           -- synthesize + play text
  sabrina tts-voices            -- list Piper voice presets
  sabrina tts-download <preset> -- fetch a Piper voice
  sabrina tts-compare "hello"   -- play text through every available voice
  sabrina asr <path.wav>        -- transcribe an audio file
  sabrina asr-record [-s N]     -- record mic for N seconds, transcribe
  sabrina memory-show [-n N]    -- print the last N stored messages
  sabrina memory-clear          -- wipe the memory store (asks for confirmation)
  sabrina memory-stats          -- row counts + embedding coverage
  sabrina memory-reindex        -- embed all messages lacking vectors (--drop to rebuild)
  sabrina memory-search "q"     -- semantic search for past turns
  sabrina test-audio            -- list audio devices
  sabrina config-show           -- dump loaded config (secrets redacted)
  sabrina version
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from sabrina import __version__
from sabrina.brain.claude import ClaudeBrain
from sabrina.brain.ollama import OllamaBrain
from sabrina.brain.protocol import Brain
from sabrina.bus import EventBus
from sabrina.chat import run_repl
from sabrina.config import load_settings, project_root
from sabrina.logging import setup_logging
from sabrina.memory.store import MemoryStore
from sabrina.speaker.protocol import Speaker
from sabrina.state import StateMachine

app = typer.Typer(
    name="sabrina",
    help="Sabrina AI - personal daily-driver assistant.",
    no_args_is_help=True,
    add_completion=False,
)


# ---------------------------------------------------------------------------
# brain / chat
# ---------------------------------------------------------------------------


def _open_memory() -> MemoryStore | None:
    """Return a MemoryStore if enabled in config, else None.

    If `[memory.semantic]` is on, we pass the embedding dim so the
    `vec_messages` virtual table comes up ready to accept vectors.
    Resolving the dim here avoids importing torch on every `sabrina --help`.
    """
    settings = load_settings()
    if not settings.memory.enabled:
        return None
    raw = Path(settings.memory.db_path)
    path = raw if raw.is_absolute() else (project_root() / raw)
    dim: int | None = None
    if settings.memory.semantic.enabled:
        # Resolve the dim without instantiating the embedder. MiniLM-L6
        # is hard-coded at 384; other models will need a lookup when we
        # support them (see decision 007, thin spots).
        from sabrina.memory.embed import DEFAULT_DIM, DEFAULT_MODEL

        if settings.memory.semantic.embedding_model == DEFAULT_MODEL:
            dim = DEFAULT_DIM
        else:
            # Unknown model — instantiate eagerly so the store knows the dim.
            from sabrina.memory.embed import build_embedder

            emb = build_embedder(settings.memory.semantic.embedding_model)
            emb.warmup()
            dim = emb.dim or DEFAULT_DIM
    return MemoryStore(path, embedding_dim=dim)


def _build_brain(backend: str, model: str | None) -> Brain:
    settings = load_settings()
    if backend == "claude":
        key = (
            settings.anthropic_api_key.get_secret_value()
            if settings.anthropic_api_key
            else ""
        )
        if not key:
            raise ValueError(
                "No Anthropic API key found. Expected ANTHROPIC_API_KEY in your .env file "
                "(at the project root) or shell environment. Run `sabrina config-show` "
                "to inspect the loaded config."
            )
        return ClaudeBrain(
            api_key=key,
            model=model or settings.brain.claude.model,
            max_tokens=settings.brain.claude.max_tokens,
        )
    if backend == "ollama":
        return OllamaBrain(
            host=settings.brain.ollama.host,
            model=model or settings.brain.ollama.model,
        )
    raise typer.BadParameter(f"Unknown brain: {backend!r}. Try 'claude' or 'ollama'.")


@app.command()
def version() -> None:
    """Print the Sabrina version."""
    typer.echo(f"sabrina {__version__}")


@app.command()
def chat(
    brain: str = typer.Option(
        None,
        "--brain",
        "-b",
        help="Backend: 'claude' or 'ollama'. Default from sabrina.toml.",
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Override the model name for the chosen backend.",
    ),
) -> None:
    """Open an interactive text chat against a brain backend."""
    settings = load_settings()
    setup_logging(settings.logging.level)
    chosen = brain or settings.brain.default

    console = Console()
    bus = EventBus()
    sm = StateMachine(bus=bus)

    try:
        b = _build_brain(chosen, model)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        console.print(
            "[dim]Tip: copy .env.example to .env and set ANTHROPIC_API_KEY, "
            "or pass --brain ollama to use the local model.[/]"
        )
        raise typer.Exit(code=1) from None

    memory = _open_memory()
    try:
        asyncio.run(
            run_repl(
                b,
                bus,
                sm,
                console,
                memory=memory,
                load_recent=settings.memory.load_recent,
            )
        )
    finally:
        if memory is not None:
            memory.close()


@app.command("config-show")
def config_show() -> None:
    """Print the loaded config (with secrets redacted)."""
    settings = load_settings()
    data = settings.model_dump()
    if data.get("anthropic_api_key"):
        data["anthropic_api_key"] = "***redacted***"
    import json

    typer.echo(json.dumps(data, indent=2, default=str))


@app.command("settings")
def settings_gui() -> None:
    """Open the graphical settings window.

    Writes back to sabrina.toml, preserving comments. Running commands do
    not pick up changes live — restart `sabrina voice` (etc.) to apply.
    """
    # Lazy import keeps customtkinter off the hot path for other commands.
    try:
        from sabrina.gui.settings import open_settings
    except ImportError as e:
        typer.secho(
            f"Settings GUI unavailable ({e}). Try `uv sync` to install customtkinter.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from None
    open_settings()


# ---------------------------------------------------------------------------
# speaker / tts
# ---------------------------------------------------------------------------


def _parse_device(raw: str | int | None) -> int | str | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    return int(raw) if raw.isdigit() else raw


def _build_speaker(engine: str, voice_override: str | None = None) -> Speaker:
    settings = load_settings()
    device = _parse_device(settings.tts.output_device)
    if engine == "piper":
        from sabrina.speaker.piper import PiperSpeaker

        model = settings.tts.piper.voice_model
        model_path = (
            Path(model)
            if Path(model).is_absolute()
            else (project_root() / model).resolve()
        )
        return PiperSpeaker(
            voice_model=model_path,
            binary=settings.tts.piper.binary or None,
            output_device=device,
            length_scale=settings.tts.piper.length_scale,
            speaker_id=settings.tts.piper.speaker_id,
        )
    if engine == "sapi":
        from sabrina.speaker.sapi import SapiSpeaker

        return SapiSpeaker(
            voice=voice_override or settings.tts.sapi.voice,
            rate=settings.tts.sapi.rate,
        )
    raise typer.BadParameter(f"Unknown tts engine: {engine!r}. Try 'piper' or 'sapi'.")


@app.command("tts")
def tts(
    text: str = typer.Argument(..., help="What to say."),
    engine: str = typer.Option(
        None, "--engine", "-e", help="'piper' or 'sapi'. Default from sabrina.toml."
    ),
    voice: str = typer.Option(None, "--voice", "-v", help="Voice name override."),
) -> None:
    """Synthesize text and play it through the selected speaker."""
    settings = load_settings()
    setup_logging(settings.logging.level)
    chosen = engine or settings.tts.default
    try:
        speaker = _build_speaker(chosen, voice_override=voice)
    except (FileNotFoundError, ValueError) as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

    async def _go() -> None:
        result = await speaker.speak(text, voice=voice)
        tail = (
            f" @ {result.sample_rate} Hz ({result.samples} samples)"
            if result.samples
            else ""
        )
        typer.echo(f"[{result.engine}] played in {result.duration_s:.2f}s{tail}")

    asyncio.run(_go())


@app.command("tts-voices")
def tts_voices() -> None:
    """List available Piper voice presets."""
    from sabrina.speaker.voices import list_presets

    for v in list_presets():
        typer.echo(f"  {v.id:<30s} [{v.quality:<6s}]  {v.description}")


@app.command("tts-download")
def tts_download(
    preset: str = typer.Argument(..., help="Preset id. See `sabrina tts-voices`."),
    out_dir: Path = typer.Option(
        None, "--out", help="Directory to download into (default: ./voices)."
    ),
) -> None:
    """Download a Piper voice model (.onnx + config JSON)."""
    from sabrina.speaker.voices import download_voice

    settings = load_settings()
    setup_logging(settings.logging.level)
    dest = out_dir or (project_root() / "voices")
    path = download_voice(preset, dest)
    typer.echo(f"Downloaded: {path}")


@app.command("tts-compare")
def tts_compare(
    text: str = typer.Argument(..., help="Sentence to play through each voice."),
    voices_dir: Path = typer.Option(
        None,
        "--dir",
        help="Directory to scan for .onnx voice models (default: ./voices).",
    ),
    engine: str = typer.Option(
        "piper",
        "--engine",
        "-e",
        help="TTS engine. Currently only 'piper' is supported.",
    ),
) -> None:
    """Play `text` through every downloaded Piper voice so you can pick one.

    Only voices present on disk (in ./voices or --dir) are used — this
    won't auto-download. Use `sabrina tts-download <preset>` first.
    """
    if engine != "piper":
        raise typer.BadParameter("tts-compare currently supports 'piper' only.")
    settings = load_settings()
    setup_logging(settings.logging.level)

    voices_root = voices_dir or (project_root() / "voices")
    if not voices_root.is_dir():
        typer.secho(
            f"No voices directory at {voices_root}. "
            "Run `sabrina tts-download amy-medium` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    onnx_files = sorted(voices_root.glob("*.onnx"))
    if not onnx_files:
        typer.secho(
            f"No .onnx voice models in {voices_root}.", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1)

    from sabrina.speaker.piper import PiperSpeaker

    device = _parse_device(settings.tts.output_device)

    async def _go() -> None:
        for model_path in onnx_files:
            typer.echo(f"\n--- {model_path.stem} ---")
            try:
                spk = PiperSpeaker(
                    voice_model=model_path,
                    binary=settings.tts.piper.binary or None,
                    output_device=device,
                    length_scale=settings.tts.piper.length_scale,
                )
            except Exception as exc:  # noqa: BLE001 - keep going through the list
                typer.secho(f"  skipped: {exc}", fg=typer.colors.YELLOW)
                continue
            result = await spk.speak(text)
            typer.echo(f"  [{result.engine}] {result.duration_s:.2f}s")

    asyncio.run(_go())


@app.command("test-audio")
def test_audio() -> None:
    """List audio devices (so you can pick one for SABRINA_TTS__OUTPUT_DEVICE)."""
    import sounddevice as sd

    typer.echo("Available audio devices:")
    for i, dev in enumerate(sd.query_devices()):
        flags = []
        if dev.get("max_input_channels"):
            flags.append(f"in={dev['max_input_channels']}")
        if dev.get("max_output_channels"):
            flags.append(f"out={dev['max_output_channels']}")
        sr = int(dev.get("default_samplerate") or 0)
        typer.echo(f"  [{i:>2}] {dev['name']:<60s}  {' '.join(flags):<12s}  {sr} Hz")
    default_in, default_out = sd.default.device
    typer.echo(f"\nDefault input:  [{default_in}]")
    typer.echo(f"Default output: [{default_out}]")


# ---------------------------------------------------------------------------
# listener / asr
# ---------------------------------------------------------------------------


def _build_listener(model_override: str | None = None):
    from sabrina.listener.faster_whisper import FasterWhisperListener

    settings = load_settings()
    fw = settings.asr.faster_whisper
    return FasterWhisperListener(
        model=model_override or fw.model,
        device=fw.device,
        compute_type=fw.compute_type,
        beam_size=fw.beam_size,
        language=fw.language or None,
    )


@app.command("asr")
def asr(
    audio: Path = typer.Argument(
        ..., exists=True, help="Path to an audio file (wav/mp3/flac/etc)."
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Override model size (e.g. tiny.en, base.en, small.en).",
    ),
) -> None:
    """Transcribe an audio file and print the result."""
    settings = load_settings()
    setup_logging(settings.logging.level)
    listener = _build_listener(model)

    async def _go() -> None:
        result = await listener.transcribe(audio)
        typer.echo(f"[{listener.name}]")
        typer.echo(
            f"  audio: {result.audio_duration_s:.2f}s  "
            f"transcribe: {result.transcribe_duration_s:.2f}s  "
            f"RTF: {result.rtf:.3f}  "
            f"lang: {result.language} ({result.language_prob:.2f})"
        )
        typer.echo(f"  text: {result.text}")

    asyncio.run(_go())


@app.command("asr-record")
def asr_record(
    seconds: float = typer.Option(
        5.0, "--seconds", "-s", help="How long to record before transcribing."
    ),
    model: str = typer.Option(None, "--model", "-m", help="Override model size."),
) -> None:
    """Record from the mic for N seconds, then transcribe."""
    settings = load_settings()
    setup_logging(settings.logging.level)
    listener = _build_listener(model)

    from sabrina.listener.record import record_clip

    device_raw = settings.asr.input_device
    device = _parse_device(device_raw) if device_raw else None

    async def _go() -> None:
        typer.echo(f"Recording {seconds:.1f}s ... speak now.")
        audio = record_clip(seconds, device=device)
        typer.echo("Transcribing ...")
        result = await listener.transcribe(audio)
        typer.echo(f"[{listener.name}]")
        typer.echo(
            f"  audio: {result.audio_duration_s:.2f}s  "
            f"transcribe: {result.transcribe_duration_s:.2f}s  "
            f"RTF: {result.rtf:.3f}  "
            f"lang: {result.language} ({result.language_prob:.2f})"
        )
        typer.echo(f"  text: {result.text}")

    asyncio.run(_go())


# ---------------------------------------------------------------------------
# voice loop (PTT -> ASR -> brain -> streaming TTS)
# ---------------------------------------------------------------------------


@app.command("voice")
def voice(
    brain: str = typer.Option(
        None,
        "--brain",
        "-b",
        help="Backend: 'claude' or 'ollama'. Default from sabrina.toml.",
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="Override model for the chosen brain."
    ),
    engine: str = typer.Option(
        None,
        "--engine",
        "-e",
        help="TTS engine: 'piper' or 'sapi'. Default from sabrina.toml.",
    ),
    asr_model: str = typer.Option(
        None, "--asr-model", help="Override faster-whisper model size (e.g. base.en)."
    ),
    hotkey: str = typer.Option(
        "shift_r",
        "--hotkey",
        "-k",
        help="Push-to-talk key name (pynput.keyboard.Key name).",
    ),
) -> None:
    """Hold a key, speak, release. Sabrina transcribes, thinks, and speaks back."""
    settings = load_settings()
    setup_logging(settings.logging.level)

    console = Console()
    bus = EventBus()
    sm = StateMachine(bus=bus)

    chosen_brain = brain or settings.brain.default
    chosen_engine = engine or settings.tts.default

    try:
        b = _build_brain(chosen_brain, model)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(code=1) from None

    try:
        spk = _build_speaker(chosen_engine)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]speaker error:[/] {e}")
        raise typer.Exit(code=1) from None

    listener = _build_listener(asr_model)

    device_raw = settings.asr.input_device
    device = _parse_device(device_raw) if device_raw else None

    from sabrina.voice_loop import run_voice_loop

    memory = _open_memory()
    try:
        asyncio.run(
            run_voice_loop(
                b,
                listener,
                spk,
                bus,
                sm,
                console,
                hotkey=hotkey,
                input_device=device,
                memory=memory,
                load_recent=settings.memory.load_recent,
                settings=settings,
            )
        )
    finally:
        if memory is not None:
            memory.close()


# ---------------------------------------------------------------------------
# vision
# ---------------------------------------------------------------------------


@app.command("look")
def look(
    question: str = typer.Argument(
        "What's on my screen right now?",
        help="What you want Sabrina to tell you about the screen.",
    ),
    save: str = typer.Option(
        None,
        "--save",
        "-s",
        help="If set, write the captured PNG to this path before asking.",
    ),
    speak: bool = typer.Option(
        False,
        "--speak/--no-speak",
        help="Also speak the reply through the default TTS engine.",
    ),
) -> None:
    """Take a screenshot and ask Claude about it.

    Uses the [vision] section of sabrina.toml: monitor index, max_edge_px,
    and model override. Great for smoke-testing without firing up the voice loop.
    """
    settings = load_settings()
    setup_logging(settings.logging.level)

    from sabrina.brain.protocol import Done, TextDelta
    from sabrina.vision.see import capture as capture_screen
    from sabrina.vision.see import see

    console = Console()

    shot = capture_screen(settings)
    console.print(
        f"[dim]Captured {shot.source_width}x{shot.source_height} "
        f"-> {shot.width}x{shot.height}  ({len(shot.data)/1024:.0f} KB, "
        f"{shot.capture_duration_s*1000:.0f} ms)[/]"
    )
    if save:
        Path(save).write_bytes(shot.data)
        console.print(f"[dim]Saved screenshot to {save}[/]")

    pieces: list[str] = []

    async def _go() -> None:
        async for ev in see(question, settings=settings, screenshot=shot):
            if isinstance(ev, TextDelta):
                typer.echo(ev.text, nl=False)
                pieces.append(ev.text)
            elif isinstance(ev, Done):
                typer.echo()
                if ev.input_tokens is not None:
                    console.print(
                        f"[dim]{ev.input_tokens} in / {ev.output_tokens} out, "
                        f"stop={ev.stop_reason}[/]"
                    )

    asyncio.run(_go())

    if speak:
        reply = "".join(pieces).strip()
        if reply:
            speaker = _build_speaker(settings.tts.default)
            asyncio.run(speaker.speak(reply))


# ---------------------------------------------------------------------------
# memory admin
# ---------------------------------------------------------------------------


@app.command("memory-show")
def memory_show(
    n: int = typer.Option(
        10, "--n", "-n", help="How many most-recent messages to print."
    ),
) -> None:
    """Print the last N messages stored in long-term memory."""
    memory = _open_memory()
    if memory is None:
        typer.echo("Memory is disabled in config.")
        raise typer.Exit(code=0)
    try:
        msgs = memory.load_recent(n)
        total = memory.count()
    finally:
        memory.close()
    typer.echo(f"Memory at {memory.path}  ({total} total message(s))")
    if not msgs:
        typer.echo("  (empty)")
        return
    for m in msgs:
        stamp = m.ts.strftime("%Y-%m-%d %H:%M:%S")
        first_line = m.content.splitlines()[0] if m.content else ""
        snippet = first_line[:120] + ("..." if len(first_line) > 120 else "")
        typer.echo(f"  [{stamp}] {m.role:>9s}  {snippet}")


@app.command("memory-clear")
def memory_clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Wipe every message from the memory store. Irreversible."""
    memory = _open_memory()
    if memory is None:
        typer.echo("Memory is disabled in config.")
        raise typer.Exit(code=0)
    try:
        n = memory.count()
        if n == 0:
            typer.echo("Memory is already empty.")
            return
        if not yes:
            confirm = typer.confirm(f"Delete all {n} message(s)?", default=False)
            if not confirm:
                typer.echo("Aborted.")
                raise typer.Exit(code=1)
        removed = memory.clear()
        typer.echo(f"Deleted {removed} message(s).")
    finally:
        memory.close()


@app.command("memory-stats")
def memory_stats() -> None:
    """Print memory row counts and embedding coverage."""
    memory = _open_memory()
    if memory is None:
        typer.echo("Memory is disabled in config.")
        raise typer.Exit(code=0)
    try:
        total = memory.count()
        with_emb = memory.count_with_embeddings() if memory.vec_enabled else 0
    finally:
        memory.close()
    typer.echo(f"Memory at {memory.path}")
    typer.echo(f"  messages:    {total}")
    if memory.vec_enabled:
        pct = (100.0 * with_emb / total) if total else 0.0
        typer.echo(f"  embeddings:  {with_emb}  ({pct:.0f}% of messages)")
        typer.echo(f"  vec dim:     {memory.embedding_dim}")
    else:
        typer.echo("  vec table:   disabled (sqlite-vec unavailable or config off)")


@app.command("memory-reindex")
def memory_reindex(
    drop: bool = typer.Option(
        False,
        "--drop",
        help="Drop the vec table before rebuilding. Use when changing embedding models.",
    ),
    batch_size: int = typer.Option(
        32, "--batch-size", "-b", help="Embedder batch size."
    ),
) -> None:
    """Backfill embeddings for every message that lacks one.

    Safe to run repeatedly. Use --drop if you've switched embedding models
    and need to rebuild the whole index with the new dimensions.
    """
    settings = load_settings()
    setup_logging(settings.logging.level)
    if not settings.memory.semantic.enabled:
        typer.secho(
            "[memory.semantic] is disabled in config. Set enabled=true to reindex.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    memory = _open_memory()
    if memory is None:
        typer.echo("Memory is disabled in config.")
        raise typer.Exit(code=1)
    if not memory.vec_enabled:
        typer.secho(
            "sqlite-vec is not available. Install it or check that your Python "
            "build supports `enable_load_extension`.",
            fg=typer.colors.RED,
        )
        memory.close()
        raise typer.Exit(code=1)

    try:
        if drop:
            typer.echo("Dropping vec_messages table...")
            memory.drop_vectors()

        from sabrina.memory.embed import build_embedder

        emb = build_embedder(settings.memory.semantic.embedding_model)
        typer.echo(f"Loading embedder: {emb.model_name} ...")
        emb.warmup()
        typer.echo(f"  dim={emb.dim}")

        total = len(memory.messages_missing_embeddings())
        if total == 0:
            typer.echo("Nothing to do — all messages already embedded.")
            return
        typer.echo(f"Embedding {total} message(s) in batches of {batch_size}...")

        def progress(done: int, tot: int) -> None:
            pct = 100.0 * done / tot if tot else 100.0
            typer.echo(f"  [{done}/{tot}] {pct:.0f}%")

        written = memory.backfill_embeddings(
            emb, batch_size=batch_size, progress=progress
        )
        typer.echo(f"Done. Wrote {written} embedding(s).")
    finally:
        memory.close()


@app.command("memory-search")
def memory_search(
    query: str = typer.Argument(
        ..., help="Free-text query to match against past turns."
    ),
    k: int = typer.Option(5, "--k", "-k", help="How many results to return."),
    max_distance: float = typer.Option(
        1.0,
        "--max-distance",
        help="Drop hits further than this (0=identical, 1=orthogonal).",
    ),
) -> None:
    """Semantic search against the memory store. Sanity-check for retrieval quality."""
    settings = load_settings()
    setup_logging(settings.logging.level)
    memory = _open_memory()
    if memory is None:
        typer.echo("Memory is disabled in config.")
        raise typer.Exit(code=1)
    if not memory.vec_enabled:
        typer.secho("sqlite-vec is not available.", fg=typer.colors.RED)
        memory.close()
        raise typer.Exit(code=1)

    try:
        from sabrina.memory.embed import build_embedder

        emb = build_embedder(settings.memory.semantic.embedding_model)
        emb.warmup()
        qvec = emb.embed(query)
        hits = memory.search(qvec, k=k, max_distance=max_distance)
        if not hits:
            typer.echo("(no matches)")
            return
        for h in hits:
            stamp = h.message.ts.strftime("%Y-%m-%d %H:%M")
            first_line = h.message.content.splitlines()[0] if h.message.content else ""
            snippet = first_line[:120] + ("..." if len(first_line) > 120 else "")
            typer.echo(
                f"  d={h.distance:.3f}  [{stamp}]  {h.message.role:>9s}  {snippet}"
            )
    finally:
        memory.close()


if __name__ == "__main__":
    app()
