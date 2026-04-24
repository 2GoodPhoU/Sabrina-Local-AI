# Wake word plan — custom "Hey Sabrina" (working doc — ready-to-ship)

**Date:** 2026-04-23
**Status:** Draft. Ready once barge-in's `AudioMonitor` has landed (the
shared input-stream primitive this plan leans on). No further research
needed before implementation.
**Closes:** daily-driver gap #1 from decision 006. Roadmap component 3.

## The one-liner

Train a small openWakeWord model for "Hey Sabrina" using Piper-synthesized
samples (we already ship Piper, so data generation is free), wire it into
a new `listener/wake.py` that feeds off barge-in's `AudioMonitor` during
the `idle` state, fire `WakeWordDetected` on trigger, and let the
voice loop treat it identically to a PTT press. Both triggers coexist;
wake-word defaults off until Eric has tuned threshold on his mic + room.

## Scope

In:
- `tools/wake-training/`: data synthesis + training scripts. Not runtime
  code — lives outside `src/sabrina/`, mirrors `install-piper.ps1`'s
  tools-directory pattern.
- `voices/wake/hey_sabrina.onnx`: the trained model, checked in (~2-5 MB,
  fine for git).
- Runtime: `listener/wake.py` (~100 lines), `WakeWordConfig`,
  `WakeWordDetected` event, voice-loop integration.
- GUI tab: "Listen" (consolidates PTT + wake-word + barge-in; the tab
  reorganization decision was deferred in the master plan — ship as a
  new tab this session).
- `sabrina wake-test` CLI verb: records 5 s, runs the detector, prints
  peak score. Used for threshold tuning.
- Tests: synthetic-score sequence tests, voice-loop wake-path test
  (stub detector).

Out:
- **Runtime training.** Training is offline, one-time, done on Eric's box
  via the `tools/wake-training/` scripts. Runtime only loads ONNX +
  inferences.
- **Multiple wake words.** One model, one phrase. Add a second detector
  in a follow-up if there's ever a reason.
- **Custom VAD.** openWakeWord ships its own VAD gate; good enough.
  Silero (from barge-in) is available but not wired — avoid double-
  stacking.
- **Pre-login trigger.** Wake-word only fires when Sabrina's process is
  running. Daily-driver supervisor + autostart (other draft) covers
  "is Sabrina running"; this plan covers "what starts a turn."

## Files to touch

```
sabrina-2/
├── src/sabrina/
│   ├── listener/
│   │   ├── wake.py                  # NEW, ~100 lines
│   │   └── __init__.py              # export WakeWordDetector
│   ├── voice_loop.py                # +wake path in idle
│   ├── events.py                    # +WakeWordDetected
│   ├── config.py                    # +WakeWordConfig
│   ├── gui/settings.py              # +"Listen" tab consolidation
│   └── cli.py                       # +sabrina wake-test
├── tools/wake-training/             # NEW — offline tooling, not runtime
│   ├── README.md                    # how to retrain "hey sabrina"
│   ├── synthesize_positives.py      # uses Piper voices/<libritts_r>.onnx
│   ├── train_hey_sabrina.py         # calls openwakeword's trainer
│   └── requirements-training.txt    # training-only deps (torch already present)
├── voices/wake/
│   └── hey_sabrina.onnx             # trained model, committed
├── pyproject.toml                   # +openwakeword>=0.6
├── sabrina.toml                     # +[wake_word]
└── tests/test_smoke.py              # +wake-word tests
```

Runtime: one new ~100-line file. Offline tooling: a distinct package that
doesn't ship in the wheel (`tools/` is already excluded from the hatch
build target).

## Protocol / API changes

- `events.py`: add `WakeWordDetected(word: str, score: float)` and
  include it in the `Event` union.
- `voice_loop.py`: in the `idle → listening` step, race PTT press against
  a `WakeWordDetected` subscription on the bus. First one wins.
- `Listener` protocol: unchanged. Transcription entry point is the same.
- No change to Brain, Speaker, Memory.

## Config additions

