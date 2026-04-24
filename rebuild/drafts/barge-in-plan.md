# Barge-in design plan (working doc — needs Eric's sign-off)

**Date:** 2026-04-23
**Status:** Draft. Not a decision doc yet. Sign-off required before code.
**Target component:** the top item on decision 007's "next session, pick
one" menu — closes the biggest remaining daily-driver gap.
**Related:** the cancel-token work here is a prerequisite for tool use.

## The one-liner

Sabrina should shut up when the user starts talking. Detect new speech
from the mic during playback (Silero VAD), cancel the in-flight TTS and
the brain stream, and return to the listening state so the user's new
utterance is captured cleanly. All three backend protocols (Brain,
Speaker, Listener) already expose async cancellation semantics; we
thread a single `CancelToken` through the voice loop's turn instead of
relying on `asyncio.Task.cancel()` race conditions.

## Scope

In:
- Always-on VAD running during `speaking` state, listening to the same
  input device as PTT.
- Mid-reply interrupt: VAD fires → cancel brain stream → stop speaker →
  transition back to `listening` → capture the user's new turn from the
  same stream (no gap).
- `CancelToken` added to `Brain.chat` and `Speaker.speak` signatures.
- `[barge_in]` config block in `sabrina.toml`.
- Tests for the VAD detector, the cancel-token semantics, and the
  voice-loop interrupt path (stubbed VAD + stubbed speaker).

Out:
- Full-duplex overlapping audio ("she keeps talking while I talk").
  Goal is *interrupt*, not duplex.
- Acoustic echo cancellation. We'll rely on a short dead-zone after each
  sentence finishes playback to avoid the mic capturing Sabrina's own voice.
- Wake-word replacement. PTT still drives the *start* of a turn; barge-in
  only affects the *during a reply* window.

## Files to touch

```
sabrina-2/src/sabrina/
├── brain/
│   └── protocol.py              # + cancel_token param on Brain.chat
├── brain/claude.py               # honor cancel_token (raise at next delta)
├── brain/ollama.py               # honor cancel_token
├── speaker/
│   └── protocol.py              # + cancel_token param on Speaker.speak
├── speaker/piper.py              # poll cancel_token during synth + playback
├── speaker/sapi.py               # poll cancel_token; purge SAPI queue
├── listener/
│   ├── vad.py                   # NEW: SileroVAD wrapper + AudioMonitor
│   └── __init__.py              # export the new names
├── voice_loop.py                 # wire VAD into speaking state; new cancel path
├── events.py                     # + BargeInDetected event
├── state.py                      # (no change expected; speaking -> listening already legal)
├── config.py                     # + BargeInConfig
└── cli.py                        # (no change expected)
sabrina-2/
├── sabrina.toml                  # + [barge_in] block
├── pyproject.toml                # + silero-vad (pip package; see below)
└── tests/test_smoke.py           # + barge-in tests (stub VAD, stub speaker)
```

No new top-level modules outside the existing component folders. One new
file (`listener/vad.py`) — justified by a genuinely new capability that
doesn't fit into `ptt.py` or `record.py`.

## Dependencies to add

**Decision: use the `silero-vad` pip package, not torch hub.**

The torch-hub route (`torch.hub.load('snakers4/silero-vad', 'silero_vad')`)
is Silero's "official" entrypoint but it pulls the model over the network
on first use, caches in a torch-specific folder, and requires torch. It's
also been fragile across torch versions historically.

The `silero-vad` package on PyPI (v5.1+) ships the ONNX weights inside the
wheel and has a thin `silero_vad.VADIterator` wrapper over onnxruntime.
Advantages:

- **No torch required at runtime for VAD.** We already have torch from
  sentence-transformers, so this doesn't shrink our install today — but
  it keeps VAD independent of that dep in case we swap to the
  onnx-only embedder later.
- **Offline after install.** No hub download on first run.
- **Deterministic pin.** The wheel carries a specific model version; we
  don't get surprised by a silent Silero model update.

Added to `pyproject.toml`:

```toml
"silero-vad>=5.1",
```

That's the only new runtime dep. onnxruntime comes in transitively.

