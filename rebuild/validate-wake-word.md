# Wake word — Windows validation procedure

**Purpose:** confirm the "Hey Sabrina" wake-word trigger works end-to-
end on Eric's Windows box before we call the wake-word decision
validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.
Wake-word implementation has landed per `rebuild/drafts/wake-word-plan.md`
(`listener/wake.py`, `voices/wake/hey_sabrina.onnx` committed,
`sabrina wake-test` verb, `[wake_word]` block in `sabrina.toml`). **Barge-
in must have shipped first** — wake-word relies on `AudioMonitor` from
the barge-in work.

All commands are copy-pasteable. Each step lists the success signal. The
"If step N fails" section at the bottom maps failure symptoms to likely
causes.

---

## Step 0 — Sanity-check openwakeword + model file

```powershell
uv run python -c "import openwakeword; from openwakeword import Model; m = Model(wakeword_models=['voices/wake/hey_sabrina.onnx'], inference_framework='onnx'); print('ok', list(m.models.keys()))"
```

**Success:** prints `ok ['hey_sabrina']` (or similar — the list should
include the basename of the committed model file).
**Failure signal A:** `ImportError: openwakeword`. `uv sync` didn't
install it; re-run step 1.
**Failure signal B:** `FileNotFoundError: voices/wake/hey_sabrina.onnx`.
The committed model never landed. Check `git log voices/wake/` —
if blank, the model commit is missing.
**Failure signal C:** `onnxruntime` DLL load error. Same VS C++
redistributable problem as barge-in step 0.

---

## Step 1 — `uv sync`

```powershell
uv sync
```

**Success:** pulls `openwakeword>=0.6`. `uv.lock` mtime bumps.

---

## Step 2 — `uv run pytest -q`

```powershell
uv run pytest -q
```

**Success:** existing tests pass, plus the wake-word block (~5 new
tests):

- `test_wake_detector_below_threshold_returns_none`
- `test_wake_detector_cooldown_suppresses_rapid_retriggers`
- `test_wake_detector_fires_after_cooldown`
- `test_voice_loop_wake_path_captures_audio_and_transcribes`
- `test_wake_word_event_schema_guard`

**Failure signals:** same pattern as other validation docs — capture the
traceback. If the openwakeword-gated tests skip, that means
`importorskip` tripped at collection and step 0 should have caught it.

---

## Step 3 — `uv run sabrina wake-test` for threshold tuning

```powershell
uv run sabrina wake-test --samples 10
```

Read the prompt. It will ask you to say "hey sabrina" 10 times at
conversational volume from your usual desktop position (~1 m from the
mic). Say it clearly, leave a short pause between utterances.

**Success:** output looks like:

```
Listening for 10 samples of "hey sabrina"...
  [1/10] peak score = 0.83
  [2/10] peak score = 0.79
  [3/10] peak score = 0.88
  ...
  [10/10] peak score = 0.81

Suggested threshold: 0.63  (min peak 0.79 * 0.8)
```

Every sample should peak above 0.7 — meaningfully above the library's
default threshold of 0.5. If any peak is below 0.7, your mic level or
room acoustics are marginal for this model.

**Failure signal A:** some or all samples below 0.5 peak. The model
isn't recognizing *your* voice well. Options:
- Confirm mic level: `sabrina test-audio` reads peaks when you speak
  normally; should hit -6 to -12 dBFS. If it's -24 dBFS or below,
  raise your mic level in Windows sound settings first.
- If mic level is fine, the model was trained on Piper synthetic
  positives which may not match your voice timbre. File a follow-up
  decision to retrain with a handful of real Eric-voice positives.

**Failure signal B:** peaks are fine but jittery (0.3, 0.9, 0.4, 0.7, ...).
Suggests the VAD gate inside openwakeword is cutting off the word. Try
saying "hey sabrina" with a slightly clearer pause after.

Record the suggested threshold. You'll use it in step 4.

---

## Step 4 — Turn wake-word on

Edit `sabrina-2/sabrina.toml`:

