# CLAUDE.md — working on Sabrina AI

You are picking up a personal passion project. This file is the
fastest path from "clean session" to "useful contributor." Read it
straight through (~5 minutes), then follow the bootstrap sequence at
the bottom.

## What Sabrina is

A Windows voice assistant Eric uses as a daily driver. Push-to-talk
(right-Shift) → ASR (faster-whisper) → brain (Claude by default,
Ollama for offline) → streaming TTS (Piper, sentence-by-sentence).
Plus vision (mss → Claude), semantic memory (sqlite-vec + MiniLM-L6),
a customtkinter settings GUI, and mid-reply barge-in (Silero VAD +
cooperative CancelToken). ~4,200 lines, 57 tests running in ~3 s.

It's a second-generation rebuild. The original project grew past the
point of "I know how it works" — `core.py` ~700 lines,
`component_service_wrappers.py` ~2000, state machine ~600. The rebuild
equivalents are ~80 to ~300 lines, and every abstraction has to
justify itself with a second caller before it earns its own file.

## Where the code and docs live

```
Sabrina-Local-AI/
├── CLAUDE.md                    # you are here
├── README.md                    # top-level landing page + pointers
├── sabrina-2/                   # THE CODE. Python package + tests.
│   ├── README.md                #   current-state component snapshot
│   └── src/sabrina/             #   brain/, listener/, speaker/, memory/, vision/, gui/, voice_loop.py ...
├── rebuild/
│   ├── ROADMAP.md               # component progress + "what's next" menu
│   ├── when-you-return.md       # CURRENT session state — start here every time
│   ├── decisions/001–009-*.md   # one write-up per shipped component
│   ├── validate-*.md            # per-component Windows validation procedures
│   └── drafts/                  # plans awaiting Eric's sign-off + code
├── core/, services/, docs/, tests/, ...  # LEGACY pre-rebuild code. Marked inline.
```

Everything Eric asks about is almost certainly in `sabrina-2/` or
`rebuild/`. Ignore the legacy folders unless he references them
explicitly; they're fossils.

## How Eric works (match this)

- **Decision doc per shipped component.** Every non-trivial addition
  gets a write-up in `rebuild/decisions/NNN-*.md`. Match the voice of
  002–009: terse prose, bullets sparingly, "thin spots" section at the
  end, "alternatives worth researching" list.
- **Anti-sprawl, enforced.** No new abstraction until the second caller
  exists. No module past 300 lines without a justification in the
  header. No new top-level folders when an existing one fits. Past
  abstractions that weren't immediately needed are the reason the
  original project died.
- **Ship-one-validate-next.** A component doesn't count as done until
  it's in main with a smoke test and a `validate-*.md` procedure.
  Don't start the next one until the previous is green on Eric's box.
- **Additive protocol extensions** over new protocols. `Message.images`,
  `system_suffix`, `cancel_token` are the pattern — a new kwarg with a
  `None` default beats a new protocol every time.
- **Atomic commits per component step.** Not per function, not per
  file — per meaningful step.
- **Terse prose.** No report-style formatting unless asked. Bullets
  only when the content is genuinely multi-item. Short sentences.
- **Secrets live in `.env`, never in `sabrina.toml`.** Loaded via
  `SecretStr`. The settings GUI hides `SecretStr` fields by convention.

## Common gotchas you WILL hit

1. **Copied `.venv` → stale console scripts.** Windows pip wrappers
   (`pytest.exe`, `sabrina.exe`, etc.) bake the install-time Python
   path into their launcher stub. If the project folder was copied
   (migrated, restored, etc.) and `uv run <tool>` reports a wrong
   `sys.executable`, nuke and re-sync:
   `Remove-Item .venv -Recurse -Force; uv sync`.
2. **`pre-commit` not in venv.** Until `uv add --dev pre-commit && uv
   run pre-commit install` runs, every commit needs
   `git commit --no-verify`. Known thin spot.
3. **`sqlite-vec` needs `enable_load_extension`.** Some Windows Python
   distributions compile it out. Fix: `uv python install 3.12 && uv
   sync --python 3.12`. See `rebuild/validate-007-windows.md`.
4. **OneDrive breaks venvs.** If the project is under OneDrive, expect
   sync conflicts on binary files (models, onnx, sqlite DB). Eric has
   moved off OneDrive; don't move it back.
5. **Hardcoded absolute paths in `.env`.** `SABRINA_TTS__PIPER__BINARY`
   is the canonical example. After any move, check `.env` for stale
   absolute paths.

## Tools you should and shouldn't reach for

**Reach for these:**
- `Read`, `Edit`, `Write`, `Glob`, `Grep` — the file tools are all you
  need for 95% of work.
- `mcp__workspace__bash` — for running python, git, ls. Note: `.git`
  may not be visible through the FUSE mount; git commands often fail
  silently. Ask Eric to run git.
- `AskUserQuestion` when ambiguous, but don't ask to re-establish
  context that's in the memory or in this file.

**Avoid these unless needed:**
- Computer-use (screenshot/click). Terminals are tier-"click" only;
  you can't type. Use bash or the file tools.
- Creating new files. Default to editing existing ones — new files
  are the anti-sprawl enemy.
- Creating new abstractions. Always look for a "second caller exists"
  before abstracting.

## Bootstrap sequence (do this every session)

1. **Read [`rebuild/when-you-return.md`](rebuild/when-you-return.md).**
   This is the single most current document — it tells you what the
   last session ended on, what needs validation, what's queued, and
   what's awaiting Eric's sign-off.
2. **Skim [`sabrina-2/README.md`](sabrina-2/README.md) and
   [`rebuild/ROADMAP.md`](rebuild/ROADMAP.md).** The README gives you
   the component state table and CLI cheat sheet; the ROADMAP has the
   progress-at-a-glance grid and the architecture diagram.
3. **Check `MEMORY.md` in your persistent-memory directory.** The
   memory index points at the project, architecture, working-style,
   and migration-gotcha files. They carry forward across sessions.
4. **Only then** ask Eric what he wants to do. Don't re-ask for
   context he's already paid for (who he is, what Sabrina is, what the
   guardrails are) — that's in here.

## When Eric says "continue" or "let's keep going"

He means pick up where the last session stopped, per
`rebuild/when-you-return.md`. If validation is pending, run through
the gating `validate-*.md`. If not, surface the "Next session — pick
one" menu from the ROADMAP and ask which path (infra-first vs.
character-first, typically).

## When Eric describes a new problem

First ask whether it's a bug, a component to ship, or a thin-spot
polish. For components, start with a plan in `rebuild/drafts/` that
has a "Recommendations-attached pattern" — 2–4 open questions with
your suggested default and the rationale, so Eric's review is
eyeball-speed. Only after sign-off do you code.

## What to save to memory

Surprises, corrections, validated judgment calls. Not code patterns,
not git history, not conventions that are derivable from the repo.
See the memory-system instructions in your system prompt for the
full taxonomy.
