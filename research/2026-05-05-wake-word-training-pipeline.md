# Wake-word custom model training pipeline — grounded research

**Date:** 2026-05-05
**Author:** sabrina-researcher (4am scheduled run)
**Picked up from:** QUEUE.md `Decomposed (next-pull-ready)` → **P2.1 Wake-word — custom "Hey Sabrina" training pipeline research draft** (`[linux-runnable] [P1] [M]`).
**Predecessor:** `rebuild/drafts/wake-word-plan.md` (2026-04-23, "ready-to-ship draft"). This research grounds the predecessor plan against the current state of openWakeWord + piper-sample-generator and reports where the predecessor still holds, where it diverges from current upstream practice, and where Eric's recommendation should be adjusted.

---

## Question (verbatim from QUEUE.md P2.1)

> Bounded investigation into openWakeWord's training-data shape, tooling, and packaging path, given the current `hey_jarvis` placeholder.
>
> Definition of done (research-only, no DoD tier — it's a research artifact): `research/2026-05-MM-wake-word-training-pipeline.md` exists describing (1) the openWakeWord training data format + minimum sample counts, (2) the audio capture / synthesis pipeline (Eric's voice samples vs. TTS-generated negatives), (3) the .onnx packaging shape that drops into `sabrina-2/models/openwakeword/`, (4) the validation procedure on Windows once trained, (5) a reasoned go/no-go recommendation. No code changes.

---

## What I checked

### Project files (read-only)

- `CLAUDE.md`, `STATE.md`, `QUEUE.md`, `NEEDS-INPUT.md`, `JOURNAL.md` (last cycle).
- `rebuild/drafts/wake-word-plan.md` — full predecessor plan, dated 2026-04-23.
- `sabrina-2/src/sabrina/listener/wake_word.py` — runtime detector + monitor (270 lines, scaffold landed 2026-04-25 with `hey_jarvis` placeholder).
- `sabrina-2/pyproject.toml` — current deps and uv environment scoping (`sys_platform == 'win32'`).
- `sabrina-2/sabrina.toml` — `[wake_word]` block (current `model = "hey_jarvis"`, `enabled = false`).
- `sabrina-2/models/openwakeword/` — empty (no custom `.onnx` checked in yet).
- `roles/researcher.md` — confirmed scope and output shape.

### Web sources