```toml
[wake_word]
# Master switch. Off by default until you've tuned threshold on your mic.
enabled = false

# Path to the ONNX model. Relative paths resolve to project root.
model_path = "voices/wake/hey_sabrina.onnx"

# Inference threshold. openWakeWord emits a 0..1 score per 80 ms chunk.
# 0.5 is the library default; lower catches more, raises false-positive
# rate. Use `sabrina wake-test` to pick.
threshold = 0.5

# Suppress repeated triggers for this many milliseconds after a detection.
# Prevents the tail of "hey sabrina" re-triggering mid-utterance.
cooldown_ms = 2000

# Auto-start recording for this many ms after detection. Bridge from
# "Sabrina heard her name" to the first transcribe() call. Set 0 to
# require a PTT press anyway (low-trust mode while tuning).
auto_capture_s = 5.0
```

## How the runtime piece fits together

```
┌───────────────────────┐
│ (idle state)          │
│  AudioMonitor running │  <— same InputStream barge-in uses, now
│  at 16 kHz mono       │     multi-consumer during idle too
└──┬────────────────────┘
   │ 80 ms chunks
   ├────────────────────────────┐
   │                            │
   ▼                            ▼
┌─────────────┐          ┌─────────────┐
│ SileroVAD   │          │ OpenWakeWord│
│ (barge-in)  │          │ (this plan) │
│ only active │          │ only active │
│ in speaking │          │ in idle     │
└─────────────┘          └──────┬──────┘
                                │ score >= threshold &&
                                │ >cooldown since last fire
                                ▼
                     ┌──────────────────────┐
                     │ bus.publish(         │
                     │   WakeWordDetected)  │
                     └──────────┬───────────┘
                                │
                    ┌───────────┴──────────┐
                    ▼                      ▼
           voice_loop idle:       Start recording
           race this against      auto_capture_s of audio
           PTT.wait_press()       (piggyback on AudioMonitor's
                                   ring buffer; no gap)
```

Key idea: `AudioMonitor` from barge-in already owns the input stream.
This plan extends it to a multi-consumer dispatch: each consumer
(VAD, wake, ...) subscribes to chunks. Only one consumer runs per
state — VAD during `speaking`, wake during `idle`. No double-open on
the audio device.

## `listener/wake.py` sketch

```python
import numpy as np
from openwakeword import Model

class WakeWordDetector:
    """openWakeWord-backed detector. Consumes 80 ms 16 kHz mono chunks."""

    def __init__(
        self,
        model_path: Path,
        threshold: float = 0.5,
        cooldown_ms: int = 2000,
    ) -> None:
        self._model = Model(
            wakeword_models=[str(model_path)],
            inference_framework="onnx",
        )
        self._threshold = threshold
        self._cooldown_s = cooldown_ms / 1000.0
        self._last_fire = 0.0
        # Name derived from the ONNX file basename — used in events/logs
        self.word = model_path.stem  # "hey_sabrina"

    def reset(self) -> None:
        self._model.reset()
        self._last_fire = 0.0

    def feed(self, chunk_int16: np.ndarray) -> float | None:
        """Returns score if detection fired (past cooldown), else None.
        Expects int16 PCM mono at 16 kHz."""
        scores = self._model.predict(chunk_int16)
        score = scores.get(self.word, 0.0)
        if score < self._threshold:
            return None
        now = time.monotonic()
        if now - self._last_fire < self._cooldown_s:
            return None
        self._last_fire = now
        return score
```

Integration in `voice_loop.py`:

```python
# inside the idle-state branch
async def _wait_for_trigger() -> "TriggerSource":
    ptt_task = asyncio.create_task(ptt.wait_press())
    wake_task = asyncio.create_task(bus.wait_for(WakeWordDetected))
    done, pending = await asyncio.wait(
        {ptt_task, wake_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for t in pending:
        t.cancel()
    return "wake" if wake_task in done else "ptt"

trigger = await _wait_for_trigger() if wake_enabled else "ptt"
if trigger == "wake":
    audio = audio_monitor.drain_recent(seconds=settings.wake_word.auto_capture_s)
else:
    audio = await ptt.record_while_held()
```

`AudioMonitor.drain_recent` (added in barge-in) returns the last N
seconds of its ring buffer. That's how the user's "Hey Sabrina, what's
the weather" becomes one contiguous clip fed straight into the
existing `listener.transcribe` path.

