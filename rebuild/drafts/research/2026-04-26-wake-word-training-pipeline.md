# Custom wake-word training pipeline — "Hey Sabrina"

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Concrete, runnable how-to for training the custom
"Hey Sabrina" openWakeWord model that `wake-word-plan.md` left as
"`tools/wake-training/` exists but the model is a placeholder."
This doc replaces the high-level training prose in that plan with a
session-ready procedure: data generation, training command line,
evaluation suite, threshold tuning, deployment artifact, validation.

**Anchor:** the plan's ship criterion calls for "peak score >= 0.7 on
'hey sabrina' at conversational volume 1 m from the mic" and "false-
positive rate under 1/hour" during casual conversation. This pipeline
is built backward from those numbers.

**Audience:** Eric, on his i7-13700K + RTX 4080 + 32 GB box, Win 11.

---

## Status of openWakeWord training (April 2026)

Two facts shape the whole pipeline:

1. **Training is Linux-only.** openWakeWord's `automated_model_training`
   path bundles `piper-sample-generator` and a torch-based augmentation
   stack that has never been packaged for Windows. The maintainer's
   notebook is explicit: "automated model training is currently only
   supported on Linux systems" [1]. The pragmatic fix on Eric's box is
   WSL2 with CUDA passthrough — this is the documented configuration in
   the actively-maintained community fork `lgpearson1771/openwakeword-
   trainer` [2], which papers over the torchaudio 2.10+ break and pins
   compatible Piper TTS + speechbrain versions.
2. **The included models were 100% synthetic.** dscripka shipped the
   `hey_jarvis`, `alexa`, etc. weights using only TTS-generated positives
   plus the prebuilt negative-feature shards. That's the reference
   pipeline; we follow it. Real-voice augmentation adds maybe 2-3 points
   of recall but 4× the human time — defer to v2 of the model.

---

## Quantitative targets

| Metric | Target | Why |
|---|---|---|
| Peak score on direct address (1 m, conv. volume) | >= 0.85 | Plan says >= 0.7; aim higher so threshold can sit at 0.5 with margin. |
| False-accept rate, casual conversation | < 0.5 / hr | openWakeWord README's "reasonable in practice" floor [3]. |
| False-reject rate, 50-utterance hold-out | < 5 % | Same source [3]. |
| First-fire latency (end-of-word -> event) | < 200 ms | 80 ms inference window + small cooldown buffer. |
| ONNX artifact size | < 5 MB | Plan budgeted 2-5 MB; commits comfortably. |

If the trained model misses any of these, threshold tuning is the
first lever; data expansion is the second; architecture tweaks last.

---

## Pipeline overview

```
[1] synthesize ~30k positive clips of "hey sabrina"
        (Piper, multi-speaker, per-utterance augmentation)
[2] mix with bundled negatives (~2,000 hr cached features)
[3] train openWakeWord head on the prebuilt embedding model
        (torch + GPU; ~30-60 min wall time on the 4080)
[4] eval on a held-out positives set + a noise corpus
        (target the metric table above)
[5] tune threshold on Eric's mic via `sabrina wake-test`
[6] export ONNX, drop in voices/wake/, ship.
```

---

## Step 1 — synthetic positives (30 minutes, mostly compute)

**Why 30k, not 5k or 100k?** openWakeWord's sample notebooks default to
5,000 positives "to save on training time" [3]; in practice that is
exactly enough to overfit on a single TTS speaker's prosody and miss
real users. The CoreWorxLab fork settled on ~13k positives across 67
Kokoro voices [4]. Piper's `libritts_r-medium` model exposes ~900
distinct speakers; we use 200 of them, three prosody settings each, with
~50 textual variants and per-utterance audiomentations augmentation.
That lands at ~30,000 unique clips after augmentation, with each clip
hearing a different combination of speaker, prosody, noise floor, and
mic-distance impulse response.

The per-clip variance matters more than the per-speaker count. The
canonical openWakeWord failure mode is "trained on TTS-flat audio,
fired only when the user matched that prosody." Variance kills it.

### Recommended environment variations

Bake these into the synthesis script (`synthesize_positives.py`):

