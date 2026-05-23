# P2.2 — Wake-word build (train + package "Hey Sabrina") — spec

**Date:** 2026-05-06
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 2 → **P2.2 Wake-word — train + package "Hey Sabrina" custom model** (`[linux-runnable] [partial-dod-eligible] [P1] [L]`).
**Predecessor:** `rebuild/drafts/wake-word-plan.md` (2026-04-23, "ready-to-ship draft") + `research/2026-05-05-wake-word-training-pipeline.md` (researcher 2026-05-05, Recommendation = Go, recommends WSL2 + `piper-sample-generator`). The 2026-04-23 plan predates the rebuild's current scaffold and assumes a Windows-CPU training path that the 2026-05-05 research found is no longer viable (`piper-phonemize` lacks Windows wheels). **This spec narrows the queue entry to the *build* surface and supersedes the 2026-04-23 plan's `tools/wake-training/` proposal in favour of the WSL2 + `piper-sample-generator` flow the research recommends.**
**Scope:** mixed-surface — names the (a) Linux-runnable / (b) Windows-required boundary. Off-limits: legacy `services/`, `rebuild/decisions/`. The runtime detector (`listener/wake_word.py`) already shipped in pass 2 (2026-04-25) with the `hey_jarvis` placeholder; this spec only swaps the model, not the detector wiring.

---

## What this item is

