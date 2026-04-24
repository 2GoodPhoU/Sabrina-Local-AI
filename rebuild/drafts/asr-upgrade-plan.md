# ASR upgrade plan — from faster-whisper base.en

**Date:** 2026-04-23
**Status:** Research + draft. Implementation blocked on two open
questions at the top. Research below resolved.
**Closes:** ROADMAP open question "Upgrade ASR to medium.en?" +
decision 006 thin-spots in the ASR section.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Target model: `large-v3-turbo` or `medium.en`?** Research points
   to `large-v3-turbo` as the best default (better than `medium.en` on
   most audio, only marginally slower on the 4080, and multilingual so
   the `language` config can be relaxed if Eric ever wants it). But
   `medium.en` is a safer, more conservative bump from `base.en` with
   less model-weights disk use. Pick one to default to; the other can
   remain reachable via config.

   **Recommendation: `large-v3-turbo` as the default, with the
   bake-off script gating the actual flip.** The 4080 is not the
   constraint (decision 001 has ~13 GB of VRAM unused after Ollama's
   `qwen2.5:14b`). Turbo's ~400 ms for a 3 s clip leaves ~1.6 s of
   budget before the existing 2 s first-audio target; it's cheap. And
   the plan already has a backstop — `sabrina asr-bench` runs on
   Eric's own mic/voice clips and the ship criterion ("≥30% WER
   reduction") empirically validates or overrides the pick. The
   multilingual-optionality side benefit is free. Override: if turbo
   bakes poorly on Eric's voice or VRAM pressure shows up, the fallback
   is `medium.en` — same code path, one TOML line.

2. **Streaming partials: in scope or deferred?** faster-whisper does
   not have a first-class streaming API; building one is real work
   (VAD-gated windowing + partial-hypothesis stitching). Alternative
   is WhisperLive or switching engine entirely to Moonshine (designed
   for streaming). Streaming partials would cut first-token latency
   ~200-400 ms by letting the brain start on a partial transcript. Is
   that worth a separate ~500-line component, or is the ASR upgrade
   strictly model-swap?

   **Recommendation: deferred. This plan is strictly model-swap +
   bake-off.** Two reasons. First, anti-sprawl: streaming is a ~500-
   line component that earns its own session + decision doc, not a
   rider on a one-line model flip. Second, the barge-in plan already
   ships a Silero VAD + `AudioMonitor` — streaming partials should be
   built on top of that VAD once it exists, not in parallel. Pulling
   streaming into this plan would mean building the VAD twice or
   blocking this plan on barge-in, neither of which is cheap.
   Override: if Eric wants streaming sooner, promote it to a
   standalone `asr-streaming-plan.md` that explicitly depends on
   `barge-in-plan.md`'s VAD landing first.

Everything below reflects the above recommendations.

---

## The one-liner

Swap the default faster-whisper model from `base.en` to a larger
variant, with a real bake-off script (`sabrina asr-bench`) that loops
a set of pre-recorded clips through every candidate and prints
WER + wall-time. Make the choice data-driven on Eric's mic + voice, not
from leaderboards. Same faster-whisper code path; one config line flip.

## Research — the five realistic candidates

Ranked by plausibility for Sabrina's use case.

### 1. `large-v3-turbo` — the strongest default

Released Oct 2024. Distilled/optimized successor to `large-v3`.
~1.6 GB. Multilingual. faster-whisper supports the model string
`large-v3-turbo` directly (CTranslate2 conversion is upstream).

- **Quality:** within 1-2% WER of full `large-v3` on clean English;
  significantly better than `base.en` on mumbled / accented / noisy
  speech.
- **Latency on RTX 4080:** ~350-500 ms for a 3 s clip at
  `compute_type=float16`, beam_size=1. Well under the 2 s total-turn
  budget.
- **VRAM:** ~2.5 GB. Coexists fine with Ollama's `qwen2.5:14b` (~9 GB
  at Q5) — plenty of headroom on 16 GB.
- **English-only boost:** none — it's multilingual. Offset by the
  model's raw quality. Optionally pass `language="en"` to skip
  auto-detect.

### 2. `medium.en` — the safe bump

~1.5 GB. English-only. faster-whisper native. Roughly in between
`base.en` and `large-v3-turbo`.

- **Quality:** better than base.en, worse than large-v3-turbo on hard
  audio. For clean, direct-to-mic speech at normal volume, the WER
  gap to turbo is small.
- **Latency:** ~400-600 ms for a 3 s clip on the 4080.
- **VRAM:** ~1.5 GB.
- **Why it's still in the picture:** less compute, proven stable
  across faster-whisper versions, zero risk.

### 3. Distil-Whisper large-v3 — 6× faster, 1% WER regression

Distilled from large-v3. ~750 MB. English-only (at the time of this
writing). faster-whisper supports it via a local CT2-converted model
directory; there's a community conversion on HuggingFace
(`distil-whisper/distil-large-v3` and its CT2 variant).

