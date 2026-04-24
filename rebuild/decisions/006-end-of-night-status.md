# Decision 006: End-of-night status snapshot

**Date:** 2026-04-22 (late)
**Status:** Informational — not a decision, a checkpoint

## The one-liner

We have a working voice assistant. PTT in, Claude or Ollama in the middle,
streaming sentence-by-sentence Piper TTS out, SQLite memory across restarts,
optional screenshot attachment to Claude on a trigger phrase or hotkey, and
a customtkinter settings GUI that writes `sabrina.toml` without eating the
comments. About 3,500 lines of Python, including tests.

## What shipped

| Component | Status | Backing decision |
|---|---|---|
| Foundation (uv, pydantic-settings, structlog, typer) | ✅ | — |
| TTS — Piper primary, SAPI fallback | ✅ | 002 |
| ASR — faster-whisper `base.en` | ✅ | 003 |
| Voice loop (PTT + sentence-streaming TTS) | ✅ | 003 |
| Memory (SQLite, rolling context) | ✅ basic | 003 |
| Brain protocol + Claude + Ollama backends | ✅ | 003 |
| Event bus + state machine | ✅ | 003 |
| Vision (mss → downscale → Claude vision) | ✅ | 005 |
| Settings GUI (customtkinter, TOML round-trip) | ✅ | 004 |

What's **not** shipped from the original roadmap: wake word, avatar,
automation, brain router, semantic memory / RAG, budget tracker. The
wake-word slot is currently filled by push-to-talk (we said in the original
"always available as fallback" — turns out the fallback was good enough to
promote).

## What changed vs. the original roadmap

Three meaningful departures.

First, **push-to-talk replaced wake word as the primary trigger**, not the
fallback. Porcupine/openWakeWord were planned for component 3. PTT is
reliable, false-positive-free, costs nothing, and keeps Claude from
"hearing" across the room. Adding wake-word is still on the list but it's
an enhancement now, not a prerequisite.

