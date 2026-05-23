# Wake-word training — "Hey Sabrina"

This directory holds the tooling that produces a custom `hey_sabrina.onnx`
openWakeWord model. The runtime detector at
`sabrina-2/src/sabrina/listener/wake_word.py` already accepts a path-shaped
model id; flipping `[wake_word].model` in `sabrina.toml` to point at the
trained artifact is the swap.

The **training run is Linux-only** (openWakeWord's training stack pulls
`piper-phonemize`, which lacks Windows wheels — see
`research/2026-05-05-wake-word-training-pipeline.md` § "Why WSL2"). Eric
runs the pipeline from his WSL2 / Ubuntu-22.04 install; the resulting
`.onnx` is committed back to the project as a binary artifact.

## Pipeline

Three commands, run from the repo root in WSL2:

```bash
# 1. Install the training-only dependencies into the project venv.
uv pip install -r sabrina-2/tools/wake-training/requirements-training.txt

# 2. Synthesize ~4000 positive samples ("Hey Sabrina") via piper-sample-generator.
#    Output lands in tools/wake-training/data/positive/ (gitignored).
python sabrina-2/tools/wake-training/synthesize_positives.py

# 3. Train the openWakeWord model. Output lands at
#    tools/wake-training/output/hey_sabrina.onnx (gitignored).
#    The script enforces upstream acceptance criteria
#    (recall >= 0.5, false-accepts <= 0.2/hour) and exits non-zero on failure.
python sabrina-2/tools/wake-training/train_hey_sabrina.py
```

To preview the synth command without running it:

```bash
python sabrina-2/tools/wake-training/synthesize_positives.py --dry-run
```

## Promoting the trained artifact

Once `train_hey_sabrina.py` completes successfully (acceptance check
passes), promote the artifact into the runtime model directory and
commit it as a separate atomic step:

```bash
mkdir -p sabrina-2/models/openwakeword
cp sabrina-2/tools/wake-training/output/hey_sabrina.onnx \
   sabrina-2/models/openwakeword/hey_sabrina.onnx
git add sabrina-2/models/openwakeword/hey_sabrina.onnx
git commit -m "feat(wake): promote hey_sabrina.onnx (queue: P2.2)"
```

`sabrina-2/models/openwakeword/hey_sabrina.onnx` is the only training
output that ships in git; the synth data, scratch, and pre-promotion
output are all gitignored.

The `[wake_word].model` field in `sabrina-2/sabrina.toml` already points
at `models/openwakeword/hey_sabrina.onnx`. Once the artifact is committed
the runtime detector will load it on the next start. `[wake_word].enabled`
stays `false` until the Windows validation gate (queue P2.3) passes.

## Validation gate (P2.3, Windows-only)

After the artifact is promoted, the next item is queue P2.3:

- Run `validate-wake-word.md` on the Windows daily-driver box.
- Confirm `sabrina wake-test --samples 5` reports peak score >= 0.7,
  5 / 5 triggers, fewer than one false-positive in a 10-minute background-
  conversation test.
- Flip `[wake_word].enabled = true` in `sabrina.toml`.
- File `rebuild/decisions/0XX-wake-word-shipped.md` in decision-doc voice.
- One real voice loop turn end-to-end: say "Hey Sabrina, what time is it"
  without PTT and confirm the turn fires.

## Out of scope

The following are deliberately not in P2.2 — file follow-ups if they
prove necessary:

- Custom verifier model (openWakeWord's
  `docs/custom_verifier_models.md`). Considered only if the base model's
  false-accept rate is unacceptable in real use.
- Eric's voice samples in the training set. Bundled-model training is
  100% TTS-synthesised per the research; recording Eric's voice is
  verifier-model territory.
- Outside-augmentation beyond what `piper-sample-generator` and
  openWakeWord's bundled augmentation already do. The research found
  outside-augmentation can hurt as much as help when the augmentation
  distribution drifts from the bundled negatives.