The runtime detector and `[wake_word]` config block already live in `sabrina-2/src/sabrina/listener/wake_word.py` (270 lines, scaffolded 2026-04-25). Today the bundled placeholder model is `hey_jarvis` and `[wake_word] enabled = false` in `sabrina.toml`. P2.2 closes the gap by (1) producing a custom `hey_sabrina.onnx` from the WSL2 training pipeline the 2026-05-05 research grounds, (2) committing the model under `sabrina-2/models/openwakeword/hey_sabrina.onnx` (path called out by both the 2026-05-05 research and the QUEUE entry — supersedes the 2026-04-23 plan's `voices/wake/` proposal), (3) updating `[wake_word].model_path` to point at the new file but keeping `enabled = false` until P2.3's Windows validation flips it. The build's (a)-half — Linux-runnable — is everything except the actual training run, which Eric has to start in WSL2 because the script needs his microphone-room acoustics aren't relevant (per research: 100% TTS-synthesised) but the training requires Linux + ~15 GB scratch and finishes in ~30–60 min. The (b)-half — Windows-required — is the validation pass per `validate-wake-word.md` and the `enabled` flip; that already lives in QUEUE as P2.3 and this spec respects the existing P2.2/P2.3 boundary.

## Proposed approach

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**
  - `sabrina-2/tools/wake-training/synthesize_positives.py` (new, ~80 lines) — thin wrapper around `piper-sample-generator` per the 2026-05-05 research recommendation. Single `python -m piper_sample_generator 'Hey Sabrina' --max-samples 4000 --output-dir tools/wake-training/data/positive/` invocation plus a `--dry-run` flag that prints the command without running. **No hand-rolled `200 speakers × 3 prosody × 7 textual variants` loop** — that was the 2026-04-23 plan's approach and the research found `piper-sample-generator` consolidates that loop into a single tool call. The script's job is to wrap the tool with project-aware paths + a deterministic seed argument so retrains are reproducible.
  - `sabrina-2/tools/wake-training/train_hey_sabrina.py` (new, ~120 lines) — wrapper around openWakeWord's `automatic_model_training.ipynb` flow, callable as a script. Reads positives from `tools/wake-training/data/positive/`, points at the bundled openWakeWord negative-features path, writes `tools/wake-training/output/hey_sabrina.onnx`. Enforces upstream acceptance criteria (recall ≥ 0.5, false-accept ≤ 0.2/hour) before declaring success — fail-loud per the research's "issue #110 cautionary tale" finding. Exits non-zero if the trained model fails validation against the held-out test split.
  - `sabrina-2/tools/wake-training/README.md` (new, ~100 lines) — operator runbook. Verbatim WSL2 setup commands (Eric has Ubuntu + Ubuntu-22.04 already installed per `request_access` history); the three-command pipeline (`uv pip install -e .[training]`, `python tools/wake-training/synthesize_positives.py`, `python tools/wake-training/train_hey_sabrina.py`); the artifact promotion step (`cp tools/wake-training/output/hey_sabrina.onnx sabrina-2/models/openwakeword/hey_sabrina.onnx`); pointer to P2.3 for the Windows validation gate.
  - `sabrina-2/tools/wake-training/requirements-training.txt` (new, ~6 lines) — `openwakeword[training]>=0.6`, `piper-sample-generator`, `audiomentations>=0.36`, `soundfile>=0.12`. Training-only deps; not in the runtime wheel (`tools/` is already excluded from the hatch build target per the 2026-04-23 plan, confirmed by inspection).
  - `sabrina-2/.gitignore` — append `tools/wake-training/data/`, `tools/wake-training/scratch/`, `tools/wake-training/output/`. Synthesised positives + scratch + pre-promotion model are not committed; only the final promoted artifact at `sabrina-2/models/openwakeword/hey_sabrina.onnx` is.
  - `sabrina-2/tests/test_wake_training_tooling.py` (new, ~80 lines) — unit tests for the wrapper scripts: synthesize_positives's `--dry-run` prints the expected command; train_hey_sabrina raises a `RuntimeError` when the trained-model acceptance check fails (mock the `openwakeword.train` call to return a sub-threshold model); README path-references resolve. Does NOT actually train a model — that's an Eric-side WSL2 run. Tests run in ~0.1 s.
  - **Model file** — `sabrina-2/models/openwakeword/hey_sabrina.onnx` lands here only after Eric's WSL2 training run completes and the artifact is promoted. The (a)-half ships *the tooling*, not the model. The model commit is a separate atomic step Eric runs after training succeeds; it does not count as production-code change (binary artifact, ~200 KB per the lgpearson1771 trainer baseline the research cited).
  - `sabrina-2/sabrina.toml` — flip `[wake_word] model_path` from `"hey_jarvis"` (current bundled placeholder) to `"models/openwakeword/hey_sabrina.onnx"`. Keep `enabled = false`. **This is a Linux-runnable single-line edit** — it does not flip the runtime gate, and `wake_word.py:104-116` already accepts a path-shaped `model_id` per its existing scaffold.
- **(b)-half — `[windows-required]` (the existing P2.3 queue item; this spec does not pre-stage that item):**
  - Run `validate-wake-word.md` on Eric's i7-13700K/4080/Win11 box: `sabrina wake-test --samples 5` reports peak score ≥ 0.7, 5/5 triggers, < 1 false-positive in 10-min background-conversation test.
  - Flip `[wake_word] enabled = true` in `sabrina.toml`.
  - File `rebuild/decisions/0XX-wake-word-shipped.md` in decision-doc voice.
  - Voice loop end-to-end on Windows: say "Hey Sabrina, what time is it" without PTT and confirm the turn fires.
- **What's deliberately NOT in scope.**
  - Verifier model (`docs/custom_verifier_models.md`) — the 2026-05-05 research surfaces this as a follow-up if base-model false-accept rate is unacceptable, not as initial scope. Defer to a P2.2-follow-up if needed.
  - Eric's voice samples in the training set. Research found bundled-model training is 100% TTS-synthesised; recording Eric's voice is verifier-model territory.
  - GUI tab consolidation. The 2026-04-23 plan proposed a "Listen" tab merging PTT + wake-word controls; that's polish and orthogonal to the build. Defer.
  - `AudioMonitor` multi-consumer extension. The 2026-04-23 plan proposed extending `AudioMonitor` for multi-consumer dispatch; the 2026-04-25 scaffold already wires `wake_word.py` to its own audio-stream subscription, so this is moot. Confirmed by inspection of `wake_word.py:104-116`.
  - Custom training-data augmentation beyond what `piper-sample-generator` + openWakeWord's bundled augmentation already do. Research found outside-augmentation can hurt as much as help when the augmentation distribution drifts from the bundled negatives.

## Dependencies

- **`research/2026-05-05-wake-word-training-pipeline.md`** — canonical reference for the WSL2 + `piper-sample-generator` recommendation, the upstream acceptance criteria (recall ≥ 0.5, false-accept ≤ 0.2/hour), and the issue #110 / discussion #45 cautionary tales. The (a)-half wrappers cite this doc inline.
- **`sabrina-2/src/sabrina/listener/wake_word.py:104-116`** — runtime detector. Already accepts a path-shaped `model_id`; no changes needed. The model swap is `sabrina.toml`-only.
- **`sabrina-2/sabrina.toml` `[wake_word]` block** — single edit (`model_path`); `enabled = false` stays.
- **PROPOSED #32** (per STATE.md 2026-05-05) — "amend wake-word-plan to recommend WSL2." Worth checking for `[x]` before pulling P2.2; if approved, the 2026-04-23 wake-word-plan gets a header-note supersession. Not blocking — the spec already supersedes the plan in this file's header.
- **PROPOSED #33** — "sandbox-host probe before P2.2." Asks whether the Cowork Linux/3.10 sandbox can execute the training run (vs. Eric's WSL2 box). Per the research's "Did not check Eric's i7-13700K + RTX 4080 against current torch/CUDA matrix — out of bounded scope" + the issue #204 finding (Ubuntu 24.04 WSL2 incompatibility for some training paths), the sandbox-vs-WSL2 question is open. Spec routes around it: the (a)-half ships *the tooling*, not the model — so whichever environment ends up training is determined later. If Eric checks #33 and the sandbox-host probe shows training works in the Cowork sandbox, a future Worker run can do the training; otherwise it stays on Eric's WSL2.
- **CLAUDE.md "Partial-DoD tiers"** — defines the (a)/(b) seam. The (a)-half does NOT touch `voice_loop.py`, `events.py`, audio I/O, clipboard, mss/pynput/pyperclip paths, or pywin32-only modules.
- **`pyproject.toml`** — `openwakeword>=0.6` is already a runtime dep per the 2026-04-25 scaffold; no runtime dep additions needed.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. Five tooling files exist with the contents described above: `sabrina-2/tools/wake-training/{synthesize_positives.py,train_hey_sabrina.py,README.md,requirements-training.txt}` and `sabrina-2/tests/test_wake_training_tooling.py`.
2. `sabrina-2/.gitignore` extended with the three `tools/wake-training/{data,scratch,output}/` rules.
3. `sabrina-2/sabrina.toml` `[wake_word].model_path` flipped to `"models/openwakeword/hey_sabrina.onnx"`. `[wake_word].enabled` stays `false`.
4. `python -m compileall sabrina-2/tools sabrina-2/tests` clean. `python -m compileall sabrina-2/src` clean (no production-code change should affect this, but verify).
5. `python sabrina-2/tools/wake-training/synthesize_positives.py --dry-run` prints the expected `python -m piper_sample_generator …` command and exits 0.
6. `pytest sabrina-2/tests/test_wake_training_tooling.py -v` passes under Linux/3.10 (≥ 6 tests covering wrapper-script behaviour with mocked openwakeword/piper-sample-generator imports).
7. Pre-existing tests still pass: `pytest sabrina-2/tests/` shows no regression vs. the worker-11am 2026-05-05 baseline (4 ToolSpec round-trip tests + 6 (a)-half wire-up tests + 4 prior P5 ports + the existing wake-word scaffold tests in `test_smoke.py` if any).
8. Diff is committed to `automation/<role>-2026-05-MM-Nam` with `Windows-pending: e2e` in the body. Body lists the (b)-half checklist verbatim from the existing P2.3 queue entry. Item moves to `[linux-shipped]` in QUEUE/DONE; promotion to `[done]` is gated on Eric (i) running the WSL2 training, (ii) committing the resulting `hey_sabrina.onnx`, (iii) running P2.3.
9. **Non-bundled deliverable — Eric's WSL2 training run.** The (a)-half ships the tooling but not the trained artifact. After commit, Eric runs:
   ```bash
   # in WSL2 / Ubuntu-22.04
   cd <project>/sabrina-2
   uv pip install -r tools/wake-training/requirements-training.txt
   python tools/wake-training/synthesize_positives.py
   python tools/wake-training/train_hey_sabrina.py
   cp tools/wake-training/output/hey_sabrina.onnx models/openwakeword/hey_sabrina.onnx
   ```
   then commits `sabrina-2/models/openwakeword/hey_sabrina.onnx` as a separate atomic commit. The artifact-commit is the (a)-half's "completion" gate but is not Worker-runnable — Eric's WSL2 session does it.

**(b)-half DoD (Full DoD per CLAUDE.md, the existing P2.3 queue item — promotes the (a)-half to `[done]` when satisfied):**

See the QUEUE.md P2.3 entry verbatim. No additions from this spec.

## Open questions for NEEDS-INPUT

Two open questions worth raising before a Worker picks up the (a)-half. Filed today as `[from: spec-writer / 2026-05-06 06:50]` entries in NEEDS-INPUT.md.

- **Sandbox-vs-WSL2 training host (composes with PROPOSED #33).** Should the (a)-half attempt to make `train_hey_sabrina.py` runnable inside the Cowork Linux/3.10 sandbox (which would let a future Worker actually train the model), or strictly require WSL2 (which keeps the run on Eric's box and avoids the sandbox-CUDA-matrix question)? **Spec recommends "strictly WSL2"** — the research flagged the sandbox-host probe as out-of-scope, the training run produces a binary artifact Eric has to commit anyway, and a partial-success in the sandbox would muddy the audit trail. Worker can ship against "WSL2 only" without waiting; if Eric checks PROPOSED #33 and a sandbox-host probe later shows the sandbox can train, that's a follow-up to extend `train_hey_sabrina.py`.
- **Model-file commit policy.** Should `sabrina-2/models/openwakeword/hey_sabrina.onnx` be (a) committed to git directly (~200 KB binary, lives forever in history), (b) tracked via `git lfs` (overhead for one file is silly), or (c) downloaded on first run from a release artifact (introduces network dependency on first-boot — bad for daily-driver). **Spec recommends (a)** — small enough that direct commit is fine, matches the rebuild's pattern of committing trained `.onnx` artifacts (the existing ONNX embedder model lives in the same shape per the 008 refactor). Worker can ship without waiting; Eric can override before merge.

One non-blocking judgment call a Worker can decide in-line:

- **`tools/wake-training/` vs. `sabrina-2/tools/wake-training/`.** The 2026-04-23 plan put it at project-root `tools/`; the queue note implies `sabrina-2/`-relative. Spec picks `sabrina-2/tools/wake-training/` because everything-rebuild lives under `sabrina-2/` and the `tools/` exclusion from hatch build is already configured at that level. Worker can override; re-rooting is a `git mv` follow-up.
