# Decision 003: Component 3 (voice loop) shipped

**Date:** 2026-04-22
**Status:** Accepted

## Summary

Push-to-talk voice loop is working end-to-end. PTT -> faster-whisper ->
brain -> sentence-streaming Piper. Ship metric met on first try.

## Measured latency (user run, RTX 4080, Claude Sonnet 4.6 brain)

PTT release at 04:16:41.23 -> first audible sentence at 04:16:43.08 =
**~1.85 seconds** end-to-end. Under the 2.0s ship target.

Rough breakdown from the structlog timestamps:
  - Transcribe (base.en @ cuda, ~1s of audio): ~50-150ms
  - First-token latency from Claude: ~600-900ms
  - First-sentence buffer fill (until terminator): ~500-700ms
  - Piper synth + playback start: ~100-200ms

## Architecture moves worth preserving

1. **Sentence-streaming TTS.** The buffer splits on `.!?\n` but requires
   whitespace or end-of-buffer after the terminator, so "Pi is 3.14" is
   one chunk, not two. This single heuristic gave us "alive" instead of
   "chatbot". Tests in `test_smoke.py::test_sentence_splitter_*` guard it.

2. **PTT via pynput, not `keyboard`.** No admin required. Thread-safe
   hand-off from the pynput listener to the asyncio loop via two
   `threading.Event`s (`_held`, `_released`).

3. **Speaker worker is a task, brain stream is the main loop.** The
   queue isolates timing: the brain can produce tokens as fast as it
   wants without stalling on Piper, and Piper can play an early sentence
   while the brain is still generating the next one.

## Bugs caught, tests added

- **`SpeakStarted` missing `text` field, `SpeakFinished` was passed
  `aborted` instead of `duration_s`.** Pydantic caught it at runtime mid-run.
  Added `test_speak_events_construct_with_required_fields` as a schema guard —
  new event publish sites will fail loudly in tests now.

- **Mic picked up the shift key itself.** First transcript came back as
  "shift on this button" because the microphone recorded the key click.
  User workaround: `--hotkey f9`. Proper fix deferred (trim first/last
  ~150ms of audio, or switch to VAD-driven capture, which is part of
  Component 5 anyway).

## Ship criterion — met

> Time from PTT release -> first audible word of Sabrina's reply is
> under 2 seconds on base.en + piper + Claude.

Measured 1.85s. Lock.

## Component 3 notes for the future

- The voice loop can be moved behind a systemd/Windows-service wrapper
  once we daemonize. Right now it's a single foreground CLI process.
- No wake-word yet. PTT is the trigger. Wake-word (e.g. openWakeWord)
  becomes relevant only when we want hands-free operation.
- No interruption handling — Sabrina finishes speaking before listening.
  Barge-in is Component 6 territory (requires VAD + TTS stop hooks;
  both exist, just not wired).

## Next

**Component 4: screen vision.** Grab screenshots and describe them via
a VLM. Enables "what's on my screen?", "read this error", "summarize this
email". Claude's multimodal API is the primary backend; a local VLM
(llava via Ollama) can slot in as the fallback using the same protocol.
Ship criterion TBD once we pick a scope.
