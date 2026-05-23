# Dashboard answer batch (2026-05-15) — rework surface against lock-blocked Worker (a)-halves

## Question

Today's chain entered to a structurally transformed state: between yesterday's 16:45 digest and tonight's 02:37 night-auditor, Eric's dashboard producer wrote 28 `**[answered: <letter> 2026-05-15 via dashboard]**` markers across `NEEDS-INPUT.md`, closing the 21 spec-writer (a)-half decisions consolidated under OPEN-DECISIONS S11(a), the 04-30 GitHub MCP question, the 04-30 researcher menu, the 05-07 lock-bail forensic carve-out question, the 05-07 JOURNAL data-loss recovery ask, the four P4.A1/A2/A3 picks, and the four P4.B1/B2/B3/C1/C2 spec picks.

The bounded question this investigation answers:

> Do the 12 lock-blocked Linux Partial-DoD GREEN Worker (a)-half diffs currently in the working tree cleanly align with Eric's 2026-05-15 dashboard answer batch, and which (if any) require pre-commit rework before Eric clears `.git/index.lock` and the diffs land?

This matters because the lock-clear is OPEN-DECISIONS S1 (top-1 urgent-gating Eric-side action). If a diff requires rework, the Worker that lands it after the lock clears either ships a stale-against-Eric's-letter implementation or has to re-run the (a)-half. Knowing the rework surface ahead of the lock-clear lets tomorrow's planner queue the touch-ups as separate items (or fold them into the lock-clear sweep) instead of discovering them mid-commit.

## What I checked

- `NEEDS-INPUT.md` — full canonical Read+Grep view (29 `^- \[ \]` entries, 28 `**[answered: ... via dashboard]**` markers; 1 unanswered = worker-9am 5/14 09:00 P4.A2 libEGL line 284).
- `STATE.md` (planner 2026-05-14 07:00 overwrite) — to enumerate the canonical lock-blocked diff pile (10 + 2 added by worker-10am + worker-11am 5/14 = 12 total per digest 5/14 16:45).
- `JOURNAL.md` lines 1198-1214 (2026-05-14 16:45 digest + 2026-05-15 02:37 night-auditor) — to ground the answer batch as Eric-side and the producer fire as out-of-band per the 5/14 14:53 wiring.
- `sabrina-2/src/sabrina/automation/kill_switch.py` end-to-end — in-tree shape of P4.B1 (a)-half (worker-9am 2026-05-08).
- `sabrina-2/src/sabrina/automation/allow_list.py` referenced via the working-tree census — in-tree shape of P4.B3 (a)-half (worker-11am 2026-05-14).
- `sabrina-2/src/sabrina/brain/router.py` end-to-end — in-tree shape of P4.C2 (a)-half (worker-11am 2026-05-08).
- `sabrina-2/src/sabrina/config.py` `AutomationConfig` (lines 272-294) + `BrainRouterConfig` (lines 63-86) — config-side shape.
- `sabrina-2/sabrina.toml` `[automation]` (lines 246-249) + `[brain.router]` (lines 36-54) — toml-side shape.
- `sabrina-2/tests/test_router.py` lines 160-398 — tests that pin the `warn_threshold_usd` resolver shape on the (a)-half.
- Cross-referenced each `**[answered:]**` marker's letter against the spec-recommendation line immediately above it (`- Recommendation: (a)` / `(b)` / `(c)`) to classify each as either spec-alignment (Worker (a)-half ships under the same letter Eric chose) or spec-override (Worker (a)-half ships against a different letter than Eric chose).
- Did NOT modify any state file via this investigation. Did NOT run write-side experiments. Did NOT edit code. Read-only per role-doc letter.

## What I found

### Marker tally

Canonical count of `**[answered: ... 2026-05-15 via dashboard]**` markers across `NEEDS-INPUT.md` via the Grep tool: **28 total**, broken down as **21 × A + 6 × B + 1 × C**.

