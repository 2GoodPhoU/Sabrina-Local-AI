# P2.6 — Crash-recovery supervisor (validation + decision doc) — spec

**Date:** 2026-05-07
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 2 → **P2.6 Crash-recovery supervisor — implement + ship** (`[windows-required] [P1] [M]`).
**Predecessors:**
- `rebuild/drafts/supervisor-autostart-plan.md` (2026-04-23, "ready-to-ship draft") — covers both autostart (P2.4/P2.5) and supervisor (P2.6) under one umbrella; treat as canonical design.
- `rebuild/drafts/research/2026-05-06-autostart-approach.md` (researcher 2026-05-06 03:30) — ratifies Task Scheduler for P2.4 and surfaces six XML-template tightening follow-ups. Read-only consumer here.
- Commit `acd6725` (Eric, 2026-05-05 08:43, in DONE.md) — landed `sabrina-2/src/sabrina/supervisor.py` (317 lines: `run_supervised`, `_RestartBudget`, `render_task_scheduler_xml`, `install_task_scheduler_task`, `uninstall_task_scheduler_task`, `find_nssm`, `build_nssm_install_commands`, `build_nssm_uninstall_commands`, `default_child_argv`) plus 8 supervisor unit tests at `tests/test_smoke.py:1436-1614` plus `[supervisor]` config block in `sabrina.toml`.
- `roles/spec-writer.md` step 5 (partial-DoD framing) — names mixed-surface explicitly.

