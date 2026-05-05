# State — Sabrina-Local-AI

> Overwritten by the Planner each morning. One page max. Reflects the current state of the world as of the last Planner run.

## Last updated

2026-05-05 07:00 (planner)

## Current focus

Phase 3 (a)-half ClaudeBrain wire-up is **code-complete in the working tree, blocked on a stale `.git/index.lock`** (5+ days old, mtime 2026-04-29 14:15:52 UTC). worker-9am 2026-05-04 wrote and Linux-tested the diff — protocol.py + claude.py + ollama.py + 6 unit tests, all 6 PASS, the 4 ToolSpec round-trip tests at `test_smoke.py:1872-1965` continue to PASS — but bailed on the commit step per role-doc policy ("Do NOT delete the lock"). Eric clearing the lock is the single highest-leverage unblock. Even with the lock still in place, **today's Workers have four other Linux-runnable Next-pull-ready items to choose from** (P5.2 / P5.4 / P5.5 / P2.1), so today is the first plausibly-productive Worker slot in 7 days.

## Open threads

- **(a)-half wire-up commit (P1, `[in-progress]`)** — code in-tree, Linux gates GREEN, blocked on stale `.git/index.lock`. NEEDS-INPUT entry from worker-9am 2026-05-04 09:00 still open (option (a) commit tonight, (b) tomorrow's Worker, (c) revert + redo).
- **(b)-half wire-up (P1, `[ ] [windows-required]`)** — parked for Eric's Windows session per Partial-DoD tier; promotion to `[done]` couples to the (a)-half.
- **Next-pull-ready Linux-runnable backlog** — four items beyond the (a)-half: P5.2 shortcut-table data port (S), P5.4 test-fixtures port (S), P5.5 pytest scaffolding port (M, **spec just landed at `rebuild/drafts/research/2026-05-05-p55-pytest-scaffolding-port-spec.md`**), P2.1 wake-word training pipeline research (**DoD satisfied this morning** — see below). Workers can pick any of these without waiting on the lock-clear.
- **P2.1 wake-word research DoD satisfied 2026-05-05 03:30** — researcher produced `research/2026-05-05-wake-word-training-pipeline.md` (~270 lines, Recommendation = Go; recommends WSL2 + `piper-sample-generator` wrapper + adopt QUEUE-P2.2's `sabrina-2/models/openwakeword/hey_sabrina.onnx` path). Three new PROPOSED items appended (#32 amend wake-word-plan to recommend WSL2; #33 sandbox-host probe before P2.2; #34 cite upstream acceptance criteria); all unchecked. P2.1 itself should move to DONE in a Worker slot or evening review.
- **Spec-writer 2026-05-05 06:50 produced two new design-note drafts** — P5.5 spec (separates "primitives to port" from "abstractions the rebuild rejected") and P2.7 budget tracker spec (split at the existing P2.7/P2.8 [linux-runnable]/[windows-required] boundary; JSONL persistence; left cost-table location as a NEEDS-INPUT for Eric with spec recommendation = (a) inline constants).
- **NEEDS-INPUT down from 6 to 3 open today** — three `[answered]` entries archived to JOURNAL this run (worker-8am 04-29 DoD fork, night-auditor 04-29 pytest-gate, planner 04-30 day-2 marker; resolved by the 2026-05-04 unblock). Remaining open: night-auditor 04-30 GitHub-MCP, researcher 04-30 bounded-question (de-facto resolved by P2.1 reaching QUEUE; never marked `[answered]`, leaving in place per role-doc), worker-9am 05-04 stale-`.git/index.lock` (load-bearing — clear the lock to unblock the (a)-half commit), spec-writer 05-05 P2.7 cost-table location (Worker can ship against the (a) recommendation without an answer).

## Recent decisions

- 2026-05-05 wake-word recommendation (researcher): train inside WSL2 (Eric has Ubuntu + Ubuntu-22.04 installed), use `piper-sample-generator` wrapper (replaces predecessor plan's hand-rolled Piper-binary loop). Predecessor plan's Windows-CPU assumption is wrong against current upstream tooling — `piper-phonemize` has no Windows wheel as of late 2025, and the `automatic_model_training.ipynb` is consolidating around Linux paths.
- 2026-05-05 spec-writer split-authority precedent: P2.7 budget tracker split at the existing P2.7/P2.8 boundary; cost-table location flagged as a NEEDS-INPUT but Worker can ship against the (a) recommendation immediately.
- 2026-05-05 11:00 [automation] new-roles run: spec-writer (06:50) and graduation-sweeper (07:30) registered as scheduled tasks; schedule grew from 9 to 11 daily tasks.
- 2026-05-04 unblock structurally applied (no change since): CLAUDE.md "Partial-DoD tiers" section, planner.md step 3 split-authority, night-auditor.md step 2 dropped-pytest amendment. Three `[answered]` NEEDS-INPUT entries archived to JOURNAL this run.
- No code commits since 2026-04-28 automation scaffold. The (a)-half wire-up is in-tree but uncommitted, blocked on the stale lock.

## Known constraints

- **Stale `.git/index.lock`** (mtime 2026-04-29 14:15:52 UTC) blocks any `git add` in the working tree. (a)-half wire-up code is intact; Eric clears the lock per worker-9am NEEDS-INPUT options (a/b/c) to unblock the commit. Workers cannot self-clear per role doc.
- **Working-tree triage still gating** any code-touching commit on the dirty files. `brain/claude.py` +279 dirty (134 personality + ~145 wire-up by worker-9am), `voice_loop.py` +33 dirty, `.pre-commit-config.yaml` dirty, ` D write_test.txt` deleted-not-staged. Surgical hunk extraction reserved for human-led work per PROPOSED #5.
- **Linux-sandbox / Windows-runtime mismatch** still gates Windows-required items. Partial-DoD tier handles this for everything except voice-loop runtime, audio I/O, clipboard, mss/pynput/pyperclip paths, and pywin32-only modules.
- **GitHub MCP not connected** in scheduled-task sessions. Night-auditor PR-audit step skips, planner step 6 skips, worker push-back-verification skips. Existing NEEDS-INPUT entry from 2026-04-30 02:37 covers it.
- **Off-limits per CLAUDE.md unchanged**: `rebuild/decisions/`, legacy root-level `core/`/`services/`/`utilities/`/`scripts/`/`models/`, no pushes to `main`/`master`, no force-pushes, no new logger calls without `redact_secrets`. Pre-commit hook scope is fixed.
- **State-file hygiene debt** — JOURNAL.md has duplicate/triplicate 2026-05-04 entries from yesterday's heredoc-recovery sequence (PROPOSED #29, #30, #31); QUEUE.md (a)/(b) entries were duplicated in old lines 41–53 (deduped this run); the original 2026-05-04 16:45 digest JOURNAL entry is truncated mid-word at line 370 (canonical complete copy is at line 388). Cleanup is human-led per PROPOSED #29.