- `github.com/dscripka/openWakeWord` (README + notebooks + issue tracker).
- `github.com/rhasspy/piper-sample-generator` (sample generator README + `generate_samples.py`).
- `pypi.org/project/openwakeword/` and `pypi.org/project/piper-sample-generator/`.
- `home-assistant.io/voice_control/create_wake_word/` (Home Assistant's documented end-user training pipeline).
- `medium.com/neural-engineer/evaluation-of-openwakeword-engine-false-reject-performance-...` (third-party empirical evaluation).
- GitHub issue #110 (poor performance with the automatic notebook), discussion #45 (community training experience), discussion #62 (training-failure-at-75%), issue #204 (Ubuntu 24.04 WSL2 incompatibility).
- `github.com/lgpearson1771/openwakeword-trainer` — third-party 13-step pipeline, "WSL2/Linux + CUDA required" — produces ~200 KB ONNX models.
- `github.com/sujitvasanth/openwakeword-simplified` — single-file simplified training fork.
- Outspoken Cloud's commercial wake-word service write-up (data-volume reference points only).

### Not checked

- Did not run any training code. Researcher role is read-only.
- Did not install openwakeword's `[training]` extra in this sandbox; the upstream project explicitly states automated training is "Linux only" because piper-phonemize lacks Windows wheels (relevant for the recommendation below).
- Did not check Eric's i7-13700K + RTX 4080 against current torch/CUDA matrix — out of bounded scope for a research-only doc.

---

## What I found

### 1) Training data format + minimum sample counts

**Format the trainer consumes.** openWakeWord 0.6's automated training pipeline expects:

- **Positive clips** — directory of WAV files at 16 kHz mono, 1–2 s each, containing the target wake phrase. The clips do not need to be transcribed or labeled — directory membership is the label.
- **Negative features** — pre-computed feature tensors representing speech, music, and noise. openWakeWord's training distribution ships ~30,000 hours of pre-computed negatives that the trainer consumes directly. You do not synthesize your own negatives; you point the trainer at the bundled feature path.
- **Room impulse responses (RIRs)** — bundled MIT RIR set for acoustic augmentation. The trainer convolves positives against RIRs at training time to simulate distance + room reverb.
- **Background audio** — bundled clips for negative augmentation (low-level noise mixed under positives during training).

The upstream training script is configured by a single YAML file with paths to each of those four sources. `automatic_model_training.ipynb` is the canonical reference; `training_models.ipynb` is the manual lower-level path.

**Minimum sample counts (empirical, not a hard floor).** Upstream has no published "minimum samples" number. Practical signal from issue #110 + discussion #45 + the lgpearson1771 trainer:

- **Default upstream config** generates ~10,000 training positives and ~2,000 validation positives. This is the "you'll get a defensible model" tier.
- **Rhasspy/Home-Assistant community baseline** is ~3,000–4,000 synthesized positives for usable single-speaker models — works but with elevated false-reject rates.
- **Floor where the trainer just starts to converge** — ~1,000 positives, but at this volume the model often fails the upstream default acceptance criteria (recall ≥ 0.5, false-positive ≤ 0.2/hour).
- **Issue #110 is the cautionary tale** — running automatic_model_training.ipynb with the default config in Colab routinely produces poor models; users on the issue tracker land usable models only after augmenting with personal voice samples or moving to a longer-running local training run.

The **upstream-published acceptance criteria the trainer optimizes against** are: accuracy ≥ 0.7, recall ≥ 0.5, false-accept rate ≤ 0.2/hour. Real production targets often reach: false-reject < 5%, false-accept < 0.5/hour with threshold tuning. The predecessor plan's ship criterion ("peak score ≥ 0.7 at 1 m, 5/5 triggers, < 1 false-positive/hour") is consistent with the strict end of these targets.

### 2) Audio capture / synthesis pipeline — the predecessor plan vs. current upstream practice

**The predecessor plan's approach (2026-04-23):** Use Piper voices we already ship to synthesize ~4,000 positives (200 speakers × 3 prosody × ~7 textual variants), augment with audiomentations 3× to ~12,000 clips, train on CPU for ~30–60 minutes.

**Current upstream practice:** Almost identical *in spirit*, but the canonical tooling has consolidated into the **`rhasspy/piper-sample-generator`** package, which is purpose-built for exactly this. Key facts:

- `piper-sample-generator` ships a special English-only "generator" voice that mixes speaker embeddings on the fly, replacing the predecessor plan's hand-rolled "200 speakers × prosody variants" loop. CLI: `python -m piper_sample_generator '<phrase>' --max-samples N --output-dir <dir>`.
- It outputs 16 kHz mono WAVs directly (no resample step needed).
- Speaker count and prosody variation are parameters of one tool call, not a manually scripted multiplication.
- piper-sample-generator's PyPI metadata claims `Operating System :: OS Independent`. **However**, it depends on `piper-phonemize`, which **does not build on Windows** as of late 2025 — the fastest first hit on this is the upstream wake-word-plan note plus current GitHub issues. Practically: sample generation runs cleanly on Linux/WSL2; on native Windows it requires either a pre-built wheel (none ships for cp312) or running inside WSL2.
- openWakeWord's `automatic_model_training.ipynb` itself states **"only supported on Linux"** in its preamble — same root cause (depends on piper-phonemize).

**Eric's voice samples (per the question's "TTS-generated vs Eric's voice"):** None of the upstream pipelines require Eric's voice. Bundled-model training is 100% TTS-synthesized. Custom *verifier* models — a separate openWakeWord feature documented at `docs/custom_verifier_models.md` — sit *on top of* a base wake-word model and act as a per-speaker filter. Verifier models DO use Eric's recorded voice (a few dozen positive samples), and they reduce false-accept rate substantially when the base model false-fires on unrelated speech. The predecessor plan does not use verifier models and treats them as out-of-scope. Recommendation in §5 below revisits this.

**Augmentation:** openWakeWord's training pipeline already does RIR convolution + background-noise mixing internally. The predecessor plan's `audiomentations` 3× expansion is *additional* augmentation outside the trainer; it can help but is not strictly necessary. Upstream's bundled augmentations are calibrated to the bundled negative set; adding outside augmentation can occasionally hurt as much as help if the augmentation distribution drifts from what the negatives represent.

### 3) ONNX packaging shape that drops into `sabrina-2/models/openwakeword/`

**Trainer output.** The auto-training script emits two artifacts in the present working directory:

- `my_custom_model/<model_name>.onnx` — the inference model.
- `my_custom_model/<model_name>.tflite` — TFLite version (Linux-only at runtime).