## The training pipeline — `tools/wake-training/`

Training is offline, runs once when we need a new model. Checked-in ONNX
is the artifact of interest at runtime.

### Data generation — `synthesize_positives.py`

Uses the Piper binary we already install, plus the `libritts_r-medium`
voice which has ~900 distinct speakers. Script generates ~4,000 positive
utterances of "Hey Sabrina" with variations:

- 200 speakers × 3 prosody variants (length_scale ∈ {0.85, 1.0, 1.15})
  × ~7 textual variants ("hey sabrina", "hey sabrina,", "hey sabrina.",
  "hey, sabrina", trailing pauses, etc.)
- Post-synthesis: audiomentations augmentations — add noise (room tone
  + white), pitch shift ±1 semitone, time-stretch ±5%, simulate mic
  distance with a short-tail IR. Each utterance expanded ~3×.

Final positive set: ~12,000 clips at 16 kHz mono, 1–2 s each. Saved under
`tools/wake-training/data/positive/<hash>.wav`.

### Negatives

openWakeWord ships with pre-computed negative features (several hundred
hours of speech + noise) that the trainer consumes directly. We don't
generate our own; the library's bundled set is exactly this use case.

### Training — `train_hey_sabrina.py`

Calls openWakeWord's training entrypoint (`openwakeword.train`). Inputs:

- Positive directory (our synthesized set).
- Negative features (library-provided path).
- Output: `voices/wake/hey_sabrina.onnx`.

Training runtime on this hardware:
- CPU-only (i7-13700K): ~30–60 min for a competitive model.
- GPU (RTX 4080): same, actually — training is feature-based and
  dominated by I/O, not matmul. **Use CPU.** The 4080 is overkill and
  running training there while Ollama is loaded is likely to OOM.