- **Quality:** per their paper, ~1% WER regression vs. the teacher on
  a typical benchmark. In practice, "mostly as good."
- **Latency:** ~200-300 ms for a 3 s clip on the 4080. The fastest
  serious option.
- **Why it's not the default:** requires manually downloading and
  pointing faster-whisper at a local directory; slight UX friction.
  Also, `large-v3-turbo` is the newer official story from OpenAI.

### 4. NVIDIA Parakeet-TDT (NeMo or parakeet-tdt-1.1b) — different lane

Non-Whisper architecture (CTC / TDT). ~1.1B params, fp16 ~2.2 GB.
Top of HuggingFace leaderboard for English. Requires NeMo or a
specific runtime; not a faster-whisper drop-in.

- **Quality:** arguably best-in-class for English on clean audio.
- **Latency:** blazing on GPU (sub-200 ms).
- **Why it's not the plan's default:** different runtime. Switching
  engines is a larger project than swapping Whisper sizes — worth a
  separate session if `large-v3-turbo` still feels slow.

### 5. Moonshine — only if we want streaming

Tiny (27M-190M params), onnxruntime-deployable, designed for streaming.

- **Quality:** between `tiny.en` and `base.en` on full clips —
  intentionally a quality drop for latency/battery.
- **Real value:** native streaming and tiny footprint.
- **Only relevant if open question 2 lands on "streaming in scope."**
  In that case, Moonshine replaces the ASR engine entirely for the
  real-time path, with faster-whisper as the fallback for recorded
  CLI-input (`sabrina asr <file.wav>`).

## The plan's recommendation

