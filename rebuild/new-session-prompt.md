# New-session paste-in prompt

**When to use this:** you're starting a fresh Claude session on this
project (after a context reset, on a new machine, after a project
migration, or with a different agent harness that doesn't auto-read
`CLAUDE.md`).

Copy everything between the two `---` lines below as the first
message. Adjust the "I want to work on" sentence before sending.

---

You're joining Sabrina AI 2.0, a Windows voice-assistant rebuild I
work on as a personal project. Before you do anything else, please
read the following files in this order:

1. `CLAUDE.md` at the repo root — bootstrap context, file map, working
   style, common gotchas.
2. `rebuild/when-you-return.md` — the most-current session state:
   what landed last, what's pending validation, what's queued, and
   what's awaiting my sign-off.
3. `sabrina-2/README.md` — component state table and CLI cheat sheet.
4. `rebuild/ROADMAP.md` — progress-at-a-glance, architecture diagram,
   "pick one" menu for the next session.
5. Your persistent memory index (`MEMORY.md`) — the project,
   architecture, working-style, and migration-gotcha memories carry
   forward from prior sessions.

Work style: anti-sprawl (no new abstraction until the second caller
exists; no module past 300 lines without justification), decision doc
per shipped component, ship-one-validate-next, terse prose, atomic
commits. Match the voice of `rebuild/decisions/002-*.md` through
`009-*.md` for any new decision doc.

Once you've read those, let me know where we left off and what the
natural next steps are. Then I'll tell you what I want to work on
this session.

---

## Notes

- The prompt above is deliberately short. Details live in the linked
  files — the agent reads them once and has everything.
- If you want the agent to start on a specific task, append one more
  sentence after the "Then I'll tell you" line:
  *"Tonight I want to <X>."*
- On resumed sessions where `MEMORY.md` is already populated, the
  agent usually has enough context from memory alone that you can
  skip steps 4–5 of the reading list. Use judgment.
- If Claude is already connected via Claude Code or Cowork mode with
  `CLAUDE.md` auto-reading, this prompt is redundant — the bootstrap
  happens for free.
