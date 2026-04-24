# Decision 001 — Hardware and budget posture

**Date:** 2026-04-22
**Status:** Accepted

## Context

Rebuild is a single-machine, personal daily-driver on the author's existing Windows desktop. Budget posture was stated as "$0 target, $100 ceiling."

## Hardware (target machine)

- CPU: Intel i7-13700K (16 physical / 24 logical cores, 3.4 GHz base)
- RAM: 32 GB DDR5-6000 (2 sticks)
- GPU: NVIDIA GeForce RTX 4080, 16 GB VRAM, driver 591.86
- iGPU: Intel UHD 770 (available for light work; primary display can use it to keep 4080 free)
- OS: Windows 11 Pro, build 26200
- Disk: 930 GB total, 297 GB free
- Audio: Realtek onboard + 2 USB audio devices + NVIDIA HDMI audio
- Existing tooling: Python 3.10.11 (pyenv-win), git 2.43

## Decisions

### Local tier is first-class, not a fallback
The 4080's 16 GB VRAM comfortably hosts a 14B-parameter model in Q5 quantization with headroom for context and a possible second model. Local inference is fast (expected 40–80 tok/s on Qwen 14B Q5_K_M) and free. Cloud becomes the exception, used for:
- Complex multi-step planning
- Nuanced language / creative tasks
- Vision (unless user opts into local Qwen VL)
- Cases where local tool use fails and the router escalates

### Model picks
- **Primary local brain:** `qwen2.5:14b` (Q5_K_M). Chosen for best-in-class tool use at this size, strong general reasoning, Apache 2.0 license.
- **Fast local:** `qwen2.5:7b` (Q5_K_M). Used for router decisions and latency-sensitive simple queries. ~2× faster than 14B.
- **Optional local vision:** `qwen2.5vl:7b`. Opt-in, not default. Claude vision is better but cloud.
- **Cloud light:** Claude Haiku 4.5 (default cloud tier).
- **Cloud heavy:** Claude Sonnet 4.6 (reserved for hard tasks, explicit "think hard" intents, vision-heavy).

### Budget configuration
- Target: **$0/month** (achieved by local-preferring router + fast-path + prompt caching).
- Daily warn: $1/day logged.
- Monthly warn: **$10/month**.
- Monthly ceiling (hard kill-switch): **$100/month** — all cloud calls route to local or fast-path until reset.

### Consequences
- Ollama becomes a hard dependency on the target machine.
- Install disk budget: ~15 GB for the two primary local models, plus ~2 GB for Piper + Whisper + misc — comfortably within the 297 GB free.
- Local tier absorbs an expected 55%+ of queries; cost model shows realistic monthly spend in the $2–$5 range for typical daily use.
- 24 logical cores and 32 GB RAM mean Whisper ASR, Piper TTS, PyQt6 avatar, and memory subsystem all run on CPU in parallel with GPU inference without contention.
- Multiple audio devices means explicit device selection is required in config; Sabrina should never auto-pick a default that might change.

## Open
- Which specific input mic + output device to pin in config (resolve during Phase 1 voice-loop work by running `sabrina test-audio`).
- Whether to primary-display on the iGPU to free the 4080 entirely for inference (minor tweak, can defer).