Peak RAM: ~8 GB during training. Disk: ~15 GB temporary during
augmentation (scratch under `tools/wake-training/scratch/`; .gitignore'd).

### Retrain-on-demand

README documents the full loop:

```powershell
# one-time setup
uv pip install -r tools/wake-training/requirements-training.txt
# full pipeline, ~1 hour
uv run python tools/wake-training/synthesize_positives.py
uv run python tools/wake-training/train_hey_sabrina.py
# validate
uv run sabrina wake-test --samples 20
```

Output gets committed: `voices/wake/hey_sabrina.onnx` (~2-5 MB). The
synthesized data is not committed (gitignore `tools/wake-training/data/`
and `tools/wake-training/scratch/`).

## Dependencies to add

**Runtime (in main `pyproject.toml`):**

```toml
"openwakeword>=0.6",
```

onnxruntime comes transitively (already pulled by sentence-transformers).
No new large dep.

**Training only (in `tools/wake-training/requirements-training.txt`):**

```
openwakeword[training]>=0.6
audiomentations>=0.36
soundfile>=0.12         # already in main, listed here for tool-standalone install
```

openwakeword's `[training]` extra pulls the trainer-specific deps. Not in
the runtime wheel — `tools/` is excluded from hatch build already.

## Test strategy

Runtime tests (fast, no real audio or real model):

- `test_wake_detector_below_threshold_returns_none` — monkeypatch
  `openwakeword.Model.predict` to return a fixed score map; confirm
  silent behavior below threshold.
- `test_wake_detector_cooldown_suppresses_rapid_retriggers` — same
  monkeypatch, feed two "hot" chunks 100 ms apart, assert only first
  fires.
- `test_wake_detector_fires_after_cooldown` — advance time via a clock
  stub, assert second fire goes through.
- `test_voice_loop_wake_path_captures_audio_and_transcribes` — stub
  detector + stub AudioMonitor (returns canned PCM). Assert
  `idle → listening → thinking` transitions happen via the wake path
  without a PTT press. Publishes `WakeWordDetected` on the bus.
- `test_wake_word_event_schema_guard` — verify `WakeWordDetected` has
  required fields (follows the pattern added after the Speak event
  regression in decision 003).

openwakeword loading test — guarded like sqlite-vec in 007:

```python
pytest.importorskip("openwakeword")
pytest.importorskip("onnxruntime")
```

Skip cleanly if the training extra isn't installed.

Manual smoke (to be added to a `validate-wake-on-windows.md`):

- `sabrina wake-test` — say "hey sabrina" 5 times, note peak scores.
  Adjust threshold to (min peak * 0.8).
- `sabrina voice` with wake enabled: stand ~1 m from mic, normal
  conversation voice, say "hey sabrina, what time is it." Confirm
  the turn fires without a PTT press.
- False-positive smoke: run a 5-min podcast through the speakers in
  the room; log how many spurious triggers fire (goal: zero).

## Step-ordered implementation outline

Assumes barge-in has landed (shared `AudioMonitor` + `CancelToken`
exist).

1. **Training tooling first** — because the model is a prerequisite for
   every downstream test. `tools/wake-training/` with both scripts +
   the README. Run them; commit `voices/wake/hey_sabrina.onnx`. One
   commit per script, one for the model.
2. `WakeWordConfig` in `config.py` + `[wake_word]` block in
   `sabrina.toml`. One commit.
3. `events.py`: add `WakeWordDetected`. One commit.
4. `listener/wake.py` + unit tests. One commit.
5. Extend `AudioMonitor` for multi-consumer dispatch (minor — it's
   already designed to dispatch to a single consumer per state).
   One commit.
6. `voice_loop.py`: wake-path integration. One commit; manual smoke
   at this point.
7. `sabrina wake-test` CLI verb. One commit.
8. GUI: new "Listen" tab, consolidating PTT + wake + (future) barge-in
   controls. One commit.
9. `validate-wake-on-windows.md`. One commit.

Atomic-per-step as usual.

## Windows-specific concerns (i7-13700K / Python 3.12 / RTX 4080)

- openwakeword 0.6+ has Windows wheels on PyPI. Confirmed supported
  Python: 3.8–3.12.
- onnxruntime's CPU provider is what we use at runtime. ~0.5 ms per
  80 ms chunk on one core. No GPU cost.
- The training step uses `torch` that we already have installed; no
  CUDA setup needed because we train on CPU. Explicitly set
  `CUDA_VISIBLE_DEVICES=""` in `train_hey_sabrina.py` to avoid
  accidental GPU use that might collide with Ollama.
- Audio device pinning: wake-word uses the same `input_device` as PTT
  via the shared `AudioMonitor`. No separate device knob. If Eric's USB
  mic has a level issue, `sabrina wake-test` surfaces it before we
  wire wake-word into the main loop.
- pygetwindow / admin: not relevant here — no window-focus dependency.

## Open questions

None. Eric's sign-off resolved the model choice (custom "Hey Sabrina").
Threshold, cooldown, and auto-capture duration are defaults in the
config block; `sabrina wake-test` is how they get tuned on his setup.

If the trained model's false-positive rate turns out to be unacceptable
in real-room testing, we expand the positive/negative data or revisit
the threshold. That's operational, not a plan question.

## Ship criterion

- All new unit tests pass.
- `sabrina wake-test` reports a peak score >= 0.7 for "hey sabrina"
  spoken at conversational volume 1 m from the mic on Eric's setup.
- `sabrina voice` with wake enabled: 5 for 5 triggers on direct
  address. False-positive rate under 1/hour during a casual-conversation
  smoke run (no one addressing Sabrina).
- First-audio latency on a wake-triggered turn within 500 ms of PTT-
  triggered baseline (the wake path adds ~80–160 ms for the tail of
  the word + cooldown; measurable, should not regress meaningfully).
- PTT continues to work alongside. Both paths coexist.

## Not in this plan (later)

- Second wake word (e.g. "sabrina, stop" for global interrupt).
- On-device retraining (grab "real" positives from Eric's voice to
  augment the synthetic set). Big quality lever; out of MVP scope.
- Wake-word status indicator in the GUI ("is she listening right now").
  Same pattern as `SpeakStarted` events; slots in when the GUI grows a
  status bar.
- Shared VAD between wake + barge-in. Not necessary; openWakeWord's
  built-in VAD is independent of Silero and the two don't conflict.

---

**Ready for implementation** the moment barge-in ships. No pending
decisions; all open questions from the master plan were resolved by
Eric's sign-off.
