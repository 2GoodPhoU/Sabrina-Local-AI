# Decision 009: Barge-in (mid-reply interrupt) shipped

**Date:** 2026-04-24
**Status:** Shipped code; off by default. Flip `[barge_in].enabled = true` and
run `rebuild/validate-barge-in.md` to validate on your mic/speaker.

## The one-liner

Sabrina now stops talking when the user starts. A Silero VAD runs during
the `speaking` state, a cooperative `CancelToken` threads through
`Brain.chat` and `Speaker.speak`, and when the VAD fires the in-flight
brain stream and TTS are cancelled, the state returns to `listening`,
and — by default — the captured audio becomes the next user turn
without a PTT press.

## What shipped

| Piece | Where | Notes |
|---|---|---|
| `CancelToken` dataclass | `brain/protocol.py` | Plain boolean flag; no event-loop dependency (VAD callback runs on a threadpool). |
| `cancel_token=None` on `Brain.chat` | `brain/protocol.py`, `claude.py`, `ollama.py` | Backward-compatible default. Implementations check between stream deltas and emit `Done(stop_reason="cancelled")` on trip. |
| `cancel_token=None` on `Speaker.speak` | `speaker/protocol.py`, `piper.py`, `sapi.py` | Background poller spawned per `speak()` call; calls `self.stop()` when the token trips. Torn down in `finally`. |
| `SileroVAD` | `listener/vad.py` (new) | ONNX wrapper via the `silero-vad` pip package. 512-sample frames at 16 kHz. Lazy model load on first `feed()`. Stateful across frames; `reset()` clears between phases. `min_speech_ms` gate filters coughs and bleed. |
| `AudioMonitor` | `listener/vad.py` (new) | `sounddevice.InputStream` during `speaking`. Fires `cancel_token.cancel()` on VAD detection; buffers captured audio so `voice_loop` can re-transcribe. `dead_zone_ms` suppresses TTS-onset self-trigger. |
| Voice-loop wiring | `voice_loop.py` | `pending_barge_audio` carries captured audio across iterations; cancel path drops the partial reply, publishes `BargeInDetected`, transitions to idle, and feeds the barge audio into the next iteration in place of the PTT record. |
| `[barge_in]` config block | `config.py`, `sabrina.toml` | `enabled`, `threshold`, `min_speech_ms`, `dead_zone_ms`, `continue_on_interrupt`. Ships off-by-default (master-switch pattern from `[memory.semantic]`). |
| `silero-vad>=5.1` dep | `pyproject.toml` | Ships ONNX weights in the wheel — no torch-hub download on first run. See "Design calls" below for why not torch hub. |
| `BargeInDetected` event | `events.py` | Added to the `Event` union. Published once per cancel trip. |
| Tests | `tests/test_smoke.py` | `test_cancel_token_basic`, `_propagates_through_stub_brain`, `_stops_stub_speaker`, `_vad_state_machine_ignores_below_min_speech_ms`, `_vad_fires_on_sustained_speech`. 5 tests; 57 total. |

## Design calls

### `CancelToken` as a plain boolean, not `asyncio.Event`

The VAD detection callback runs on a sounddevice threadpool — not the
asyncio loop. A cooperative bool flag (atomic assignment in CPython) is
free to set from the callback without touching the loop. `asyncio.Event`
would have needed `call_soon_threadsafe` to set — fine, but more moving
parts for no benefit.

### `CancelToken` lives in `brain/protocol.py`, not a new module

Symmetric placement (both Brain and Speaker use it) would argue for a
new `sabrina/cancel.py`. Anti-sprawl guardrail #2 says new abstractions
earn their file only when a third caller materializes. Today two
callers; keep the token colocated with the primary cancellation surface.
Revisit if tool-use (drafted) adds a third.

### `silero-vad` pip package, not torch hub

`torch.hub.load('snakers4/silero-vad', …)` is Silero's "official"
entrypoint but pulls weights over the network on first use, caches in a
torch-specific folder, and is historically fragile across torch versions.
The `silero-vad` PyPI wheel ships ONNX weights inside the wheel, is
deterministically pinned, and keeps VAD independent of our torch dep in
case we swap to the onnx-only embedder later. Trade-off: one new runtime
dep instead of zero.

### Poll-and-stop speakers, not bare `asyncio.Task.cancel()`

Calling `asyncio.Task.cancel()` on an in-flight `speak()` races with the
subprocess pipe read, the SAPI COM thread, and the sounddevice `sd.wait`.
The cancellation exception can fire mid-write and leave the audio
subsystem in a weird state. The poll task we spawn per `speak()` waits
for `cancel_token.cancelled` and calls the speaker's own `stop()` at a
safe point — subprocess `kill()` + `sd.stop()` for Piper, SAPI "purge"
for the COM path. Cooperative instead of preemptive.

### Dead-zone starts on first sentence, not on entering `speaking`

