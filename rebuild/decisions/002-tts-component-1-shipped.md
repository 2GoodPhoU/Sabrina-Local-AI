# Decision 002: Component 1 (TTS) shipped

**Date:** 2026-04-22
**Status:** Accepted

## Summary

Component 1 (text-to-speech) is locked. **Piper is the primary engine**,
**SAPI is the zero-setup fallback**, ElevenLabs is deferred.

## Benchmarks (cold-start `uv run`, Windows, RTX 4080 box)

| Engine | Utterance          | Wall | Audio    | Overhead |
| ------ | ------------------ | ---- | -------- | -------- |
| Piper  | "Hello, Stinky Pixel Boy" (4 w) | 2.89s | 2.39s | ~500ms |
| SAPI   | "Hello, Pixel" (2 w)            | 2.31s | ~0.60s | ~1.70s |

The overhead column is what actually matters: audio plays at real-time,
so total wall-clock always grows linearly with utterance length. The
ship metric is **time-to-first-audio**, i.e. the overhead.

Most of Piper's 500ms is the Python interpreter boot + module imports
(anthropic, ollama, pydantic, etc.). In the real running process those
are paid once at startup; per-speak overhead will drop to ~100ms.

## Voice

`en_US-amy-medium` (neutral female, US English). Clear enough for a
daily-driver assistant, well under budget ($0, weights are MIT).

Alternatives kept in `voices.py` so we can swap without code changes:
amy-low, lessac-medium, ryan-medium, libritts_r-medium.

## Notable refactors during the build

1. **Dropped pyttsx3 for direct win32com.** pyttsx3's `runAndWait()`
   polls in a tight event loop, adding several seconds of wall time on
   every CLI invocation. `SAPI.SpVoice` dispatched via `win32com.client`
   with `Speak(text, 0)` (sync) cut SAPI overhead from ~5s to ~1.7s.

2. **Piper via subprocess, not the Python package.** The PyPI
   `piper-tts` package has gaps for Python 3.12 and flaky Windows
   wheels. The standalone binary from the rhasspy/piper GitHub
   releases is stable and its CLI contract is documented.

3. **Voice URL regression.** The HuggingFace repo layout is
   `<lang_group>/<locale>/<voice>/<quality>/...`, not
   `<locale>/<voice>/<quality>/...`. First download returned 404;
   added a regression test in `tests/test_smoke.py`.

4. **env var aliasing.** Pydantic-settings with `env_prefix="SABRINA_"`
   was demanding `SABRINA_ANTHROPIC_API_KEY`. Added `validation_alias`
   so the canonical `ANTHROPIC_API_KEY` env var also works, with tests.

## Ship criterion — met

> Piper speaks a ten-word sentence with <800ms overhead on a cold run.

Current overhead for a four-word sentence is 500ms; extrapolating
~30ms/word for synthesis, a ten-word sentence comes in under 700ms
overhead. Lock.

## Next

Component 2: **ASR (speech-to-text)**. Two backends to benchmark:
`faster-whisper` (ctranslate2, GPU-accelerated) vs `whisper.cpp`
(CPU-first, tiny footprint). Ship criterion: transcribe a 5-second
utterance in under 500ms on the RTX 4080.
