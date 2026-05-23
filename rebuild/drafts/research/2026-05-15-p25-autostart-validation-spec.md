# P2.5 — Autostart (Task Scheduler) validation + XML tightening — spec

**Date:** 2026-05-15
**Author:** sabrina-spec-writer (later-day scheduled run; morning 06:50 spec-writer 2026-05-14 idle-exited on a caught-up backlog and did not pick this up)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 2 → **P2.5 Autostart — validate `sabrina autostart enable/disable` on Eric's box + tighten XML template** (`[windows-required] [P1] [M]`).
**Predecessors:**
- `rebuild/drafts/supervisor-autostart-plan.md` (2026-04-23, "ready-to-ship draft") — canonical umbrella design for both autostart (P2.4/P2.5) and supervisor (P2.6). Picks Task Scheduler with NSSM service as opt-in.
- `research/2026-05-06-autostart-approach.md` (researcher 2026-05-06 03:30) — ratifies Task Scheduler for P2.4 against Run key / NSSM / shell:startup. Surfaces the **six XML-template tightening follow-ups** this spec sequences.
- `rebuild/drafts/research/2026-05-07-p26-supervisor-validation-spec.md` (spec-writer 2026-05-07 06:50) — sibling spec for P2.6 supervisor validation. Step 4 there expects P2.5 to compose with it; this spec mirrors its structure.
- Commit `acd6725` (Eric, 2026-05-05 08:43, in DONE.md) — landed `sabrina-2/src/sabrina/supervisor.py` (`render_task_scheduler_xml` + `write_task_scheduler_xml` + `install_task_scheduler_task` + `uninstall_task_scheduler_task`) and `sabrina-2/src/sabrina/cli.py:1151–1241` (`sabrina autostart {enable,disable,status}` Typer verbs). XML template at `supervisor.py:160-193`.
- `roles/spec-writer.md` step 5 (partial-DoD framing) — names mixed-surface explicitly; this item is `[windows-required]` so no partial-DoD tier applies.

**Scope:** Windows-required validation + the six XML-template tightening follow-ups + decision doc. **The implementation has already shipped** (`acd6725`); P2.5's remaining scope is Eric's Windows session, NOT a Worker pull. This spec sharpens the queue entry's "(3) optional XML-template tightening per the six follow-ups in `research/2026-05-06-autostart-approach.md`" from an unranked menu into a prioritized recommendation, and replaces the "validate enable/disable + reboot survives" prose DoD with a concrete checklist.

Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, no force-pushes, no remote rewrites. Off-scope: re-implementing what `acd6725` already shipped; pre-staging P2.6 (separately specced); NSSM Service-mode validation (covered in plan but deferred per "Service-mode manual smoke deferred unless Eric asks"); cross-platform autostart.

---

## What this item is

The QUEUE entry's DoD reads: "(1) `sabrina autostart enable` registers the `SabrinaAI` Task Scheduler task on Eric's box and survives reboot … (2) `sabrina autostart disable` removes it cleanly; (3) **optional XML-template tightening per the six follow-ups** in `research/2026-05-06-autostart-approach.md`; (4) decision doc filed." Item (3) is the genuinely fuzzy half: six follow-ups, one of them defect-class (`RestartOnFailure` missing), the other five cosmetic / paranoia / future-flexibility, with no ordering or priority — Eric would have to interpret intent before deciding which to pull. The autostart implementation itself is in `main` as of `acd6725`: `_TASK_XML_TEMPLATE` at `supervisor.py:160-193` (UTF-16-LE BOM XML), `render_task_scheduler_xml` / `write_task_scheduler_xml` / `install_task_scheduler_task` / `uninstall_task_scheduler_task` helpers (lines 196-252), and `sabrina autostart {enable,disable,status}` Typer verbs at `cli.py:1151–1241` shelling to `schtasks /create|delete|query`. Composability with the supervisor primitive (P2.6) is already wired — autostart launches `python -m sabrina run` (the supervisor verb), which then watches the voice subprocess. What remains for P2.5 is purely Eric-side Windows validation plus a yes/no on the six follow-ups plus a decision doc that ratifies the choice.