```toml
[wake_word]
enabled = true
model_path = "voices/wake/hey_sabrina.onnx"
threshold = 0.63              # <- paste step 3's suggested threshold
cooldown_ms = 2000
auto_capture_s = 5.0
```

---

## Step 5 — Cold-start load test

This is the "does the wake model load on launch without GPU contention
with Ollama" smoke. Shut down any running Ollama instance first:

```powershell
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process
uv run sabrina voice
```

**Success:** launch completes in under ~2 s. Structlog shows:

```
wake.model_loaded path=voices/wake/hey_sabrina.onnx
audio_monitor.started consumer=wake
state.transition from=boot to=idle
```

No GPU-related error lines. openWakeWord runs CPU-only; if you see any
CUDA lines, the onnxruntime provider priority is wrong.

**Failure signal:** crash on startup with a model-load traceback →
the ONNX file may be committed but malformed, or the library version
in `pyproject.toml` doesn't match the model's training format.
Capture the traceback and the openwakeword version:

```powershell
uv pip show openwakeword
```

---

## Step 6 — Wake-from-idle smoke (5-for-5)

With `sabrina voice` running and the window idle in another app, say
*"Hey Sabrina, what time is it?"* — conversational volume, ~1 m from
the mic. Repeat 5 times, leaving ~10 s between attempts so the
cooldown clears.

**Success:** all 5 attempts trigger the turn without any PTT press.
Structlog between each:

```
wake.detected word=hey_sabrina score=0.7x
state.transition from=idle to=listening reason=wake_word
listener.transcribe_start audio_src=audio_monitor.drain_recent seconds=5.0
```

The transcription should include the full "what time is it" because
`AudioMonitor.drain_recent` captured the audio alongside detection.

**Failure signal A:** wake detects but `drain_recent` returns silence,
and the transcribed text is empty or just "hey sabrina" without the
follow-on → AudioMonitor's ring buffer is too short (the user's full
utterance doesn't fit in the cached window), or the drain happens
before the user finishes speaking. Check the `audio_monitor.ring_buffer_size`
log line; should be at least 6-8 s.

**Failure signal B:** some attempts don't fire → threshold too high
for this session's conditions. Drop to `(step 3 min peak) * 0.7`
instead of `* 0.8`.

**Failure signal C:** wake fires but voice loop doesn't transition —
PTT race lost. `_wait_for_trigger` in voice_loop isn't cancelling
`ptt_task` cleanly when `wake_task` wins.

---

## Step 7 — False-positive check over typical desktop noise

Leave `sabrina voice` running. Set a timer for 5 minutes. During those
5 minutes, use your computer normally — no addressing Sabrina: type,
open apps, watch a short video, have a normal phone call, play music
at moderate volume through the speakers, etc. Do **not** say "hey
sabrina" (or similar-sounding phrases — "hey samantha," "say gabrina,"
etc.).

**Success:** zero `wake.detected` log lines in 5 minutes.

**Failure signal A — one or two triggers:** borderline, tune up
`threshold` by 0.05 and repeat. A daily-driver false-positive rate
above 1/hour is unacceptable.
**Failure signal B — repeated triggers on specific sounds:** note what
was playing. Music tracks with cymbal-heavy percussion or certain
vowel-dense English phrases ("hey [everything]") are the known failure
mode for openWakeWord's default training. File a follow-up decision
to add those clips as negatives and retrain.

---

## Step 8 — Wake-while-TTS is playing (barge-in cross-dependency)

This tests that AudioMonitor can run in both consumer modes without
device contention. Barge-in uses AudioMonitor during *speaking* state;
wake uses it during *idle*. The design says they're single-consumer
per state — but a transition between them happens every turn, so we
verify the hand-off.

```powershell
uv run sabrina voice
```

1. Press PTT, ask *"give me a long three-paragraph reply about
   anything"*, release.
2. As Sabrina starts speaking, let her finish one full sentence —
   do not interrupt, do not say "hey sabrina" yet. Confirm VAD isn't
   firing on her own voice (if it is, that's a barge-in validation
   problem, not a wake problem).
3. As soon as she stops speaking and state transitions back to idle,
   say *"hey sabrina, stop"*. Expect wake to fire immediately.