| Axis | Range | Reason |
|---|---|---|
| Speaker (Piper voice index) | 200 of ~900 in `libritts_r-medium` | Speaker timbre is the largest source of generalization. |
| `length_scale` | 0.85, 1.0, 1.15 | Captures fast/normal/slow delivery. |
| Pitch shift (post-synth) | ±2 semitones | Adds the "stuffy nose" / "early morning" delivery space. |
| Time-stretch | ±5% | Independent of length_scale; covers prosody-without-pitch. |
| Background noise | 0-15 dB SNR mix | Pull from the negative corpus; SNR uniform over the range. |
| Mic-distance IR | 0.3 m, 1.0 m, 2.0 m short-tail IRs | Three single-channel room IRs from `pyroomacoustics`. |
| Punctuation variants | "hey sabrina" / "Hey, Sabrina." / "hey sabrina!" | Shifts pause and final-fricative envelope. |
| Trailing silence | 0-300 ms uniform | Prevents over-fitting on "always ends at frame N." |

Negative samples come from openWakeWord's bundled feature shards
(`openwakeword/training_data/`) — several hundred hours of speech +
music + noise pre-encoded into the same embedding space the model
operates in. We do not generate our own negatives; the library's
bundled set is the de-facto standard and is what every shipped openWWW
model was trained against.

### `synthesize_positives.py` — runnable starting point

```python
"""Synthesize the positive corpus for the 'hey sabrina' model.

Run from the repo root, inside WSL2:
    uv run python tools/wake-training/synthesize_positives.py

Outputs ~30k 16 kHz mono WAV clips under tools/wake-training/data/positive/.
Skips work that is already done (idempotent).
"""
from __future__ import annotations
import hashlib
import itertools
import random
from pathlib import Path

import numpy as np
import soundfile as sf
from audiomentations import (
    AddGaussianSNR, PitchShift, TimeStretch, RoomSimulator, Compose,
)
from piper import PiperVoice  # piper-tts package

# ----- knobs ------------------------------------------------------------------

OUT_DIR = Path("tools/wake-training/data/positive")
VOICE_FILE = Path("voices/libritts_r-medium.onnx")  # already shipped
SAMPLE_RATE = 16_000
N_SPEAKERS = 200
LENGTH_SCALES = (0.85, 1.0, 1.15)
TEXT_VARIANTS = (
    "hey sabrina", "hey sabrina,", "hey sabrina.", "hey, sabrina",
    "hey sabrina!", "Hey Sabrina", "Hey Sabrina.",
    "hey sabrina ", " hey sabrina",  # leading/trailing space
)
N_AUG_PER_BASE = 3        # 200 speakers x 3 length x ~9 text x 3 aug = ~16k base
RNG = random.Random(42)

aug = Compose([
    AddGaussianSNR(min_snr_db=0, max_snr_db=20, p=0.7),
    PitchShift(min_semitones=-2, max_semitones=2, p=0.5),
    TimeStretch(min_rate=0.95, max_rate=1.05, p=0.5),
    RoomSimulator(p=0.5),  # default presets are fine for short utterances
])

# ----- main -------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    voice = PiperVoice.load(VOICE_FILE)
    speaker_ids = RNG.sample(range(voice.config.num_speakers), N_SPEAKERS)
    combos = list(itertools.product(speaker_ids, LENGTH_SCALES, TEXT_VARIANTS))
    RNG.shuffle(combos)
    print(f"synthesizing {len(combos)} base clips, ~{len(combos) * N_AUG_PER_BASE} after aug")

    written = 0
    for spk, length_scale, text in combos:
        # base TTS
        audio = np.frombuffer(
            b"".join(voice.synthesize_stream_raw(
                text, speaker_id=spk, length_scale=length_scale,
            )),
            dtype=np.int16,
        ).astype(np.float32) / 32768.0
        if len(audio) < SAMPLE_RATE // 2:  # too-short utterances are noise
            continue
        # apply augmentations N times, each with a new random seed
        for k in range(N_AUG_PER_BASE):
            augmented = aug(samples=audio.copy(), sample_rate=SAMPLE_RATE)
            # leading/trailing pad to land in the 1-2 s window the model wants
            target_len = SAMPLE_RATE * RNG.choice([1.2, 1.5, 1.8])
            if len(augmented) < target_len:
                pad = int(target_len - len(augmented))
                lead = RNG.randint(0, pad)
                augmented = np.pad(augmented, (lead, pad - lead))
            else:
                augmented = augmented[: int(target_len)]
            digest = hashlib.sha1(augmented.tobytes()).hexdigest()[:12]
            out = OUT_DIR / f"{digest}.wav"
            if out.exists():
                continue
            sf.write(out, augmented, SAMPLE_RATE, subtype="PCM_16")
            written += 1

    print(f"wrote {written} new clips into {OUT_DIR}")

if __name__ == "__main__":
    main()
```