`AudioMonitor.start()` is called from inside `_speaker_worker` when the
*first* queued sentence fires, not earlier when the brain starts
streaming or when the state machine transitions to `speaking`. If we
started it when entering `speaking`, the dead-zone countdown would
expire during the silent "waiting for first sentence" phase and
Sabrina's own TTS onset would hit an unguarded VAD. Aligning the
dead-zone with actual audio output is the correct reference point.

### Drop the partial reply on interrupt

Alternatives: persist with `"[interrupted]"` marker, or save to a
separate `fragments` table. Rejected: a cut-off assistant sentence
is usually bad context for the next turn (the user's barge-in often
contradicts or redirects). Dropping keeps the next turn's context clean.
Memory writes are skipped on the cancel path for the same reason.

### `continue_on_interrupt = true` default

The whole point of barge-in is that the user has something to say. The
alternative (`false`) makes them press PTT again after interrupting,
which is the ergonomic equivalent of "wait, let me press this button so
I can say the thing I already said." Yes, the loop is slightly more
complex (a `pending_barge_audio` variable plumbed across iterations),
but the UX payoff is obvious.

## What works well

- **Every existing path stays dead simple.** `cancel_token=None` default
  on `Brain.chat` and `Speaker.speak` means the 99% of callers (chat
  CLI, one-shot `sabrina tts ...`, tests) never see the new code path.
- **The poll task pattern is the same in Piper and SAPI.** 8 lines each,
  no coupling. If a future speaker backend lands, the pattern is
  obvious.
- **VAD load is lazy.** No onnxruntime + torch import cost when barge-in
  is off, which is the default. Only kicks in when `settings.barge_in.enabled`
  is true AND a speaking phase actually starts.
- **Graceful degrade if silero-vad isn't importable.** The import is
  inside `SileroVAD._ensure_loaded()`; any `ImportError` there raises
  into the voice loop, which currently crashes. (Thin spot — see below.)
  The right behavior is to log-and-disable, mirroring semantic memory's
  `_try_enable_vec` pattern.

## Thin spots