## The `CancelToken` shape

```python
# sabrina/brain/protocol.py (new)

@dataclass(slots=True)
class CancelToken:
    """Cooperative cancellation for long-running async operations.

    Callers (voice_loop) create a token per turn, pass it into Brain.chat
    and Speaker.speak, and call `.cancel()` from a different task to
    request termination. Implementations check `.cancelled` at safe
    points and raise `asyncio.CancelledError` (or equivalent) to unwind.

    Why not asyncio.Event: we want a plain boolean flag with no event-loop
    dependency. VAD's detection callback runs on a threadpool; it shouldn't
    need the loop to set the flag.
    """
    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled
```

Signature additions (breaking but backward-compatible via defaults):

```python
# Brain
async def chat(
    self, messages, *, system=None, max_tokens=None,
    cancel_token: CancelToken | None = None,    # NEW
) -> AsyncIterator[StreamEvent]: ...

# Speaker
async def speak(
    self, text, *, voice=None,
    cancel_token: CancelToken | None = None,    # NEW
) -> SpeakResult: ...
```

Default `None` keeps existing callers working. Implementations that
ignore it get a documented "you may not interrupt mid-synth" caveat;
Piper/SAPI/Claude/Ollama all need to honor it for barge-in to work.

**Why `CancelToken` and not just `asyncio.Task.cancel()`?**
`Task.cancel()` races with the brain's in-flight HTTP read, and the
cancellation exception can fire in the middle of a SQLite write or a
sounddevice callback. A cooperative token lets each implementation
cancel at a safe point (between stream events, between sentences,
before starting the next subprocess).

## VAD wiring

```python
# sabrina/listener/vad.py (new, ~100 lines)

class SileroVAD:
    """ONNX-backed Silero VAD at 16 kHz. Frame-by-frame (30 ms chunks).

    API:
        vad = SileroVAD(threshold=0.5, min_speech_ms=300)
        vad.reset()                            # clear state between turns
        is_speech = vad.feed(pcm_chunk)        # bool, returns True as soon
                                               #  as min_speech_ms has passed
    """

class AudioMonitor:
    """Always-on sounddevice InputStream during speaking state.

    On each callback chunk, feed VAD. If VAD fires, set the passed-in
    CancelToken and enqueue the audio buffer for the next transcribe()
    call so the user doesn't have to repeat themselves.

    Starts/stops cheaply — voice_loop spins it up on entry to speaking,
    tears it down on exit. Same input device as PTT.
    """
```

## Voice-loop integration

The `speaking` branch of the loop changes like this (sketch):

```python
await sm.transition("speaking", reason="first_sentence")
cancel = CancelToken()
monitor = AudioMonitor(vad, cancel, device=input_device)
monitor.start()
try:
    async for ev in turn_brain.chat(history, system=turn_system, cancel_token=cancel):
        if cancel.cancelled:
            break
        # ... existing sentence-buffer + speak_queue logic ...
        # speaker.speak() also receives cancel
finally:
    barge_audio = monitor.stop()  # returns captured-so-far audio or None

if cancel.cancelled:
    await bus.publish(BargeInDetected())
    await sm.transition("listening", reason="barge_in")
    # short-circuit: transcribe barge_audio immediately, skip PTT wait
    transcript = await listener.transcribe(barge_audio)
    # ... continue to thinking ...
```

Design calls:
- **Drop the partial reply.** Don't persist the partial assistant text to
  memory. A cut-off reply is usually wrong context for the next turn.
- **Keep the captured barge-in audio.** Feed it straight into transcribe
  so the user doesn't have to press PTT again. (Optional: make this
  configurable.)
- **Dead-zone first 300 ms of speaking.** VAD would otherwise fire on
  Sabrina's own voice bleeding through the mic. Suppress barge-in
  detection for the first chunk after TTS playback starts.

## Test strategy

Fast unit tests (< 100 ms each, no real audio):

- `test_cancel_token_basic` — cancel flag is boolean-monotonic; `.cancel()` sticks.
- `test_cancel_token_propagates_through_stub_brain` — stub Brain that
  checks the token between yields; yields stop after cancel.
