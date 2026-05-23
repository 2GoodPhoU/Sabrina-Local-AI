# P4.B1 — Automation safety primitives (kill-switch + dry-run + ToolSpec scaffold) — spec

**Date:** 2026-05-08
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Automation → **P4.B1 Automation — kill-switch + dry-run + ToolSpec scaffold** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-04-26-toolspec-first-three.md` — side-effect taxonomy (read-only / read-fs / write-clipboard / execute-OS) and the per-tool risk tier framing. Treated as canon for the side-effect classes B1's primitives must guard.
- `rebuild/drafts/research/2026-04-26-threat-model.md` — automation threat model. Calls out the kill-switch as the single most load-bearing safety primitive.
- `rebuild/drafts/tool-use-plan.md` — original tool-use plan; calls out kill-switch + dry-run + destructive-action gate as the three legs of automation safety. P4.B1 builds the first two; P4.B3 is the third (allow-list).
- `ROADMAP.md` § "Phase 4" — "most-dangerous-component-last" framing. Component 10 (Automation) ships only after the safety primitives are in place.
- `sabrina-2/src/sabrina/tools/__init__.py:35-113` — current `ToolSpec` dataclass + `BUILTIN_TOOLS` list + `find()` lookup. The scaffold extends this surface; no protocol change.
- `sabrina-2/src/sabrina/tools/clipboard.py` — only existing handler. The scaffold's `noop_action` follows the same shape: async function, dict-in / dict-out, no side effects beyond the documented one.
- `sabrina-2/src/sabrina/brain/claude.py:177-237` — current tool-dispatch loop in `ClaudeBrain.chat`. The dry-run shim wraps handler invocation here; the kill-switch trips raise into this same path and surface as `ToolUseDone(error="...")`.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, `voice_loop.py` runtime path (no event-bus changes in this spec — kill-switch trip flows through the existing tool-dispatch error channel; no new `Event` type yet).

---

## What this item is

Component 10 (Automation) is the most-dangerous-component-last item per ROADMAP §"Phase 4". Before any real action ToolSpec ships (`send_hotkey` in P4.B2, `launch_app` later, `open_file` later still), the safety primitives have to land first: a kill-switch that aborts a running automation handler from a global hotkey on the user's keyboard; a dry-run flag that lets the brain "perform" actions without the side effect (handler logs the would-be call and returns a synthetic success); and a ToolSpec scaffold (`noop_action`) that exercises the new dispatch path end-to-end without depending on any real-action handler. The scaffold proves the wire-up before the dangerous tools ride it. Linux-runnable because all three primitives are pure-stdlib + protocol additions; the only Windows-specific piece (the actual `pynput` global-hotkey listener) is deferred to P4.B4 where one real keypress validates the chain.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/automation/__init__.py` (new package marker, ~10 lines) — module docstring naming the three safety primitives, the dispatch contract (kill-switch raises `KillSwitchTripped`; dry-run handlers return `{"dry_run": true, ...}`), and the off-limits posture (no new `Event` type yet).
- `sabrina-2/src/sabrina/automation/kill_switch.py` (new, ~140 lines):
  - `class KillSwitchTripped(Exception)` — raised inside the handler context manager when the trip flag is set. Inherits `Exception`, not `BaseException` — the brain's tool-dispatch error path catches it and emits `ToolUseDone(error="kill_switch_tripped")`.
  - `class KillSwitch` — context-manager. `__enter__` registers the global hotkey listener (Windows: `pynput.keyboard.GlobalHotKeys`; Linux/sandbox: a no-op stub registered behind `_LISTENER_FACTORY` so unit tests inject a fake). `__exit__` unregisters. Exposes `.tripped: bool` (atomic flag, read-after-write semantics, same shape as `CancelToken`'s `.cancelled`); `.trip()` (manual programmatic trip — what tests call); `.check()` (raises `KillSwitchTripped` if `.tripped` is True). Sole consumer responsibility: call `.check()` between safe points inside any automation handler. Mirrors the `CancelToken.cancelled`-poll pattern from `brain/protocol.py:43-50`.
  - `_LISTENER_FACTORY: Callable[[Callable[[], None]], object]` — module-level injection seam. Default = a real `pynput.keyboard.GlobalHotKeys` factory; tests override with a `_NoopListener` that exposes `.start()` / `.stop()` no-ops + a programmatic `.fire()` for trip simulation.
  - Hotkey binding: hard-coded `"<ctrl>+<alt>+k"` for v1; the `[automation.kill_switch] hotkey` config knob lands behind the open question Q1 below.
- `sabrina-2/src/sabrina/automation/dry_run.py` (new, ~80 lines):
  - `DRY_RUN_RESULT_SHAPE` — a frozen dict-like sentinel structure: `{"dry_run": True, "would_have_called": "<tool_name>", "input": <input_dict>}`. Returned by `dry_run_wrap(handler)` instead of invoking the real handler.
  - `def dry_run_wrap(handler: ToolHandler) -> ToolHandler` — pure-function wrapper. Takes any `ToolHandler` (`(input_dict) -> Awaitable[dict]`), returns a coroutine that logs `automation.dry_run.would_call` at INFO and returns the synthetic shape. No side effects beyond the log line.
  - `def is_dry_run(settings) -> bool` — single-source-of-truth resolver: reads `[automation] dry_run` from `Settings.automation.dry_run`, defaulting True until P4.B4 ships (so even a misconfigured `[tools] enabled = true` Phase-4 install can't accidentally fire a real action handler before validation).
- `sabrina-2/src/sabrina/automation/scaffold.py` (new, ~60 lines):
  - `async def noop_action(content: str) -> dict[str, Any]` — the scaffold handler. Returns `{"ok": True, "content_length": len(content)}`. No side effects. Intentionally not registered as `BUILTIN_TOOLS` member by default — the registry append happens behind `[tools.noop_action] enabled = true` (off by default; tests register inline).
  - `NOOP_ACTION_SPEC: ToolSpec` — module-level constant; consumers do `from sabrina.automation.scaffold import NOOP_ACTION_SPEC` and pass through `tools=[NOOP_ACTION_SPEC, *BUILTIN_TOOLS]` in tests.
- `sabrina-2/src/sabrina/config.py` — additive `BrainAutomationConfig` Pydantic model:
  - `class AutomationConfig(BaseModel): dry_run: bool = True; kill_switch_enabled: bool = True; kill_switch_hotkey: str = "<ctrl>+<alt>+k"; destructive_actions: list[str] = []` — last field is the P4.B3 hook so the config schema doesn't need to change again when P4.B3 ships.
  - Add `automation: AutomationConfig = AutomationConfig()` to `Settings` model.
- `sabrina-2/sabrina.toml` — additive `[automation]` block mirroring the new defaults. Lives below `[tools]`; no schema-version bump needed (additive-with-defaults is back-compat per decision 008's posture).
- `sabrina-2/src/sabrina/brain/claude.py` — extend tool-dispatch loop (lines ~210-235):
  - Inside the `tool_use` block-handling branch, wrap the handler call in `KillSwitch.check()` polls — once before `await handler(...)`, once after. If tripped, re-raise as `KillSwitchTripped` and let the existing `except` branch catch it (the existing code emits `ToolUseDone(error=str(exc))`; the spec keeps that shape, just with a more specific exception name).
  - If `is_dry_run(settings)`, swap `handler` for `dry_run_wrap(handler)` before the call. The `KillSwitch` poll still wraps the dry-run wrapper — dry-run shouldn't bypass the kill-switch.
  - The `settings`-passthrough is the smallest possible change: a new `kill_switch: KillSwitch | None = None` kwarg on `ClaudeBrain.chat()` (default None — pass-through behavior matches today's). Voice-loop wiring (b)-half rolls into P4.B4.
- `sabrina-2/tests/test_automation_safety.py` (new, ~280 lines) — eighteen unit tests:
  - `test_kill_switch_starts_untripped` — `.tripped` is False at context entry.
  - `test_kill_switch_check_does_not_raise_when_untripped` — `.check()` returns None.
  - `test_kill_switch_trip_sets_tripped_flag` — programmatic `.trip()` sets the flag.
  - `test_kill_switch_check_raises_when_tripped` — post-trip `.check()` raises `KillSwitchTripped`.
  - `test_kill_switch_listener_factory_is_invoked_on_enter` — fake factory's `.start()` was called.
  - `test_kill_switch_listener_factory_stop_called_on_exit` — fake factory's `.stop()` was called.
  - `test_kill_switch_listener_callback_trips_flag` — fake listener's `.fire()` propagates to `.tripped`.
  - `test_dry_run_wrap_returns_synthetic_shape` — wrapped handler's coroutine returns `{"dry_run": True, ...}`.
  - `test_dry_run_wrap_does_not_invoke_underlying` — wrapped `noop_action` doesn't fire (sentinel side-effect mock not called).
  - `test_dry_run_wrap_logs_would_call_at_info` — caplog captures the structured log line.
  - `test_is_dry_run_default_is_true` — fresh `Settings()` returns True from `is_dry_run`.
  - `test_is_dry_run_respects_config_override` — `Settings(automation=AutomationConfig(dry_run=False))` returns False.
  - `test_noop_action_returns_ok_shape` — `await noop_action("hello")` → `{"ok": True, "content_length": 5}`.
  - `test_noop_action_spec_round_trips_to_anthropic_dict` — `NOOP_ACTION_SPEC.to_anthropic_dict()` matches the existing `BUILTIN_TOOLS[0]` shape (parallel to the four ToolSpec round-trip tests at `test_smoke.py:1869-1965`).
  - `test_claude_dispatch_calls_handler_when_dry_run_false` — fake Anthropic stream emits a `tool_use` for `noop_action`; with `dry_run=False`, the underlying handler runs.
  - `test_claude_dispatch_returns_dry_run_shape_when_dry_run_true` — same fake stream; with `dry_run=True`, the `tool_result` content is the synthetic shape; underlying handler did not run.
  - `test_claude_dispatch_returns_kill_switch_error_when_tripped` — fake stream emits `tool_use`; `kill_switch.trip()` between the LLM stream and the handler invocation; assert `ToolUseDone(error="kill_switch_tripped")`.
  - `test_claude_dispatch_dry_run_still_honors_kill_switch` — combination case: `dry_run=True` AND `kill_switch.trip()` pre-handler; assert kill-switch error wins (ordering matters; spec recommendation is poll-before-dispatch).

**(b)-half — folded into P4.B4, NOT deliverable here:**

- Real `pynput.keyboard.GlobalHotKeys` listener exercised on Windows (the (a)-half ships the listener factory but uses the no-op stub in tests — the real listener path isn't validated until Eric's box).
- `voice_loop.py` instantiates `KillSwitch` once per run and threads it into `ClaudeBrain.chat`'s `kill_switch=` kwarg — runtime change, off the (a)-half partial-DoD scope.
- `[tools.noop_action] enabled = true` flip + the registry append — only meaningful once a real action ToolSpec is co-shipped; deferred to P4.B2.
- One real Windows session that fires `<ctrl>+<alt>+k` mid-handler and confirms abort — Full-DoD gate.
- Decision doc (under P4.B4) covering the B1 + B2 + B3 + B4 quartet under one number.

## What's deliberately NOT in scope

- **Audio + visual feedback on kill-switch trip** — a "killed" TTS line or a visible avatar blink would be useful UX but it's voice-loop / avatar / event-bus territory. The (a)-half emits a `ToolUseDone(error="kill_switch_tripped")` and lets the existing voice-loop error-rendering path handle it (which already prints a dim status line per the (b)-half wire-up in `voice_loop.py`). UX polish lives behind P4.B4 + P4.A4.
- **Multi-action dispatch state machine** — a single in-flight handler is the v1 surface. Concurrent automation actions would need a richer state machine; the kill-switch in v1 trips the one running handler and that's it.
- **Persisting kill-switch trip events for an audit log** — the `automation.dry_run.would_call` and `automation.kill_switch.tripped` log lines are structlog INFO-level + the standard rotating sink. A separate audit log file would compose with `ACTION_ITEMS.md` regression tracking but is out of scope.
- **`pyautogui` vs. `pynput` choice for the actual global hotkey listener** — both are listed in the threat model as candidates; the spec defers the pick to P4.B2's `send_hotkey` work since both libraries are needed anyway. The factory injection seam in `kill_switch.py` makes the choice swappable later.
- **Destructive-action allow-list** — that's P4.B3. The `destructive_actions: list[str]` config field gets added in this spec because adding it now (default empty list) saves a schema-version bump when P4.B3 ships. The runtime guard is P4.B3.
- **`open_app` ToolSpec or any real action** — P4.B2 (`send_hotkey`) is the first real action; this spec only ships the scaffold.

## Dependencies

- **`rebuild/drafts/research/2026-04-26-toolspec-first-three.md` § "Side-effect taxonomy"** — canon for the per-tool side-effect class. The scaffold's `noop_action` is the side-effect class `read-only / pure` (no fs / no network / no clipboard).
- **`rebuild/drafts/research/2026-04-26-threat-model.md`** — kill-switch threat model. The hotkey choice (`<ctrl>+<alt>+k`) is the threat-model recommendation; the open question Q1 below revisits whether to make it configurable.
- **`sabrina-2/src/sabrina/brain/claude.py:148-237`** — the existing tool-dispatch loop. The (a)-half adds two checkpoints + one wrapper; net delta is ~30 lines.
- **`sabrina-2/src/sabrina/config.py`** — adding `AutomationConfig` to `Settings`. Mirrors the existing `BudgetConfig` pattern verbatim (worker-8am 2026-05-06 shipped that one — known-good template).
- **Phase 3 (a)-half landed (`acd6725`)** — confirmed in DONE.md 2026-05-05. Kill-switch + dry-run hook into the existing tool-dispatch loop; without that loop, the hooks have nowhere to live.
- **Phase 3 (b)-half NOT a dependency for the (a)-half** — `[tools] enabled = false` in `sabrina.toml` today; the (a)-half tests inject `tools=[NOOP_ACTION_SPEC]` directly without needing the toml flip.
- **`pynput`** — already in `pyproject.toml` as a runtime dep (used by the vision hotkey + the planned `send_hotkey`). No new dependency.
- **CLAUDE.md "Partial-DoD tiers"** — the (a)-half does NOT touch `voice_loop.py`, audio I/O, clipboard, mss/pynput/pyperclip runtime paths (the listener factory is a Linux-no-op stub by default in this spec), or pywin32-only modules. Eligible for partial-DoD ship.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. `sabrina-2/src/sabrina/automation/__init__.py`, `kill_switch.py`, `dry_run.py`, `scaffold.py` exist with the surfaces named above.
2. `sabrina-2/src/sabrina/config.py` has `AutomationConfig` model with the four named fields and defaults; `Settings.automation` defaults to `AutomationConfig()`.
3. `sabrina-2/sabrina.toml` has an `[automation]` block with the four fields and matching defaults.
4. `sabrina-2/src/sabrina/brain/claude.py` `chat()` accepts `kill_switch: KillSwitch | None = None` kwarg; tool-dispatch loop polls `kill_switch.check()` before and after handler invocation; dispatches through `dry_run_wrap(handler)` when `is_dry_run(settings)` is True.
5. `python3 -m compileall -q sabrina-2/src sabrina-2/tests` exits 0.
6. AST-parse spot-check on the five touched files (the four new automation files + claude.py + config.py) confirms intact tails per CLAUDE.md edit-tool truncation hazard guidance.
7. `python3 -m pytest sabrina-2/tests/test_automation_safety.py -v` → 18/18 PASS.
8. Combined regression run on `test_automation_safety.py` + `test_smoke.py::test_claude_*` (the 6 (a)-half wire-up tests + the 4 ToolSpec round-trip tests) + `test_budget.py` → all PASS, no new failures vs. the worker-8am 2026-05-07 baseline (122 PASS / 10 SKIPPED / 4 pre-existing failures unchanged).
9. `ruff check sabrina-2/src/sabrina/automation sabrina-2/src/sabrina/brain/claude.py sabrina-2/src/sabrina/config.py` reports no new errors above the post-P0 baseline.
10. Commit lands on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` in the body and a Windows DoD checklist in JOURNAL.md naming the (b)-half work (one Windows session firing `<ctrl>+<alt>+k` mid-handler aborts the in-flight noop_action; pynput listener attaches without admin elevation).
11. JOURNAL.md run summary names the diff partition (5 new files + 2 extended files = 7) and the partition's independence from the in-flight P4.C1 (a)-half (zero file overlap; `brain/persona.py` lift in C1 doesn't touch the dispatch loop).

**(b)-half DoD — owned by P4.B4, not this spec:**

12. Real `pynput.keyboard.GlobalHotKeys` listener attaches on Windows without admin elevation; `<ctrl>+<alt>+k` press flips `KillSwitch.tripped`.
13. One Windows voice session ≥3 turns: brain calls `noop_action`; mid-handler hotkey press aborts; `ToolUseDone(error="kill_switch_tripped")` reaches the voice-loop renderer; user hears the resulting error line.
14. `voice_loop.py` instantiates `KillSwitch` once per run, threads it into `ClaudeBrain.chat`, and reuses the same instance across turns.
15. Decision doc filed (next free integer in `rebuild/decisions/`, decision-doc voice) covering the B1 + B2 + B3 + B4 quartet under a single "Automation safety primitives shipped" entry.

## Open questions for NEEDS-INPUT

**Q1 — Kill-switch hotkey: hard-coded `<ctrl>+<alt>+k`, configurable, or platform-aware?**

- **(a) Hard-coded `<ctrl>+<alt>+k` for v1.** Cheapest. Threat model recommends a 3-key chord (single-key would clash with normal typing; 2-key combos like `<ctrl>+<k>` collide with editor / browser shortcuts). Cost: a chord that conflicts with another app on Eric's box requires a code edit + commit to swap. Spec recommends this — the chord is unlikely to conflict on a personal-use Windows box, and the config-knob exposure adds surface area pre-Windows-validation.
- **(b) Configurable via `[automation.kill_switch] hotkey` in TOML.** The spec already adds the `kill_switch_hotkey: str = "<ctrl>+<alt>+k"` field (so the schema is forward-compatible). Cost: adds one config-load test case + the validation that the parsed string is a valid `pynput` hotkey spec.
- **(c) Platform-aware default — `<ctrl>+<alt>+k` on Windows, `<cmd>+<shift>+k` on macOS, `<super>+<alt>+k` on Linux.** Premature; macOS / Linux aren't supported targets per CLAUDE.md.
- **Spec recommendation: (a).** Worker can ship the (a)-half against (a) without waiting; the field is in the config model already so flipping to (b) later is a 1-line commit. If Eric overrides to (b) before pull, Worker reroutes per the answer.

**Q2 — Dry-run default-True posture: ship True, ship False, or ship True only until P4.B4?**

- **(a) Default True forever.** Every Sabrina install starts in dry-run; Eric flips `[automation] dry_run = false` in TOML to enable real-action handlers. Cost: every voice loop's tool dispatch logs `automation.dry_run.would_call` until Eric explicitly flips, even after Windows e2e validation. Spec recommends this — defense-in-depth posture, and the flip is one TOML edit.
- **(b) Default False once P4.B4 ships.** v1 default True; P4.B4's decision doc flips it to False; from v1.1 onward the install ships with real actions enabled. Cost: a future Worker has to remember to ship the toml flip alongside P4.B4's decision doc; one more thing to forget.
- **(c) Default False from day one.** Trust the kill-switch + destructive-action allow-list as sufficient guardrails. Cost: a misconfigured `[tools] enabled = true` plus a misregistered destructive-action list, on a hosted automation install, could fire real actions before Eric's first manual review. Threat model arguments against.
- **Spec recommendation: (a).** The cost of (a) is one extra TOML flip Eric makes once; the cost of (c) is unbounded. Worker can ship the (a)-half against (a) without waiting; if Eric overrides to (b) or (c) before pull, the change is a one-line default flip.

**Q3 — `noop_action` registry membership: pre-register in `BUILTIN_TOOLS`, gate behind `[tools.noop_action] enabled`, or test-only?**

- **(a) Test-only — never in `BUILTIN_TOOLS`.** Tests import `NOOP_ACTION_SPEC` directly and pass through `tools=[NOOP_ACTION_SPEC, *BUILTIN_TOOLS]`. The brain at runtime only sees `BUILTIN_TOOLS`. Cost: P4.B4's "Windows e2e validation of the dispatch path" needs an in-tree real ToolSpec to fire; the first real one is `send_hotkey` from P4.B2, so P4.B4 has to wait for B2. Benefit: the brain never sees a no-op tool in production — leaks impossible by construction.
- **(b) Pre-register in `BUILTIN_TOOLS` behind `[tools.noop_action] enabled = false` default.** Same surface as `[tools.write_clipboard]` precedent. Cost: a misconfigured `[tools] enabled = true` could fire `noop_action` (harmless since it's a no-op, but it widens the "what tools does the brain see" surface). Benefit: P4.B4 can validate the dispatch path against `noop_action` directly without waiting for P4.B2.
- **(c) Pre-register only when an env var is set (`SABRINA_AUTOMATION_NOOP_REGISTERED=1`).** Test fixture mode. Same cost/benefit profile as (a) but more explicit.
- **Spec recommendation: (a).** The "leaks impossible by construction" argument outweighs the "P4.B4 has to wait for B2" cost since they're sequential anyway (B2 depends on P5.2 + B1; B4 closes the quartet). Worker can ship the (a)-half against (a) without waiting; if Eric overrides to (b), the change is two lines (`BUILTIN_TOOLS.append(NOOP_ACTION_SPEC)` + the toml gate).

All three questions written to `NEEDS-INPUT.md` per the spec-writer role doc.

## Bailout / not-yet conditions

- The `pynput` import path on Windows differs slightly between the wheel and the source-built version; `pynput.keyboard.GlobalHotKeys` is stable on both per the existing `vision/hotkey.py` precedent. Spec mitigation: the `_LISTENER_FACTORY` injection seam means the import happens only when a real (not stub) listener is requested — Linux test runs never trigger the import, so the (a)-half ship doesn't depend on the import succeeding under sandbox.
- If `voice_loop.py` is in the working tree as part of an in-flight P4.C1 / (b)-half wire-up when this spec is pulled, the (a)-half is still independently shippable: the kill-switch instantiation lives in voice_loop, but the spec's (a)-half explicitly does not touch voice_loop. Worker reads `git status sabrina-2/src/sabrina/voice_loop.py` first; if dirty, marks `[in-progress]` and writes to NEEDS-INPUT.
- If a future P4.B2 / P4.B3 spec lands before this one is pulled and changes the `AutomationConfig` shape, this spec's `destructive_actions: list[str] = []` field is the forward-compat hook — the schema bump is paid here, not later.
- If the Edit-tool truncation hazard hits on `claude.py` (worker-8am 2026-05-06 + 2026-05-07 both reported it), use the documented bash-heredoc + `os.fsync()` rewrite path. Verify post-edit per CLAUDE.md ("AST-parse Python files; spot-check >300 lines for tail integrity"); the existing dispatch-loop block at lines ~210-235 is the most fragile region.