**Scope:** Windows-required validation + tightening. **The implementation has already shipped.** This spec sharpens the queue entry from "build the supervisor primitive" to "validate the supervisor primitive on Eric's box, optionally tighten the six XML follow-ups researcher 2026-05-06 03:30 surfaced, file decision doc." Same posture the planner 2026-05-06 07:00 used to sharpen P2.5 from "implement install + uninstall scripts" to "validate `sabrina autostart enable/disable` on Eric's box + tighten XML template" — the description was post-hoc relative to in-tree code.

Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`. Off-scope: re-implementing what `acd6725` already shipped; pre-staging P2.5 (already specced in queue); the nssm Service mode (covered in plan but deferred per "Service-mode manual smoke deferred unless Eric asks").

---

## What this item is

The QUEUE entry's DoD says "build the supervisor primitive `drafts/` already designs; verify it restarts `sabrina voice` after a forced kill" with "supervisor module in `sabrina-2/src/sabrina/` (location TBD by impl) restarts the voice loop within 5 s of a forced exit." That description is post-hoc against the current tree: `acd6725` already shipped `supervisor.py` with `run_supervised` (the spawn-and-watch loop with crash budget + exponential backoff), the Task Scheduler XML rendering and install/uninstall, and the nssm command-builder helpers — total 317 lines, mirroring `supervisor-autostart-plan.md`'s "spawn → reap → restart on unhandled exit with a budget" design verbatim. The 8 unit tests at `test_smoke.py:1436-1614` cover the supervisor's exit-on-clean-child, restart-within-budget-then-give-up, user-interrupt-returns-immediately, backoff-cap-at-60s, Task Scheduler XML render + UTF-16 BOM write + schtasks invocation, and nssm command-sequence shape. The Linux gates are GREEN (compileall + AST + unit tests pass). What remains is purely Eric-side Windows validation: a real `sabrina run` session that supervises a `sabrina voice` subprocess through one forced kill cycle and one restart-budget-exhausted cycle, plus a decision doc that ratifies the choice. The "5-second restart" target named in the queue entry is a Windows-runtime measurement that can't be made from a Linux sandbox.

## Proposed approach

**Validation steps Eric runs on his i7-13700K/4080/Win11 box (the entire spec's deliverable):**

- **Step 1 — Forced-kill recovery (~5 min).** Open a PowerShell terminal in the project root. `uv run sabrina run` to start the supervisor + voice subprocess. In a second PowerShell, `Get-Process python` to confirm two python processes (supervisor parent + voice child). `Stop-Process -Id <voice_pid> -Force` to simulate a hard crash. Watch `logs/supervisor.log` and the running PowerShell — supervisor logs `supervisor.child_exit rc=...`, then `supervisor.backoff seconds=2.0 consecutive=1`, then `supervisor.spawned`. Confirm a new child PID appears in `Get-Process python` within 5 seconds of the kill. The "5-second" target is `restart_backoff_s = 2` (config default) plus subprocess startup; if it lands at 4-6 seconds the gate is met. If it lands >10 seconds, that's a backoff-config tuning question not a code defect — file as PROPOSED, don't reset the gate.
- **Step 2 — Restart-budget exhaustion (~5 min).** Same setup. `Stop-Process` the voice child five times in rapid succession (within 60 seconds; the rolling-window default is `restart_window_s = 60`, max 5 crashes per window per `SupervisorConfig` defaults — confirm via `cat sabrina-2/sabrina.toml | Select-String supervisor`). On the sixth kill, supervisor should log `supervisor.budget_exceeded crashes=6` and exit with rc 2. Confirm the parent python process is gone via `Get-Process python`. This validates the budget logic; the unit test covers the math, but only Windows-runtime confirms the signal flow.
- **Step 3 — Clean-exit propagation (~3 min).** `uv run sabrina run`. Press Ctrl+C in the PowerShell. Supervisor should log `supervisor.child_exit rc=...` with one of the user-interrupt rcs (per `_USER_INTERRUPT_RCS = {0, 130, 3221225786, -2}`) and exit cleanly without restart. Confirm both python processes are gone. This validates the Windows `CTRL_C_EVENT` propagation path that the unit test stubs out.
- **Step 4 — Compose with autostart (~3 min, optional but high-leverage).** If P2.5 has been validated this same session: `sabrina autostart enable` to register the Task Scheduler task. Reboot. After login, `Get-Process python` within 30 seconds should show a supervisor + voice. `logs/supervisor.log` should show one `supervisor.spawned` line near the login timestamp. Forced-kill the voice child once and confirm respawn (per Step 1) — this is the integration test that the supervisor + autostart compose correctly. This is the load-bearing test for daily-driver readiness item #3.
- **Step 5 — Optional XML template tightening per researcher 2026-05-06 03:30's six follow-ups.** From `research/2026-05-06-autostart-approach.md`: (1) `RestartOnFailure` block in the Task Scheduler XML (currently absent — let Task Scheduler restart the supervisor itself if the supervisor crashes, separate from the supervisor restarting its child); (2) `Priority` audit (current value `7` = below-normal; confirm Eric wants normal-priority audio I/O); (3) `UserId` substitution check on non-domain-joined Win11 (the current XML template substitutes `{user_id}` — verify `whoami` output works as `UserId`); (4) `Hidden` cosmetic (currently `false`; flip if Eric prefers no console window flash on login); (5) `RunOnlyIfIdle` paranoia test (confirm absence — should NOT be set; Sabrina runs always); (6) task-name uniqueness knob (currently hard-coded `SabrinaAI`; consider exposing via `[supervisor].task_name` if Eric wants multiple instances). All six are opt-in polish; spec-writer recommends pulling **only #1 (RestartOnFailure)** since it's the only one with a defect-class consequence (without it, supervisor crash = no recovery; Task Scheduler can paper over it). The other five are cosmetic / paranoia / future-flexibility.
- **Step 6 — Decision doc (~30 min).** File `rebuild/decisions/0XX-crash-recovery-supervisor.md` in decision-doc voice covering: (1) the design (spawn-and-watch + crash budget + exponential backoff + user-interrupt fast path); (2) what was deliberately NOT built (watchdog health pings, telemetry / Sentry, cross-platform autostart, restart-on-config-change); (3) the validation results from Steps 1-4 (with PIDs and timestamps as evidence); (4) the optional Step 5 XML follow-up status (which were applied vs. deferred); (5) reference to `supervisor-autostart-plan.md` as predecessor + reference to `autostart-approach.md` for the Task Scheduler choice. Number is the next free integer in `rebuild/decisions/` — 011 is reserved for v1.0 release per `roles/spec-writer.md`'s no-modify rule on existing decisions, so this lands at the appropriate slot in the 0XX sequence (Eric picks the number when filing).

**What the (a)-half partial-DoD posture says here:** P2.6 is `[windows-required]`. Steps 1-4 are all Windows-runtime. Step 5 is technically Linux-runnable (the XML template lives in `supervisor.py` and changes can be unit-tested under Linux per the existing `test_task_scheduler_xml_renders_with_paths_and_user` pattern), but its value is gated on the Step 1-4 validation actually surfacing a defect class that the tightening would fix. **No Linux-only diff lands as a partial-DoD ship for P2.6.** Step 5 is bundled with the Windows session.

## What's deliberately NOT in scope

- **nssm Service-mode validation.** `supervisor-autostart-plan.md`'s "Service-mode manual smoke deferred unless Eric asks; Task Scheduler covers the declared daily-driver use case" still applies. The nssm command-builders shipped (and have unit tests) but the Service-mode validation is not part of P2.6.
- **Re-implementing or re-designing supervisor.py.** The implementation matches the plan; no change needed unless Step 1-4 surface a specific defect.
- **Watchdog health pings.** Plan-explicit "Out of scope" carry-over. Supervisor reacts to process exit only.
- **Cross-platform autostart.** Plan-explicit "Out of scope" carry-over. Windows-only this session.
- **`[supervisor].task_name` config knob.** One of the six XML follow-ups; spec-writer recommends deferring per Step 5 commentary.
- **Setting up a Windows-runner CI.** Out of band; CLAUDE.md's Linux-vs-Windows mismatch is a separate axis covered in the partial-DoD tier.
- **The one open question in the plan ("nssm license + redistribution. OK to mirror `install-piper.ps1`'s download-on-demand pattern?").** Plan defers to Eric's call. Spec-writer recommends: keep the download-on-demand precedent; do NOT redistribute nssm.exe in the repo. This question is Service-mode-relevant and is not blocking P2.6.

## Dependencies

- **`acd6725` already in `main`** — supervisor.py + tests + sabrina.toml `[supervisor]` block + cli `sabrina run` verb all shipped. Confirmed via DONE.md 2026-05-05.
- **P2.5 NOT a hard dependency.** P2.5 is "validate `sabrina autostart enable/disable` on Eric's box + tighten XML template." P2.6 Steps 1-3 only need `sabrina run` (the supervisor verb), not `sabrina autostart` (the registration verb). Step 4 is the integration step that benefits from P2.5 having shipped first; recommend Eric run P2.5 + P2.6 in the same Windows session.
- **`research/2026-05-06-autostart-approach.md`** — read-only reference for the six XML-template follow-ups. Not blocking; the validation can ship without applying any of them.
- **`logs/supervisor.log`** — needs to be writable; defaults to `logs/supervisor.log` per `[supervisor].log_path`. Confirm via `Test-Path logs/` before Step 1.
- **No new pip deps.** Pure stdlib + existing `subprocess` + `schtasks.exe` (built into Windows).
- **Off-limits per CLAUDE.md unchanged.**

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable Windows checklist)

**Full DoD (this is `[windows-required]` — no partial-DoD tier applies):**

1. Step 1 (forced-kill recovery) executed; voice child respawns within ≤10 seconds; `logs/supervisor.log` shows the `supervisor.child_exit` → `supervisor.backoff` → `supervisor.spawned` sequence; PIDs captured for the decision doc.
2. Step 2 (budget exhaustion) executed; supervisor exits with rc 2 after the 6th kill; `logs/supervisor.log` shows `supervisor.budget_exceeded crashes=6`.
3. Step 3 (clean exit on Ctrl+C) executed; both processes gone; rc lands in `_USER_INTERRUPT_RCS`.
4. Step 4 (compose with autostart) executed if P2.5 validated this session — supervisor + voice come up within 30 s of login; one forced-kill respawn cycle confirmed. **OR** noted as deferred to a P2.5+P2.6 joint session (mark step as N/A in the decision doc).
5. Step 5 (optional XML tightening) — at minimum, evaluate whether `RestartOnFailure` is worth adding. If yes, the change is a 4-line XML template addition + one unit test (the spec author's recommendation, not a hard gate); if no, document the choice in the decision doc.
6. Step 6 — `rebuild/decisions/0XX-crash-recovery-supervisor.md` exists in decision-doc voice, names PIDs/timestamps from Steps 1-3 as evidence, references `supervisor-autostart-plan.md` and `autostart-approach.md` as predecessors.
7. `pytest sabrina-2/tests/test_smoke.py -k supervisor or task_scheduler or nssm` → 8/8 PASS on Eric's Windows runner. No regressions vs. the Linux baseline.
8. `python -m compileall sabrina-2/src` clean on Windows.
9. Voice loop validated end-to-end on the same Windows session per CLAUDE.md ("record sample → STT → brain → TTS"). This is sanity-check that supervisor wrap doesn't perturb the voice loop's first-audio latency.
10. Daily-driver readiness item #3 in `rebuild/ROADMAP.md` flips to `[x]` (Eric's edit).
11. QUEUE.md P2.6 promotes from `[ ]` to `[done]`; DONE.md gets the entry.
12. Commit lands on `main` via Eric's normal client (the decision doc + any optional XML tightening); no `automation/` branch path here since this is a Windows-side human-led ship.

## Open questions for NEEDS-INPUT

**Q1 — Step 5 scope: ship `RestartOnFailure` opt-in or skip the entire XML tightening pass?**

- **(a) Apply only `RestartOnFailure` (researcher 2026-05-06 follow-up #1).** Adds a `<RestartOnFailure>` block to the Task Scheduler XML template so the OS itself restarts the supervisor if the supervisor crashes (separate from the supervisor restarting its child). 4-line XML addition + one unit test. Cost: small. Benefit: defense-in-depth — without it, if `run_supervised` itself raises (not the child), there's no recovery.
- **(b) Apply all six follow-ups in one pass.** RestartOnFailure + Priority audit + UserId check + Hidden + RunOnlyIfIdle + task-name knob. Cost: ~200 LOC of XML/test/config changes; bundles cosmetic with structural in one decision doc. Benefit: closes the entire researcher follow-up list.
- **(c) Skip all six; ship the validation alone.** Cost: zero code change. Benefit: the decision doc is purely about validation results, not template polish. The follow-ups become a separate P2.6.1 item if/when defect classes surface.
- **Spec recommendation: (a).** The `RestartOnFailure` follow-up is the only one that prevents a recovery-failure class (supervisor itself crashing) that the current code doesn't cover. The other five are cosmetic, paranoia, or future-flexibility — all defensible deferrals. Eric can pull this for the same Windows session as the validation; the diff is small enough to ride along on the decision doc commit.

**Q2 — Decision doc number: file as next free integer or reserve a sub-number?**

- **(a) Next free integer in `rebuild/decisions/`.** If 010 is the latest and 011 is reserved for v1.0 release, this lands at 011 + 1, conflicting with the v1.0 reservation. Concrete answer is "whatever's next when filed" — Eric picks at filing time.
- **(b) Sub-number under decision 003 (voice-loop-shipped).** Treats supervisor as a 003 follow-up since it wraps the voice loop. Cost: breaks the flat-numbering precedent.
- **(c) Sub-number under decision 008 (foundational-refactor-bundle).** Treats supervisor as part of the foundational infrastructure. Cost: same as (b).
- **Spec recommendation: (a).** The flat-numbering precedent is load-bearing; sub-numbering would be the first deviation. Use the next-free integer **excluding the v1.0 reservation slot**; if 011 is taken, this is 012. Eric picks at filing time, not before. This question is informational, not blocking.

Both questions written to `NEEDS-INPUT.md` per the spec-writer role doc; neither is a Worker blocker (Worker can't pull `[windows-required]` items anyway, so the questions only matter for Eric's session prep).

## Bailout / not-yet conditions

- **If `acd6725` somehow does NOT contain `supervisor.py` on Eric's box** (working-tree drift between sandbox view and Eric's client), this spec is invalid and a fresh spec for "actually build supervisor.py" is needed. Spec mitigation: Eric runs `git log --oneline -5 sabrina-2/src/sabrina/supervisor.py` first; if the file doesn't exist, abort and refile under the original P2.6 "implement" framing.
- **If `sabrina run` is not registered as a CLI verb in `cli.py`** (the verb has to exist for `sabrina run` to invoke `run_supervised`), the validation is blocked on a CLI gap. Spec mitigation: Eric runs `sabrina --help` first; if `run` is not listed, that's a new P2.6.0 cli-verb item, not a validation step. Confirmed by inspection of `cli.py:1048-1051` references that supervisor mode/config wiring exists; `sabrina run` verb existence should be confirmed by Eric pre-flight.
- **If P2.5 validation surfaces a Task Scheduler XML defect** that breaks the at-logon path, P2.6 Step 4 is blocked but Steps 1-3 + 5 + 6 are independent. Spec mitigation: split the decision doc into "supervisor validated, autostart pending" and re-file when P2.5 is unblocked.
- **If the supervisor's restart logic surfaces a defect during Step 1 or 2** (rather than confirming the design), the spec exits to NEEDS-INPUT — that's a P2.6 fix that needs Eric's call on the fix scope, not a quiet patch.
