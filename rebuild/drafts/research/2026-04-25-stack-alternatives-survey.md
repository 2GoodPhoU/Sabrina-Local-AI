# Stack alternatives survey — April 2026

**Date:** 2026-04-25 (overnight research, no code touched)
**Scope:** ten subsystems across Sabrina's current daily-driver stack.
For each: what we run today, what else exists in May 2026, how it
scores against the dimensions that actually matter for this project,
and a keep / switch / watch verdict.

**Anchor:** versions and rationale come from `sabrina-2/pyproject.toml`
+ `sabrina-2/sabrina.toml` + decision logs 001–009. Everything else is
cited inline. No code or planning docs were modified.

---

## 1. TTS — Piper

**Current:** Piper (`piper-tts`) with `libritts_r-medium` model, speaker 0,
length_scale 1.0, plus a Windows SAPI fallback. Decision 002 picked Piper
for being one of the fastest and most efficient open-source TTS systems
that runs locally even on tiny boxes ([Piper releases](https://github.com/rhasspy/piper/releases),
[piper-tts on PyPI](https://pypi.org/project/piper-tts/)). The
`rhasspy/piper` repo is now in maintenance/redirect mode; primary
development moved to [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)
and v1.3.0 changed the license from MIT to GPL-3.0
([piper1-gpl release v1.3.0](https://github.com/OHF-Voice/piper1-gpl/releases/tag/v1.3.0)).
1.4.x has shipped through April 2026; the project is alive but the
Open Home Foundation is actively soliciting maintainers.

**Alternatives in May 2026:**

- **Kokoro-82M.** Apache-2.0 weights, ~82M params. Bare-metal install
  on Windows is `pip install kokoro soundfile` plus an espeak-ng MSI.
  Reported RTF ~0.04–0.06 on RTX 4090 / sub-300ms on small chunks; TTFA
  ~100ms in cloud-server contexts. ([Kokoro local guide](https://aleksandarhaber.com/kokoro-82m-install-and-run-locally-fast-small-and-free-text-to-speech-tts-ai-model-kokoro-82m/),
  [BentoML 2026 TTS roundup](https://www.bentoml.com/blog/exploring-the-world-of-open-source-text-to-speech-models)).
  Naturalness is rated above Piper but below F5-TTS/XTTS in 2026
  comparative writeups.
- **F5-TTS.** Code MIT, **weights CC-BY-NC** ([SWivid/F5-TTS LICENSE](https://github.com/SWivid/F5-TTS/blob/main/LICENSE)).
  Zero-shot voice cloning from ~10s reference; RTF ~0.15. Best-in-class
  naturalness in current zero-shot evaluations
  ([Uberduck writeup](https://www.uberduck.ai/post/f5-tts-is-the-most-realistic-open-source-zero-shot-text-to-speech-so-far)).
  The CC-BY-NC weights mean a personal-use Sabrina is fine; commercial
  is not.
- **Coqui XTTS-v2 (Idiap fork).** Coqui AI shut down December 2025;
  [`idiap/coqui-ai-TTS`](https://github.com/idiap/coqui-ai-TTS) and the
  `coqui-tts` PyPI package took over. v0.24+ ships prebuilt Windows
  wheels. XTTS-v2 model is on a Coqui non-commercial public license,
  17 languages, 6-second clone reference. Quality is high; install is
  the heaviest of the alternatives because it pulls torch + transformers.
- **MARS5-TTS.** Apache-2.0 from CAMB.AI. AR ~750M + NAR ~450M params,
  PyTorch only, English-only. Strong prosody but ~1.5GB download and a
  big model footprint vs. Piper's ~70MB. ([MARS5 HF card](https://huggingface.co/CAMB-AI/MARS5-TTS),
  [MARS5 GitHub](https://github.com/Camb-ai/MARS5-TTS)).
- **StyleTTS 2.** MIT, Python 3.9/3.10 only, requires phonemizer. 95×
  realtime on RTX 4090, very natural for diffusion-based TTS
  ([StyleTTS 2 setup guide](https://llm-tracker.info/howto/StyleTTS-2-Setup-Guide)).
  Versioning constraint clashes with Sabrina's `requires-python = ">=3.12"`
  — would force a separate process or downgrade.
- **OpenVoice / Bark.** Both still around, both eclipsed for the
  English daily-driver use-case. Bark is MIT and prosodic but slow
  and prone to hallucinated audio artifacts
  ([suno/bark on HF](https://huggingface.co/suno/bark)).

**Comparative axis (vs. Piper):**

| Alt | Latency on 4080 | Naturalness | Footprint | Win install | Offline | Eng-only OK | License-friendly |
|---|---|---|---|---|---|---|---|
| Kokoro-82M | ≈ Piper | Better | ~80MB+espeak | Easy | Yes | Yes | Apache-2.0 ✅ |
| F5-TTS | Slower (RTF ~0.15) | Best | ~1GB+ | Medium | Yes | Yes | **CC-BY-NC weights** ⚠️ |
| XTTS-v2 (Idiap) | Slower | Better | ~2GB+torch | Medium | Yes | Yes | Coqui non-commercial ⚠️ |
| MARS5 | Much slower | Better prosody | ~5GB | Heavy | Yes | Yes | Apache-2.0 ✅ |
| StyleTTS 2 | Faster on GPU | Better | ~500MB | Hard (py3.10) | Yes | Yes | MIT ✅ |
| Bark | Much slower | Variable | ~4GB | Medium | Yes | Yes | MIT ✅ |

**Recommendation: keep Piper, watch Kokoro.** Piper is still the only
candidate that gives sub-second TTFA on CPU let alone the 4080, ships a
~70MB model, and integrates trivially with the sentence-streaming loop
in `speaker/piper.py`. Two material flags worth Eric knowing about:

1. **Piper relicensed to GPL-3.0 in v1.3.0** (Open Home Foundation
   fork). Sabrina is a personal daily-driver, so the copyleft is
   inert. If the project ever distributes binaries or links Piper into
   a closed-source product, GPL becomes load-bearing — flag it now so
   future-Eric isn't surprised.
2. **Kokoro-82M is the closest like-for-like upgrade candidate.**
   Apache, similar footprint, faster on GPU, naturally better. The
   thin-spot list in decision 002 mentions "no prosody knobs; no
   streaming synth" — Kokoro doesn't fix prosody knobs but the quality
   floor is higher. Worth a Sunday A/B if prosody starts feeling thin.

XTTS / F5-TTS / MARS5 are only interesting if voice cloning becomes a
goal — which decision 002 didn't list. Not now.

---

## 2. ASR — faster-whisper

**Current:** `faster-whisper>=1.0` running `base.en`, `int8_float16` on
CUDA, beam_size 5, language locked to "en" ([sabrina.toml [asr.faster_whisper]
block](file:sabrina-2/sabrina.toml)). Decision 003 picked it for being
"up to 4× faster than openai/whisper for the same accuracy"
([SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)).
The `rebuild/drafts/asr-upgrade-plan.md` already proposes upgrading to
`large-v3-turbo` — this section adds market context.

**Alternatives in May 2026:**

- **NVIDIA Parakeet-TDT (0.6B v2/v3 and 1.1B).** SOTA on the Hugging
  Face Open ASR Leaderboard (TDT was the first model under 7.0% average
  WER) ([Parakeet TDT 1.1B](https://huggingface.co/nvidia/parakeet-tdt-1.1b),
  [Open ASR Leaderboard 2026 trends](https://huggingface.co/blog/open-asr-leaderboard)).
  Distributed via NeMo. NeMo on Windows is a real install — works but
  requires CUDA-matching torch builds and isn't a single pip line. Not
  drop-in replaceable inside the existing CTranslate2 backend.
- **Whisper large-v3-turbo (via faster-whisper).** Pruned decoder
  (32→4 layers), much faster than large-v3 with minor quality drop
  ([openai/whisper-large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo)).
  Already CTranslate2-quantized as
  [`deepdml/faster-whisper-large-v3-turbo-ct2`](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2)
  — it slots into the existing backend with a `model = "large-v3-turbo"`
  edit. ~30× realtime on consumer GPUs.
- **Distil-Whisper (distil-large-v3 / v3.5).** MIT, English-only,
  6× faster than large-v3, 49% smaller, ~1% WER gap on out-of-distribution
  short-form audio (9.7% vs. 8.4%) ([Distil-Whisper repo](https://github.com/huggingface/distil-whisper),
  [distil-whisper/distil-large-v3](https://huggingface.co/distil-whisper/distil-large-v3)).
  Also CTranslate2-compatible.
- **whisper.cpp.** GGML/quantized, 5–15× CPU-only speedup, real CUDA
  build available on Windows but requires CMake+SDL2 dance for the
  streaming example ([whisper.cpp on Windows CUDA blog](https://blog.binaee.com/2025/04/whisper-cpp-cuda-build-windows/)).
  Loses the Python in-process integration; would mean shelling out.
- **whisper_streaming + faster-whisper.** Not a model — a streaming
  policy layer that gives partial transcripts using self-adaptive
  latency; faster-whisper is the recommended back-end
  ([ufal/whisper_streaming](https://github.com/ufal/whisper_streaming)).
  Useful only if Sabrina wants partials before end-of-utterance.

**Comparative axis (vs. faster-whisper base.en):**

| Alt | Latency on 4080 | WER (English clean) | Footprint | Win install | Streaming | License |
|---|---|---|---|---|---|---|
| Parakeet TDT 0.6B v2 | Fastest | Best (sub-7% avg) | ~1.2GB | Hard (NeMo) | Yes | CC-BY-4.0 ✅ |
| Whisper large-v3-turbo (CT2) | Fast | Near-large-v3 | ~1.5GB | Trivial swap | No (chunked) | MIT ✅ |
| Distil-Whisper large-v3 | Faster | ~1% gap | ~750MB | Trivial swap | No | MIT ✅ |
| whisper.cpp | Variable | Same as Whisper | Tiny | Hard (build) | Yes | MIT ✅ |
| whisper_streaming + FW | Same as base | Same | Same | Easy | Yes (partial) | MIT ✅ |

**Recommendation: switch to Whisper large-v3-turbo (via faster-whisper),
keep faster-whisper as the runtime.** This is the lowest-effort,
highest-impact ASR change. The CTranslate2 weights already exist on HF;
the model field in `sabrina.toml` is the only edit needed. The asr-upgrade
plan in drafts already proposes this — the survey backs it.

**Watch Parakeet-TDT.** It is *the* benchmark leader by mid-2026 and
Eric's 4080 has the headroom. The blocker is the NeMo install on Windows.
If openWakeWord-style ONNX exports start showing up for Parakeet, revisit.
Distil-Whisper is a fallback — same backend, smaller, but more WER drop
than turbo.

---

## 3. Wake word — openWakeWord (scaffolded)

**Current:** scaffolded in step-2 of overnight Track B
(`listener/wake_word.py`), reusing the AudioMonitor primitive from
decision 009. Bundled placeholder model `hey_jarvis`. Custom "Hey
Sabrina" lives in `tools/wake-training/` (not yet shipped).
[`openwakeword>=0.6`](https://github.com/dscripka/openWakeWord) is the
declared dep.

**Alternatives in May 2026:**

- **Picovoice Porcupine.** Vendor-quoted 97% true-positive with <1
  false alarm per 10 hours in noisy speech-background conditions
  ([Porcupine FAQ](https://picovoice.ai/docs/faq/porcupine/)). Free
  tier exists for personal use; *custom* wake words and commercial use
  hit the Picovoice paywall. Excellent SDKs, awful licensing for a
  community-built passion project.
- **Mycroft Precise.** Effectively unmaintained; the
  [mycroft-precise repo](https://github.com/MycroftAI/mycroft-precise)
  has had no release activity since the Mycroft AI shutdown chain in
  2023–2024. The lite plugin still works for the bundled `hey_mycroft.tflite`,
  but custom training relies on a Mycroft-era pipeline. Dead end.
- **HAwake / community openWakeWord training.** Community has built
  several alternative training pipelines around openWakeWord
  ([CoreWorxLab/openwakeword-training](https://github.com/CoreWorxLab/openwakeword-training),
  [IT-BAER/hawake-wakeword](https://github.com/IT-BAER/hawake-wakeword))
  because the official Colab notebook is fragile. Quality is good when
  you use a two-word phrase and avoid acoustically-near negatives.
- **Home Assistant Wyoming wake-word stack.** Not really an alternative
  — uses openWakeWord under the hood via Wyoming protocol. Useful
  reference if Sabrina ever wants HA integration.

**Comparative axis (vs. openWakeWord):**

| Alt | False-accept | Custom-train cost | License | Windows install |
|---|---|---|---|---|
| Porcupine (free) | <1/10hr (vendor) | **Paid only** | Apache code, paid weights | Easy |
| Mycroft Precise | Worse than oWW | Yes but unmaintained | Apache | Medium |
| HAwake / community pipelines | Same as oWW | Free, ~1hr Colab | Apache | Easy |
| openWakeWord | <0.5/hr, <5% FRR | Free, ~1hr Colab | Apache-2.0 | Easy |

**Recommendation: keep openWakeWord.** The Picovoice benchmarks
favor Porcupine on a per-engine basis but openWakeWord's own benchmarks
(prepared differently) show it competitive on the same test data
([Picovoice blog](https://picovoice.ai/blog/best-voice-activity-detection-vad/)).
For a *personal* daily-driver where Eric wants a "Hey Sabrina" trained
on his own voice without paying Picovoice or filing a commercial-use
form, oWW is the only realistic option.

**One worth-it follow-up:** when Eric trains the custom model, lean
on the community Colab variants ([atlas-voice-training](https://github.com/briankelley/atlas-voice-training))
not the official one — official is documented to break frequently.

---

## 4. VAD — Silero

**Current:** Silero VAD via `silero-vad>=5.1` ONNX wheel, threshold
0.5, min_speech_ms 300, dead_zone_ms 300. Shipped in decision 009 +
009a. Picked for shipping ONNX weights inside the wheel (no torch-hub
fragility).

**Alternatives in May 2026:**

- **WebRTC VAD (`py-webrtcvad` / `webrtcvad-wheels`).** GMM-based.
  PyPI shows no new releases in 12 months and effectively
  discontinued ([Snyk advisor](https://snyk.io/advisor/python/webrtcvad)).
  Ultra-low latency but ~50% TPR at 5% FPR (Picovoice's own benchmarks
  put Silero at ~88% and Cobra at ~99% at the same operating point)
  ([Picovoice 2026 VAD guide](https://picovoice.ai/blog/best-voice-activity-detection-vad/)).
- **Picovoice Cobra.** DNN-based, paid commercial license for anything
  beyond personal use, vendor-claimed 50× fewer errors than WebRTC and
  12× fewer than Silero at 5% FPR ([Cobra benchmark](https://picovoice.ai/docs/benchmark/vad/)).
  Same licensing problem as Porcupine.
- **`webrtcvad-wheels`.** Maintenance fork that ships wheels but
  identical model. Fixes the install pain on Windows but doesn't
  improve accuracy.

**Comparative axis (vs. Silero VAD):**

| Alt | TPR at 5% FPR | Latency | License | Maintained |
|---|---|---|---|---|
| WebRTC VAD | ~50% | Lowest | BSD | **No (12mo silence)** |
| webrtcvad-wheels | ~50% | Lowest | BSD | Yes |
| Picovoice Cobra | ~99% | Low | Paid commercial | Yes |
| Silero VAD | ~88% | Low | MIT | Yes |

**Recommendation: keep Silero.** The 009 validation showed 264 ms cut
latency at threshold 0.5 against keyboard/mouse noise on Eric's box —
which is the load-bearing real-world test. Cobra is more accurate on
paper, but the licensing makes it a nonstarter for a personal repo.
WebRTC is too noisy for barge-in (a 1-in-2 miss rate on speech frames
would either over-trigger if you tune sensitive or under-detect the
user starting to talk — exactly the failure mode that killed the
original Sabrina's interrupt UX). Silero hits the right point on the
curve at the right price.

---

## 5. Local LLM (Ollama brain) — Qwen 2.5 14B

**Current:** `qwen2.5:14b` as default, `qwen2.5:7b` as fast model
([sabrina.toml](file:sabrina-2/sabrina.toml) `[brain.ollama]`).
Hardware: i7-13700K + RTX 4080 16GB ([decision 001](file:rebuild/decisions/001-hardware-and-budget.md)).

**Alternatives in May 2026:**

- **Qwen 3 14B (Q4_K_M).** ~10–11 GB VRAM at Q4_K_M, ~60–70 tok/s on
  RTX 4080/4090, MMLU 81.1 ([willitrunai 2026 calculator](https://willitrunai.com/blog/what-llm-can-i-run-locally),
  [hardware-corner RTX 4080 benchmarks](https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-4080/)).
  Direct line of succession from Qwen 2.5 14B.
- **Phi-4 14B.** Microsoft, MIT-licensed; "nearly equivalent" to Qwen 3
  14B per the [apxml RTX 40-series guide](https://apxml.com/posts/best-local-llm-rtx-40-gpu).
  Tighter on safety alignment, looser on style by reputation.
- **Mistral Small 3.1 24B (Q4_K_M).** ~13.4GB at Q4_K_M, fits 16GB
  with thin headroom, ~55 tok/s on a 4080, Apache-2.0, latency-tuned
  by design, native function calling and JSON output
  ([mistral.ai Mistral Small 3.1](https://mistral.ai/news/mistral-small-3-1),
  [willitrunai Mistral page](https://willitrunai.com/blog/mistral-models-gpu-requirements)).
  Vendor pitch is explicitly "virtual assistants where users expect
  immediate feedback".
- **Gemma 3 12B.** Strong instruction-following, multilingual; Google's
  license is acceptable for personal use but more restrictive than
  Apache. Not the obvious fit for English-only personality work.
- **Llama 3.3 70B.** Out of bounds on 16GB. Even Q2 exceeds 30GB.

**Comparative axis (vs. Qwen 2.5 14B for a voice-loop brain):**

| Alt | VRAM @ Q4 | tok/s on 4080 | License | Function calling | Style fit |
|---|---|---|---|---|---|
| Qwen 3 14B | ~10–11GB | 60–70 | Apache-2.0 | Yes | Same family, drop-in |
| Phi-4 14B | ~9GB | ~60 | MIT | Yes | Tighter alignment |
| Mistral Small 3.1 24B | ~13.4GB | ~55 | Apache-2.0 | **Native, JSON-out** | Latency-tuned |
| Gemma 3 12B | ~8GB | ~70 | Gemma TOS | Yes | Multilingual focus |
| Qwen 2.5 14B | ~10GB | ~60 | Apache-2.0 | Yes | Current |

**Recommendation: switch to Qwen 3 14B as default; watch Mistral
Small 3.1.** Qwen 3 14B is the same family, same VRAM envelope, 81.1
MMLU vs. Qwen 2.5's older score — a free upgrade in Ollama once the
tag exists. Mistral Small 3.1 24B is the more interesting choice if
the planned tool-use work in `drafts/tool-use-plan.md` lands: it has
native function calling and JSON-mode and is explicitly latency-tuned
for assistants. The 13.4GB Q4 footprint is tight on 16GB but workable
if the Brain is the only GPU resident (which it would be once the ASR
is on its own slot or running CPU-side for the offline tier).

The router-plan deferral remains correct — there's no point routing
between Claude and Ollama until the Ollama side is genuinely worth
falling back to. A Mistral Small 3.1 brain, with native tool use,
would be that.

---

## 6. Vector store / semantic memory — sqlite-vec

**Current:** `sqlite-vec>=0.1.6` with `sentence-transformers/all-MiniLM-L6-v2`
(384-dim) embeddings. Decision 007 picked sqlite-vec for being
zero-server, single-file, Python-native, and SQLite-adjacent.

**Alternatives in May 2026:**

- **LanceDB.** Embedded columnar (Lance format), Apache-2.0. Brute-force
  search over Lance is fast enough that benchmarks frequently skip vector
  indexing entirely ([prrao87 LanceDB study](https://github.com/prrao87/lancedb-study)).
  Better concurrent throughput than SQLite's file-locked reads
  ([Newtuple speed/scalability post](https://www.newtuple.com/post/speed-and-scalability-in-vector-search)).
- **Chroma (local).** Apache-2.0. Fastest single-query latency in
  contemporary benchmarks but bottlenecks on concurrency because of
  SQLite-style file locking ([Newtuple post](https://www.newtuple.com/post/speed-and-scalability-in-vector-search)).
  For a single-user voice loop with no concurrency, this is moot.
- **Qdrant local mode.** Apache-2.0. In-process Python implementation
  ([Qdrant local docs](https://deepwiki.com/qdrant/qdrant-client/2.2-local-mode)),
  but vendor-recommended ceiling is ~20,000 points and a `.lock` file
  blocks concurrent processes — known to bite hot-reload workflows
  ([qdrant-client #765](https://github.com/qdrant/qdrant-client/issues/765)).
- **FAISS / hnswlib.** Pure ANN libraries, no DB layer. hnswlib is
  faster than FAISS on CPU and has lower memory footprint
  ([Zilliz Faiss vs HNSWlib](https://zilliz.com/blog/faiss-vs-hnswlib-choosing-the-right-tool-for-vector-search)).
  Either pairs with raw SQLite for metadata. More code on Sabrina's
  side; no operational benefit at this scale.
- **Flat numpy + brute force.** At Eric's likely corpus size (months of
  conversational turns, not millions), a numpy `dot` against a stacked
  matrix of ~100k embeddings is sub-millisecond on the 4080 and
  microseconds on the i7. Zero deps.

**Comparative axis (vs. sqlite-vec):**

| Alt | Footprint | Latency at 100k vectors | Win quirks | License | Migration cost |
|---|---|---|---|---|---|
| LanceDB | ~50MB + data | Better at scale | Clean | Apache-2.0 | Medium |
| Chroma local | ~80MB + data | Best single-query | SQLite-locking | Apache-2.0 | Medium |
| Qdrant local | ~150MB + data | Good, capped at 20k | `.lock` file | Apache-2.0 | High |
| FAISS | ~20MB | Excellent | Clean | MIT | High (own DB) |
| hnswlib | ~5MB | Excellent | Clean | Apache-2.0 | High (own DB) |
| flat numpy | 0 | Microseconds at <100k | Clean | n/a | Low |
| sqlite-vec | tiny extension | Good at <100k | `enable_load_extension` quirk | MIT | n/a |

**Recommendation: keep sqlite-vec.** The corpus size doesn't justify
moving. The one Windows quirk (some Python builds compile out
`enable_load_extension`) is documented in `validate-007-windows.md`
and was already solved in 007 by switching to a `uv python install
3.12` build. The single biggest win in this stack isn't *the store* —
it's **dropping `sentence-transformers` for an ONNX-only MiniLM**
to kill the ~700MB torch transitive dep (already noted in
`pyproject.toml` as a research item). The ONNX file for
all-MiniLM-L6-v2 is ~80MB and gives the same embeddings
([sentence-transformers ONNX backend docs](https://sbert.net/docs/sentence_transformer/usage/efficiency.html),
[onnx-models/all-MiniLM-L6-v2-onnx](https://huggingface.co/onnx-models/all-MiniLM-L6-v2-onnx)).

**Watch flat numpy.** If a future thin-spot pass surfaces "sqlite-vec
extension fails on a fresh Windows install," the fallback path is
flat-numpy — not LanceDB. At Sabrina's scale, the index isn't earning
its complexity.

---

## 7. Avatar / Live2D

**Current:** planned but not started. Roadmap names `live2d-py` as the
primary candidate; design also flagged `pixi-live2d-display` via
QWebEngine as the web-rendered alternative.

**Alternatives in May 2026:**

- **`live2d-py`.** [EasyLive2D/live2d-py](https://github.com/EasyLive2D/live2d-py),
  v0.6.1.1 released 2026-01-16, active ([live2d-py on PyPI](https://pypi.org/project/live2d-py/)).
  C-extension over the Live2D Native SDK, OpenGL-based rendering, lip
  sync + face rigging + click test. Win wheels for cp310–cp313 (32-bit
  and 64-bit). Native and fast; no browser overhead. License: depends
  on the underlying Live2D Cubism SDK terms — non-commercial use is
  free, commercial requires Live2D licensing.
- **`pixi-live2d-display` via PyQt6 + QWebEngineView.** Web-rendered
  ([guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display)),
  supports both Cubism 2.1 and 4. Browser-engine renderer, very mature
  Live2D abstraction. Cost: bundling Qt6 WebEngine adds ~150MB and a
  Chromium-class memory footprint per avatar window.
- **VTube Studio plugin (via [`pyvts`](https://pypi.org/project/pyvts/)).**
  Use VTube Studio as the rendering process, drive it via the official
  WebSocket API on port 8001 ([VTubeStudio plugin docs](https://github.com/DenchiSoft/VTubeStudio/wiki/Plugins)).
  Sabrina becomes the plugin: hotkey expressions, parameter pushes,
  lip sync via TTS audio. Licensing: VTube Studio is paid (Steam) but
  has a free demo tier; its API is open. Trades "build the renderer"
  for "depend on a separate paid app being installed and running."
- **Spine 2D / sprite-strip / custom shader.** Not Live2D. Sprite-strip
  is the simplest possible thing that could work — a frame sequence
  per state. Spine adds skeleton rigging without the Live2D licensing
  question. Both are dead-ends for Sabrina's planned facial-expression
  fidelity.

**Comparative axis (for Sabrina specifically):**

| Alt | Effort to first frame | Render perf | Memory | Lip sync | License complications |
|---|---|---|---|---|---|
| live2d-py | Medium (C extension + GL setup) | Native, fast | Small | Yes | Live2D Cubism SDK terms |
| pixi-live2d-display + QWebEngine | Low (well-trodden) | Good | ~150MB+Chromium | Yes | Same SDK terms |
| VTube Studio + pyvts | Lowest (it's just a WS client) | Excellent | External app | Yes | Paid app dep |
| Spine / sprite-strip | Lowest code, lowest fidelity | Excellent | Tiny | Manual | None |

**Recommendation: keep `live2d-py` as the primary, `pixi-live2d-display`
as the documented fallback.** The decision tree should be:

1. Try `live2d-py` first. The maintenance signal is strong (Jan 2026
   release, Win wheels for current Python versions).
2. If the OpenGL-context-from-PyQt6 dance turns into an integration
   nightmare, fall to `pixi-live2d-display` inside QWebEngineView.
   That tradeoff is well-known and works.
3. **Worth seriously considering: VTube Studio + pyvts** as a
   "skip-the-renderer" option for the first iteration. Eric already
   uses Sabrina as a daily driver; standing up a VTube Studio plugin
   that drives expression hotkeys from `StateChanged` events would
   give *something on screen* in a day, while live2d-py work continues
   in parallel. The downside (depending on a paid app) is real, but
   for prototyping the personality-character path it's an option worth
   not dismissing.

---

## 8. System prompt / personality engineering

**Current:** drafted in `rebuild/drafts/personality-plan.md`. The
plan references tag-based emotion tracks, "inferred vs. stated"
calibration, and Eric-specific signals. Track A may have rewritten
this overnight (see `ACTION_ITEMS_personality.md`).

**State of the art in May 2026:**

- **Persona Selection Model (PSM).** Anthropic's
  [March 2026 alignment writeup](https://alignment.anthropic.com/2026/psm/)
  frames LLMs as actors who "select" a persona during inference, with
  post-training shaping which persona is the default. Practical
  takeaway: persona prompts work *because* they index into
  pre-existing simulator capacity, not because they "instruct" the
  model. Concrete implication for Sabrina: lean on names, contexts,
  and example interactions that uniquely identify the *Sabrina*
  persona, not on rule-lists.
- **Persona vectors.** Anthropic's
  [persona vectors research](https://venturebeat.com/ai/new-persona-vectors-from-anthropic-let-you-decode-and-direct-an-llms-personality)
  — directions in activation space corresponding to traits. Currently
  experimental and not exposed in the public API, but informs *why*
  examples-over-rules works: examples land closer to the activation
  manifold of the desired persona than constraint enumeration does.
- **Examples > rules.** The current best-practice consensus is that
  "do it like this" lands harder than "follow these 15 requirements"
  ([Comet few-shot guide](https://www.comet.com/site/blog/few-shot-prompting/),
  [Brim Labs personas writeup](https://brimlabs.ai/blog/llm-personas-how-system-prompts-influence-style-tone-and-intent/)).
  Persona prompting helps stylistic tasks; it does *not* improve
  factual performance ([2023 paper on personas](https://arxiv.org/html/2311.10054v3)
  still cited in 2026 critiques).
- **XML tags for persona state and emotion tracks.** XML is
  recommended specifically by Anthropic and has resurged across
  providers; tags work as "high-salience anchors" that stabilize
  multi-turn persona output
  ([cloud-authority XML writeup](https://cloud-authority.com/xml-is-making-a-comeback-in-prompt-engineering-and-it-makes-llms-better),
  [Tech for Humans XML guide](https://medium.com/@TechforHumans/effective-prompt-engineering-mastering-xml-tags-for-clarity-precision-and-security-in-llms-992cae203fdc)).
  Caveat from current research: tags as state markers don't *create*
  persistent state — the LLM still treats each utterance largely in
  isolation unless emotion is explicitly threaded through context
  ([emotion + intention LLM survey](https://www.mdpi.com/2227-7390/13/23/3768)).
  For Sabrina, that means: `<emotion>` tags should be mirrored back in
  the next turn's context block, not assumed to persist as model state.
- **Reflection loops.** Increasingly popular for agentic systems but
  a poor fit for a real-time voice assistant — they double latency.

**Recommendation:** the personality-plan draft's choices are aligned
with current best practice. Two specific cross-cuts to flag:

1. **Lean on examples over rule-lists in the system prompt.** If the
   draft has a "Sabrina is X, Sabrina avoids Y" enumeration, replace
   chunks of it with 2–4 short example turns (user input → Sabrina
   reply) that demonstrate the same behavior. This is the single
   highest-leverage prompt-engineering change available in 2026.
2. **XML emotion tags require feedback into context.** If `<mood>` or
   similar tags are emitted by the model, reading them and threading
   them into the next turn's system suffix is what makes them
   load-bearing. Otherwise they're decorative.

The "inferred vs. stated" callout in the draft is the right structural
move regardless of which specific framing wins.

---

## 9. Tool-use protocol

**Current:** planned, drafted in `rebuild/drafts/tool-use-plan.md`,
not shipped. Plan defaults to Anthropic native tool use through the
`Brain` protocol.

**State in May 2026:**

- **Anthropic native tool-use API.** The model emits `tool_use` blocks;
  the client executes and returns `tool_result`. Same pattern as
  OpenAI's function calling. Stable, in-API, no extra layer.
- **MCP (Model Context Protocol).** Open standard introduced by
  Anthropic Nov 2024; by March 2026 the Anthropic blog cites 97M
  installs ([Wikipedia MCP](https://en.wikipedia.org/wiki/Model_Context_Protocol),
  [The New Stack: why MCP won](https://thenewstack.io/why-the-model-context-protocol-won/)).
  Anthropic, OpenAI, Google DeepMind, Microsoft Copilot all support it
  natively. MCP defines tools, resources, and prompts; Claude / OpenAI
  / Gemini all consume MCP-defined tools through their respective
  native tool-use mechanics.
- **Outlines.** FSM-constrained sampling for guaranteed schema
  compliance, only useful for *local* models ([outlines on PyPI](https://pypi.org/project/outlines/)).
  For the Claude path it's irrelevant; for the Ollama path it's
  interesting if structured output reliability becomes a problem.
- **Instructor.** Pydantic-style structured-output wrapper, works
  across 15+ providers ([useinstructor.com](https://python.useinstructor.com/)).
  Useful if the same `Brain` interface needs to extract structured
  results across both Claude and Ollama backends without re-implementing
  the validation layer.
- **Mirascope.** Decorator-based, "anti-framework" structured-output
  library ([Mirascope structured outputs](https://mirascope.com/docs/mirascope/guides/getting-started/structured-outputs/)).
  Smaller community than Instructor; similar capability surface.

**Comparative axis:**

| Alt | Vendor lock-in | Effort to integrate | Local model support | Schema guarantees |
|---|---|---|---|---|
| Anthropic native | Anthropic only | Lowest | No | Best-effort |
| MCP | None | Medium (standing up servers) | Yes | Best-effort |
| Outlines | None | Medium | Yes (HF/Ollama) | Hard guarantee |
| Instructor | None | Low (Pydantic-y) | Yes | Pydantic validation + retry |
| Mirascope | None | Low | Yes | Pydantic validation |

**Recommendation: keep Anthropic native tool-use for the immediate
shippable version; design the `Brain` protocol so tools are
MCP-compatible by construction.**

The native API is the lowest-effort first cut and matches the existing
Brain protocol. But the writing is on the wall: every major provider
now consumes MCP-defined tools and the standard is the path of least
friction for *adding* new tool sources later (filesystem, Slack,
calendar, browser — all already exist as MCP servers). The right move
is to define tool surfaces in a shape that maps cleanly to MCP's
JSON-Schema-based tool definitions, even if the first round of code
calls Anthropic's native API directly. Migration cost from "native
tools defined in MCP-compatible JSON" to "MCP server" is then a
rewrite of the transport, not the schema.

**Watch Instructor.** If the `Brain` ever needs to extract structured
output from *both* Claude and Ollama (e.g., for the brain router with
tool-using fallback), Instructor is the obvious adapter. Outlines is
only worth it if Ollama-side schema breakage becomes a real problem.

---

## 10. Audio I/O on Windows — sounddevice

**Current:** [`sounddevice>=0.4.7`](https://python-sounddevice.readthedocs.io/)
across Listener, Speaker, and AudioMonitor. Picked early; never
benchmarked against alternatives.

**Alternatives in May 2026:**

- **PyAudio.** Original PortAudio wrapper, similar capability surface
  to sounddevice. Documented to *interfere* with sounddevice's ASIO
  device enumeration if both are installed
  ([sounddevice issue #229](https://github.com/spatialaudio/python-sounddevice/issues/229)).
  No reason to pick this over sounddevice for a greenfield install.
- **PyAudioWPatch.** PortAudio fork that adds **WASAPI loopback** —
  recording from speakers, BT headsets, etc.
  ([s0d3s/PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch)).
  Win wheels for cp37–cp313. Only relevant if Sabrina ever wants to
  capture system audio (e.g., transcribe the audio of a YouTube tab).
  Not a replacement, an *addition*.
- **`miniaudio` (`pyminiaudio`).** [pyminiaudio](https://github.com/irmen/pyminiaudio)
  wraps Mackron's miniaudio. Reported Windows latency 83–93ms
  vs. ~1ms on Mac because of the older WASAPI backend
  ([miniaudio issue #949](https://github.com/mackron/miniaudio/issues/949)).
  Not a fit for a real-time voice loop on Windows.
- **`rtmixer`.** [spatialaudio/python-rtmixer](https://github.com/spatialaudio/python-rtmixer)
  — same authors as sounddevice, dedicated to low-latency callback
  audio implemented in C to dodge the GIL. Useful if Sabrina ever
  needs sub-10ms callback timing (it doesn't today).
- **Direct WASAPI / wdm-ks via sounddevice.** sounddevice already
  exposes `WasapiSettings` for exclusive mode and supports WDM-KS
  drivers ([sounddevice platform-specific settings](https://python-sounddevice.readthedocs.io/en/latest/api/platform-specific-settings.html)).
  Reported wdm-ks latencies as low as 1–1.5ms on Windows
  ([PsychoPy thread](https://discourse.psychopy.org/t/low-sound-latency-with-sounddevice-module-wdm-ks-driver/912)).

**Comparative axis (vs. sounddevice):**

| Alt | Win latency floor | Loopback | Maintained | Replaces sounddevice? |
|---|---|---|---|---|
| PyAudio | Similar | No | Yes | No advantage |
| PyAudioWPatch | Similar | **Yes** | Yes | No (additive) |
| miniaudio | ~85ms | No | Yes | **No, worse** |
| rtmixer | <10ms callback | Via sounddevice | Yes | No (specialized) |
| sounddevice + WASAPI exclusive / wdm-ks | 1–1.5ms | Via PyAudioWPatch | Yes | n/a |

**Recommendation: keep sounddevice; reach for PyAudioWPatch only when
loopback recording becomes a feature request.** The "device-index drift"
question Eric flagged in the prompt is a portaudio-level concern, not
a wrapper-level one — both PyAudio and sounddevice are bound to the
same enumeration. The Sabrina-shaped fix is to allow string-based
device selection (substring match) in the config and resolve to an
index at startup, which `sabrina.toml` already supports
(`output_device = ""` accepts substring or index). Switching wrappers
wouldn't move the needle.

If exclusive-mode latency ever matters (e.g., Eric notices TTS-onset
drift in the barge-in dead zone), `WasapiSettings(exclusive=True)` is
a one-line config inside the existing sounddevice usage. No swap
required.

---

## Recommendations table

| # | Subsystem | Verdict | Why |
|---|---|---|---|
| 1 | TTS (Piper) | **Keep, watch Kokoro-82M** | Piper's still the speed/footprint winner; flag the GPL-3.0 relicense for future-Eric. |
| 2 | ASR (faster-whisper base.en) | **Switch (model)** | Move to `large-v3-turbo` via faster-whisper; trivial config edit, large quality jump. Watch Parakeet TDT. |
| 3 | Wake word (openWakeWord) | Keep | Only realistic Apache option for custom training without Picovoice paywall. |
| 4 | VAD (Silero) | Keep | Cobra is more accurate but commercial-licensed; WebRTC unmaintained. |
| 5 | Local LLM (Qwen 2.5 14B) | **Switch** | Bump to Qwen 3 14B as drop-in; consider Mistral Small 3.1 24B once tool-use ships. |
| 6 | Vector store (sqlite-vec) | Keep, switch *embedder* | Replace `sentence-transformers` with ONNX-only MiniLM to drop the torch dep. |
| 7 | Avatar (live2d-py) | Keep primary, document fallback | live2d-py is actively maintained; keep `pixi-live2d-display` + QWebEngine as documented escape hatch. |
| 8 | Personality engineering | Keep direction, refine | Examples > rules; XML tags require explicit context-thread to be load-bearing. |
| 9 | Tool-use (Anthropic native) | Keep, design MCP-compatibly | MCP has won; design the schema once, swap transport later. |
| 10 | Audio I/O (sounddevice) | Keep | No swap is faster on Windows; reach for PyAudioWPatch only when loopback is needed. |

---

## Highest-leverage potential switch

**Drop `sentence-transformers` and run all-MiniLM-L6-v2 directly under
`onnxruntime`.** The `pyproject.toml` comment already flags this
("sentence-transformers pulls torch (~700MB) transitively. A leaner
onnxruntime+MiniLM replacement is on the research list."). Confirmed
by the 2026 ecosystem: the ONNX file is ~80MB, gives equivalent
embeddings, and `onnxruntime` is already in the dependency closure
(via openWakeWord and silero-vad). The diff is a single `Embedder`
class swap; the wheel size for a fresh `uv sync` drops by close to a
gigabyte. Robustness goes *up* — fewer torch version games on Windows,
no nondeterministic CUDA-init paths in the embed code path.

Honorable mention: the **ASR model bump to `large-v3-turbo`** is
already in `drafts/asr-upgrade-plan.md`; the survey backs it. It's a
two-line config change for measurable WER reduction — also a strong
candidate, but the embedder swap removes a structural dep, which is
worth more long-term.

---

## What got cheaper / better since the original choices

The single most material market shift is in **local LLM
parameter-efficiency**. When Sabrina's Ollama default was wired to
Qwen 2.5 14B in early-mid 2026, MMLU 81 territory required a 14B
model. Qwen 3 14B and Phi-4 14B match or exceed that on the same
VRAM, and Mistral Small 3.1 24B fits *just inside* a 16GB card with
Q4 quantization while delivering native function calling — which the
original choice did not. The "router-plan deferred until Ollama is
worth falling back to" framing in decision 003 is increasingly easy
to satisfy.

In **TTS**, the Kokoro-82M release and the F5-TTS family have made
"better-than-Piper-quality at near-Piper-speed" a real option for the
first time, but Piper's specific niche (sub-100MB model, sub-second
TTFA on CPU, sentence-streaming friendly) is still uncontested for an
always-on assistant. Coqui's December 2025 shutdown removed XTTS as a
"first-party-supported" option but the Idiap fork has kept it alive.

In **ASR**, NVIDIA's Parakeet family taking the Open ASR Leaderboard
top-five spots is the clearest "outclassed" signal — Whisper is no
longer state-of-the-art for English. But Whisper is still the best
*Windows-friendly Python-native* family by a wide margin, and
`large-v3-turbo` closes most of the practical gap. Parakeet stays a
"watch" item until NeMo's Windows install story improves.

In **vector search**, sqlite-vec, LanceDB, and Chroma have all
matured to "fine for personal-scale, no obvious winner" — meaning the
right choice today is the one with the lowest operational footprint,
which sqlite-vec wins.

In **tool use**, MCP went from "an Anthropic protocol" to "the
default" in eighteen months. Sabrina hasn't shipped tools yet, which
is *good timing*: design once, in the shape of the standard.

In **personality engineering**, the academic and applied consensus
moved decisively toward examples-over-rules and XML-tagged structure
during 2025, and Anthropic's own persona-selection-model framing
(March 2026) is the strongest theoretical grounding to date. The
draft personality plan is already in this idiom.