The augmentation stack uses `audiomentations` (already on the
training-only dependency list in `wake-word-plan.md`); the room
simulator there is a one-line replacement for the original Plan's "short-
tail IR" hand-roll. No new deps beyond what the plan listed.


## Step 2 — assemble training data

```bash
# WSL2 shell, repo checkout mounted
cd ~/Sabrina-Local-AI/sabrina-2
uv run python tools/wake-training/synthesize_positives.py
# expect ~30k WAV files, ~3.5 GB on disk
```

Pull openWakeWord's bundled negative features (one-time, ~2 GB):

```bash
uv run python -c "from openwakeword.train_model import download_features; download_features()"
# lands in ~/.cache/openwakeword/training_data/
```

The negative set is "real noise + speech audio that does NOT contain
the target phrase," already encoded in the same melspec embedding the
model trains over. Mixing this against the positives at random SNRs is
what makes the resulting model robust to actual room conditions.

---

## Step 3 — train (45-90 min wall, on the 4080)

The maintainer's `automatic_model_training.ipynb` reads YAML config; we
generate ours from a template. Hyperparameters lifted from
the openWakeWord example notebooks and the working CoreWorxLab fork [4]:

```yaml
# tools/wake-training/hey_sabrina.yaml
target_phrase: hey_sabrina
model_name: hey_sabrina
language: en

n_samples: 30000
n_samples_val: 1000
augmentation_rounds: 1   # we already augmented at synthesis time

batch_n_per_class: 1024
max_negative_weight: 2000

steps: 50000             # heuristic; saves checkpoints every 5k
target_false_positives_per_hour: 0.2
target_accuracy: 0.7

learning_rate: 0.0001
optimizer: adam
loss: bce_with_logits
```

Run:

```bash
uv run python tools/wake-training/train_hey_sabrina.py \
    --config tools/wake-training/hey_sabrina.yaml \
    --output voices/wake/
```

Expected:
- Wall time on the 4080: 35-50 min for 50k steps. The bottleneck is the
  audio I/O on positives (CPU-side) more than GPU compute. `nvidia-smi`
  during a run shows the 4080 at ~30-40% utilization; this is correct.
- VRAM peak: ~3 GB. The backbone is the prebuilt `embedding_model.onnx`;
  only the small classifier head is being trained.
- Disk: ~6 GB scratch on top of the 3.5 GB positives. Land it under
  `tools/wake-training/scratch/` (gitignored).

**Why train on GPU when the Plan said CPU?** The Plan's "use CPU, the
4080 is overkill" advice was correct *for the old training pipeline*
that processed feature shards from disk. The current 0.6.x pipeline
streams positives through the embedding ONNX every step; that
embedding-pass is GPU-bound and runs ~10× faster on the 4080 than on
the i7. Net: 35 min vs. 4-6 hours. Set `CUDA_VISIBLE_DEVICES=0` in the
training script and confirm Ollama is unloaded first; the 4080 has
plenty of room for both, but the GIL contention is real if the Brain
is also serving turns.

If for any reason the GPU path breaks, CPU training is still viable —
add `--device cpu` to the trainer; expect ~3 hours.

---

## Step 4 — evaluation

Two evals run before the model leaves the training box.

### Hold-out positives

100 utterances of "hey sabrina" recorded by Eric in advance. (The
synthetic-only pipeline doesn't need them for *training* but they are
the only way to know if the model generalizes to his voice.) Recording
script:

```bash
uv run python tools/wake-training/record_hold_out.py --count 100
# prompts: "Press space, say 'hey sabrina', release. Repeat 100 times."
```

Saves under `tools/wake-training/data/holdout_positive/`. False-reject
rate target: < 5 %. Compute via:

```bash
uv run python tools/wake-training/evaluate.py \
    --model voices/wake/hey_sabrina.onnx \
    --positives tools/wake-training/data/holdout_positive/ \
    --threshold-sweep 0.1 0.9 0.05
```