`<model_name>` is set in the training YAML. For "Hey Sabrina" the convention would be `hey_sabrina`.

**Runtime expectations of the existing scaffold.** `sabrina-2/src/sabrina/listener/wake_word.py:104-116` already accepts either a bundled name or a path to an `.onnx` file. The relevant excerpt:

```python
path = Path(self._model_id)
if path.suffix.lower() == ".onnx" and path.is_file():
    self._impl = Model(
        wakeword_models=[str(path)],
        inference_framework="onnx",
    )
else:
    # Pass the bundled model name; openwakeword resolves it
    # against its packaged set.
    self._impl = Model(
        wakeword_models=[self._model_id],
        inference_framework="onnx",
    )
```

So the runtime piece is already wired. To switch from `hey_jarvis` to a custom model, only `sabrina.toml` needs to change:

```toml
[wake_word]
model = "models/openwakeword/hey_sabrina.onnx"
```

**Where to drop the file.** The QUEUE P2.2 item already specifies `sabrina-2/models/openwakeword/hey_sabrina.onnx`. That directory does not yet exist; checking it in with the `.onnx` is the natural creation path.

**File size.** Custom openWakeWord models are typically ~200 KB to ~5 MB (the third-party lgpearson1771-trainer notes specifically advertises "tiny ONNX models (~200 KB)"). Comfortably git-trackable; no LFS needed. The predecessor plan's "2-5 MB" estimate is the conservative end of this range.

**Predecessor plan divergence.** The predecessor plan placed the trained model under `voices/wake/hey_sabrina.onnx`. The QUEUE P2.2 item changed this to `sabrina-2/models/openwakeword/hey_sabrina.onnx` — closer to upstream openWakeWord's convention of grouping wake-word models under one directory. The QUEUE convention is preferred; the predecessor plan was authored before the rebuild's models/ layout settled.

### 4) Windows validation procedure once trained

The predecessor plan's `validate-wake-on-windows.md` doesn't yet exist (the file is referenced in step 9 but not yet created). The substance of what it should contain is well-defined by current upstream practice plus the predecessor's "Ship criterion" section. Concretely:

**Pre-flight:**
1. Eric's i7-13700K + Win11 + Python 3.12 box has openwakeword 0.6+ and onnxruntime installed (already in `pyproject.toml`).
2. Custom `hey_sabrina.onnx` lives at `sabrina-2/models/openwakeword/hey_sabrina.onnx`.
3. `sabrina.toml` `[wake_word]` block: `enabled = false` (still — flip is the last step), `model = "models/openwakeword/hey_sabrina.onnx"`, `threshold = 0.5` initial.

