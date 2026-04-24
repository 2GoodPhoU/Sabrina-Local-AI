# Barge-in — Windows validation procedure

**Purpose:** confirm barge-in (Silero VAD mid-TTS interrupt) works end-to-end
on Eric's Windows box before we call the barge-in decision validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from `sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`. Barge-in
implementation has landed per `rebuild/drafts/barge-in-plan.md` (CancelToken
on Brain/Speaker, `listener/vad.py`, `AudioMonitor`, voice-loop wiring,
`[barge_in]` block in `sabrina.toml`).

All commands are copy-pasteable. Each step lists the success signal. The
"If step N fails" section at the bottom maps failure symptoms to likely
causes so you can report back without a second round-trip.

---

## Step 0 — Sanity-check Silero VAD loads

Most likely failure mode here is the `silero-vad` pip wheel not loading
onnxruntime on this Python. Before we touch anything else, prove the
import works.

```powershell
uv run python -c "from silero_vad import VADIterator, load_silero_vad; m = load_silero_vad(onnx=True); print('ok', type(m).__name__)"
```

**Success:** prints `ok OrtInferenceSession` (or similar onnxruntime
session type).
**Failure signal:** `ImportError: silero_vad`, or
`RuntimeError: LoadLibrary failed with error ... onnxruntime`.
**Fix for import error:** `uv sync` didn't pick up the new dep; re-run
step 1 below. **Fix for onnxruntime load error:** onnxruntime's MSVC
runtime isn't on the machine — install the VS 2022 C++ redistributable
from Microsoft and retry. If it still fails, file the barge-in
decision's "VAD won't load on this Windows box" branch.

---

## Step 1 — `uv sync`

```powershell
uv sync
```

**Success:** finishes without errors. Pulls `silero-vad>=5.1` and its
onnxruntime transitive. `uv.lock` mtime bumps.
**Failure signal:** resolver errors, wheel-not-found on `silero-vad`.
**Fix:** capture the full resolver error; see "If step 1 fails" below.

---

## Step 2 — `uv run pytest -q`

```powershell
uv run pytest -q
```

**Success:** all existing tests still pass (70+ from decision 007), plus
the new barge-in block — roughly 6–8 new tests:

