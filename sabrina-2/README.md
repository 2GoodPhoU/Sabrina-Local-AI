# Sabrina AI 2.0

Personal daily-driver voice assistant for Windows. Local-first (Ollama +
Qwen 2.5) with Claude as the cloud reasoning tier. Rebuilt from scratch
after the original grew past the point of "I know how it works" —
anti-sprawl guardrails and component-first shipping are the organizing
principles.

## Status

Eight of nine planned components shipped plus bonuses — voice loop with
PTT + streaming TTS + ASR + Claude/Ollama brains, vision, semantic memory,
settings GUI, and barge-in. Nine decision docs filed. ~4,200 lines,
57 tests running in ~3 s.

| # | Component | Status | Decision |
|---|---|---|---|
| 0 | Foundation (uv, pydantic-settings, structlog, typer) | ✅ | 001 |
| 1 | TTS (Piper + SAPI fallback) | ✅ | 002 |
| 2 | ASR (faster-whisper base.en) | ✅ | 003 |
| 3 | Wake word | ⏭ replaced by PTT | — |
| 4 | Brain protocol (Claude + Ollama) | ✅ | 003 |
| 5 | Event bus + state machine | ✅ | 003 |
| 5.5 | Settings GUI (customtkinter) | ✅ | 004 |
| 6 | Avatar | ❌ deferred | — |
| 7 | Memory (SQLite + sqlite-vec + MiniLM-L6) | ✅ | 007 |
| 8 | Vision (mss + Claude) | ✅ | 005 |
| 9 | Automation | ❌ deferred | — |
| — | Foundational refactor (schema + log redaction + file sink) | ✅ | 008 |
| — | Barge-in (Silero VAD + CancelToken) | ✅ | 009 |

Roadmap, progress notes, and "what's next" live in
[`../rebuild/ROADMAP.md`](../rebuild/ROADMAP.md). Decision log is in
[`../rebuild/decisions/`](../rebuild/decisions/).

## Quick start

```powershell
# 1. Install uv (one-time)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Install deps + create venv
uv sync

# 3. Set up secrets
copy .env.template .env
# Edit .env: paste ANTHROPIC_API_KEY and (if the binary isn't on PATH)
# SABRINA_TTS__PIPER__BINARY pointing at piper.exe.

# 4. Install Piper voice (first run only)
powershell -ExecutionPolicy Bypass -File .\install-piper.ps1
uv run sabrina tts-download libritts_r-medium

# 5. Chat (text REPL)
uv run sabrina chat                           # via Claude
uv run sabrina chat --brain ollama            # via local Ollama

# 6. Voice loop (hold right-Shift to talk, Ctrl+C to quit)
uv run sabrina voice

# 7. Settings GUI (live-editable sabrina.toml)
uv run sabrina settings

# 8. Tests
uv run pytest -q
```

## CLI cheat sheet

| Command | What it does |
|---|---|
| `sabrina chat` | Text REPL against the configured brain. |
| `sabrina voice` | Full voice loop: PTT → ASR → brain → streaming TTS. |
| `sabrina settings` | Live-editable GUI over `sabrina.toml`. |
| `sabrina config-show` | Print the merged config (useful for verifying env overrides). |
| `sabrina tts "hello"` | One-shot speak. |
| `sabrina tts-voices` | List available Piper voice presets. |
| `sabrina tts-download <preset>` | Fetch a voice model into `voices/`. |
| `sabrina tts-compare "hello"` | Speak the same sentence through every model in `voices/`. |
| `sabrina asr-record` | Record a short clip and transcribe (ASR smoke). |
| `sabrina memory-stats` | DB row counts, embedding coverage, vec dim. |
| `sabrina memory-reindex [--drop]` | Backfill embeddings; `--drop` for model changes. |
| `sabrina memory-search "query"` | Show semantic hits (tune `max_distance` / `top_k` here). |
| `sabrina look "question"` | One-shot screen capture + question to Claude vision. |

## Layout