The 5/15 02:37 night-auditor narrated this as "A in 25 cases, B in 3 cases, C in 1 case" — the **B count is off by 3** (actual is 6, not 3). This is the second night-auditor counting drift in the 5/14 → 5/15 window (the first was the 5/14 02:37 NEEDS-INPUT `^- \[ \]` count of 27 vs. canonical 29, reframed by researcher 5/14 03:30 as the FUSE H2 bash-cache lag). The 5/15 02:37 entry does not narrate which channel (bash-grep vs. Read+Grep) produced the 25/3/1 split, but the cross-tool divergence pattern is now well-grounded enough that a re-count via Read tool is the cheap fix; tomorrow's planner's STATE.md narrative should use 21/6/1 rather than 25/3/1. Filed as PROPOSED #44 below.

### Per-letter alignment vs. in-tree (a)-half diffs

**21 A answers — all align with the spec-recommended letter every (a)-half Worker shipped against. No rework needed.** Spot-verified two representative cases by reading the in-tree code:

- P2.7 budget cost-table location (A = inline constants in `budget.py`) — worker-8am 5/6 shipped against (a); confirmed by reading `budget.py:1-50` shape (cost table is a module-level `COSTS` dict, no toml/YAML knob).
- P4.C1 router persona-projection per-rule knobs (A = per-rule knobs in `[brain.persona]`) — worker-10am 5/8 shipped against (a); confirmed via `config.BrainPersonaConfig` Pydantic model + `sabrina.toml` `[brain.persona]` block presence.

The remaining 19 A answers fall into the same shape: Worker (a)-half shipped against spec-recommended (a), Eric ratified (a). Zero rework surface.

**6 B answers — 2 already aligned, 1 affects role-doc only, 1 has no v1 code-shape implication, 1 needs docstring-only rework, 1 needs real code rework.**

| Line | Question | Spec rec | Eric | In-tree alignment | Rework needed |
|------|----------|----------|------|-------------------|---------------|
| 24 | GitHub MCP install vs. remove | (none; menu) | B = remove | N/A — affects `roles/night-auditor.md` step 3 only | role-doc edit (new Worker work, not (a)-half rework) |
| 113 | P4.B1 kill-switch hotkey hard-coded vs. configurable | (a) | B = configurable | (a)-half already plumbed the config field forward-compat: `AutomationConfig.kill_switch_hotkey` + `KillSwitch.__init__(hotkey=...)` + toml `kill_switch_hotkey = "<ctrl>+<alt>+k"` all present | docstring-only: `kill_switch.py` lines 18-21 + 39-42 still say "spec Q1 (a)" / "hard-coded for v1"; flip framing to (b). (b)-half wiring (voice_loop reads `settings.automation.kill_switch_hotkey` and passes to `KillSwitch.__init__`) was always (b)-half scope, unaffected. |
| 122 | P4.B1 dry-run default True forever vs. flip-in-P4.B4 | (a) | B = flip-in-P4.B4 | v1 default is True under both letters; (a)-half ships `[automation] dry_run = true` already | none today. Future P4.B4 decision doc lands a toml flip. |
| 140 | P4.C2 router warn_threshold null-fallback vs. single-source | (c) | B = single-source | (a)-half shipped (c)-shape: `BrainRouterConfig.warn_threshold_usd: float \| None = None` + `make_router_from_settings` resolver `threshold = router_cfg.warn_threshold_usd; if threshold is None: threshold = settings.budget.warn_usd_monthly` + commented-out toml line + 2 tests pinning each branch | **REAL CODE REWORK** — see § below |
| 168 | P4.B2 send_hotkey backend pyautogui vs. pynput vs. keyboard | (b) | B = pynput | (a)-half shipped against (b) per spec; worker-10am 5/14 JOURNAL claim + `tools/hotkey.py` import surface | none |
| 252 | P4.A2 PyQt6 packaging tier core vs. optional vs. lazy | (b) | B = optional | P4.A2 (a)-half bailed pre-ship (libEGL); no in-tree diff exists yet to rework. When P4.A2 ships, the worker should target (b) per spec which Eric ratified. | none for existing in-tree pile; future P4.A2 ship targets (b). |