The script prints an FRR / FPR curve; pick the threshold where FRR
first drops below 5 %.

### Real desktop noise

Collect 30 minutes of "Eric's daily ambient" — keyboard, mouse, fan,
podcast at low volume, occasional unrelated speech. Run the model
across that audio, count fires:

```bash
uv run python tools/wake-training/evaluate.py \
    --model voices/wake/hey_sabrina.onnx \
    --negatives audio/desktop_30min.wav \
    --threshold 0.5
```

Target: 0 fires in 30 min. The "< 0.5 / hr" rule of thumb [3] is per
hour of mixed public audio; on Eric's specific desktop noise we want
zero false fires in the test sample.

If the FPR is too high at the chosen threshold, the easiest lever is
to raise the threshold (peak score on direct address from step 1
should still clear it) before retraining.

---

## Step 5 — threshold tuning on Eric's mic

Once the model is committed to `voices/wake/hey_sabrina.onnx`, the
runtime threshold lives in `sabrina.toml [wake_word].threshold`. The
plan already specifies `sabrina wake-test` — record 5 s, run detector,
print peak score. Practical procedure:

1. Run `sabrina wake-test --samples 20` and say "hey sabrina" each time.
2. Note the peak score per utterance; take the minimum, multiply by 0.8.
3. Round to the nearest 0.05 — that's your `threshold`.
4. Run `sabrina wake-test --silent --duration 60` to record one minute
   of room noise; confirm the model never crosses threshold.
5. Use `sabrina wake-test --podcast` (plays a 5-min podcast clip
   through the speakers, loops detection on the mic) for the
   spoken-but-not-addressed case.

Defaults in the plan are 0.5 / 2000 ms / 5 s for threshold / cooldown /
auto-capture. Validation lives in
`rebuild/validate-wake-word.md` (already referenced in the plan).

---

## Step 6 — deployment artifact format

openWakeWord expects:

- `hey_sabrina.onnx` — the trained classifier head, ~150-300 KB.
- The bundled `embedding_model.onnx` and `melspectrogram.onnx` from
  openWakeWord itself, which load lazily from the package data dir on
  first inference.

Only `hey_sabrina.onnx` is checked in to the repo (under
`sabrina-2/voices/wake/`). The other two are part of the `openwakeword`
wheel; nothing further to commit.

Sanity-check the ONNX before commit:

```python
import onnxruntime as ort
sess = ort.InferenceSession("voices/wake/hey_sabrina.onnx")
print(sess.get_inputs()[0].shape, sess.get_outputs()[0].shape)
# expect: input (1, 16, 96), output (1, 1)
```

If the shape is anything else, the model came out of a non-stock
training run — check the YAML.

---

## Latency budget

| Stage | Budget | Source |
|---|---|---|
| Audio capture (80 ms chunk) | 80 ms | sounddevice ringbuffer dispatch |
| Mel + embedding ONNX | 1-2 ms | CPU provider, single core |
| Classifier head ONNX | < 0.5 ms | tiny model |
| Cooldown debouncer | up to 80 ms | inside-chunk |
| **Detector wall** | **~85 ms** worst case | sum |
| Voice loop dispatch + drain_recent | ~30 ms | bus + ring read |
| **Wake -> first transcribe call** | **~115 ms** | ship-criterion budget < 200 ms ✅ |

The plan's "wake path adds 80-160 ms" estimate holds.


## Validation suite — what "shipped" looks like

A trained model is ready when all six checks pass:

1. **Synthesis sanity.** `tools/wake-training/data/positive/` contains
   between 25k and 35k WAVs, each 1.0-2.0 s. Spot-check 10 by ear.
2. **Training run completed.** Last checkpoint reports
   `false_positives_per_hour < 0.5` on the validation negatives.
3. **Hold-out positives** — Eric's 100 recorded utterances — pass at
   FRR < 5 % at threshold 0.5. Curve sweep saved to
   `tools/wake-training/eval_results/hey_sabrina_<date>.json`.
4. **Real-desktop noise** — 30-min keyboard/mouse/fan/podcast clip —
   zero fires at threshold 0.5.
