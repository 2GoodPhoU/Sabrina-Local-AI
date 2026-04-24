# Sabrina AI (rebuild)

Personal daily-driver voice assistant. Windows desktop. Local-first (Ollama +
Qwen 2.5) with Claude as the cloud reasoning tier.

**Status:** Phase 0 - foundation skeleton. No voice yet. Text REPL only,
against either the Claude API or a local Ollama model.

Build plan lives in [`../rebuild/ROADMAP.md`](../rebuild/ROADMAP.md).

## Quick start

```powershell
# 1. Install uv (one-time)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Install deps + create venv
uv sync

# 3. Set up secrets
copy .env.example .env
# Edit .env and paste your ANTHROPIC_API_KEY

# 4. Chat via Claude
uv run sabrina chat

# 5. Or chat via local Ollama (requires `ollama serve` running)
uv run sabrina chat --brain ollama
uv run sabrina chat --brain ollama --model qwen2.5:7b

# 6. Run tests
uv run pytest
```

## Layout

```
sabrina-2/
  src/sabrina/
    __init__.py         # package
    __main__.py         # python -m sabrina
    cli.py              # typer CLI entry
    config.py           # typed config (pydantic-settings)
    logging.py          # structlog setup
    events.py           # event types (pydantic)
    bus.py              # async pub/sub
    state.py            # state machine
    chat.py             # REPL loop
    brain/
      __init__.py
      protocol.py       # Brain protocol + message types
      claude.py         # Claude backend
      ollama.py         # Ollama backend
  tests/
    test_smoke.py       # smoke tests
  sabrina.toml          # main config
  .env                  # secrets (gitignored)
  .env.example          # template
```

## Design rules

- One process, one config (`sabrina.toml` + `.env`).
- Every capability publishes/consumes typed events on the async bus.
- `Brain` is a protocol with swappable implementations. The rest of the code
  never knows which backend answered.
- No module over 300 lines without a comment explaining why.