**Default: `large-v3-turbo`** (per Q1 recommendation above, subject to
bake-off validation on Eric's own clips).

Rationale:
- Quality headroom. Sabrina's failure mode today is occasional miss-
  transcription of names and mumbled words; turbo materially fixes that.
- 4080 headroom. ~400 ms is fine.
- Same faster-whisper code path. One line change in config; zero new
  deps; the existing `FasterWhisperConfig` handles it.
- Future-compatible with multilingual if Eric ever wants it (sets
  `language = ""` for auto-detect).

Fallback if turbo proves too slow or too unstable in Eric's testing:
`medium.en`. Same code path, smaller model.

## Scope

In:
- **Bake-off script** `sabrina asr-bench`: loops a folder of WAV clips
  through a configurable list of candidate models; prints wall time +
  WER (against a `.txt` transcript alongside each WAV). One manifest
  file (`tests/asr-bench/README.md`) documents how to collect clips.
- **Config default flip:** `asr.faster_whisper.model` changes from
  `base.en` to `large-v3-turbo` (per Q1 recommendation; flip guarded
  by bake-off result).
- **Pre-download CLI:** `sabrina asr-download <model>` pre-pulls the
  model into the CT2 cache so first `sabrina voice` isn't delayed by
  a 1.5 GB download.
- Docstring updates in `sabrina.toml` reflecting the new default +
  cold-download size.
- Tests: `asr-bench` argument parsing + CSV output shape.

Out:
- Streaming partials — deferred to a separate plan per Q2
  recommendation (depends on barge-in's VAD landing first).
- Engine switch (Parakeet, Moonshine).
- Voice activity detection (Silero) for recording — that's in the
  barge-in plan.

## Files to touch

```
sabrina-2/src/sabrina/
├── listener/
│   └── bench.py                  # NEW, ~100 lines — the bake-off loop
├── cli.py / cli/asr.py           # +asr-bench, +asr-download verbs
└── config.py                     # no schema change; just docstring
sabrina-2/
├── sabrina.toml                  # default flip + comment update
├── tests/asr-bench/              # NEW — sample manifest
│   └── README.md                 # how to record and label clips
└── tests/test_smoke.py           # +asr-bench output shape test
```

No new runtime deps. `faster-whisper>=1.0` already ships
`large-v3-turbo` support.

## Protocol / API changes

None. `Listener.transcribe` stays the same.

## Config changes

```toml
[asr.faster_whisper]
# Previously: base.en (~140 MB).
# New default: large-v3-turbo (~1.6 GB). First run downloads to the
# HF cache (~/.cache/huggingface/hub on Windows: %USERPROFILE%\.cache\...).
# Alternatives (change here and re-run `sabrina asr-download <name>`):
#   base.en        fast, mumble-prone        ~140 MB
#   medium.en      conservative upgrade      ~1.5 GB
#   large-v3-turbo recommended               ~1.6 GB
#   large-v3       best quality, slowest     ~2.9 GB
model = "large-v3-turbo"
```

Every other knob in `[asr.faster_whisper]` stays as-is.

## `sabrina asr-bench` sketch

```python
# listener/bench.py
@dataclass
class BenchResult:
    model: str
    clip: str
    wall_ms: float
    hypothesis: str
    reference: str
    wer: float

async def run_bench(clip_dir: Path, models: list[str],
                    device: str = "auto",
                    compute_type: str = "float16") -> list[BenchResult]:
    results = []
    for model_name in models:
        listener = FasterWhisperListener(
            model=model_name, device=device, compute_type=compute_type,
        )
        for wav_path in sorted(clip_dir.glob("*.wav")):
            ref_path = wav_path.with_suffix(".txt")
            if not ref_path.is_file():
                continue
            reference = ref_path.read_text("utf-8").strip()
            audio, _sr = sf.read(str(wav_path), dtype="float32")
            t0 = time.monotonic()
            tr = await listener.transcribe(audio)
            wall_ms = (time.monotonic() - t0) * 1000
            wer = _word_error_rate(reference, tr.text)
            results.append(BenchResult(
                model=model_name, clip=wav_path.name,
                wall_ms=wall_ms, hypothesis=tr.text,
                reference=reference, wer=wer,
            ))
    return results
```

`_word_error_rate` is a 20-line implementation (Levenshtein over
whitespace-tokenized strings); no new dep. Output prints a table and
optionally writes `tests/asr-bench/results-<date>.csv` for diffing.

The CLI surface:

```
sabrina asr-bench                               # uses defaults
sabrina asr-bench --models base.en,medium.en,large-v3-turbo
sabrina asr-bench --clips tests/asr-bench/my-clips/
sabrina asr-bench --csv out.csv
```

## Collecting bake-off clips

Documented in `tests/asr-bench/README.md`:

- Record 10 short clips (2-8 s) that cover Eric's realistic voice
  usage: direct address, a mumble, a query with a proper noun, a
  code/technical phrase, a low-volume "nudge"-style phrase, etc.
- Label each: `clip-01.wav` + `clip-01.txt` with the expected
  transcript.
- Commit them under `tests/asr-bench/eric/` if privacy is fine; or
  keep them local and `.gitignore` the dir.

Time cost to collect: ~15 minutes. Keeps the bake-off honest to Eric's
voice, not to some unknown LibriSpeech speaker.

## Expected results

Predicted (WER on Eric's clips, based on research):

| Model | WER | Wall (3 s clip on 4080) |
|---|---|---|
| `base.en` | ~10-15% | 100 ms |
| `medium.en` | ~6-9% | 500 ms |
| `large-v3-turbo` | ~4-6% | 400 ms |
| `distil-large-v3` | ~5-7% | 250 ms |

If the bake-off disagrees with the prediction, trust the bake-off. That's
the whole point.

## Test strategy

Unit tests only — integration tests use pre-recorded clips and are
considered "manual smoke" since they require data on disk:

- `test_wer_basic` — "hello world" vs "hello worlde" → 1/2 = 0.5.
- `test_wer_identical_is_zero` — obvious.
- `test_wer_empty_reference_handling` — returns 1.0 if hypothesis
  non-empty, 0 if both empty.
- `test_bench_skips_clips_without_reference` — a `.wav` without a
  `.txt` sibling is dropped, not errored on.
- `test_bench_returns_one_row_per_clip_per_model` — matrix shape.

Manual smoke:
- `sabrina asr-download large-v3-turbo` completes.
- `sabrina asr-bench --models base.en,large-v3-turbo` prints a table
  with at least one row per model.
- `sabrina voice` with the new default model works end-to-end, with
  first-audio latency still under 2 s (turbo ≈ +200 ms vs. base.en
  stays well under 2 s because the total turn is already ~1.85 s and
  most of that is the brain).

## Dependencies to add

None. `faster-whisper>=1.0` and `soundfile>=0.12` are both in
pyproject.

## Windows-specific concerns

- HuggingFace cache location: `%USERPROFILE%\.cache\huggingface\hub`
  (forward-slash path works under Python; no special handling).
- First `sabrina voice` after the swap will take 2-3 s extra for model
  load — the warmup path in `run_voice_loop` pre-loads, so by the time
  the user hits PTT, it's ready. Document this in the validation
  procedure.
- CTranslate2's CUDA path needs a matching CUDA runtime installed (the
  faster-whisper wheels bundle CTranslate2 binaries for CUDA 12 on
  Windows). Eric's box has driver 591.86 which supports CUDA 12. No
  action needed.

## Ship criterion

- `sabrina asr-bench` runs cleanly against the committed fixture clips.
- For Eric's own clips, the chosen new model shows a ≥30% relative
  WER reduction vs. `base.en`. If not, either the fallback (`medium.en`)
  or staying on `base.en` is the outcome — this is the one plan where
  the data could override the plan.
- `sabrina voice` end-to-end latency budget held (first-audio ≤ 2.2 s
  warm after the swap, vs. 1.85 s before; +350 ms budget).

## Not in this plan (later)

- Streaming partials — deferred per Q2 recommendation; own plan.
- Parakeet-TDT engine swap.
- Distil-Whisper as a first-class option (add the CT2-converted local
  dir pattern to the config if Eric's bake-off shows it wins).
- VAD-driven capture (ships with barge-in's `AudioMonitor`).
- Per-call model override (`--asr-model` on `sabrina voice` already
  exists; no change needed).