```
sabrina-2/
  src/sabrina/
    __init__.py            # package
    __main__.py            # python -m sabrina
    cli.py                 # typer CLI — entry for every `sabrina <verb>`
    config.py              # Settings (pydantic-settings) + migration hook
    logging.py             # structlog + redaction + rotating file sink
    settings_io.py         # tomlkit-based round-trip (preserves comments)
    chat.py                # text REPL
    voice_loop.py          # voice loop: PTT → ASR → brain → streaming TTS
    events.py              # typed event definitions (UserMessage, etc.)
    bus.py                 # async pub/sub
    state.py               # 5-state machine (idle/listening/thinking/speaking/acting)
    brain/
      protocol.py          # Brain + CancelToken + Message + StreamEvent
      claude.py            # Anthropic backend
      ollama.py            # Ollama backend
    listener/
      protocol.py          # Listener + Transcript
      ptt.py               # push-to-talk via pynput + sounddevice
      whisper.py           # faster-whisper backend
      record.py            # one-shot capture for ASR smoke
      vad.py               # Silero VAD + AudioMonitor (barge-in)
    speaker/
      protocol.py          # Speaker + SpeakResult
      piper.py             # Piper binary via subprocess
      sapi.py              # Windows SAPI fallback
      voices.py            # voice preset registry + download
    memory/
      store.py             # SQLite + sqlite-vec
      embed.py             # Embedder protocol + sentence-transformers impl
    vision/
      capture.py           # mss → Pillow → PNG bytes
      see.py               # one-shot Claude vision query
      triggers.py          # phrase + hotkey triggers
      hotkey.py            # global-hotkey arm/consume
    gui/
      settings.py          # customtkinter settings window
  tests/
    test_smoke.py          # ~57 tests, ~3 s wall
  voices/                  # downloaded Piper voice models (gitignored)
  tools/piper/              # Piper binary + espeak-ng data (gitignored)
  data/                    # SQLite DB (gitignored)
  logs/                    # rotating app logs (gitignored)
  sabrina.toml             # main config (comments preserved)
  .env                     # secrets (gitignored)
  .env.template            # copy and fill in
  install-piper.ps1        # Piper binary installer
  pyproject.toml           # deps + uv + pytest config
```

## Design rules

- One process, one config (`sabrina.toml` + `.env` for secrets).
- Every capability publishes/consumes typed events on the async bus.
- `Brain`, `Speaker`, `Listener` are `Protocol`s with swappable
  implementations. The rest of the code never knows which backend
  answered.
- No module past 300 lines without a comment in the header explaining
  why.
- No new abstraction until the second caller exists.
- Additive protocol extensions over new protocols
  (`Message.images`, `cancel_token` are the canonical patterns).
- Secrets live in `.env`, never in `sabrina.toml`.
- Ship-one-before-next: no component starts until the previous one is
  in main with a smoke test.

Full working-style notes and the one-per-component decision docs are
in [`../rebuild/`](../rebuild/).

## Troubleshooting

**"`piper` binary not found on PATH."** Either add
`tools\piper\` to your PATH, or set `SABRINA_TTS__PIPER__BINARY` in
`.env` to the absolute path of `piper.exe`. Running
`install-piper.ps1` prints the correct path.

**`sqlite-vec` won't load.** Your Python was built without
`enable_load_extension`. The fix is uv-managed Python:
`uv python install 3.12 && uv sync --python 3.12`. See
[`../rebuild/validate-007-windows.md`](../rebuild/validate-007-windows.md).

**`uv run pytest` uses the wrong venv after copying the folder.**
Windows pip console scripts bake the install-time Python path into
their launcher stub. If `pytest --version` or any other `uv run <tool>`
call reports an unexpected path, nuke and re-sync:
`Remove-Item .\.venv -Recurse -Force; uv sync`.

**Barge-in self-triggers on your own voice.** Raise `dead_zone_ms` to
500 or `threshold` to 0.6 in `[barge_in]` before disabling the feature.
Full tuning procedure in
[`../rebuild/validate-barge-in.md`](../rebuild/validate-barge-in.md).