**Post-ship bundle 009a (2026-04-24).** Four of the five thin spots
below were closed in a ride-along fix pass: graceful-degrade on Silero
load failure (voice loop now logs `vad.unavailable` and runs without
barge-in), trim-to-VAD-start in `AudioMonitor.stop()` with a 150 ms
pre-fire margin, per-frame `vad.prob` DEBUG log, and Piper cancel-poll
tightened from 30 ms to 10 ms. Pre-commit hook install (#5) is an
Eric-runs-locally step. See commit with message prefix
`fix: barge-in thin-spots`. Two new unit tests: `test_make_barge_in_vad_degrades_on_load_failure`
and `test_audio_monitor_trims_capture_to_speech_onset` (57 → 59).

### Implementation

- **No log-and-degrade if silero-vad won't import at runtime.** Today
  a broken install crashes the voice loop on first speaking phase. A
  `try: from silero_vad import …` at `SileroVAD._ensure_loaded` time
  with a "barge-in disabled for this session" log is the obvious fix;
  mirrors the sqlite-vec graceful-degrade from decision 007. Deferred
  because a crash surfaces the install problem faster during the first
  run; revisit after validation.
- **`AudioMonitor` captures the full speaking window, TTS bleed and all.**
  When `continue_on_interrupt` fires, whatever audio was buffered —
  potentially including Sabrina's own voice bleeding through the mic
  before the user spoke — gets re-transcribed. Whisper usually handles
  this (the user's voice is louder + closer to the mic), but on a
  speakerphone setup this will produce garbage. Two cleanups to
  consider: trim to the VAD-detected start, or require a headset in the
  docs. Defer until validation shows the real failure mode.
- **No VAD state observability.** We log `bargein.detected` when the
  gate trips but not the underlying probabilities, so tuning `threshold`
  is blind. A `SABRINA_LOGGING__LEVEL=DEBUG` path that logs per-frame
  `vad.prob` would make step 7 of `validate-barge-in.md` much easier.
- **`AudioMonitor.stop()` is synchronous.** The sounddevice `InputStream.stop()`
  + `.close()` block. Running on the main asyncio loop is fine for ~ms
  latency, but if sounddevice ever stalls, the voice loop stalls. Not
  worth a `to_thread` wrap until we see it stall in practice.
- **Shared input device with PTT.** Both `PushToTalk` and
  `AudioMonitor` want `input_device`. Today they're used in disjoint
  phases (PTT on `listening`, AudioMonitor on `speaking`), so the
  device can be opened and closed cleanly. If a future phase needs
  both simultaneously (e.g. always-on wake-word), we'll need a shared
  capture abstraction. Wake-word plan already acknowledges this.

### Protocol

- **`CancelToken` has no cancellation reason.** A single `cancelled: bool`
  is enough today; if we later want "cancelled by VAD" vs. "cancelled by
  user" vs. "cancelled by supervisor", an enum field opens that door.
  Additive.
- **Speaker cancellation granularity is per-sentence.** `speaker.speak()`
  handles one sentence; the poll task aborts mid-playback via
  `self.stop()`. But the outer `_speaker_worker` consumes the queue
  one item at a time, and if the current sentence is already mid-synth
  the cancel interrupt has to wait for the current synth to complete.
  In practice Piper synth is <1s per sentence so this is fine, but it's
  not sub-100ms.

### Tests

- **No real-audio integration test.** The original plan listed
  `test_voice_loop_interrupt_stops_reply_and_captures_audio` — dropped
  in favor of the manual procedure in `validate-barge-in.md`. A
  reasonable trade: mocking the full brain/speaker/bus/state-machine
  interplay would add brittleness without catching the failures we
  actually care about (VAD false-positives, dead-zone timing, device
  locks). The manual validation steps 5–8 cover all of those.
- **VAD tests mock the Silero model.** Fast and deterministic but
  doesn't exercise the real ONNX path. An `importorskip`-gated smoke
  test that loads real Silero and fires it with a clip of prerecorded
  speech would add confidence; deferred until we have such a clip.

## Alternatives worth researching

1. **Webrtcvad or SileroLarge v6.** Silero small is what we shipped;
   Silero v6 (released 2025) claims better noise robustness. Drop-in
   via the same `silero-vad` package's model selector.
2. **Two-stage VAD.** Cheap energy threshold first (no model call),
   Silero only when energy crosses baseline. Saves onnxruntime ticks
   per callback. Relevant if CPU budget tightens; not today.
3. **Duplex capture (always-on mic).** The plan explicitly scoped
   this out. If we ever want true overlap ("keep talking while I
   interject"), the shared `AudioMonitor` primitive this session
   introduces is the right foundation.
4. **Acoustic echo cancellation.** Would let us drop or shrink the
   dead-zone. Real AEC is a whole component; speexdsp / WebRTC AEC3
   are the usual candidates. Defer.
5. **Unified `CancelReason` enum.** If tool-use adds a third cancel
   direction, promote the token to `CancelToken(reason: CancelReason | None)`
   and update callers.

## Ship-criterion check

Per decision 006's "daily-driver gap" list:

- [ ] Wake word / global PTT — unchanged.
- [ ] Auto-start on login — unchanged.
- [ ] Crash-recovery supervisor — unchanged.
- [x] **Barge-in** — ✅ shipped this session (`[barge_in].enabled` default
      `false`; flip after `validate-barge-in.md` passes on your hardware).
- [ ] Budget observability — unchanged.

Per Eric's working-style guardrails:

- No new top-level module (`listener/vad.py` is inside an existing
  folder; `CancelToken` is in `brain/protocol.py`). ✅
- No protocol broken — both `Brain.chat` and `Speaker.speak` got an
  additive kwarg with a `None` default. ✅
- `voice_loop.py` grew by ~60 lines; still under 300. ✅
- Test suite stays fast (< 5 s wall; barge-in tests are pure-function
  with mocked VAD model). ✅
- Atomic commit for the bundle.
- Validation procedure (`validate-barge-in.md`) ships with the feature.

## Where the new code lives

```
sabrina-2/src/sabrina/
├── brain/
│   ├── protocol.py        # +CancelToken, +cancel_token on Brain.chat
│   ├── claude.py          # honors cancel_token between deltas
│   └── ollama.py          # honors cancel_token between chunks
├── speaker/
│   ├── protocol.py        # +cancel_token on Speaker.speak
│   ├── piper.py           # +_poll_and_stop task; honors cancel_token
│   └── sapi.py            # inline poll task; honors cancel_token
├── listener/
│   ├── __init__.py        # exports SileroVAD, AudioMonitor
│   └── vad.py             # NEW: SileroVAD + AudioMonitor (~180 lines)
├── config.py              # +BargeInConfig, +barge_in field
├── events.py              # +BargeInDetected
└── voice_loop.py          # +VAD wiring, cancel path, pending_barge_audio
sabrina-2/
├── pyproject.toml         # +silero-vad>=5.1
├── sabrina.toml           # +[barge_in] block
└── tests/test_smoke.py    # +5 barge-in tests
```

## One thing to feel good about

The cancel-token machinery isn't a one-off for barge-in. It's the same
cooperative-cancel primitive tool-use needs, supervisor autostart needs,
and eventually the GUI-stop-button needs. Shipped it as a thin protocol
extension in the same session as its first caller — no speculative
abstraction, but the future callers get a ready surface instead of
racing `Task.cancel()`.

## Next session — pick one

1. **Validate barge-in on Windows** (`validate-barge-in.md`). No new
   code; just steps 0–8 and either a ROADMAP bump or a follow-up
   decision if something breaks.
2. **Wake word (openWakeWord)** — next on the infra path. Shares the
   `AudioMonitor` primitive shipped here; new Silero/openWakeWord model
   instead of VAD.
3. **Supervisor + autostart** — final infra item. OS-level process
   management; no audio at all.
4. **Personality calibration** — character path. Voice inference in
   `personality-plan.md` needs Eric's stated preferences.
