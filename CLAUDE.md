# Sabrina-Local-AI — Automation Standing Orders

> This file is read at the start of every automated run. If you are reading this as a scheduled task, you are operating under the constraints below. Read this fully before doing anything else.

## What this project is

Personality-forward local-first voice assistant for daily-driver use on Windows. Mic → STT → brain → TTS, with persistent semantic memory, barge-in, wake-word, and a Live2D avatar layer planned. Cortana-style "with you, not toward you" operator voice, defined canonically in `rebuild/decisions/010-personality-spec.md`.

## Stack & conventions

Python 3.12, uv-managed. faster-whisper STT, Anthropic Claude + Ollama brain (with persona-projection layer planned for parity), Piper TTS, sqlite-vec semantic memory with ONNX MiniLM-L6 embedder, Silero VAD + barge-in (CancelToken plumbing through `Brain.chat` / `Speaker.speak`), openWakeWord scaffolded ('hey_jarvis' bundled placeholder, custom 'Hey Sabrina' model training pending). pytest, structlog with redacting + truncating processors, rotating `logs/sabrina.log` sink, schema-versioned config + memory migrations.

## Off-limits

- Do not modify `rebuild/decisions/` files — the decision-doc voice is canon.
- Do not modify the legacy root-level `core/`, `services/`, `utilities/`, `scripts/`, `models/` — these are pre-rebuild and slated for archive (see `rebuild/LEGACY_REPLACEMENT_GATE.md`).
- Do not push to remote unless explicitly approved.
- Do not log secrets — `redact_secrets` structlog processor is in place; any new logger call should respect it.
- Do not modify or extend the pre-commit hook outside its existing scope.

## Definition of done (project-wide)

- All `pytest` tests pass on Windows.
- New behavior has at least one regression test.
- Decision-doc-voice DECISIONS.md entry for any architecturally novel change.
- No new dependencies without justification recorded in ACTION_ITEMS or a decision doc.
- Voice loop validated end-to-end (record sample → STT → brain → TTS) before claiming any voice-loop change ships.
- Edit-tool truncation is a recurring hazard — verify file contents post-edit (AST-parse Python files; spot-check >300 lines for tail integrity).

## Project-specific notes

- Pre-commit hook runs `python -m compileall -q sabrina-2/src` to catch SyntaxError-on-commit.
- ToolSpec MCP migration shipped uncommitted but `ClaudeBrain.chat` doesn't yet pass `tools=` or handle `ToolUseBlock` events (~150 LOC of brain-side wire-up needed before `[tools] enabled = true` actually fires `write_clipboard`).
- 010 personality spec just shipped — operator-voice / no-cheerleading / push-back posture is canonical. Three-condition rule for warmth spike moments: work going well, one sentence max, no relational pivot.
- ONNX embedder is the default in `[memory.semantic.embedder]`; `sentence-transformers` retained as `backend = "sentence-transformers"` legacy fallback.
- Park-style retrieval scoring (`α·recency + β·importance + γ·relevance`) lives in `MemoryStore.search_scored()`; `search()` retains cosine-only ordering.

---

# How automation works in this project

This project runs on a "shift worker" model. Each scheduled run is a different role with one job. You are NOT working on the project all day — you are doing one specific shift, then handing off via the state files.

## State files (read these every run)

- `STATE.md` — current state of the world; 1 page; overwritten by the Planner each morning
- `JOURNAL.md` — append-only log; every run adds an entry
- `QUEUE.md` — prioritized work waiting to be done by Workers
- `PROPOSED.md` — things runs want to do but need human approval first
- `NEEDS-INPUT.md` — questions and blockers waiting for the human
- `DONE.md` — completed items

## Your role

The scheduled task that invoked you specified a role in the prompt. Find your role's instructions in `roles/<role>.md` and follow them. Do not do work outside your role.

Roles available:
- `night-auditor` — read-only audit at midnight (`roles/night-auditor.md`)
- `researcher` — bounded investigation in early morning (`roles/researcher.md`)
- `planner` — synthesizes the day's plan at 7am (`roles/planner.md`)
- `worker` — executes one queued item per run, hourly during morning (`roles/worker.md`)
- `digest` — produces end-of-day summary for human review (`roles/digest.md`)

## Universal rules (apply to every role)

1. **Read STATE.md and JOURNAL.md before doing anything else.** Get oriented.
2. **Append to JOURNAL.md when you finish.** Format: `## [YYYY-MM-DD HH:MM] role-name`, then up to 5 bullets about what you did and what you produced.
3. **If you hit ambiguity, write to NEEDS-INPUT.md and stop.** Do not guess. Do not improvise outside your role.
4. **Never modify code unless your role explicitly allows it.** Most roles propose; they do not execute.
5. **Stay in your lane.** A Researcher does not refactor. A Worker does not start new research. A Night Auditor does not "fix things while I'm in here."
6. **Time-box yourself.** If your role is taking dramatically longer than expected, stop, write what you have to JOURNAL and NEEDS-INPUT, and exit cleanly.
7. **No silent failures.** If something didn't work, JOURNAL it. The human reads JOURNAL during evening review.

## Working style (Eric's, applies everywhere)

- Operator voice. No cheerleading. Direct, no hedging.
- Anti-sprawl: don't create files unless they earn it.
- Ship-one-validate-next: validate on Windows before queuing next ship.
- Decision-doc voice in all DECISIONS.md entries.

## Don't

- No emoji unless asked.
- No status reports without an action.
- No new dashboards/files without explicit ask.
- No README/docs proactively.
- Do not propagate the pre-commit hook beyond Sabrina-Local-AI in Phase 1.

## Automation status

Sabrina automation went live 2026-04-28. Nine scheduled tasks (`sabrina-night-auditor`, `sabrina-researcher`, `sabrina-planner`, `sabrina-worker-8am`–`sabrina-worker-12pm`, `sabrina-digest`) registered via Cowork's scheduled-tasks MCP. Times in `schedule.json` are local-time. The Eva-validation-week task-registration freeze previously listed in this file is no longer in effect — it was lifted on 2026-04-28 when Sabrina's own automation was bootstrapped.