**1 C answer (line 91)** — worker-8am 2026-05-07 lock-bail question. The question text named only options (a) and (b); the answer marker writes "C" mapped to the tail-of-text suggestion "carve-out for `roles/worker.md` step 7." Eric's choice is to extend `roles/worker.md` step 7 with a forensic carve-out (mtime-within-N-min + 0-byte + sandbox-user-owner → safe to remove). This is new Worker work, not (a)-half rework. Maps directly to OPEN-DECISIONS S3 per the dashboard answer hint. No in-tree code diff affected.

### The one real code rework: P4.C2 router warn_threshold

The P4.C2 (a)-half (worker-11am 2026-05-08) shipped the spec-recommended (c) shape — `warn_threshold_usd: float | None = None` on `BrainRouterConfig`, with a null-fallback resolver in `make_router_from_settings` and a commented-out toml override line. Eric's B answer is "Read `[budget].warn_usd_monthly` directly; no `warn_threshold_usd` on `[brain.router]`. Single source of truth."

The rework delta to align (a)-half-as-shipped with Eric's B answer, by file:

1. **`sabrina-2/src/sabrina/config.py`** lines 73-83: drop the `warn_threshold_usd: float | None = None` field from `BrainRouterConfig`. Drop the docstring bullet about it at lines 74-76. Net: -3 lines of model + 3 lines of docstring.

2. **`sabrina-2/src/sabrina/brain/router.py`** lines 17-21 + 317-322: docstring updates ("Q1 (a)" → "Q1 (b)"; "defaults to None and falls back" → "reads `[budget].warn_usd_monthly` directly"). Lines 359-361: replace the conditional with `threshold = settings.budget.warn_usd_monthly`. Net: -2 LOC + docstring re-wording.

3. **`sabrina-2/sabrina.toml`** lines 40-54: drop the `warn_threshold_usd` mention from the `[brain.router]` block comment (lines 40-45) and drop the commented-out override line at 52. Net: -7 lines.

4. **`sabrina-2/tests/test_router.py`** lines 365-398 — two tests pin the resolver shape:
   - `test_make_router_from_settings_threshold_from_router_cfg` (lines 365-382): asserts that `[brain.router].warn_threshold_usd = 7.5` overrides budget; under B this knob no longer exists, so this test needs to be deleted.
   - `test_make_router_from_settings_threshold_falls_back_to_budget` (lines 385-398): asserts that with `warn_threshold_usd = None`, the resolver reads from `[budget].warn_usd_monthly = 12.5`. Under B this is the only path; the test can stay but the docstring "Q1 (a) recommendation: warn_threshold_usd unset => use [budget].warn_usd_monthly" should flip to "Q1 (b): threshold always reads from [budget].warn_usd_monthly." The test's setup of the env var override on warn_threshold_usd no longer applies; trim that. Net: ~10 LOC edited; -1 test, simplified +1 test.

   Direct-construction tests at lines 160-241 (instantiating `Router(... warn_threshold_usd=10.0)`) **stay unchanged** — the `Router` class constructor still accepts `warn_threshold_usd` for direct testing. Only the config-side knob disappears.

Total rework: ~25 LOC removed (config field + toml lines + one resolver branch + one test) + ~15 LOC of docstring updates. No new files. No new tests. The diff is small and surgical; same `automation/worker-2026-05-07-8am` branch as the rest of the pile.

### The docstring-only rework: P4.B1 kill-switch hotkey

The P4.B1 (a)-half (worker-9am 2026-05-08) ALREADY plumbed the kill-switch hotkey field through `AutomationConfig` (line 293 sets `kill_switch_hotkey: str = "<ctrl>+<alt>+k"`) and through the `KillSwitch.__init__` signature (line 132 accepts `hotkey: str = DEFAULT_KILL_SWITCH_HOTKEY`). The toml block (lines 246-248) also declares `kill_switch_hotkey = "<ctrl>+<alt>+k"`. The (a)-half shipped forward-compatible with either A or B answer.