**Tuning loop:**
1. **Threshold pick.** Run a `sabrina wake-test` CLI verb (planned in predecessor plan, not yet shipped — corresponds to ROADMAP P2.3's "validate-wake-word.md checklist"). Records 5 s, runs detector, prints peak score. Say "hey sabrina" 5 times, note the minimum peak. Set `threshold = (min_peak * 0.8)` rounded to two decimals. Empirical default of 0.5 often holds; some mics will need 0.4 or 0.6.
2. **True-positive smoke.** With `enabled = true`, run `sabrina voice` and direct-address the assistant 5 times from ~1 m, normal volume. Target: 5/5 trigger. If < 5/5, lower threshold by 0.05 and retry. If > 1 chunk delay, the issue is detector cold-load — first turn will always be slowest.
3. **False-positive smoke.** Play a 5-minute podcast through speakers in the room with `sabrina voice` running. Goal: zero spurious triggers. If > 0/5min, raise threshold by 0.05 and retry. The predecessor plan's < 1/hour target is generous.
4. **First-audio latency.** Time from end-of-wake-phrase to start-of-recording. Target: within 500 ms of PTT-triggered baseline. The wake path adds ~80–160 ms naturally (one openWakeWord frame + cooldown reset).

**Promotion to `[done]`:**
- All four items pass.
- `pytest sabrina-2/tests/test_smoke.py -k "wake"` passes on Windows / Python 3.12.
- Voice loop validated end-to-end (record → STT → brain → TTS) per CLAUDE.md.
- `[wake_word] enabled = true` committed in `sabrina.toml`.
- Decision doc filed (next number in `rebuild/decisions/`).

This procedure maps directly onto QUEUE P2.3's DoD ("validate-wake-word.md checklist runs clean on Windows; `sabrina voice` activates on 'Hey Sabrina' with no false positives in a 10-minute background-conversation test").

### 5) Where to actually run the training

This is the load-bearing finding of this research. The predecessor plan assumes training runs on Eric's Windows box ("Use CPU. The 4080 is overkill ... ~30-60 min"). **Current upstream reality contradicts that assumption.**

- openWakeWord's automatic training notebook is **explicitly Linux-only** because piper-sample-generator depends on piper-phonemize, which has no Windows wheels. Issue tracker confirms this is current as of late 2025 — no Windows fix has shipped.
- The third-party lgpearson1771 trainer that produces the "tiny ONNX" results is also flagged "WSL2/Linux + CUDA required" in its README.
- Native-Windows training requires either re-implementing the phonemization step against a Windows-buildable phonemizer (espeak-ng has Windows builds; non-trivial substitution) or skipping piper-sample-generator entirely and using a different TTS that runs on Windows (e.g., the Piper binary we already ship, scripted manually as the predecessor plan describes — the predecessor plan path).

**Three viable paths, in increasing fidelity to upstream:**

- **Path A — Predecessor plan as-is (manual Piper synthesis on Windows).** Synthesize positives by scripting the Piper *binary* (not the sample-generator package, which requires phonemize). Avoids the phonemize wheel issue. Trainer is the manual `training_models.ipynb` code, which can run on Windows because it's just feature extraction + a small classifier — no piper-phonemize dependency at training time. Loses upstream's RIR/background augmentation calibration; gets the predecessor plan's audiomentations augmentation back. Estimated 30–60 min CPU train per the predecessor plan, plausibly accurate.

- **Path B — Run the upstream pipeline inside WSL2.** Eric's machine has WSL2 (Ubuntu and Ubuntu-22.04 both installed per the system inventory). Inside WSL2: `pip install piper-sample-generator openwakeword[training]`, run `automatic_model_training.ipynb` end-to-end, copy the resulting `.onnx` back to the Windows side. ~1–2 hour wall-clock first run (more if CUDA passthrough is configured for the 4080; CPU works fine without). Highest-fidelity to upstream defaults; lowest false-positive risk in real use.

- **Path C — Cloud Colab.** The upstream automatic_model_training.ipynb has a Colab "Open in Colab" link. Free tier sometimes works but issue #110 + discussion #62 document repeated failures. Not recommended as a primary path; useful as a fallback if WSL2 setup hits a snag.

**Verifier model is the missing high-leverage feature in the predecessor plan.** A custom verifier model trained on ~50 recordings of Eric saying "Hey Sabrina" sits on top of the base model and substantially cuts false-accepts (per upstream `docs/custom_verifier_models.md`). The predecessor plan deliberately scoped this out as "out of MVP scope." With the predecessor plan's plain-base-model approach, the predecessor's "< 1 false-positive/hour" target is achievable but tight; with a verifier model layered on top, "< 1 false-positive/8 hours" is realistic. Recommendation flag: keep verifier-model as out-of-MVP for now (predecessor plan stands), but file a follow-up if the post-bake-in false-accept rate is unacceptable.

---

## Recommendation

**Actionable change with one nuance.**

The predecessor plan (`rebuild/drafts/wake-word-plan.md`) is fundamentally sound and should ship as the canonical implementation reference. It correctly identifies the runtime piece, the file layout, the test strategy, and the operational tuning loop. However, the predecessor plan's training-runs-on-Windows-CPU assumption is wrong against current upstream tooling and should be amended to **Path B (run upstream pipeline inside WSL2)** as the recommended training path, with **Path A (manual Piper-binary synthesis on Windows)** as the documented fallback if WSL2 setup is more friction than expected.

Concrete amendments to bring the predecessor plan in line with this research:

1. **`rebuild/drafts/wake-word-plan.md` §"The training pipeline" → §"Where to run training"** — add a subsection naming the three paths above, mark Path B as recommended, document the WSL2-vs-Windows decision boundary.
2. **Replace `tools/wake-training/synthesize_positives.py` (predecessor's hand-rolled multi-voice loop) with a wrapper around `piper-sample-generator`** — ~30 lines, calls `python -m piper_sample_generator` with the right flags. Path B uses this directly; Path A skips the wrapper and uses the Piper binary instead.
3. **Adopt QUEUE P2.2's path convention** (`sabrina-2/models/openwakeword/hey_sabrina.onnx`) over the predecessor plan's `voices/wake/hey_sabrina.onnx`. The runtime detector at `wake_word.py:104-116` doesn't care; it accepts either path verbatim from `sabrina.toml`.
4. **Add the verifier-model follow-up to "Not in this plan (later)"** — reframe it as "if the false-accept rate after first bake-in week is too high, add a verifier model trained on Eric's voice; ~50 recordings is sufficient."
5. **Tighten the upstream acceptance criteria reference** — predecessor plan's ship criterion is consistent with upstream's strict end (recall ≥ 0.5, FA ≤ 0.2/hour for the trainer, < 0.5/hour at production threshold). Cite upstream's published numbers for legibility.

After these amendments, the path forward is unblocked:

- **QUEUE P2.1 (this research item)** → satisfied by this document.
- **QUEUE P2.2 (train + package "Hey Sabrina")** → executable as a `[linux-runnable] [partial-dod-eligible]` Worker run inside WSL2 if a future Worker shift can spin up WSL2 from inside the Cowork sandbox. (See "Open follow-ups" — this is a Worker-harness question, not a project question.)
- **QUEUE P2.3 (Windows validation + flip enable)** → executable as a `[windows-required]` Eric session against §4's procedure.

**Go.** No further research grounding needed before P2.2 starts. The remaining gates are operational (run the pipeline) and engineering (ship the wrapper script + amend the plan), not bounded research questions.

---

## Open follow-ups

1. **Can a `[linux-runnable]` Worker actually run the upstream training pipeline inside the Cowork sandbox?** Cowork's Linux sandbox is Python 3.10 with allowlisted network. Does it allow `pip install openwakeword[training]` (~700 MB of torch + CUDA-less variants)? Does it allow downloading the bundled negatives/RIRs (multi-GB)? If not, P2.2 is structurally `[windows-required]` despite its current `[linux-runnable]` tag — Eric runs the WSL2 path himself. Worth confirming with a one-shot Worker probe before the planner schedules a P2.2 pull.
2. **WSL2 `[wake_word]` model handoff:** the trained `.onnx` lives inside the WSL2 filesystem after Path B; Eric copies it to `sabrina-2/models/openwakeword/`. Trivial — `cp /mnt/c/...` — but worth a one-line README.md note in `tools/wake-training/`.
3. **Verifier-model follow-up:** out of scope for this round. Keep on the radar for after P2.3 ships and bake-in surfaces a real FA rate. ~50 recordings of Eric saying "Hey Sabrina" + a mid-day session is the rough estimate.
4. **Decision doc voice for the wake-word ship.** Predecessor plan + this research + the trained model + the validation pass should fold into one decision doc at the next free `rebuild/decisions/0XX-` slot. This research file is not a decision doc; it's grounding. The decision-doc voice rule per CLAUDE.md still applies when the time comes.

---

## Sources

- [openWakeWord (dscripka/openWakeWord) — main repo + README](https://github.com/dscripka/openWakeWord)
- [openWakeWord — automatic_model_training.ipynb](https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)
- [openWakeWord — training_models.ipynb (manual lower-level path)](https://github.com/dscripka/openWakeWord/blob/main/notebooks/training_models.ipynb)
- [openWakeWord — docs/custom_verifier_models.md](https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md)
- [openWakeWord — Issue #110 (poor performance with automatic notebook)](https://github.com/dscripka/openWakeWord/issues/110)
- [openWakeWord — Discussion #45 (community training experience)](https://github.com/dscripka/openWakeWord/discussions/45)
- [openWakeWord — Discussion #62 (training failures at 75%)](https://github.com/dscripka/openWakeWord/discussions/62)
- [openWakeWord — Issue #204 (Ubuntu 24.04 WSL2 incompatibility)](https://github.com/dscripka/openWakeWord/issues/204)
- [openwakeword on PyPI](https://pypi.org/project/openwakeword/)
- [piper-sample-generator (rhasspy)](https://github.com/rhasspy/piper-sample-generator)
- [piper-sample-generator on PyPI](https://pypi.org/project/piper-sample-generator/)
- [Home Assistant — Wake words for Assist (end-user training pipeline doc)](https://www.home-assistant.io/voice_control/create_wake_word/)
- [lgpearson1771/openwakeword-trainer (third-party 13-step pipeline, "WSL2/Linux + CUDA required")](https://github.com/lgpearson1771/openwakeword-trainer)
- [sujitvasanth/openwakeword-simplified (single-file simplified fork)](https://github.com/sujitvasanth/openwakeword-simplified)
- [Evaluation of OpenWakeword Engine: False Reject Performance (Medium / Neural Engineer)](https://medium.com/neural-engineer/evaluation-of-openwakeword-engine-false-reject-performance-4d440ee8c4b4)