- `test_cancel_token_basic`
- `test_cancel_token_propagates_through_stub_brain`
- `test_cancel_token_stops_stub_speaker`
- `test_vad_state_machine_ignores_below_min_speech_ms`
- `test_vad_fires_on_sustained_speech` (may skip if silero-vad isn't
  importable at collection time — that's OK via `pytest.importorskip`)
- `test_voice_loop_interrupt_stops_reply_and_captures_audio`

Wall time under ~6 s.

**Failure signal A — skips on the VAD-gated tests.** `pytest -q -rs`
will show the skip reason. If it's `silero-vad not importable`, step 0
should have caught it — re-check. If it's something else, capture.
**Failure signal B — real assertion failures.** Capture the full
traceback, especially on `test_voice_loop_interrupt_stops_reply_and_captures_audio`
(the tricky integration test).

---

## Step 3 — Turn barge-in on

Edit `sabrina-2/sabrina.toml`:

```toml
[barge_in]
enabled = true
threshold = 0.5
min_speech_ms = 300
dead_zone_ms = 300
continue_on_interrupt = true
```

Leave the other keys at defaults. `sabrina config-show | findstr
/i barge` will confirm on step 4.

---

## Step 4 — `uv run sabrina config-show | findstr /i barge`

```powershell
uv run sabrina config-show | findstr /i barge
```

**Success:** shows the five barge-in keys including `enabled = True`.
**Failure signal:** key missing → `[barge_in]` block didn't round-trip
through settings loader. Run `type sabrina.toml | findstr -i barge`
to confirm the file was saved correctly.

---

## Step 5 — One real voice loop, no interrupt (baseline)

```powershell
uv run sabrina voice
```

Hold right-Shift, ask *"tell me about the brain router in three
sentences"*, release, let her finish.

**Success:** reply completes normally. Structlog output (with
`SABRINA_LOGGING__LEVEL=DEBUG` in `.env`) shows `audio_monitor.started`
on entry to speaking and `audio_monitor.stopped` on exit, with no
`bargein.detected` line between them.

**Why this matters:** a VAD that misfires on Sabrina's own TTS bleed
makes every turn self-interrupt. If this step shows any `bargein.detected`
firing without you speaking, the dead-zone or threshold needs tuning
before moving on. Capture `logs/sabrina.log` and bump `dead_zone_ms` to
500 before retrying.

**First-audio latency check:** warm-turn first-audio should be within
~50 ms of the pre-barge-in baseline (the VAD monitor runs during speaking,
not on the cold path). Report the number.

---

## Step 6 — Mid-reply interrupt

Same `uv run sabrina voice` session. Ask a long-answer question:
*"give me a five-paragraph essay about sqlite"*. As soon as you hear
her start speaking the second sentence, say loudly and clearly:
*"stop — never mind"*.

**Success — three things to observe:**

1. **TTS cuts within ~250 ms of your voice onset.** Measure by ear or
   by the `bargein.detected` timestamp relative to the next audio chunk
   going silent.
2. **Structlog shows the cancellation propagating:**
   ```
   bargein.detected score=0.6x min_speech_ms=300
   brain.cancel_token.fired
   speaker.cancel_acknowledged
   state.transition from=speaking to=listening reason=barge_in
   ```
3. **Your "stop — never mind" becomes the next transcribed turn** (if
   `continue_on_interrupt = true`). No PTT press needed. The brain
   replies to *that*, not the original essay prompt.

**Failure signals:**
- TTS keeps playing for more than ~1 s after you speak → cancel token
  isn't checked often enough inside `PiperSpeaker.speak` (between
  sentences is too coarse for a 5-paragraph reply). See "If step 6 fails"
  below.
- Brain keeps streaming after cancel → `ClaudeBrain.chat` isn't checking
  `cancel_token.cancelled` between deltas. Log will show `text_delta`
  lines continuing after `brain.cancel_token.fired`.
- State doesn't return to `listening` → `voice_loop` finally-block
  isn't publishing `BargeInDetected` or the state machine rejected the
  transition. Check `state.transition_rejected` line.

---

## Step 7 — Noise smoke (false-positive check)

```powershell
uv run sabrina voice
```

Hold PTT, ask a long-answer question. While she's speaking, do *not*
speak but do introduce typical desktop noise: type on the keyboard at
normal speed for ~5 s, move the mouse, click a few times. Let her
finish without you interrupting.

**Success:** reply completes cleanly. No `bargein.detected` line in the
structlog output despite the noise. If one fires on keyboard noise,
`threshold = 0.5` is too low for this room/mic — bump to 0.6 and
retest.

**Why this matters:** Silero VAD is speech-trained but not perfect.
Mechanical noise shouldn't trip it at default threshold. If it does,
the barge-in feature is unusable until threshold is tuned.

---

## Step 8 — Audio-device lock race check

Ctrl+C out of `sabrina voice`. Immediately relaunch:

```powershell
uv run sabrina voice
```

**Success:** starts cleanly. No `sounddevice` / `PortAudio` error about
the device being in use. The input stream the previous `AudioMonitor`
held must have been closed cleanly.