The only stale-against-Eric thing is the docstring framing:

1. **`sabrina-2/src/sabrina/automation/kill_switch.py` line 18**: "Hotkey binding is hard-coded `<ctrl>+<alt>+k` for v1 (spec Q1 (a))." → flip to "Hotkey binding defaults to `<ctrl>+<alt>+k` and can be overridden via `[automation] kill_switch_hotkey` (spec Q1 (b))."
2. **Lines 39-42**: comment "Default hotkey (spec Q1 (a)). The spec recommends keeping this hard-coded for v1..." → flip to "Default hotkey (spec Q1 (b)). v1 default; `AutomationConfig.kill_switch_hotkey` overrides..."

The (b)-half wiring — `voice_loop.py` reads `settings.automation.kill_switch_hotkey` and passes it to `KillSwitch.__init__` — was always part of the (b)-half scope (Windows e2e validation lands the wiring), and Eric's B answer doesn't change that. The (a)-half ships clean against B with no behavior change, only docstring framing.

### Other answer-batch implications worth flagging

- **The libEGL pick (line 284) is the only remaining unanswered NEEDS-INPUT actual entry.** Eric answered the P4.A2 headless-platform question at line 254 (A = `QT_QPA_PLATFORM=offscreen`), so the spec-recommended test platform is settled. The libEGL sandbox-system-dep question (a/b/c bail/shim/skip) is now the actual P4.A2 (a)-half blocker. Per spec recommendation: (a) bail to Windows. Per pragmatic ship-today framing: (b) sandbox shim. The lock-clear unblocks 12 diffs whether or not Eric answers this one; libEGL is P4.A2-specific.
- **The 5/15 02:37 night-auditor's 25/3/1 letter tally is wrong** (canonical is 21/6/1). Tomorrow's planner's STATE.md narrative should use the canonical count; the 25/3/1 reading underestimates Eric's spec-override rate by 3× and could lead a future role to assume "Eric ratified everything" when in fact 5 of 28 picks were spec overrides (the GitHub MCP question's framing was not a spec recommendation). The miscount cause is unverified but most likely the night-auditor used bash-grep (where the FUSE H2 lag continues to widen on the NEEDS-INPUT channel per the 5/15 02:37 audit's own narration) instead of the canonical Grep-tool channel for the per-letter split. This is the same H2 lag pattern researcher 5/14 03:30's doc already documents; PROPOSED #43's `roles/night-auditor.md` step 4 cross-verify line, if it had been in place this morning, would have caught the miscount.
- **The S11(a) bulk-ratify scope is mooted.** STATE.md 5/14 07:00 framed S11(a) as "23 spec-writer (a)-half picks consolidated" awaiting bulk-ratify. With the per-item dashboard answer batch, all 23 individual entries now have their own answer; S11 as an OPEN-DECISIONS line item collapses. Tomorrow's planner should reflect this in STATE narrative.

## Recommendation

**Actionable change.** Two PROPOSED entries to file. Both Improvable P1, doc/code-only, runnable today on Linux without lock-clear.

1. **P4.C2 router warn_threshold field-removal rework** — ~25 LOC code + ~15 LOC docstring + 1 test deletion + 1 test simplification, all in `sabrina-2/src/sabrina/{config,brain/router}.py` + `sabrina-2/sabrina.toml` + `sabrina-2/tests/test_router.py`. Worker shift; partial-DoD-eligible; lands on the same `automation/worker-2026-05-07-8am` branch as the rest of the lock-blocked pile so it commits in the same lock-clear sweep. Tomorrow's planner can queue this as a standalone P1 (a)-half item or fold it into a `[from: researcher / 2026-05-15]` follow-up to the P4.C2 (a)-half entry already in QUEUE.md.