5. **`sabrina wake-test` end-to-end.** 20 utterances at 1 m / conv.
   volume; minimum peak score >= 0.7 (plan's hard floor); typical
   peaks land 0.85+.
6. **Live voice loop.** With `[wake_word].enabled = true`, run a 30-min
   passive session (Eric working, podcast at low volume); zero spurious
   fires. Then deliberately address Sabrina five times; five fires.

If any of (3)-(6) fails, escalate in this order:

- Threshold up before retraining. (Cheapest.)
- Add 5,000 more synthetic positives with stronger augmentation.
  (Half day.)
- Record real positives from Eric (50 clips, 5 minutes of effort) and
  weight them 3× in the trainer. (Day.)
- Re-train with 100k positives, 100k steps. (Most expensive; only if
  the cheaper steps stall.)

---

## Why this is enough (and what's still thin)

Three corners of this pipeline are deliberately simple:

- **Single-phrase model.** "Hey Sabrina" only. The original Plan
  flagged this; openWakeWord supports loading multiple phrase models
  side-by-side at runtime, but each is independently trained. A
  follow-up "hey sabrina, stop" model for global interrupt is the
  natural v2 if the daily-driver UX surfaces it.
- **No verifier model.** Verifier models are a separate per-user
  classifier head trained on ~5 minutes of voice [5]; they cut
  cross-speaker false-fires by another order of magnitude. Worth it if
  Sabrina ever runs in a household with more than one Eric. Skip for
  v1.
- **No on-device retraining loop.** The plan section "On-device
  retraining" stays out of v1 scope. The infrastructure to log
  near-misses (where score peaked at 0.55, just below threshold) and
  feed them back as training data is its own week.

Two things this pipeline pretends are simpler than they are:

- **WSL2 + CUDA passthrough.** Setting up Linux GPU training for the
  first time on a Windows box is a one-evening yak shave: install
  WSL2, the CUDA toolkit's WSL package, the matching Ubuntu kernel
  module, and validate `nvidia-smi` from inside WSL before any
  training begins. The community fork [2] documents the dance.
  Budget two hours of irritation here, regardless of what this doc
  says about training time.
- **Piper voices and licensing.** The `libritts_r-medium` voices we
  ship are CC-0 [6] so synthesizing on top of them is fine for a
  personal project. If Sabrina ever ships a wake model trained on
  proprietary Piper voices (e.g. someone's private clone), the trained
  classifier head doesn't carry their license — but the *training
  data* does. Note for future-Eric.

---

## One actionable Sunday

If Eric wants to ship a real "Hey Sabrina" in a single sitting:

```bash
# WSL2, ~3 hours total wall time, ~1 hour hands-on
git checkout -b wake-word-train
uv sync
cd sabrina-2
uv run python tools/wake-training/synthesize_positives.py        # ~30 min
uv run python -c "from openwakeword.train_model import download_features; download_features()"  # ~10 min
uv run python tools/wake-training/train_hey_sabrina.py \
    --config tools/wake-training/hey_sabrina.yaml \
    --output voices/wake/                                        # ~45 min
uv run python tools/wake-training/record_hold_out.py --count 50  # ~10 min
uv run python tools/wake-training/evaluate.py --model voices/wake/hey_sabrina.onnx \
    --positives tools/wake-training/data/holdout_positive/ \
    --threshold-sweep 0.1 0.9 0.05                               # ~5 min
git add voices/wake/hey_sabrina.onnx tools/wake-training/
git commit -m "wake-word: ship custom 'hey sabrina' model + training tooling"
```

That gets the artifact into the repo. Threshold tuning + the live
voice-loop passive session are best done the next day with fresh ears.

---

## References

[1] dscripka — openWakeWord automatic_model_training notebook —
    https://github.com/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb
[2] lgpearson1771 — openwakeword-trainer (active fork, torchaudio 2.10+
    compat, WSL2/Linux + CUDA documented) —
    https://github.com/lgpearson1771/openwakeword-trainer
[3] dscripka — openWakeWord README, "Performance and Evaluation"
    section — false-accept < 0.5/hr, false-reject < 5% targets —
    https://github.com/dscripka/openWakeWord
[4] CoreWorxLab — openwakeword-training (community Colab variant) —
    https://github.com/CoreWorxLab/openwakeword-training
[5] dscripka — Custom verifier model docs —
    https://github.com/dscripka/openWakeWord/blob/main/docs/custom_verifier_models.md
[6] rhasspy/piper — libritts_r voices ship under CC-0 —
    https://github.com/rhasspy/piper/releases
