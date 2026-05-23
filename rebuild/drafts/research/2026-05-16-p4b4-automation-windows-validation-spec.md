# P4.B4 — Automation Windows e2e validation + quartet decision doc — spec

**Date:** 2026-05-16
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Automation → **P4.B4 Automation — Windows e2e validation + decision doc + ship** (`[windows-required] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-05-08-p4b1-automation-safety-primitives-spec.md` (spec-writer 2026-05-08 06:50) — the (a)-half primitives shipped against (a)+(a)+(a) by worker-9am 2026-05-08 are in the lock-blocked tree (`automation/kill_switch.py` + `automation/dry_run.py` + `automation/scaffold.py` + `claude.py` dispatch poll-points + 18 unit tests). § "(b)-half — Windows DoD" of that spec names this validation surface but does not enumerate the run sequence.
- `rebuild/drafts/research/2026-05-09-p4b2-send-hotkey-toolspec-spec.md` (spec-writer 2026-05-09 06:50) — the (a)-half shipped by worker-10am 2026-05-14 is in the lock-blocked tree (`tools/hotkey.py` + conditional `BUILTIN_TOOLS` gate + 14 unit tests). § "(b)-half — folded into P4.B4" of that spec names the real-keypress check but defers ordering and decision-doc shape.
- `rebuild/drafts/research/2026-05-09-p4b3-destructive-action-allowlist-spec.md` (spec-writer 2026-05-09 06:50) — the (a)-half shipped by worker-11am 2026-05-14 is in the lock-blocked tree (`automation/allow_list.py` + `ToolSpec.destructive` field + `claude.py` block branch + 16 unit tests). § "(b)-half — folded into P4.B4, NOT deliverable here" of that spec defers the real `send_hotkey`-blocked-vs-unblocked validation.
- `rebuild/drafts/research/2026-04-26-threat-model.md` — automation threat model. Calls out kill-switch as the single most load-bearing primitive; destructive-action gate as the second; dry-run as the third. P4.B4 is the empirical proof those three are in fact load-bearing under a real keystroke.
- `ROADMAP.md` § "Phase 4" — most-dangerous-component-last; § "Gate 1 — Component completeness" item 10 (Automation) is what P4.B4 closes.
- Commit `acd6725` (Eric, 2026-05-05 08:43, in DONE.md) — the Phase 3 (a)-half tool wire-up + ToolSpec round-trip tests that the (a)-half quartet builds on.
- `roles/spec-writer.md` step 5 (partial-DoD framing) — names mixed-surface explicitly. P4.B4 is `[windows-required]`; no partial-DoD tier applies.

**Scope:** Windows-required validation of three safety primitives + one real-action ToolSpec under one real keypress, then a single decision doc ratifying the automation surface. **The (a)-half implementations are already in the lock-blocked tree** as of worker shifts 2026-05-08 + 2026-05-14; P4.B4's scope is purely Eric-side: clear the `.git/index.lock`, land the lock-blocked pile, wire `voice_loop.py` to thread `KillSwitch` + `settings` + `dry_run` into `ClaudeBrain.chat`, validate four behaviors on Eric's box (real keypress, kill-switch mid-flight, destructive-action block, dry-run logging), file the quartet decision doc, flip `[tools] send_hotkey_enabled = true`.

Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, no force-pushes, no remote rewrites. Off-scope: re-implementing what the four (a)-halves already shipped; staging the second-real-action tool (`launch_app`, `open_file` — separate items); building telemetry beyond the existing structlog lines; NSSM service-mode validation (separate axis).

---

## What this item is

The QUEUE entry's Full DoD reads: "real keypresses fire correctly via pyautogui/pynput; kill-switch hotkey aborts a running action mid-flight; destructive-action guard refuses an attempt; `pytest` passes; voice loop validated; decision doc filed." That is the gate, but it leaves four interlocking questions Eric would have to interpret before starting:

1. **What does "voice loop validated" mean concretely when the voice loop hasn't yet been wired to instantiate `KillSwitch` or pass `settings=` through to `ClaudeBrain.chat`?** The (a)-halves added the kwargs and the dispatch-loop poll-points, but `voice_loop.py` still calls `chat(...)` without them. A Worker who pulled "P4.B4" today and read the (a)-half specs would correctly conclude the validation can't fire end-to-end until `voice_loop.py` threads the new pieces — but no spec calls out the wiring delta as part of P4.B4 vs. as a fifth (a)-half that landed quietly.
2. **In what order does the validation run, and what is the smallest possible exercise of each leg?** Running "fire a real keypress" naïvely puts a real `<ctrl>+<alt>+c` into whatever app is focused; that's recoverable but messy. The kill-switch test requires a handler that runs long enough to be aborted — `send_hotkey` finishes in ~10 ms, too fast to trip mid-flight without a sleep shim.
3. **What is the decision doc actually ratifying?** Three safety primitives + one real-action tool + the destructive-action gate is too much for one decision doc to cover in detail; either it ratifies the *architecture* (the three legs) and pushes per-tool detail to the existing specs, or it has to bloat to multi-section length. The existing decision-doc voice and length (003/008/009 are ~120-180 lines) suggests the former.
4. **What is the rollback gate if something fails mid-validation?** The (a)-half primitives ship `enabled = false` by default; nothing in `sabrina.toml` flips on unless Eric explicitly does so. If real-keypress validation surfaces a defect, `[tools] send_hotkey_enabled = false` is the rollback — the destructive-action gate stays active independent of the tool flag. The decision doc should document this rollback shape.

P4.B4 is the single closeout that answers all four. The (a)-halves did their jobs; the (b)-half is the empirical proof and the architecture ratification.

## Proposed approach

**Validation steps Eric runs on his i7-13700K/4080/Win11 box (the entire spec's deliverable):**

- **Step 0 — Pre-flight (~5 min).** Confirm the in-tree state matches the spec assumption. Run `git status --short | findstr "automation\|tools/hotkey\|brain/claude\|destructive\|test_automation_safety\|test_send_hotkey_tool\|test_destructive_allow_list"` — expect the 12 lock-blocked file modifications + new files listed. Run `git log --oneline -1 sabrina-2/src/sabrina/brain/claude.py` — confirm `acd6725` (or later) on the file. Confirm `Test-Path .git/index.lock` returns `True` (the FUSE-leaked lock is the gate to clearing). **If pre-flight fails, abort to NEEDS-INPUT — the spec's framing is wrong.**

- **Step 1 — Clear lock + land the (a)-half pile (~10 min).** Run `Remove-Item .git/index.lock`. Verify `git status` works (`fatal: Unable to create '.git/index.lock'` no longer fires). Land the 13-deep lock-blocked pile (12 prior diffs + worker-8am 2026-05-15's role-doc edits, per JOURNAL 2026-05-16 02:37) by following the Suggested-staging notes in each QUEUE item: stay on `automation/worker-2026-05-07-8am`, `git add` per the per-entry file lists, `git commit` per the per-entry messages with `Windows-pending: e2e` bodies. Order is per-Suggested-staging-note independent; recommend the answer-batch-rework items (P4.C2 router rework + P4.B1 hotkey docstring) first so the pile doesn't carry stale framing, then the four B-quartet (a)-halves so this validation runs against the (a)-half implementations as designed. `git push automation/worker-2026-05-07-8am` is informational per CLAUDE.md — pushes are not a DoD gate.

- **Step 2 — `voice_loop.py` wire-up delta (~30 min).** This is the only code change P4.B4 lands beyond the (a)-half pile. Spec calls out the minimal delta:
  1. **Instantiate `KillSwitch` once at voice-loop startup.** Inside `voice_loop.py`'s setup region (where `ClaudeBrain` is constructed), add `kill_switch = KillSwitch(hotkey=settings.automation.kill_switch_hotkey)` and enter its context manager around the main turn loop (or for the lifetime of the loop). Import via `from sabrina.automation.kill_switch import KillSwitch`. ~6 LOC.
  2. **Thread `kill_switch=`, `dry_run=`, `settings=` through `ClaudeBrain.chat`.** At every call site that forwards a brain turn to Claude (voice turn, vision turn, debug turn), pass `kill_switch=kill_switch`, `dry_run=settings.automation.dry_run`, `settings=settings`. Vision-turn callers stay `tools=None` per `acd6725`; the safety kwargs ride along regardless of tool use because the dispatch-loop poll-points are no-ops when `tools=None`. ~6 LOC across 2-3 call sites.
  3. **No `events.py` change for P4.B4.** Kill-switch trip → `ToolUseDone(error="kill_switch_tripped")` per the (a)-half contract; the existing renderer surfaces the error string. The (b)-half tool-loop-cap fold-in from PROPOSED #40 (~45 LOC) is a same-slot pickup checklist item for the ClaudeBrain (b)-half wire-up commit (`research/2026-04-29-claudebrain-tool-wire-up-surface.md` §5/§6) and IS the right place to add a `ToolUseDone` event-bus entry if needed — explicitly out of scope here per "no new `Event` type yet" in the P4.B1 spec.
  4. **Unit test for the wire-up.** Add `test_voice_loop_threads_kill_switch_and_settings` to `sabrina-2/tests/test_smoke.py` (or a new `test_voice_loop_wireup.py` if the voice-loop test surface is missing — confirm via `Grep`). Mocks the brain + speaker + listener; asserts the constructed kwargs reaching the brain. ~25 LOC. Runs under Linux/3.10 + Windows.
  5. **`python -m compileall sabrina-2/src` clean; `pytest sabrina-2/tests` PASS on Windows.** This is the Partial-DoD gate from CLAUDE.md applied to this commit specifically.

- **Step 3 — Real keypress validation (~5 min).** Edit `sabrina-2/sabrina.toml`: `[tools] enabled = true` + `[tools] send_hotkey_enabled = true`. Confirm `[automation] dry_run = false`. Restart `sabrina voice` (no autostart fire — manual launch from PowerShell). Speak: "Sabrina, copy this to my clipboard: hello world." Expected behavior:
  - Brain emits `tool_use(send_hotkey, name="copy")` (existing test surface).
  - `send_hotkey` handler dispatches `<ctrl>+c` via `pynput.keyboard.Controller` on focus.
  - Focused app (open a `Notepad` window with the text "hello world" highlighted as the test target — NOT a code editor; PowerShell will swallow the keypress) receives the keystroke; clipboard now holds the highlighted text.
  - Voice TTS confirms ("copied"). Open `Get-Clipboard` in PowerShell — expect "hello world".
  - `logs/sabrina.log` shows the `tools.send_hotkey` structlog line with `name=copy` payload.
  - Decision-doc evidence captured: timestamp + PID + clipboard read-back.
  
  **Spec-recommended target app:** a Notepad window with one line of text pre-highlighted. Avoids the focus-loss class (PowerShell consumes `<ctrl>+c` as SIGINT; browsers may have OS-level shortcut conflicts on Win11). Test target is the simplest non-conflicting host.

- **Step 4 — Kill-switch mid-flight (~5 min).** This requires a handler slow enough to be aborted. Two options:
  - **(spec-recommended)** Add a temporary `noop_action_slow` ToolSpec to the (a)-half scaffold module under a debug flag (or directly in `automation/scaffold.py`) that calls `await asyncio.sleep(5.0)` then returns the noop success shape. Registers behind `noop_action_enabled = true` (separate from `send_hotkey_enabled`). Speak: "Sabrina, run the noop slow action." After ~1 second, press `<ctrl>+<alt>+k` (the default kill-switch hotkey). Expected: handler raises `KillSwitchTripped`; `claude.py` dispatch emits `ToolUseDone(error="kill_switch_tripped")`; voice renderer says "kill switch" or similar surface message; logs/sabrina.log shows `automation.kill_switch.tripped` line. After validation, **delete** the temporary `noop_action_slow` registration before the decision-doc commit.
  - **(alternative)** Use real-`send_hotkey` and a busy-wait shim. Less safe (the keypress may still fire before trip); spec recommends against.
  
  Capture timestamps + log lines for the decision doc.

- **Step 5 — Destructive-action block (~3 min).** With `[automation] destructive_actions = []` (empty by default), confirm `send_hotkey` (which has `destructive=True` per worker-11am 2026-05-14's (a)-half) is blocked. Speak: "Sabrina, copy this." Expected: brain emits `tool_use(send_hotkey, ...)`; `claude.py` dispatch hits the pre-dispatch `check_allowed` branch from P4.B3 (a)-half; raises `DestructiveActionBlocked`; emits `ToolUseDone(error="destructive_action_blocked")`; voice surfaces the block message; logs show `automation.allow_list.blocked` WARN line with `tool=send_hotkey` + `allow_list=[]` payload. Then edit `sabrina.toml`: `[automation] destructive_actions = ["send_hotkey"]`. Restart `sabrina voice`. Re-speak the same prompt. Expected: handler now fires (per Step 3's success path); clipboard updates. Capture both log lines for the decision doc.

- **Step 6 — Dry-run logging (~3 min).** Edit `sabrina.toml`: `[automation] dry_run = true`. Keep `destructive_actions = ["send_hotkey"]`, `send_hotkey_enabled = true`. Restart. Speak: "Sabrina, copy this." Expected: brain emits `tool_use`; dispatch `dry_run_wrap` wraps the handler; logs show `tools.send_hotkey.dry_run` with `would_have_called=send_hotkey` + `input={name: copy}`; clipboard does NOT change (verify with `Get-Clipboard`). Capture the log line. After validation, flip `dry_run` back to `false`.

- **Step 7 — Voice-loop e2e + pytest on Windows (~10 min).** With all three flags in the recommended ship state (`[tools] enabled = true`, `[tools] send_hotkey_enabled = true`, `[automation] destructive_actions = ["send_hotkey"]`, `[automation] dry_run = false`), record one normal 3-turn conversation that does NOT invoke any automation tool — confirm STT → brain → TTS still works end-to-end with the new wiring. Then run `pytest sabrina-2/tests` on Windows — all PASS, including the 14 + 16 + 18 + 30 = 78 new unit tests from the (a)-halves. Capture pytest summary.

- **Step 8 — Quartet decision doc (~45 min).** File `rebuild/decisions/0XX-automation-safety-and-first-action.md` in decision-doc voice. Spec recommends covering: (1) the architecture — three safety primitives (kill-switch + dry-run + destructive-action allow-list) gating one real-action class (`send_hotkey`), with the `tools/hotkey.py` data-loaded shortcut table as the v1 vocabulary; (2) the (a)/(b) split posture — primitives ship Linux-runnable under Partial DoD; real keypress + voice-loop integration + the actual flag flip ship together as P4.B4; (3) what was deliberately NOT built — second real-action tool (`launch_app`, `open_file` — Phase 4 follow-ups); telemetry/analytics; cross-platform automation (Windows-only); kill-switch hot-reload (restart required to pick up new `kill_switch_hotkey`); (4) the validation results from Steps 3-7 with PIDs/timestamps/log lines as evidence; (5) the rollback posture — `[tools] send_hotkey_enabled = false` rolls back the real-action surface without disabling the destructive-action gate (allow-list and kill-switch stay live); (6) reference to `rebuild/drafts/research/2026-05-08-p4b1-*.md` + `2026-05-09-p4b2-*.md` + `2026-05-09-p4b3-*.md` as the per-primitive specs. **The decision-doc number is open — see Q2 below; spec recommends the next free integer (per the 005/008/009 precedent), excluding the 011 v1.0 reservation.**

**What the partial-DoD framing says here:** P4.B4 is `[windows-required]`. Step 2's `voice_loop.py` wire-up delta is technically Linux-runnable in isolation (unit test mocks all hardware), BUT its value is gated on Steps 3-7 actually firing on Windows. **No Linux-only diff lands as a partial-DoD ship for P4.B4.** Step 2's wire-up commit + Step 8's decision-doc commit ride together on `main` via Eric's normal client.

## What's deliberately NOT in scope

- **Second real-action ToolSpec** (`launch_app`, `open_file`, etc.). Future Phase 4 items; out of scope here.
- **Telemetry / Sentry / analytics on automation actions.** The structlog lines from the (a)-halves are the v1 observability surface; that's enough for v1.
- **Cross-platform automation.** Windows-only this session per CLAUDE.md's i7-13700K/4080/Win11 hardware tier.
- **`kill_switch_hotkey` hot-reload.** Restart-to-pick-up is fine for v1; live re-binding is plan-explicit out of scope per `kill_switch.py` docstring.
- **Re-implementing or re-designing the (a)-half primitives.** The implementations match their respective specs; no change here unless Steps 3-7 surface a specific defect.
- **PROPOSED #40 tool-loop-cap fold-in (~45 LOC).** That belongs to the ClaudeBrain (b)-half wire-up commit per STATE.md "Open threads" → "(b)-half ClaudeBrain wire-up + Windows-required tail." Out of scope here.
- **Setting up a Windows-runner CI.** Out of band; covered by the Partial-DoD tier in CLAUDE.md.
- **The `noop_action_slow` debug ToolSpec from Step 4** — temporary scaffolding only; removed before the decision-doc commit. Do NOT register it permanently.
- **Bake-in (P6.1) credit.** P4.B4 closes the automation component; the daily-driver bake-in clock counts separately.

## Dependencies

- **`.git/index.lock` cleared.** Step 1 prerequisite per OPEN-DECISIONS S1(a). Without lock-clear, the (a)-half pile sits in working tree and P4.B4 can't run.
- **The four (a)-halves landed on `main` (or on `automation/worker-2026-05-07-8am` and merged):** P4.B1 (kill-switch + dry-run + scaffold), P4.B2 (`send_hotkey` ToolSpec + conditional gate), P4.B3 (destructive-action allow-list + `ToolSpec.destructive`). All three are in the lock-blocked tree per QUEUE.md `[in-progress]` markers from worker shifts 2026-05-08 + 2026-05-14.
- **P4.C2 router warn_threshold field-removal rework** (queued P1 today). Independent of P4.B4 mechanically, but recommended landed first per Step 1's "answer-batch-rework items first" sequence to keep commit-message framing accurate.
- **`logs/sabrina.log` writable.** Existing default per CLAUDE.md; `Test-Path logs/` before Step 3.
- **No new pip deps.** `pynput`, `anthropic`, `structlog`, `pydantic` all already in `pyproject.toml` as of `acd6725`.
- **Off-limits per CLAUDE.md unchanged.**
- **P4.C3 not a hard prerequisite.** P4.C3 wires the router into voice_loop; P4.B4's wire-up edits the same file. If both ship the same session, recommend P4.B4 lands its `voice_loop.py` delta first; P4.C3's router-instantiation swap then composes on top (single instantiate-router call replacing the direct `ClaudeBrain(...)` line). If they ship in separate sessions, document in the decision doc which compose-step is pending.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable Windows checklist)

**Full DoD (this is `[windows-required]` — no partial-DoD tier applies; per CLAUDE.md):**

1. Step 0 pre-flight passed: lock-blocked file pile present in `git status`; `acd6725` (or later) on `brain/claude.py`; `.git/index.lock` present (confirming the lock-blocked state) or already cleared if a prior session ran Step 1.
2. Step 1 (lock-clear + (a)-half pile land) executed: `.git/index.lock` gone; 13 lock-blocked commits landed on `automation/worker-2026-05-07-8am` per the per-entry Suggested-staging notes; each commit carries `Windows-pending: e2e` in the body for the Linux-shipped ones.
3. Step 2 (`voice_loop.py` wire-up) executed: `voice_loop.py` instantiates `KillSwitch`, threads `kill_switch=` + `dry_run=` + `settings=` into `ClaudeBrain.chat`; new unit test `test_voice_loop_threads_kill_switch_and_settings` PASS under Linux/3.10 + Windows; `python -m compileall sabrina-2/src` clean on both platforms; pytest passes on both.
4. Step 3 (real keypress) executed: speak → brain → `send_hotkey(name="copy")` → real `<ctrl>+c` on a focused Notepad window → `Get-Clipboard` returns the expected text. Timestamps + log line captured for the decision doc.
5. Step 4 (kill-switch mid-flight) executed: temporary `noop_action_slow` registered; trip via `<ctrl>+<alt>+k` mid-handler raises `KillSwitchTripped`; voice renderer surfaces the kill-switch message; `automation.kill_switch.tripped` structlog line in `logs/sabrina.log`. Temporary registration removed before commit.
6. Step 5 (destructive-action block) executed: empty `destructive_actions` blocks the keypress (`DestructiveActionBlocked`, `ToolUseDone(error="destructive_action_blocked")`, `automation.allow_list.blocked` WARN); adding `"send_hotkey"` to the list unblocks per Step 3's success path. Both log lines captured.
7. Step 6 (dry-run logging) executed: `dry_run = true` produces the `tools.send_hotkey.dry_run` structlog line; clipboard is unchanged after the prompt. Reverted to `dry_run = false` before commit.
8. Step 7 (voice-loop + pytest) executed: one normal non-automation 3-turn conversation works end-to-end; `pytest sabrina-2/tests` passes on Windows including the 78 new unit tests across the four (a)-halves.
9. Step 8 — `rebuild/decisions/0XX-automation-safety-and-first-action.md` exists in decision-doc voice; names Step 3-7 timestamps + log lines as evidence; cites the three predecessor specs; documents the rollback posture.
10. `sabrina-2/sabrina.toml` final state: `[tools] enabled = true`, `[tools] send_hotkey_enabled = true`, `[automation] destructive_actions = ["send_hotkey"]`, `[automation] dry_run = false`, `[automation] kill_switch_enabled = true`. Committed alongside the decision doc.
11. Daily-driver readiness item — none directly (P4.B4 isn't on the daily-driver list); Gate 1 component 10 (Automation) in `rebuild/ROADMAP.md` flips to `[x]` (Eric's edit).
12. QUEUE.md P4.B4 promotes from `[ ]` to `[done]`; P4.B1 + P4.B2 + P4.B3 promote from `[in-progress] [linux-runnable] [partial-dod-eligible]` to `[done]`; DONE.md gets the entries.
13. Commit lands on `main` via Eric's normal client (the `voice_loop.py` delta + the decision doc + the toml flag flips); no `automation/` branch path for the decision-doc commit since this is a Windows-side human-led ship.

## Open questions for NEEDS-INPUT

**Q1 — Step 4 kill-switch validation handler: temporary `noop_action_slow` registration vs. busy-wait `send_hotkey` shim vs. skip kill-switch live validation?**

- **(a) Register `noop_action_slow` temporarily** (5 s `asyncio.sleep`, single-use). Cleanest test surface — handler is intentionally slow enough to be trippable; removal is one line. Adds the temporary registration to `automation/scaffold.py` under a `noop_slow_enabled = false` flag, flipped only for this validation. ~15 LOC + revert.
- **(b) Busy-wait `send_hotkey` shim** — re-test by binding a long keystroke sequence (`<ctrl>+<alt>+<shift>+<f1>`...`<f12>`). pynput executes each press/release pair sequentially; total elapsed ~50 ms is too short to trip reliably. Inflate via a synthetic 50-key sequence (~500 ms). Brittle — depends on pynput internal timing — and pollutes the real-action tool's vocabulary with a fake.
- **(c) Skip live kill-switch validation; rely on the 18 P4.B1 unit tests.** The unit tests already cover programmatic `KillSwitch.trip()` → `KillSwitchTripped` → `ToolUseDone(error="kill_switch_tripped")`. The Windows-only piece is the global-hotkey listener firing on a real keypress — that's a `pynput.GlobalHotKeys` smoke test, not a kill-switch correctness test. Could be deferred to a P4.B5 separate item with a smaller scope.
- **Spec recommendation: (a).** Live validation of the trip path with a real keypress is the only piece the unit tests can't cover. The temporary registration is ~15 LOC + one config flag + one revert commit — small surface, small blast radius. (b) is brittle; (c) leaves the load-bearing primitive (per `2026-04-26-threat-model.md`) without an empirical Windows test.

**Q2 — Decision-doc number and bundling: one combined "automation safety + first action" doc, or split per-primitive?**

- **(a) One combined doc at the next free integer (per 005/008/009 precedent), excluding the 011 v1.0 reservation.** Covers the three safety primitives + `send_hotkey` + the architecture under one number. ~150-200 lines (modeled on 008/009 length). Maintains flat-numbering precedent.
- **(b) Four separate decision docs** — one per (a)-half spec, plus this one. ~60-80 lines each × 4 = 240-320 lines total. Maintains the per-spec/per-doc symmetry but burns four decision numbers on a single architectural surface.
- **(c) Bundle with the v1.0 release doc (011)** — defer to P6.5. Saves the number but couples P4.B4's close-out to v1.0's, which means Gate 1 component 10 can't `[x]` until the whole release ships.
- **Spec recommendation: (a).** The three primitives + one tool are one architectural surface; one decision doc reads cleaner than four. Flat-numbering is load-bearing through 010; this lands at the next free integer (likely 012 or 013 depending on P2.5 + P2.6 sequencing). (b) over-fragments; (c) couples unrelated gates.

Both questions written to `NEEDS-INPUT.md` per the spec-writer role doc. Neither is a Worker blocker — P4.B4 is `[windows-required]` and can't be pulled by a Linux-sandbox Worker anyway; the questions only matter for Eric's session prep. The spec recommendations (a)+(a) are safe defaults: Eric can ship against them without waiting.

## Bailout / not-yet conditions

- **If Step 0 pre-flight fails** (lock-blocked pile not present, or `acd6725` not on `brain/claude.py`), the spec's "(a)-halves already in tree" framing is wrong. Abort to NEEDS-INPUT and re-spec under the original P4.B4 "implement + ship" framing.
- **If Step 1 lock-clear surfaces new lock-leak instances** (e.g. removing `.git/index.lock` produces a new one on the first subsequent `git` op), OPEN-DECISIONS S3 (forensic carve-out for `roles/worker.md` step 7) is the load-bearing prevention — confirm the queued P1 carve-out item has shipped first. If not, defer P4.B4 until after the carve-out lands; otherwise the validation session itself will leak a new lock.
- **If Step 2 wire-up unit test fails under Linux/3.10**, the wire-up is structurally wrong and the spec's "additive in `voice_loop.py`" assumption is off. File as PROPOSED; treat as a separate P4.B4.0 wire-up-fix item, not part of P4.B4's gate.
- **If Step 3 real keypress fires but the wrong app receives it** (focus stolen by another window mid-test), retry with `taskkill /im chrome.exe` (or whichever) + clean Notepad-only desktop. Not a code defect; just a focus-management note for the decision doc.
- **If Step 4 kill-switch doesn't trip** despite `<ctrl>+<alt>+k` (e.g. another global handler intercepts), confirm via `Get-Process | Where-Object {$_.Modules.ModuleName -like "*hotkey*"}` whether something else owns the binding. If conflict found, document in the decision doc and flip `kill_switch_hotkey` to the spec-Q1-(b) default (`<ctrl>+<alt>+<shift>+k`) for Eric's machine via `sabrina.toml`.
- **If Step 5 destructive-action block doesn't fire** (allow-list empty but `send_hotkey` still runs), the `claude.py` pre-dispatch `check_allowed` branch from P4.B3 (a)-half is wrong. File as P0 separate from P4.B4. The (a)-half tests are GREEN under Linux per worker-11am 2026-05-14's JOURNAL; a Windows divergence would be a serious finding.
- **If Step 7 pytest fails on a previously-Linux-GREEN test**, suspect platform-conditional code that wasn't gated correctly. Likely candidates: `_LISTENER_FACTORY` substitution in `kill_switch.py`, `_KEYPRESS_FACTORY` substitution in `tools/hotkey.py`. File the failing test list to PROPOSED; don't ship the decision doc until resolved.
- **If `noop_action_slow` (Q1-(a)) registration leaks past the decision-doc commit** (forgot to remove), file as P1 cleanup item — does not block P4.B4 close-out since the flag defaults to `false`, but it's a hygiene defect.
- **If P4.C3 ships earlier than P4.B4 in Eric's Saturday bundle**, Step 2's `voice_loop.py` delta needs to compose with the router-instantiation pattern P4.C3 introduces (`make_router_from_settings(settings)` returning a `Brain` instance). Re-shape Step 2's wire-up to thread `kill_switch=`/`dry_run=`/`settings=` through the router's `chat()` call (per the `Brain` protocol — the router delegates these kwargs to the underlying Claude/Ollama backend). The router's existing chat signature must accept them; confirm via Read on `brain/router.py` before Step 2.

---

## Quick-reference: what changes if the spec's recommendations all hold

If Q1 = (a) (temporary `noop_action_slow`) and Q2 = (a) (one combined doc at next free integer):

- **Files touched (across the session's commits):**
  - `sabrina-2/src/sabrina/voice_loop.py` — `KillSwitch` instantiation + `kill_switch=`/`dry_run=`/`settings=` threading (~12 LOC).
  - `sabrina-2/tests/test_smoke.py` (or new `test_voice_loop_wireup.py`) — `test_voice_loop_threads_kill_switch_and_settings` (~25 LOC).
  - `sabrina-2/src/sabrina/automation/scaffold.py` — temporary `noop_action_slow` + flag (~15 LOC, reverted before decision-doc commit).
  - `sabrina-2/sabrina.toml` — `[tools] enabled = true`, `[tools] send_hotkey_enabled = true`, `[automation] destructive_actions = ["send_hotkey"]` (~3 line changes).
  - `rebuild/decisions/0XX-automation-safety-and-first-action.md` — new file in decision-doc voice (~150-200 lines per 008/009 precedent).
  - `rebuild/ROADMAP.md` — Gate 1 component 10 (Automation) flipped to `[x]` (Eric's edit).
  - `QUEUE.md` — P4.B4 promoted to `[done]`; P4.B1 + P4.B2 + P4.B3 promoted from `[in-progress]` to `[done]`.
  - `DONE.md` — four new entries (P4.B1 + P4.B2 + P4.B3 + P4.B4).

- **What Eric needs in front of him for the session:** PowerShell + Notepad + 90-120 minutes (Step 0-1 = ~15 min, Step 2 wire-up = ~30 min, Steps 3-7 validation = ~25 min, Step 8 decision doc = ~45 min). One restart of `sabrina voice` between each Step 3-6 flag flip.

- **What does NOT need to happen on Saturday:** Second real-action tool, telemetry/Sentry, cross-platform automation, kill-switch hot-reload, `pynput` upgrade, NSSM service-mode wiring, P4.C3 (composes but does not block). Pure human-led Windows session against a 78-test gate that already runs GREEN under Linux.

- **Composability with P4.C3 (Router voice_loop integration, separate spec).** P4.B4's Step 2 wire-up is the first edit to `voice_loop.py` in Phase 4; P4.C3 swaps `ClaudeBrain(...)` for `make_router_from_settings(settings)` at the same construction site. If P4.B4 lands first, P4.C3's swap is a one-line change against the new construction line + the router's `chat()` signature accepts the safety kwargs unchanged (`Brain` protocol). If P4.C3 lands first, P4.B4's Step 2 lands on top of the router instantiation per the bailout-condition above. Order is flexible; same-session bundling recommended per STATE.md "Eric's Saturday-collapse" framing.