- `test_cancel_token_stops_stub_speaker` — stub Speaker that checks
  token mid-chunk.
- `test_vad_state_machine_ignores_below_min_speech_ms` — feed a short
  blip, ensure it doesn't count.
- `test_vad_fires_on_sustained_speech` — feed a synthesized sine wave
  the real Silero will flag (or skip if silero-vad isn't importable;
  use `pytest.importorskip` per the pattern in decision 007).

Integration test (stubbed VAD + stubbed speaker + real voice_loop
`speaking` branch):

- `test_voice_loop_interrupt_stops_reply_and_captures_audio` — stub
  brain emits 3 text deltas; stub VAD fires after the first; assert
  the token is cancelled, the speak_queue drained, `BargeInDetected`
  published, state returned to `listening`.

No real mic, no real speaker. The hardware-exercising test stays
manual — a documented "ask, start interrupting, confirm she shuts up"
step added to the barge-in equivalent of `validate-007-windows.md`
when we ship.

## Config block

```toml
[barge_in]
# Master switch. Off until you've validated it end-to-end on your mic/speaker.
enabled = false

# VAD threshold (0.0-1.0). Lower = more sensitive. 0.5 is Silero's default.
# Noisy environments may want 0.6-0.7.
threshold = 0.5

# Minimum speech duration (ms) before VAD fires. Filters coughs, key clicks,
# and Sabrina's own voice bleed-through.
min_speech_ms = 300

# Suppress barge-in detection for this many ms at the start of each
# speaking phase to avoid tripping on our own TTS onset.
dead_zone_ms = 300

# After interrupt, re-transcribe the captured audio and continue, rather
# than waiting for a PTT press. False = just go idle.
continue_on_interrupt = true
```

## Open questions (need Eric's sign-off)

1. **`silero-vad` pip package vs. torch hub.** Plan picks the pip package
   for the reasons above. OK?
2. **`CancelToken` lives in `brain/protocol.py`.** Symmetric placement
   would be a new `sabrina/cancel.py` since both Brain and Speaker use it.
   Anti-sprawl says stay in `brain/protocol.py` until a third caller
   materializes (guardrail #2). OK?
3. **`AudioMonitor` is a new file, not an addition to `ptt.py` or
   `record.py`.** VAD + threaded buffer is a distinct responsibility.
   I'd rather a new ~80-line file than a 250-line `ptt.py`. OK?
4. **Drop the partial reply entirely** vs. persist with an "[interrupted]"
   marker. I'd drop it — less context confusion for the next turn. OK?
5. **Continue-on-interrupt default.** `true` feels right (the whole
   point of barge-in is you have something to say) but makes the loop
   more complex. Confirm?
6. **Dead-zone value.** 300 ms is a starting guess. We'll need to tune
   it on the actual mic + speaker setup. OK to start at 300 and revisit
   in the validation procedure?
7. **Shipped decision doc numbering.** If decision 008 ended up being the
   sqlite-vec-on-Windows fix, this becomes decision 009. If not, 008.
   I'll number on ship.

## Ship criterion (for later — not this plan)

When it's done:
- All existing tests pass.
- New barge-in tests pass.
- A manual "hold PTT, ask a long-answer question, interrupt halfway,
  confirm she stops within 250 ms" smoke step goes green.
- First-audio latency on non-interrupt turns doesn't regress (VAD
  monitor only runs during speaking, doesn't touch the cold path).

## Not in this plan (later)

- Automation-scale cancellation (cancelling tool-use mid-run). Same
  `CancelToken` will be reused, but tool use isn't wired yet.
- Surfacing "barge-in triggered" in the GUI. The event bus publishes
  `BargeInDetected`; GUI subscribes when we get there.
- Per-user VAD sensitivity calibration. Static threshold for now.

---

**Ready for sign-off on the seven questions above.** Once Eric confirms,
I'll implement in this order: CancelToken + protocol additions → VAD
module → AudioMonitor → voice_loop wiring → tests → sabrina.toml block.
Atomic commits per step per the project's usual cadence.