This spec assumes the planner 2026-05-06 07:00's description-sharpening of P2.5 (per researcher 2026-05-06 03:30's recommendation) is the correct framing: P2.5 is validate-and-polish, not implement.

## Proposed approach

**Validation steps Eric runs on his i7-13700K/4080/Win11 box (the entire spec's deliverable):**

- **Step 1 — Pre-flight (~3 min).** Open PowerShell in the project root. Run `git log --oneline -5 sabrina-2/src/sabrina/supervisor.py` — confirm `acd6725` (or later) shows the file's last touch. Run `sabrina --help` — confirm `autostart` is listed. Run `Test-Path sabrina-2/src/sabrina/supervisor.py` → `True`. Run `Get-ChildItem sabrina-2/sabrina.toml | Select-String '\[supervisor\]'` — confirm the `[supervisor]` block is present. None of these touch state; they confirm the spec's assumption that `acd6725` is what's actually running on the box. **If any pre-flight fails, abort to NEEDS-INPUT — the spec's framing is wrong.**

- **Step 2 — Install + reboot survival (~10 min).** `sabrina autostart enable` from the project root. Expect `schtasks` output `SUCCESS: The scheduled task "SabrinaAI" has successfully been created.` and no Python traceback. Run `sabrina autostart status` — expect the registered task body listed. Run `schtasks /query /tn SabrinaAI /v /fo LIST` independently — confirm the same task. Reboot the box. After login, `Get-Process python` within 30 seconds should show two python processes (supervisor parent + voice child) per the `python -m sabrina run` action wired at install time. `cat logs/supervisor.log` should show one fresh `supervisor.spawned` line near the login timestamp. Capture PIDs + timestamps for the decision doc evidence. **This validates the load-bearing flow.** If the post-login spawn doesn't happen within 60 seconds, run `schtasks /query /tn SabrinaAI /v /fo LIST | findstr "Last Run"` to inspect — Task Scheduler logs its own attempt result independently.

- **Step 3 — Disable + clean removal (~3 min).** `sabrina autostart disable`. Expect `SUCCESS: The scheduled task "SabrinaAI" was successfully deleted.` Run `schtasks /query /tn SabrinaAI` — expect `ERROR: The system cannot find the file specified.` Reboot a second time (only if Eric has the time; not strictly required for the gate but the decision doc benefits from "verified clean both directions"). After login, `Get-Process python` should NOT show the supervisor — confirming uninstall is symmetric.

- **Step 4 — `UserId` substitution on non-domain-joined Win11 (~2 min, paranoia check).** This is researcher 2026-05-06 follow-up #4 inline-validated, not deferred. `cli.py:1175-1183` builds the `user_id` from `USERDOMAIN_ROAMINGPROFILE` → `USERDOMAIN` → `USERNAME` fallback. Eric's box is non-domain-joined, so `USERDOMAIN` is the local machine name. Run `whoami` in PowerShell — output should be `MACHINENAME\Eric` (or similar). After Step 2's `enable`, run `schtasks /query /tn SabrinaAI /xml` and grep the resulting XML for `<UserId>` — confirm the value matches `whoami` output. If they differ, the substitution chain is wrong and Step 2's at-logon trigger may have silently bound to the wrong SID — file as PROPOSED and reset the gate. **This is the highest-risk silent-defect class** in the existing template, and worth burning the 2 minutes.

- **Step 5 — Optional XML template tightening pass.** Six follow-ups from `research/2026-05-06-autostart-approach.md` §"Open follow-ups", ranked here by Eric-effort and defect-class severity:

  1. **`RestartOnFailure` block (follow-up #1) — RECOMMENDED PULL.** Currently absent from `_TASK_XML_TEMPLATE`. If `sabrina run` exits with rc 2 (supervisor budget exceeded) or the supervisor itself crashes before reaching the budget logic, Task Scheduler does nothing — Sabrina stays silent until Eric runs `sabrina run` manually. Adding `<RestartOnFailure><Interval>PT5M</Interval><Count>3</Count></RestartOnFailure>` inside `<Settings>` gives a "try the supervisor again three times at 5-minute intervals before giving up" recovery layer. ~4 LOC in `_TASK_XML_TEMPLATE`, +1 line in `render_task_scheduler_xml` if parameterized, +1 unit test (`test_task_scheduler_xml_includes_restart_on_failure`). Linux-runnable; the diff itself ships under the same Windows session as the decision doc.
  2. **`Priority` audit (follow-up #2).** Current value `7` = below-normal. Voice-loop response time may want normal (`4`) or higher. Validate during Step 2 with a stopwatch: time from voice child PID appearing in `Get-Process` to first wake-word match (use `validate-wake-word.md` if it exists, otherwise `sabrina chat "test"` warm-start time). If first-voice-turn lands >2 s warm relative to a comparable foreground-launched run, flip Priority to `4`. Otherwise leave at `7` — `acd6725` chose it deliberately and the default avoids competing with Eric's foreground work.
  3. **Task-name uniqueness knob (follow-up #6).** Default `SabrinaAI` is hard-coded. Exposing `[supervisor].task_name` for parallel sabrina-2 + future sabrina-3 installs is future-flexibility, not a current need. **Defer unless Eric actually plans a parallel install.**
  4. **`Hidden` cosmetic (follow-up #3).** Currently `false`. Flipping to `true` keeps `taskschd.msc` history less cluttered but makes the task easier to lose track of. Cosmetic; defer unless Eric requests.
  5. **`RunOnlyIfIdle` paranoia (follow-up #5).** Currently absent (schema default `false`). The paranoia test is one line: `assert "<RunOnlyIfIdle>true</RunOnlyIfIdle>" not in xml`. Add the test if the XML template is touched for #1; otherwise defer (no defect class today).
  6. **`UserId` substitution (follow-up #4) — folded into Step 4 above.** Inline-validated, not a deferred polish item.

  **Spec-recommended minimum scope: pull only #1 (`RestartOnFailure`).** Bundle the diff + test + decision-doc-line under one commit; the four-line XML addition rides along on the decision-doc commit. The other four are defensible deferrals — each fixes a "what if" with no current evidence of the underlying class.

- **Step 6 — Decision doc (~30 min).** File `rebuild/decisions/0XX-autostart-task-scheduler.md` in decision-doc voice. Spec recommends covering: (1) the design pick (Task Scheduler over Run key / NSSM / shell:startup, citing `2026-05-06-autostart-approach.md` for the four-way comparison); (2) the install/uninstall surface (`sabrina autostart {enable,disable,status}` + UTF-16-LE BOM XML write); (3) what was deliberately NOT built (Service mode default, cross-platform autostart, custom user-account install); (4) validation results from Steps 1-4 with PIDs and timestamps as evidence; (5) the Step 5 XML-tightening outcome (which of the six follow-ups were applied vs. deferred + why); (6) reference to `supervisor-autostart-plan.md` and `autostart-approach.md` as predecessors. **The decision-doc number is open — see Q2 below; spec recommends "next free integer, excluding the 011 v1.0 reservation."**

**What the (a)-half / (b)-half partial-DoD framing says here:** P2.5 is `[windows-required]`. Steps 1-4 are Windows-runtime measurements (logon trigger, reboot survival, PID inspection, XML `UserId` matching). Step 5 #1's XML template change is Linux-runnable in isolation (the template diff + a new unit test pass under the Cowork Linux/3.10 sandbox), BUT its value is gated on Step 2 actually confirming the at-logon path works AND on Eric's call (Q1 below). **No Linux-only diff lands as a partial-DoD ship for P2.5.** The Step 5 #1 diff, if pulled, is bundled with the Windows session's decision-doc commit — one merge, one validation cycle.

## What's deliberately NOT in scope

- **NSSM Service-mode validation.** `supervisor-autostart-plan.md`'s "Service-mode manual smoke deferred unless Eric asks; Task Scheduler covers the declared daily-driver use case" still applies. NSSM command-builders shipped in `acd6725` with unit tests; Service-mode validation is its own future item.
- **Re-implementing or re-designing the install/uninstall surface.** The implementation matches the plan; no change needed unless Step 1-4 surface a specific defect.
- **Cross-platform autostart.** Windows-only this session per plan and per CLAUDE.md's i7-13700K/4080/Win11 hardware tier.
- **Tightening follow-ups #3/#4/#5/#6 beyond their Step-5 disposition.** Spec recommends defer; Q1's (b) option pulls them all if Eric prefers.
- **Setting up a Windows-runner CI.** Out of band; Linux-vs-Windows mismatch is a separate axis (the partial-DoD tier in CLAUDE.md).
- **The `[supervisor].task_name` config knob exposure.** Future-flexibility, not blocking; deferred per Step 5 #3.
- **Custom service-account install.** Out of scope; the current template binds to Eric's user-context SID via the `USERDOMAIN_ROAMINGPROFILE` → `USERDOMAIN` → `USERNAME` chain.

## Dependencies

- **`acd6725` already in `main`** — `supervisor.py` Task Scheduler helpers + `cli.py:1151–1241` autostart verbs + `sabrina.toml` `[supervisor]` block all shipped. Confirmed via DONE.md 2026-05-05 + the Step 1 pre-flight checks.
- **`research/2026-05-06-autostart-approach.md`** — read-only reference for the Task Scheduler four-way comparison + the six follow-ups Step 5 ranks. Not blocking the validation; required reading for the decision doc.
- **P2.6 (supervisor validation) is NOT a hard prerequisite, but composes.** Spec recommends Eric runs P2.5 + P2.6 in the same Windows session: Step 2's at-logon spawn IS the integration point P2.6's Step 4 wants to validate. If P2.5 and P2.6 land in separate sessions, P2.6's Step 4 has to be re-run after P2.5 lands.
- **`logs/supervisor.log` must be writable.** Default `logs/supervisor.log` per the supervisor's structlog sink. Confirm via `Test-Path logs/` before Step 2.
- **No new pip deps.** Pure stdlib + `subprocess` + `schtasks.exe` (built into Windows).
- **No Linux-sandbox dependencies** beyond what `acd6725`'s unit tests already cover. The 8 supervisor-related unit tests at `tests/test_smoke.py:1436-1614` plus the Task Scheduler XML render tests must continue to PASS under Linux post-Step-5-#1 diff (if pulled).
- **Off-limits per CLAUDE.md unchanged.**

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable Windows checklist)

**Full DoD (this is `[windows-required]` — no partial-DoD tier applies; per CLAUDE.md):**

1. Step 1 pre-flight passed: `acd6725` (or later) shows on `supervisor.py`; `sabrina autostart` is in `--help`; `[supervisor]` block present in `sabrina.toml`.
2. Step 2 (install + reboot survival) executed: `sabrina autostart enable` succeeds; `sabrina autostart status` confirms; reboot → supervisor + voice child appear in `Get-Process python` within 30 s of login; `logs/supervisor.log` shows the fresh `supervisor.spawned` line near the login timestamp. PIDs + timestamps captured for the decision doc.
3. Step 3 (disable + clean removal) executed: `sabrina autostart disable` succeeds; `schtasks /query /tn SabrinaAI` returns `ERROR: The system cannot find the file specified.`
4. Step 4 (`UserId` substitution) executed: `whoami` output matches the `<UserId>` value in `schtasks /query /tn SabrinaAI /xml` post-`enable`. If mismatched, gate is reset and the divergence is filed as PROPOSED.
5. Step 5 (XML tightening) — Q1 answered, the chosen follow-ups applied, the test count for `test_task_scheduler_xml_*` updated accordingly. If Q1 = (a) only #1 is pulled: `_TASK_XML_TEMPLATE` gains the `<RestartOnFailure>` block + 1 new unit test asserting the block renders. If Q1 = (b) all six: a larger diff per #1-#6 with a corresponding test for each. If Q1 = (c) none: no code change, only the decision doc entry documenting the defer.
6. Step 6 — `rebuild/decisions/0XX-autostart-task-scheduler.md` exists in decision-doc voice, names Step 2 PIDs + timestamps as evidence, cites `supervisor-autostart-plan.md` + `autostart-approach.md` as predecessors, documents the Q1 outcome.
7. `pytest sabrina-2/tests/test_smoke.py -k task_scheduler or autostart or supervisor` → all PASS on Eric's Windows runner. No regression vs. the Linux baseline (which is also expected to PASS post-Step 5 #1 diff if pulled).
8. `python -m compileall sabrina-2/src` clean on Windows.
9. Voice loop validated end-to-end ON the same Windows session per CLAUDE.md ("record sample → STT → brain → TTS"). Confirms autostart doesn't perturb the voice loop's first-audio latency.
10. Daily-driver readiness item #2 in `rebuild/ROADMAP.md` flips to `[x]` (Eric's edit).
11. QUEUE.md P2.5 promotes from `[ ]` to `[done]`; DONE.md gets the entry.
12. Commit lands on `main` via Eric's normal client (the decision doc + any Step 5 #1 XML tightening); no `automation/` branch path here since this is a Windows-side human-led ship.

## Open questions for NEEDS-INPUT

**Q1 — Step 5 XML-tightening scope: ship `RestartOnFailure` only, all six follow-ups, or skip entirely?**

- **(a) Apply only `RestartOnFailure` (follow-up #1).** ~4 LOC in `_TASK_XML_TEMPLATE` + 1 unit test (`test_task_scheduler_xml_includes_restart_on_failure`) + 1 line in the decision-doc evidence section. Closes the only follow-up with a defect-class consequence (supervisor itself crashes → no recovery without it). Costs ~30 minutes of session time on top of the validation.
- **(b) Apply all six follow-ups in one pass.** `RestartOnFailure` + `Priority` audit + `UserId` validation (already inline in Step 4) + `Hidden` flip + `RunOnlyIfIdle` paranoia test + task-name knob exposure. ~200 LOC across XML template + config + tests + a `[supervisor].task_name` field in `SupervisorConfig`. Costs ~2 hours; closes the entire researcher follow-up list in one decision doc.
- **(c) Skip all six (Step 4's inline `UserId` check still runs); ship the validation alone.** Zero code change. Decision doc is purely about validation results, not template polish. The follow-ups become a separate P2.5.1 item if/when defect classes surface.
- **Spec recommendation: (a).** `RestartOnFailure` is the only follow-up that prevents a recovery-failure class the current code can't reach. Others are cosmetic / paranoia / future-flexibility — all defensible deferrals. The diff is small enough to ride along on the decision-doc commit; the Windows session that validates Steps 1-4 absorbs Step 5 #1 with no additional re-validation cycle.

**Q2 — Decision doc number for the autostart ratification?**

- **(a) Next free integer in `rebuild/decisions/`, excluding the 011 v1.0 reservation.** If 010 is the latest and 011 is reserved per ROADMAP §"Phase 6" item #6, this lands at 012 (or 013 if P2.6's decision doc lands first and takes 012). Eric picks at filing time. Maintains the flat-numbering precedent.
- **(b) Sub-number under decision 003 (voice-loop-shipped).** Treats autostart as a 003 follow-up since it wraps the voice loop's launch. Breaks the flat-numbering precedent that has held through 010.
- **(c) Bundle with the P2.6 supervisor decision doc into one combined "supervisor + autostart" decision doc.** Mirrors `supervisor-autostart-plan.md`'s umbrella framing. Cost: requires P2.5 + P2.6 to land in the same session; if they split, the doc has to be split or one of them waits.
- **Spec recommendation: (a).** Flat-numbering is load-bearing; sub-numbering would be the first deviation. Bundling (c) is appealing but couples P2.5 and P2.6 unnecessarily — Eric can ship them independently if his Saturday session has time for only one. P2.5 + P2.6 cross-reference each other in their respective decision docs instead.

Both questions written to `NEEDS-INPUT.md` per the spec-writer role doc. Neither is a Worker blocker — P2.5 is `[windows-required]` and can't be pulled by a Linux-sandbox Worker anyway; the questions only matter for Eric's session prep. The spec recommendations (a)+(a) are safe defaults: a Worker who somehow pulled this against (a)+(a) without waiting would ship a sane diff.

## Bailout / not-yet conditions

- **If Step 1 pre-flight fails** (`acd6725` not on `supervisor.py`, or `sabrina autostart` not in `--help`, or `[supervisor]` block absent from `sabrina.toml`), the spec's "implementation already shipped" framing is wrong. Abort to NEEDS-INPUT and re-spec under the original P2.5 "implement install + uninstall scripts" framing.
- **If Step 2's at-logon spawn fails** (no python processes after 60 s post-login), the load-bearing path is broken. `schtasks /query /tn SabrinaAI /v /fo LIST | findstr "Last Run"` reports Task Scheduler's own attempt rc — that diagnoses cleanly. File as PROPOSED with the rc value; do NOT mark P2.5 done; the decision doc is paused until the at-logon path works.
- **If Step 4's `UserId` substitution diverges from `whoami`**, the `USERDOMAIN_ROAMINGPROFILE` → `USERDOMAIN` → `USERNAME` chain at `cli.py:1175-1183` is wrong for non-domain-joined Win11. Spec mitigation: file as PROPOSED with the chain output captured; treat as a separate P2.5.0 cli-fix item, not part of P2.5's gate.
- **If Step 5 #1's diff breaks any existing `test_task_scheduler_xml_*` unit test under Linux**, the change is rejected and the decision doc records "RestartOnFailure deferred — XML template change conflicted with existing test surface; needs a fresh spec." This is unlikely (the new block sits inside `<Settings>` adjacent to existing siblings), but the gate is hard.
- **If P2.6 is validated FIRST without P2.5** (Eric's Saturday has time for only the supervisor-side, not autostart), P2.6's Step 4 (compose with autostart) is N/A in that session's decision doc; P2.5 + a re-run of P2.6 Step 4 ship in the next session. Both decision docs cross-reference. No spec change needed.
- **If `schtasks /create` fails with `0x80041318`** despite the UTF-16-LE BOM write, the `write_task_scheduler_xml` path is subtly broken. Confirm via `Get-Content -Encoding Byte sabrina-2/<task-xml-path> -TotalCount 4` — first two bytes should be `0xFF 0xFE` (BOM). If not, the write path regressed; file as a P0 separate from P2.5.

---

## Quick-reference: what changes if the spec's recommendations all hold

If Q1 = (a) (`RestartOnFailure` only) and Q2 = (a) (next free integer):

- **Files touched (under bundled commit with the decision doc):**
  - `sabrina-2/src/sabrina/supervisor.py` — `_TASK_XML_TEMPLATE` gains 1 `<RestartOnFailure>` block (~4 lines inside `<Settings>`).
  - `sabrina-2/tests/test_smoke.py` — 1 new unit test (`test_task_scheduler_xml_includes_restart_on_failure`).
  - `rebuild/decisions/0XX-autostart-task-scheduler.md` — new file in decision-doc voice (~120-180 lines per the 003/008/009 precedent).
  - `rebuild/ROADMAP.md` — daily-driver readiness item #2 flipped to `[x]` (Eric's edit).
  - `QUEUE.md` — P2.5 promoted to `[done]`.
  - `DONE.md` — new P2.5 entry.

- **What Eric needs in front of him for the session:** PowerShell + `git log` + 30-60 minutes (steps 1-4 = ~18 min; Step 5 #1 diff + test = ~15 min; Step 6 decision doc = ~30 min). One reboot, optionally two.

- **What does NOT need to happen on Saturday:** NSSM Service-mode validation, cross-platform autostart, the other five follow-ups, any Worker pull or PR. Pure human-led Windows session.
