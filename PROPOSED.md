# Proposed — Sabrina-Local-AI

> Things scheduled runs want to do but need human approval before execution. Triaged in the evening review window. Approved items graduate to QUEUE.md by the next Planner run.

## How approval works

- Check the box `[x]` to approve. The next Planner run will move it to QUEUE.md with appropriate priority.
- Strike through (or delete) to reject.
- Annotate with `[needs-discussion]` if you want to talk it through before deciding.

## Format

```
- [ ] [proposed-by: role / YYYY-MM-DD] Title
  - Why: ...
  - What it would do: ...
  - Risk / blast radius: ...
  - Suggested priority: P0 | P1 | P2
```

---

- [ ] [proposed-by: pre-automation-prep / 2026-04-28] Commit the ToolSpec MCP migration
  - Why: CLAUDE.md notes the migration "shipped uncommitted." Until it's in git, every Worker reads STATE describing code that may not exist on the current branch. Closes the state-vs-reality gap.
  - What it would do: stage just the ToolSpec MCP migration files (`to_anthropic_dict()` / `to_mcp_dict()` and tests), commit separately from any other in-flight work, leave the ClaudeBrain wire-up for the existing P1 queue item.
  - Risk / blast radius: low. Pure additive; no callers of `tools=` exist yet (that's the next item). Pre-commit `compileall` already in place.
  - Suggested priority: P1

- [ ] [proposed-by: pre-automation-prep / 2026-04-28] Commit the ONNX embedder swap
  - Why: STATE.md says ONNX is the default `[memory.semantic.embedder]` backend "shipped uncommitted." sentence-transformers retained as legacy fallback per CLAUDE.md. Same state-vs-reality gap as above.
  - What it would do: stage just the embedder swap (config default + ONNX backend module + the new regression tests), commit separately. Leave the rest of the working tree alone.
  - Risk / blast radius: medium. The semantic-memory layer is critical-path; swap is supposedly already shipped, but a fresh commit means the pre-commit hook re-runs `compileall` and any reviewer can see the diff cleanly. If memory tests pass on Windows, ship.
  - Suggested priority: P1

- [ ] [proposed-by: pre-automation-prep / 2026-04-28] Add ToolSpec.to_anthropic_dict / to_mcp_dict round-trip tests
  - Why: CLAUDE.md notes the ToolSpec "exposes both `to_anthropic_dict()` and `to_mcp_dict()` for forward-compat" — but there's no documented round-trip test. The existing P1 wire-up item depends on Anthropic dict shape being correct. Closing this loop unblocks that item.
  - What it would do: small new test file under `sabrina-2/tests/` exercising both serializers and asserting round-trip equivalence. ~30-60 minutes, well-scoped, no production-code change.
  - Risk / blast radius: very low. Test-only, no runtime path.
  - Suggested priority: P2

- [ ] [proposed-by: pre-automation-prep / 2026-04-28] Split the queued ClaudeBrain wire-up into two Worker-sized items
  - Why: the current QUEUE P1 (verbatim: "Wire ClaudeBrain.chat to pass tools= and handle ToolUseBlock events (~150 LOC), enabling write_clipboard ToolSpec end-to-end. Definition of done: write_clipboard fires from a real voice turn; tests pass; ToolSpec.to_anthropic_dict round-trips. Notes: ToolSpec MCP migration already shipped uncommitted; brain side is the missing wire-up.") is realistically 2-3 hours including tests and Windows e2e validation. Per planner.md, queue items should fit in one Worker run (~1 hour). Today's first Worker is likely to bail with `[in-progress]` on this one.
  - What it would do: replace the single P1 with two: (a) "ClaudeBrain.chat accepts `tools=` kwarg and emits ToolUseBlock-shaped events" + unit tests; (b) "wire `write_clipboard` handler end-to-end + Windows voice-loop validation per validate-automation.md."
  - Risk / blast radius: zero — this is a queue restructure, not a code change. Improves Worker throughput on day one. If QUEUE has shifted by the time the human approves this, treat the verbatim quote above as the canonical version of the item being split.
  - Suggested priority: P1 (both halves)