**Success:** structlog around the transition looks like:

```
state.transition from=speaking to=idle reason=reply_complete
audio_monitor.consumer_swap from=vad to=wake
wake.detected word=hey_sabrina score=0.7x
state.transition from=idle to=listening reason=wake_word
```

No `PortAudioError` between `consumer_swap` lines.

**Failure signal:** `PortAudioError: Device unavailable` on consumer
swap → AudioMonitor is tearing down the InputStream on state change
instead of holding it across the transition. The plan says "multi-
consumer dispatch with one consumer per state" — the stream should
stay open. File a follow-up.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | `FileNotFoundError` on model | ONNX commit missing | `git log -- voices/wake/` |
| 0 | `LoadLibrary` error | Missing VS C++ redist | Windows version + `uv run python -c "import onnxruntime; print(onnxruntime.get_available_providers())"` |
| 3 | All peaks below 0.5 | Mic level too low, or voice/model mismatch | `sabrina test-audio` peak reading + a 5 s WAV of "hey sabrina" via `sabrina asr-record` |
| 3 | Jittery peaks | VAD-gate timing | Raw score-per-chunk log with DEBUG level |
| 5 | Slow startup (> 5 s) | Model load on GPU → CUDA contention with Ollama | `ollama ps` + `nvidia-smi` during launch |
| 6 | Wake fires but transcript empty | Ring buffer too short or drain timing | `audio_monitor.drain_recent` log line with returned sample count |
| 6 | PTT race lost | Task cancellation missing | Full log around `wake.detected` |
| 7 | False-positive rate > 1/hr | Threshold too low OR negative training gap | 5-min log with every `wake.detected` line + what was playing |
| 8 | Device unavailable on consumer swap | InputStream torn down prematurely | Full log around `audio_monitor.consumer_swap` |

---

## Known risks from the pre-validation code audit

1. **`min_age_turns=20` from semantic memory doesn't apply here.** The
   wake model is stateless per utterance; there's no analogous "ignore
   recent speech" problem. Mentioning so the instinct to look for it
   doesn't waste time.
2. **openWakeWord's built-in VAD may conflict with Silero.** The plan
   says they're independent and coexist; both gate on different
   criteria. Watch for double-detection in step 8 — if you see both
   `bargein.detected` and `wake.detected` in sequence during a single
   utterance, the state-machine's idle/speaking gate isn't working
   (only one should run per state).
3. **`auto_capture_s=5.0` is generous.** Long enough for "Hey Sabrina,
   what's the weather in San Francisco today?" but may overrun a
   terse one-phrase command with 3+ seconds of trailing silence. The
   transcriber should trim trailing silence — if transcripts are
   consistently noisy at their tails, bump `auto_capture_s` down to
   4.0.
4. **Piper's synthetic training positives don't perfectly match Eric's
   voice.** That's why step 3 tunes threshold rather than accepting the
   0.5 library default. If the training gap is too wide to cover with
   threshold (step 3 all below 0.5), retraining with a dozen real
   positives is the fix; documented but not in this validation scope.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line at the end of the "Status:" paragraph:

```
Wake-word "hey sabrina" validated on Windows (i7-13700K/4080, Python
3.12) <YYYY-MM-DD>: threshold=<T>, 5/5 trigger rate, <F> false-
positives in 5 min noise smoke, cold-start <C> s.
```

`<T>` from step 3/4, `<F>` from step 7 (target 0), `<C>` from step 5.

Commit with message:
```
validate: wake-word on Windows (threshold T, 0 false-positives)
```

---

## If any step failed

1. Capture per the triage table.
2. File a follow-up decision doc. The three most likely follow-ups:
   - **Threshold unusable for Eric's voice** (step 3 all below 0.5) →
     retrain with real positives. Decision doc captures the data plan.
   - **False-positive rate too high at usable threshold** (step 7) →
     expand negative set, retrain. Separate doc.
   - **AudioMonitor consumer swap fails** (step 8) → fix in the
     barge-in / wake-word shared code; not a new numbered decision, just
     a commit+footnote on whichever shipped most recently.
