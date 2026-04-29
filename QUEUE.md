# Queue — Sabrina-Local-AI

> Prioritized work waiting to be picked up by Workers. The Planner curates this each morning. Workers pick the top unchecked item.

## Format

Each item:

```
- [ ] [P0|P1|P2] Title — one-sentence description.
  - Definition of done: ...
  - Notes: ...
```

Use `[in-progress]` instead of `[ ]` if a Worker started but couldn't finish (with a note in NEEDS-INPUT.md about what blocked them).

---
- [ ] [P1] Wire ClaudeBrain.chat to pass tools= and handle ToolUseBlock events (~150 LOC), enabling write_clipboard ToolSpec end-to-end.
  - Definition of done: write_clipboard fires from a real voice turn; tests pass; ToolSpec.to_anthropic_dict round-trips.
  - Notes: ToolSpec MCP migration already shipped uncommitted; brain side is the missing wire-up.