2. **P4.B1 kill-switch hotkey docstring update** — ~6-10 LOC of docstring/comment edits in `sabrina-2/src/sabrina/automation/kill_switch.py`. No code-shape change. Worker shift but trivially small; could be batched with #1 above to amortize the Worker slot's overhead.

3. **Re-count and reframe the 5/15 02:37 night-auditor's letter tally in tomorrow's STATE.md overwrite** — replace "25 A / 3 B / 1 C" with the canonical "21 A / 6 B / 1 C." Planner work, not Worker; goes in the planner's `## Recent decisions` section per the STATE-overwrite contract.

No new files; no `[from: researcher / 2026-05-15 03:30]` "what to investigate next" NEEDS-INPUT entry needed (this investigation produced a concrete answer surface, dedup-skip doesn't apply). No PROPOSED #43-style doc-only reframe needed for the broader answer-batch (the batch is a positive state change, not a finding requiring discipline change).

## Open follow-ups

- **Does the dashboard producer write `**[answered:]**` markers via Edit-tool-with-anchor or via Python `read() + os.replace()`?** Unknown from outside the producer. The 5/14 14:53 wiring lands the contract end (`roles/worker.md` + `night-auditor.md` + `CLAUDE.md`) but the producer side is `.dashboard-enrichment.json`-driven (per PROPOSED #42) and lives outside this repo's role chain. If the producer uses `read() + os.replace()`, the 28-marker batch is theoretically at risk for the same FUSE-stale-source data loss the worker-9am 2026-05-07 incident documented. The Read+Grep canonical view post-batch shows all 28 markers + all prior entries intact, so this isn't a live concern today — but the producer's write path is worth grounding before the contract sees heavy use. Out of scope for this researcher run; worth a PROPOSED entry if Eric's setup grows to handle multi-day batches.
- **Is the libEGL pick (line 284) better grounded as research or kept as a pure Eric decision?** The 3 options are sharply named and the spec recommendation is (a) bail-to-Windows. A grounded answer would inspect what `apt-get download libegl1 libegl-mesa0` plus the `dpkg-deb -x` extraction trail looks like in detail (Cowork sandbox apt-fetch policy, footprint, dpkg-deb extraction quirks, LD_LIBRARY_PATH precedence), but the worker-9am 5/14 entry already verified the workaround works (`QApplication([])` instantiates cleanly under offscreen post-shim). The bounded-question framing for a researcher would be "Does the sandbox-shim path break in any deployment-relevant edge case (e.g. transient apt-fetch failure, libegl ABI drift in PyQt6 wheel)?" — narrow enough to investigate in a slot if Eric wants the shim path grounded before deciding (b).
- **What's the right cross-verify discipline for per-letter `[answered:]` tallying going forward?** The 5/15 02:37 night-auditor's miscount and the 5/14 02:37 night-auditor's NEEDS-INPUT line-count miscount both have the same root cause (bash-grep through stale FUSE cache vs. tool-channel canonical). PROPOSED #43 already names a step-4 cross-verify line for `roles/night-auditor.md`; today's miscount is one more concrete instance reinforcing #43's day-1-eligible status. No new PROPOSED needed if #43 lands as written; if Eric chooses to strike #43, the cross-verify rule should land in some other form before the next 02:37 letter-tally run.
- **Does the P4.C2 rework's removed `warn_threshold_usd` field have any forward-compat user already?** Specifically: does any in-tree script, decision doc, or research doc reference `[brain.router].warn_threshold_usd` such that removing the field would create a stale reference? Quick Grep of the project for `warn_threshold_usd` finds the field only in `config.py`, `router.py`, `sabrina.toml`, `test_router.py`, and the P4.C2 spec at `rebuild/drafts/research/2026-05-08-p4c2-router-routing-policy-spec.md`. The spec doc will become slightly stale post-rework (it still recommends (c)); it's a draft research doc, not canonical decision text, so stale-against-shipped-decision is the normal state for these specs. No additional file edits needed.
