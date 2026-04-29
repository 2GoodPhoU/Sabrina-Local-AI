# State — Sabrina-Local-AI

> Overwritten by the Planner each morning. One page max. Reflects the current state of the world as of the last Planner run.

## Last updated

(none yet — bootstrap)

## Current focus

Wire ClaudeBrain tool-use plumbing so write_clipboard ToolSpec fires end-to-end. Validate barge-in stays clean under load.

## Open threads

- 010 personality spec shipped; needs Ollama-side parity via persona-projection layer (deferred until first dogfood week confirms drift).
- Wake-word scaffolded with `hey_jarvis` placeholder; custom "Hey Sabrina" model training is a known one-day task (WSL2 + 4080 GPU).
- ONNX embedder swap shipped uncommitted; legacy sentence-transformers retained as fallback.
- Pre-commit `compileall` hook installed; first SyntaxError catch is the success metric.

## Recent decisions

- 010 personality spec promoted to Shipped (2026-04-26).
- ONNX embedder is the default (`[memory.semantic.embedder] backend = "onnx"`).
- Tool-use ToolSpec exposes both `to_anthropic_dict()` and `to_mcp_dict()` for forward-compat.

## Known constraints

- Sabrina automation went live 2026-04-28 (9 scheduled tasks: night-auditor, researcher, planner, 5 workers 08:00–12:00, digest). Eva-validation-week registration freeze was lifted as of that date.
- Pre-commit hook is Sabrina-only; do not propagate to Bot Arena or Process-Tools yet.