Second, **settings GUI was added (wasn't planned)**. It wasn't in any of
the nine numbered components — it grew out of the vision work because
vision has a lot of knobs (trigger mode, hotkey combo, model, max_edge_px,
monitor) that are clumsy to edit in TOML by hand. Now TTS, ASR, Brain,
Vision, and Memory all have tabs. Big quality-of-life win. Comment
preservation via tomlkit is the non-obvious correctness property that
makes it safe to round-trip.

Third, **no brain router yet**. The roadmap called for fast-path → Ollama
→ Haiku → Sonnet routing. What's actually in the tree is: pick a backend
at config time, stick with it for the session, with a per-turn override
for vision (Claude Haiku always). Router is deferred because empirically
Haiku 4.5 is fast enough and cheap enough that the gain from routing hasn't
been worth the complexity yet. Revisit when daily cost crosses $1.

## What works well

- **Latency is good.** End of PTT release → first audible word: ~1.85s on
  the target machine, measured during the session. Sentence-streaming TTS
  is the single biggest win — we start speaking on the first `.` instead
  of waiting for the full reply.
- **The Brain protocol held up.** Adding `Message.images` as an additive
  field let vision slot in without changing text-only call sites. Ollama
  turns still use the compact `{"role","content":str}` wire form; Claude
  image turns switch to content-block form. Future extensions (tool use,
  documents) can use the same pattern.
- **Vision triggers feel natural.** Saying "look at my screen, what's
  this error?" works; the hotkey arms the next turn instead of
  screenshot-on-press, which removes every "I hit the wrong moment"
  footgun.
- **Settings GUI writes files safely.** Atomic tempfile+rename means a
  mid-save crash can't leave a broken TOML. Comment preservation means
  Eric's documentation-in-config doesn't get nuked.
- **State machine transitions are enforced.** Illegal transitions raise
  loudly instead of silently half-working. Debugging is much faster than
  the old repo.
- **Tests ride along.** 60+ smoke tests covering config, memory, brain
  protocol, vision, GUI config I/O. `pytest -q` takes ~3s.

## Areas that are thin / improvement candidates

Organized by component.

### TTS (Piper)

- **Upgrade path:** `libritts_r-medium` is the current default at speaker
  0. There are other speakers in that model worth A/B-ing for a voice
  Eric actually likes. Also worth trying `lessac-high` or
  `ljspeech-high` for a cleaner, less character-y voice.
- **Streaming synth.** Piper synthesizes one sentence, writes a WAV,
  plays it. We could pipe Piper's stdout directly into sounddevice to
  get sub-100ms first-audio on very long sentences. Not needed today
  (we already chunk by sentence) but an option for longer replies.
- **Prosody knobs.** `length_scale`, `noise_scale`, `noise_w` are
  exposed on piper but not in our config. Adds expressiveness.
- **Alternatives to research:** Kokoro TTS (new, small, reportedly
  excellent), XTTS v2 (voice cloning), StyleTTS 2.

### ASR (faster-whisper base.en)

- **`medium.en` or `large-v3-turbo`** would cut WER noticeably on
  mumbled queries. Base.en occasionally miss-transcribes
  "sabrina"-adjacent phrases. Cost is ~2x slower; on this hardware
  that's still under 1s. Worth a bake-off.
- **VAD instead of PTT.** Silero VAD detects end-of-utterance well;
  would let Eric drop the PTT key and just talk after a short prefix
  ("hey sabrina..."). Wake-word's adjacent cousin.
- **Streaming partials.** faster-whisper has a streaming API —
  we could start the brain on partial transcript to shave 200-400ms
  off first-token. Low-priority, but there.
- **Alternatives to research:** WhisperX (word-level timestamps +
  diarization), NVIDIA NeMo Parakeet (faster, English-only, reported
  top-of-Huggingface ASR leaderboard), Distil-Whisper (6x faster, 1%
  WER regression).

### Brain (Claude + Ollama, no router)

- **Router.** The roadmap design (fast-path → local → Haiku → Sonnet)
  is still the right shape. Defer until daily cost or offline pressure
  justifies the complexity.
- **Prompt caching.** Anthropic's prompt cache is a 90% discount on
  hits. System prompt + recent memory is a perfect candidate. One-day
  implementation.
- **Tool use.** Not wired up. The Brain protocol has a `tools` slot
  in the original design but our implementation dropped it. Comes back
  in automation component.
- **Budget tracker.** Not built. `AssistantReply` event carries
  `tier` but not `cost_usd`. Three hours of work to add.
- **Alternatives to research:** Gemini 2.x Flash (Haiku competitor,
  different strengths), GPT-5 mini (hedge against one-vendor risk).

### Vision

- **Single-monitor, whole-screen only.** Window capture or region
  crop would be useful ("what's that error in my terminal" when IDE
  is also open). mss supports rectangles; the blocker is getting
  window bounds on Windows (pygetwindow does this).
- **OCR pre-pass.** Skipped intentionally (decision 005). Revisit
  only if token cost becomes painful.
- **Local VLM fallback.** llava or Qwen2.5-VL or Moondream via
  Ollama behind the same `Message.images` interface. Privacy mode /
  offline mode. Open design question flagged at end of decision 005.
- **Screenshot in memory.** Today we store transcript only, not the
  image. Short-term fine; long-term it means Sabrina can't "remember
  what we looked at yesterday". Probably wants a separate
  short-retention image store rather than bloating the SQLite.

### Memory

- **Keyword-only recall.** Current store is linear: load the last N
  turns on startup. No semantic search. The roadmap called for
  sqlite-vec + sentence-transformers; we never built it. Next real
  feature, probably.
- **No summary compaction.** Long sessions accumulate until context
  pressure starts biting. Need a summarizer pass that rolls old
  turns into a summary row.
- **Alternatives to research:** sqlite-vec (roadmap pick) vs.
  LanceDB (newer, fast, still small), ChromaDB (heavier but batteries
  included), plain `rank_bm25` keyword fallback.

### Settings GUI

- **No live reload.** Changes require a restart. customtkinter
  writes the file fine but voice_loop already has `settings` in
  closure. Could publish a `ConfigReloaded` event on the bus.
- **No secrets handling.** API keys live in `.env`; the GUI has no
  UI to edit them. Intentional (keys shouldn't touch TOML) but
  means a first-run setup still needs a terminal.
- **No validation feedback.** Bad values get coerced silently or
  error loudly on save. Would be nicer with inline red text.

### Voice loop

- **No barge-in.** Sabrina finishes speaking before listening.
  Interrupting mid-reply should cut the TTS queue. Component 6
  territory, VAD-dependent.
- **No interrupt-the-brain.** Even if we had barge-in, we'd want
  to cancel the `async for ev in brain.chat(...)` when the user
  starts talking. Needs a `CancelToken` threaded through the brain
  protocol.
- **Error paths are quiet.** Brain errors print and retry; we
  don't surface them through TTS ("I couldn't reach the model").

## Alternatives worth researching (next week's homework)

Cross-cutting list, ordered by likely impact:

1. **openWakeWord** vs keeping PTT. openWakeWord is Apache, runs in
   ~30MB ONNX, and is the de-facto open wake-word model today.
   Porcupine has better FAR but is license-hostile at scale. If Eric
   wants true hands-free, openWakeWord is the call.
2. **Silero VAD** for end-of-turn detection, paired with wake-word or
   PTT. Tiny, fast, accurate. Unblocks barge-in.
3. **Local VLM fallback** (llava 1.6 34B, Qwen2.5-VL 7B, Moondream
   2). Qwen2.5-VL is reportedly the new leader in the 7B class.
4. **Kokoro TTS.** Much buzz lately; reportedly sub-100ms first-audio
   at XTTS-quality. Would replace Piper if it pans out.
5. **Parakeet-TDT or Distil-Whisper** for faster ASR at equivalent WER.
6. **sqlite-vec + all-MiniLM-L6-v2** for semantic memory (roadmap
   choice, just needs building).
7. **Prompt caching** via Anthropic's cache-control blocks. Near-free
   implementation, big cost reduction on repeat system prompts.

## Decisions we should make soon

- **Which way for component 5: wake-word or local VLM?** Flagged at
  end of decision 005. Eric's answer determines next session's focus.
- **Upgrade ASR to medium.en or stay on base.en?** Trivial change,
  measurable quality impact.
- **Build router or skip it indefinitely?** Without it, we can't do
  the roadmap's offline-default mode. With it, we add ~200 lines.

## Ship criterion for "daily driver" readiness

Eric's stated ambition is "personal daily-driver". Honest checklist of
what's missing:

- [ ] Wake word OR a PTT that works from any app (global hotkey works;
      need to verify it doesn't conflict with common apps).
- [ ] Auto-start on login (OS-level, not Python).
- [ ] Crash recovery (supervisor loop; restart on unhandled exception).
- [ ] Barge-in — can't be a daily driver if you can't interrupt her.
- [ ] Budget observability — Eric needs to see cost per day without
      opening the Anthropic dashboard.
- [ ] Avatar — nice-to-have, not required.
- [ ] Automation — nice-to-have, not required for "assistant".

Four of those (wake-word/PTT, autostart, crash recovery, barge-in) are
the real daily-driver gap. Budget is small; avatar/automation are
scope expansions.

## Not broken, not fixed — things to keep an eye on

- **Vision cost.** One Haiku vision call is ~$0.001; 20/day is 60 cents/
  month. Totally fine. Stays fine until vision becomes always-on.
- **Memory file growth.** SQLite grows ~5KB/turn; at 100 turns/day
  that's 1.5MB/month. Fine for years.
- **Piper warmup.** First synth takes ~600ms on a cold process; we
  pre-warm in `run_voice_loop`. Keep an eye on this if TTS backend
  ever gets swapped.

## Where the code lives

```
sabrina-2/
├── src/sabrina/
│   ├── brain/        # protocol.py, claude.py, ollama.py
│   ├── listener/     # ptt.py, whisper.py
│   ├── speaker/      # piper.py, sapi.py
│   ├── memory/       # store.py (sqlite)
│   ├── vision/       # capture.py, see.py, triggers.py, hotkey.py
│   ├── gui/          # settings.py (customtkinter)
│   ├── bus.py, state.py, events.py, voice_loop.py, cli.py, config.py,
│   └── settings_io.py  # tomlkit round-trip
├── tests/test_smoke.py  # 60+ tests, ~3s
├── sabrina.toml         # user config, comments preserved
├── pyproject.toml
└── ...
rebuild/decisions/
    001-hardware-and-budget.md
    002-tts-component-1-shipped.md
    003-voice-loop-shipped.md
    004-settings-gui-shipped.md
    005-vision-shipped.md
    006-end-of-night-status.md    ← you are here
```

## One thing to feel good about

Eric said at the start: "the old project died of over-abstraction". The
rebuild is ~3,500 lines and every line got written because something
concrete needed it. No `ComponentServiceWrapper`, no `LLMInputFramework`,
no 30KB `core.py`. The Brain protocol is 50 lines. The bus is under 100.
The state machine is ~80. Guardrails from the roadmap are holding.

## Next session, pick one

1. **Wake word (openWakeWord)** — biggest UX win; frees hands from PTT.
2. **Local VLM fallback** — privacy + offline story; unblocks
   "offline-first" mode from the roadmap.
3. **Semantic memory (sqlite-vec)** — Sabrina starts actually
   *remembering* Eric instead of just logging him.
4. **Barge-in (VAD + cancellable TTS)** — closes the biggest daily-
   driver gap on the list above.
5. **Budget tracker + prompt caching** — small lift, immediate cost
   reduction, observability win.

Eric gets to pick.