**Failure signal:** `PortAudioError: Error opening InputStream: Device
unavailable [PaErrorCode -9985]`. Means the previous AudioMonitor's
InputStream wasn't properly closed on shutdown — its `stop()` is either
not being called in the voice-loop's finally-block, or is being called
but not awaited. Capture the shutdown traceback.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | `ImportError: silero_vad` | `uv sync` skipped the dep or wheel not on PyPI for this Python | `uv pip list \| findstr silero` |
| 0 | `LoadLibrary` / onnxruntime DLL error | Missing VS C++ redistributable | `uv run python -c "import onnxruntime; print(onnxruntime.__version__)"` + Windows build number |
| 1 | resolver error | stale uv cache vs. new pin | Full `uv sync` output |
| 2 | VAD tests skipped | `silero-vad` importorskip tripped despite step 0 passing | `uv run pytest -q -rs` output for the skipped tests |
| 2 | `test_voice_loop_interrupt_stops_reply_and_captures_audio` fails | Cancel-token plumbing regression | Full traceback + which assert fired |
| 5 | VAD self-triggers on TTS bleed | `dead_zone_ms` too short OR threshold too low for Sabrina's own voice level | `logs/sabrina.log` around the false `bargein.detected` line |
| 6 | TTS keeps playing after your voice | Cancel-token not polled inside speaker synth loop | `logs/sabrina.log` — look for gap between `bargein.detected` and `speaker.cancel_acknowledged` |
| 6 | Brain keeps streaming | Cancel-token not polled between deltas in claude.py | Count of `text_delta` lines after `brain.cancel_token.fired` |
| 6 | State doesn't transition | State machine rejected the transition | `state.transition_rejected` line |
| 7 | Keyboard noise triggers barge-in | Threshold too low for this mic | Peak VAD score during the noise smoke (DEBUG log) |
| 8 | `Device unavailable` on relaunch | AudioMonitor's InputStream not closed in voice-loop shutdown | Shutdown traceback from prior Ctrl+C |

---

## Known risks from the pre-validation code audit

1. **Cancel-token check granularity varies per brain/speaker.** `ClaudeBrain`
   naturally yields between deltas, so the check is tight. `OllamaBrain`
   streams bigger chunks and may feel laggier to cancel. Piper synthesizes
   per-sentence — cancellation mid-sentence stops the *next* chunk, not
   the currently-playing one. 250 ms target for step 6 assumes Piper;
   SAPI's cancel path purges its queue which is faster.
2. **`AudioMonitor` shares the input device with PTT.** On Windows,
   sounddevice serializes access to the same device. If PTT also has an
   open stream during speaking state, opening AudioMonitor will fail.
   Voice-loop must close PTT's stream on entry to speaking and reopen
   on exit. If step 8 fails, this is likely the real bug.
3. **Dead-zone interacts with first-sentence length.** The 300 ms
   dead-zone suppresses VAD at the start of *every* sentence — but only
   the first one of a reply really needs it. A short first sentence
   followed by a longer second one is the worst case for user interrupts
   landing in the dead-zone. Tune dead-zone down if step 6 timing
   consistently misses the interrupt.
4. **Silero's bundled ONNX model is small (~2 MB) and loads instantly.**
   No cold-start cost to worry about; the model is held by the
   `AudioMonitor` for the lifetime of the voice loop.

---

## If all green — the ROADMAP bump

**Do not file a separate decision doc for validation.** Anti-sprawl:
the feature's own decision doc (the one filed when barge-in shipped)
gets the validation stamp. Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line at top to today's date.
2. Append one line at the end of the "Status:" paragraph:

```
Barge-in validated on Windows (i7-13700K/4080, Python 3.12) <YYYY-MM-DD>:
VAD loaded, <M> ms cut latency observed, no noise false-positives at
threshold=<T>, first-audio regression <R> ms.
```

Replace `<M>` with the measured cut latency from step 6, `<T>` with the
final threshold that passed step 7, and `<R>` with the first-audio
delta from step 5. `<YYYY-MM-DD>` is today.

Commit with message:
```
validate: barge-in on Windows (M ms cut, T threshold)
```

Then we move on to the next ready-to-ship component.

---

## If any step failed

1. Capture the output per the triage table above.
2. File a follow-up decision doc under `rebuild/decisions/` with the
   next free number. Template:
   - **Step X failed** with symptom Y.
   - **Root cause** based on the triage table's "Likely cause".
   - **Fix direction** (code change, config tuning, or dep bump).
3. If the failure is in the cancel-token plumbing itself (step 6 brain
   or speaker), the fix is tight enough to ride along in the same
   decision doc as barge-in with a "validation revealed X, fixed in
   commit Y" footnote — don't spawn a new decision for a single-commit
   follow-up.
