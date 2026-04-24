# Sabrina AI

Personal daily-driver voice assistant for Windows. Local-first (Ollama +
Qwen 2.5) with Claude as the cloud reasoning tier.

This repository holds two generations of the project:

- **`sabrina-2/`** — the current rebuild. Nine decisions shipped, ~4,200
  lines, 57 tests, MVP voice loop alive. Read
  [`sabrina-2/README.md`](sabrina-2/README.md) for component status and
  quickstart; read [`rebuild/ROADMAP.md`](rebuild/ROADMAP.md) for the
  component-by-component progress notes and the "what's next" menu.
- **Everything else at this level** — the original codebase (`core/`,
  `services/`, `docs/`, `tests/`, etc.). Pre-rebuild; kept in tree as
  reference while the rebuild catches up to feature parity. Marked with
  `## Legacy` headers on the docs. Will be pruned when `sabrina-2/`
  closes the last two components (avatar, automation) and the
  supervisor + autostart infra ships.

## Start here

```powershell
cd sabrina-2
uv sync
copy .env.template .env   # then fill in ANTHROPIC_API_KEY
uv run sabrina voice      # hold right-Shift to talk, Ctrl+C to quit
```

Full quickstart, CLI cheat sheet, layout, and design rules in
[`sabrina-2/README.md`](sabrina-2/README.md).

## If you're picking this up in a new session

Read [`CLAUDE.md`](CLAUDE.md) at the root of this repo — it's the
short-form bootstrap that points Claude (or any agent) at the right
docs in the right order. Then [`rebuild/when-you-return.md`](rebuild/when-you-return.md)
for the current session state.

## Why two generations

The original project "died of over-abstraction" — `core.py` grew past
700 lines, a `component_service_wrappers.py` hit 2000, and the state
machine lived in a 600-line file. The rebuild's equivalents are ~80 to
~300 lines; every abstraction has to justify itself with a second
caller before it earns its own file. Component-first, decision-doc
per ship, validation procedure per component. See
[`rebuild/`](rebuild/) for the detailed approach and guardrails.

## License

MIT.
