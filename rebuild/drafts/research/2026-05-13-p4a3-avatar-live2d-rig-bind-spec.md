# P4.A3 — Avatar Live2D model bind + render loop — spec

**Date:** 2026-05-13
**Author:** sabrina-spec-writer (06:50 scheduled run; landed 07:30ish per late-arrival convention)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Avatar → **P4.A3 Avatar — Live2D model bind + render loop** (`[linux-runnable] [partial-dod-eligible] [P2] [L]`).
**Predecessors / canon to consult:**

- `rebuild/drafts/research/2026-05-12-p4a1-avatar-architecture-research-spec.md` — the architecture-research spec. P4.A3 assumes the (a)+(a)+(a) recommendations (live2d-py SDK, full click-through, in-process via qasync) are ratified. If Eric overrides Q1 (SDK pick) before A3 is pulled, the file partition changes — see "Open NEEDS-INPUT" below.
- `rebuild/drafts/research/2026-05-12-p4a2-avatar-pyqt-skeleton-spec.md` — the skeleton spec. P4.A3 replaces A2's placeholder `QLabel` with a real Live2D rig surface; everything else A2 built (event-bus subscriber, qasync bridge, CLI subcommand, `AvatarConfig` model, headless-offscreen test pattern) stays in place.
- `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` — the April research that already settled `live2d-py` 0.6.x as primary, named the Windows-11 window-flag gotchas (`WA_TranslucentBackground` + `setAlphaBufferSize(8)` + `WindowTransparentForInput` ordering), and gave concrete dispatcher timing budgets. **Load-bearing for §"Frame budget" + §"Per-state parameter map" below — A3 is partly a re-implementation of that doc's sketch under the rebuild's protocols.**
- `sabrina-2/src/sabrina/events.py:55-63` — `StateChanged(from_state, to_state, reason)` event shape. A3 consumes these via the subscriber A2 built.
- `sabrina-2/src/sabrina/state.py` — five `StateName` values (`idle | listening | thinking | speaking | acting`). A3 maps each to a Live2D rig parameter snapshot.
- `sabrina-2/src/sabrina/bus.py:51-83` — `EventBus.subscribe()` semantics. Lossy-on-backpressure is fine; the rig is a low-stakes consumer.
- `rebuild/decisions/009-barge-in-shipped.md` — A3 must not regress the 264 ms barge-in latency. Frame-loop scheduling sits in the same process as the voice loop under (a) IPC; the spec calls out the asyncio-bridge contention point explicitly.
- `rebuild/decisions/001-hardware-and-budget.md` — i7-13700K + RTX 4080 + 32 GB target. 60 Hz @ 16.67 ms/frame is the headline budget; 120 Hz aspirational.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. The rig render path can be exercised headlessly under `QT_QPA_PLATFORM=offscreen` against a `live2d-py` mock model fixture; the real GPU + real Cubism rig + real Win11 compositor live behind P4.A4's Full DoD gate. The Worker pulling A3 ships under Partial DoD; A4 promotes A2/A3 to `[done]` after the one Windows e2e session.

Off-limits per CLAUDE.md: `rebuild/decisions/`, legacy root-level dirs, `voice_loop.py` runtime path (no event-bus changes in A3 — only the rig surface + parameter-driver coroutine), `.pre-commit-config.yaml`.

---

## What this item is

A3 is the avatar component's first surface that renders pixels. Where A2 stood up the skeleton — frameless window, click-through attributes, `bus.subscribe("state_changed")` consumer driving a placeholder `QLabel` — A3 replaces the placeholder with a real Live2D rig, drives the rig's parameters from incoming `StateChanged` events, and runs a render loop at the frame budget A1 set. The QUEUE entry says "rig loads; model parameters change in response to mocked `idle/listening/thinking/speaking` transitions; render loop hits target framerate under sandbox-emulated GPU"; that maps to a `live2d-py` `LAppModel` load, a per-state parameter map applied on each `StateChanged`, a `QTimer`-driven 60 Hz render tick that calls `model.Update()` + `model.Draw()` against a `QOpenGLWidget`, and a frame-time histogram exposed via the existing structlog channel so the budget is observable, not asserted-by-faith.

The deliverable is code under `sabrina-2/src/sabrina/avatar/` (new modules — `rig.py`, `dispatcher.py`, edits to A2's `window.py`) plus tests under `sabrina-2/tests/test_avatar_rig.py`. No `voice_loop.py` integration in A3; A4 owns the conditional that mounts the avatar against the live voice loop on Windows. A3's CLI entry point stays `sabrina avatar run` / `sabrina avatar dry-run` (the verbs A2 already shipped) — A3 extends `dry-run` to publish all five `StateChanged` transitions in sequence and assert the rig's parameter targets updated for each.

A3 is `[L]` because it adds three new modules (rig adapter, cue-style state dispatcher, an OpenGL widget host), exercises three coupled subsystems (Qt event loop, asyncio bus, GL render pipeline), and ships a parameter-map config surface. None of those individually are large; combined they justify the L tag and the spec.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/avatar/rig.py` (new, ~220 lines):
  - `class RigAdapter` — wraps a `live2d.LAppModel` instance behind a small Protocol-compatible surface (`load(model_path: Path)`, `set_parameter(name: str, value: float, weight: float = 1.0)`, `set_expression(name: str)`, `update(delta_seconds: float)`, `draw()`, `unload()`). The Protocol exists so tests can substitute a `FakeRig` without importing `live2d-py` — same pattern A2 used for `FakeBus` per `tests/test_utils/mocks.py`.
  - `class FakeRig` — same surface, no GL calls; records every `set_parameter`/`set_expression` call in a list for assertion. Lives in `rig.py` so test_avatar_rig can import without a `test_utils/` mock factory addition (mocks.py stays scoped to brain/speaker/listener/bus per its docstring).
  - `def load_rig(settings: Settings) -> RigAdapter` — factory: if `settings.avatar.fake_rig = True` (default in the Linux/3.10 sandbox; default False on Windows), returns `FakeRig()`. Otherwise imports `live2d` lazily and returns a `RigAdapter` bound to the model at `settings.avatar.model_path` (default `sabrina-2/models/live2d/hiyori_pro/runtime/hiyori_pro_t11.model3.json` — placeholder rig from `live2d-py`'s sample asset set; Eric drops in a custom rig later under a separate item).
  - All `live2d` imports are inside the constructor body, not at module top. The sandbox lacks the wheel; lazy import keeps `compileall` + `python -m sabrina ...` clean without `live2d` installed.

- `sabrina-2/src/sabrina/avatar/dispatcher.py` (new, ~160 lines):
  - `class StateDispatcher` — consumes `StateChanged` events (the same `bus.subscribe("state_changed")` A2's `AvatarWindow._consume` opens; A3 moves the consumer into the dispatcher and has `AvatarWindow` delegate). Maintains a current-state field. On each transition:
    1. Computes the target parameter snapshot for `to_state` via `PARAM_MAP[to_state]`.
    2. Schedules a 200 ms ease-from-current-to-target interpolation on each parameter (the "expression cross-fade" budget from `2026-04-26-avatar-cue-track-implementation.md` §"Cue-track timing budgets").
    3. Triggers an expression slot if the per-state map names one (e.g. `acting` → `concerned`).
    4. Emits a structlog `avatar.state_transition` line at INFO with `from_state` / `to_state` / `target_params` / `target_expression` for observability.
  - `PARAM_MAP: dict[StateName, ParamSnapshot]` — frozen dataclass mapping each of the five states to a tuple of `(param_name, target_value)` pairs. Initial mapping per `2026-04-26-avatar-cue-track-implementation.md`'s recommendations (`idle` → neutral-attentive, `listening` → slight lean-in via `ParamAngleZ` + `ParamBodyAngleX`, `thinking` → eyes-up via `ParamEyeBallY`, `speaking` → mouth driven by `ParamMouthOpenY` placeholder zero (lip-sync wiring is a follow-up under a later item), `acting` → forward-focus brows + slight squint). This is data, not behavior — Eric can edit values without touching code.
  - `class CrossFadeRunner` — given a list of `(param, start, target, t_start_ms, t_end_ms)` tuples, computes the current value via linear lerp at each `tick(now_ms)` call. Pure function unit; no Qt, no asyncio. Tested standalone.
  - `BARGE_IN_BLEND_MS = 200` — constant matching `decisions/009-barge-in-shipped.md`'s 264 ms barge-in budget. A3 listens for `BargeInDetected` events (additive subscription, not a replacement of A2's subscription) and snaps the cross-fade target to `idle` mid-fade. The cross-fade itself completes against the new target — no stutter.

- `sabrina-2/src/sabrina/avatar/window.py` (edit; net +120 lines / -30 lines):
  - Replace the placeholder `QLabel` central widget with a `QOpenGLWidget` host (`class AvatarView(QOpenGLWidget)`) that delegates `initializeGL` / `paintGL` / `resizeGL` to a `RigAdapter` instance. Per `2026-04-26-avatar-cue-track-implementation.md`'s call-out: set `QSurfaceFormat.setAlphaBufferSize(8)` and call `QSurfaceFormat.setDefaultFormat(fmt)` **before** `QApplication([])` runs (which lands in `runner.py`, not `window.py`; A3 edits `runner.py` to insert this two-line preamble — see below).
  - Wire a `QTimer.singleShot` cascade at 60 Hz (`interval_ms = 16`) that calls `self._view.update()` each tick. The 120 Hz cue-dispatch poll the April research recommended lives inside `StateDispatcher`, not the Qt timer — keeping the GL paint cadence at the display rate.
  - The existing event-bus consumer (`_consume`) shrinks: it now just forwards events to `self._dispatcher.on_state_changed(ev)` and `self._dispatcher.on_barge_in(ev)`. All animation logic lives in the dispatcher.
  - `closeEvent` cancels both consumer subscriptions and calls `self._rig.unload()`.

- `sabrina-2/src/sabrina/avatar/runner.py` (edit; net +25 lines):
  - Insert the `QSurfaceFormat` preamble (alpha buffer + default format) before `QApplication([])` per the gotcha above.
  - Construct the `RigAdapter` via `load_rig(settings)` and pass it to `AvatarWindow` (constructor signature grows by one arg). The Linux sandbox path picks `FakeRig` automatically because `settings.avatar.fake_rig` defaults to True there.

- `sabrina-2/src/sabrina/config.py` (edit; additive, +12 lines):
  - Extend `AvatarConfig` (A2 added the model) with three fields:
    - `model_path: str = "models/live2d/hiyori_pro/runtime/hiyori_pro_t11.model3.json"` — default placeholder rig. Project-relative path; resolved via `project_root() / settings.avatar.model_path` at load.
    - `fake_rig: bool = False` — when True, `load_rig()` returns `FakeRig` regardless of `model_path`. The Linux test environment sets this via `[avatar] fake_rig = true` in a test-only toml fixture; production Windows runs leave it False.
    - `target_fps: int = 60` — the QTimer interval is derived as `1000 // target_fps`. Eric can flip to 30 (battery) or 120 (aspirational) without code changes.
  - All three fields default to safe values; nothing changes for users who don't set them.

- `sabrina-2/sabrina.toml` — extend the `[avatar]` block A2 added with `model_path`, `fake_rig = false`, `target_fps = 60`. Comments tag each field's role.

- `sabrina-2/tests/test_avatar_rig.py` (new, ~380 lines, ~18 tests):
  - **RigAdapter Protocol surface** (4 tests):
    - `test_fake_rig_records_set_parameter_calls` — instantiate `FakeRig`; call `set_parameter("ParamAngleZ", 0.3)`; assert the recorded list contains exactly one `(name, value, weight)` tuple.
    - `test_fake_rig_records_set_expression_calls` — same for `set_expression`.
    - `test_fake_rig_update_and_draw_are_idempotent` — call `update(0.016)` ten times; call `draw()`; assert no exception, no recorded state corruption.
    - `test_load_rig_returns_fake_when_settings_flag_true` — instantiate `Settings.model_construct()` with `avatar.fake_rig=True`; assert `load_rig(settings)` returns a `FakeRig` instance, not an attempt to import `live2d`.
  - **StateDispatcher behavior** (7 tests):
    - `test_dispatcher_applies_param_map_on_state_change` — publish `StateChanged(idle → listening)`; tick the cross-fade runner forward 200 ms; assert FakeRig recorded the listening-state parameter snapshot.
    - `test_dispatcher_crossfades_over_200ms_default` — assert the parameter value at `t=100ms` is halfway between idle's value and listening's target (within 1e-3 tolerance).
    - `test_dispatcher_each_state_has_complete_param_map` — assert `PARAM_MAP` has all five `StateName` keys; assert each maps to a non-empty parameter snapshot.
    - `test_dispatcher_each_state_triggers_expected_expression` — parametrize over `StateName`; assert `set_expression` was called with the documented per-state name (or skipped for states that don't trigger an expression).
    - `test_dispatcher_on_barge_in_redirects_target_to_idle` — start a `listening → speaking` cross-fade; publish `BargeInDetected` at t=80 ms; assert the cross-fade target snaps to idle's param snapshot; assert no stutter (the runner re-bases against the current interpolated value, not against `speaking`'s target).
    - `test_dispatcher_logs_state_transition_at_info` — capture logs; assert one `avatar.state_transition` line per `StateChanged` with the documented fields.
    - `test_dispatcher_drops_unknown_state_logs_warning` — publish a `StateChanged` with a (synthetically constructed) unknown state; assert WARNING line; assert no parameter changes.
  - **CrossFadeRunner unit** (3 tests):
    - `test_crossfade_lerp_at_endpoints` — t=0 → start; t=end → target. Exact equality.
    - `test_crossfade_lerp_at_midpoint` — t=mid → (start+target)/2. Tolerance 1e-6.
    - `test_crossfade_clamps_after_end` — t > end → target. No extrapolation.
  - **Frame-budget instrumentation** (2 tests):
    - `test_render_tick_logs_frame_time_histogram` — tick the GL widget's `paintGL` 60 times under offscreen; capture logs; assert a `avatar.frame_time` summary line fires every N ticks (default 60 = once/second) with `p50` / `p95` / `p99` keys.
    - `test_render_tick_drops_log_when_under_budget` — assert that when all 60 frame times are < 8 ms (well under the 16.67 ms budget at 60 Hz), the summary fires at INFO not WARNING. Inverse check: synthetic frame times > 16.67 ms emit at WARNING.
  - **Config + CLI** (2 tests):
    - `test_avatar_config_extended_defaults` — assert `model_path` / `fake_rig=False` / `target_fps=60` defaults.
    - `test_cli_avatar_dry_run_walks_all_five_states` — invoke `sabrina avatar dry-run` under `SABRINA_AVATAR_HEADLESS=1` + `[avatar] fake_rig=true`; assert rc=0; assert stdout contains one transition line per `StateName` value.

- `pyproject.toml` (project root) — extend `[project.optional-dependencies].avatar` (A2 added this) with `live2d-py>=0.6.1` (currently 0.6.1.1 per the April research). `sabrina-2/pyproject.toml` mirrors. No new top-level deps — `live2d-py` stays in the optional extra.

- `sabrina-2/.gitignore` — add `models/live2d/` if a placeholder rig is committed to the tree; otherwise leave alone (Eric drops the rig in manually, model file kept out of git via existing `models/` exclusion at root). **Recommendation: leave .gitignore alone.** The placeholder model_path is informational; the rig file is sourced from `live2d-py`'s sample assets at install time, not committed.

**(b)-half — `[windows-required]`. Reserved for P4.A4 (no new stage):**

- Real `live2d-py` wheel install on Win11 + Cubism Core DLL load + real GL render against the Hiyori_pro placeholder rig.
- Frame-budget validation: 60 Hz sustained under `sabrina voice` running in the same process. p95 < 12 ms on RTX 4080 is the watermark.
- Window flags + click-through + always-on-top survival against Eric's daily-driver app rotation (browsers, terminals, full-screen video).
- `voice_loop.py` wiring (the one conditional that mounts the avatar). Single line: `if settings.avatar.enabled and not settings.avatar.fake_rig: tasks.append(asyncio.create_task(run_avatar_window(bus, settings, rig)))`. Decision doc filing (`rebuild/decisions/0XX-avatar-architecture.md`, decision-doc voice) covers A1+A2+A3 collectively per the v1.0 component-Gate-1 pattern.
- `[avatar] enabled = true` toml flip.

The (b)-half is owned by P4.A4 in the existing QUEUE; A3's spec touches it only by leaving the seams clean (`fake_rig=False` path imports `live2d` lazily and survives a clean uninstall on Linux).

## Dependencies

- **P4.A1** (avatar architecture research, `[ ]`) — spec'd 2026-05-12; ratification of its (a)+(a)+(a) recommendations gates A3's SDK pick + IPC architecture. If Eric overrides Q1 (SDK pick) before A3 is pulled, the `rig.py` adapter targets a different library and the whole file needs a refresh. The (a) `live2d-py` path is what this spec assumes throughout.
- **P4.A2** (avatar PyQt6 skeleton, `[ ]`) — spec'd 2026-05-12; A3 builds on top of A2's `AvatarWindow` shell + `AvatarConfig` + CLI surface + headless-offscreen test pattern. A3 cannot be pulled before A2 lands as `[linux-shipped]`. If A2 ships first under (b) the side-process IPC path (Eric override on A1 Q3), A3's edits to `window.py` retarget to a different module — but the rig adapter + dispatcher + cross-fade runner stay shape-compatible.
- **`sabrina-2/src/sabrina/bus.py` + `events.py`** — read-only inputs. A3 adds a `bus.subscribe("barge_in_detected")` call alongside A2's `state_changed` subscription; no changes to bus or events module surfaces.
- **Phase 4 entry criteria** (per `ROADMAP.md` §"Phase 4 — Avatar + Automation + Brain router"). The Linux Partial-DoD ship can land before Phase 2 + Phase 3 exit. The Full-DoD promotion via P4.A4 waits on Phase 4 entry per ROADMAP convention.
- **`live2d-py` 0.6.x wheel availability** — confirmed in the April research; Windows-x64 wheels exist for Python 3.10-3.13. Linux wheels are NOT confirmed; the Cowork sandbox at Python 3.10 may or may not pick up `live2d-py` cleanly. The `fake_rig=True` default in the test config sidesteps this — A3's Partial-DoD gates do not require `live2d-py` to be installable in the sandbox.

Diff partition is independent of the eleven `[in-progress]` lock-blocked Worker diffs in the working tree (P0 cli/config truncation, P5.4, P5.5, P5.1, P2.7, P2.2, P4.B1, P4.C1, P4.C2, P5.3, and A2 once it ships). `avatar/` is a package A2 introduced; A3's edits to `window.py` + `runner.py` happen entirely inside that package. `config.py` + `sabrina.toml` extensions to `AvatarConfig` / `[avatar]` are additive in the same block A2 introduced.

## Concrete DoD

The fuzzy QUEUE Partial-DoD ("rig loads; model parameters change in response to mocked `idle/listening/thinking/speaking` transitions; render loop hits target framerate under sandbox-emulated GPU; `python -m compileall sabrina-2/src` clean; commit with `Windows-pending: e2e`") gets sharpened to:

1. **Files exist:** `sabrina-2/src/sabrina/avatar/rig.py`, `avatar/dispatcher.py`, `sabrina-2/tests/test_avatar_rig.py`. `avatar/window.py` + `avatar/runner.py` + `config.py` + `sabrina.toml` edited per the file partition above.
2. **`RigAdapter` Protocol stable** — `FakeRig` satisfies the same surface as the real `live2d-py`-backed adapter. The four `test_fake_rig_*` tests pass.
3. **`StateDispatcher` covers all five states** — `PARAM_MAP` has every `StateName` key; the parametrized `test_dispatcher_each_state_has_complete_param_map` test passes.
4. **Cross-fade math correct** — three `test_crossfade_*` unit tests pass; the lerp is exact at endpoints and at midpoint.
5. **Barge-in respected** — `test_dispatcher_on_barge_in_redirects_target_to_idle` passes; the cross-fade re-targets without stutter; the 200 ms budget from `decisions/009-barge-in-shipped.md` is honored.
6. **Frame-budget logging present** — `test_render_tick_logs_frame_time_histogram` passes; the `avatar.frame_time` line emits with `p50` / `p95` / `p99` fields.
7. **CLI `sabrina avatar dry-run` walks all five states** — `test_cli_avatar_dry_run_walks_all_five_states` passes under `SABRINA_AVATAR_HEADLESS=1` + `[avatar] fake_rig=true`.
8. **No regression on A2's surface** — all 12 A2 tests in `tests/test_avatar_skeleton.py` continue to pass post-A3 diff.
9. **Per-state expression coverage** — `test_dispatcher_each_state_triggers_expected_expression` passes; the per-state expression map is documented in the test parametrize block (the spec leaves the exact expression-name set to the implementing Worker's read of the April cue-track research).
10. **`python -m compileall sabrina-2/src sabrina-2/tests` clean.** AST-parse spot check on `window.py` + `runner.py` + `dispatcher.py` + `rig.py` (all under 300 lines individually so tail-integrity check per CLAUDE.md applies only to the two edited files >300 lines if any — `config.py` already crosses that line and inherits the check).
11. **`pytest sabrina-2/tests/test_avatar_rig.py sabrina-2/tests/test_avatar_skeleton.py -v`** — 18 + 12 = 30 PASS under the Cowork Linux/3.10 sandbox with `QT_QPA_PLATFORM=offscreen` exported and `[avatar] fake_rig=true` in a test-only toml fixture.
12. **No regression on `pytest sabrina-2/tests/test_smoke.py`** — post-diff PASS/SKIPPED/FAIL counts match pre-diff. The four pre-existing failures from worker baselines (2 VAD env / 1 sqlite migration / 1 personality-snapshot) remain unchanged. The 1 new wake_word test from P2.2 and the 14 persona tests from P4.C1 are both upstream of A3 and unaffected.
13. **No new top-level deps.** `live2d-py>=0.6.1` lands only in `[project.optional-dependencies].avatar`. `uv pip install -e .` without `[avatar]` still works.
14. **Commit on `automation/<role>-2026-05-DD-<slot>` branch** with `Windows-pending: e2e` in the body. Windows DoD checklist captured in JOURNAL.md per Partial-DoD protocol:
    - `uv pip install -e .[avatar]` succeeds on Win11.
    - `python -c "import live2d.v3 as live2d; live2d.init()"` exits 0 on Win11.
    - `sabrina avatar run` (with `[avatar] fake_rig = false` + a real `model_path`) opens a frameless window that renders the rig + responds to a `StateChanged` injection.
    - Frame-budget log line shows `p95 < 12 ms` over a 60 s window on the RTX 4080.
    - These four lines roll into P4.A4's Full-DoD checklist alongside A2's.

## Open NEEDS-INPUT for Eric

Two picks the Worker can't make without an Eric call. The spec recommends an answer for each; Worker can ship the (a)-half against the recommendations without waiting; if Eric overrides before pull, Worker reroutes per the answer.

1. **Per-state expression-slot binding** — the `StateDispatcher` triggers a Live2D expression slot per state (e.g. `acting` → `concerned`, `thinking` → `focused`). Should the spec hard-code this map in `dispatcher.py` as a constant, or expose it via `[avatar.expressions]` in `sabrina.toml`?
    - (a) Hard-coded constant in `dispatcher.py`. Simplest; matches the `BUILTIN_TOOLS` pattern from the ToolSpec MCP migration. Eric edits code to retune. Recommendation: **(a)**.
    - (b) `[avatar.expressions] idle = "neutral"` etc. in toml. Eric retunes without code changes. Cost: another Pydantic model + four lines of toml parsing.
    - (c) JSON sidecar file under `sabrina-2/configs/avatar_expressions.json`. Worst of both worlds — config-style ergonomics without toml's comment preservation. Ruled out.

2. **Placeholder rig commit policy** — should the placeholder Hiyori_pro rig be committed under `sabrina-2/models/live2d/` (git-LFS or direct binary), or treated as a runtime-only asset Eric drops in manually?
    - (a) Runtime-only; the rig path is informational. Eric downloads from `live2d-py`'s sample assets and drops the files into `sabrina-2/models/live2d/` outside git. `.gitignore` rule at `models/` excludes it automatically. Recommendation: **(a)** — matches the `hey_jarvis` wake-word placeholder pattern from P2.1's research where the model file lives outside git.
    - (b) Direct commit under git-LFS. Cost: git-LFS setup + ~3 MB binary in the repo. Benefit: clone+run works without an Eric-side step.
    - (c) Runtime download from `live2d-py`'s sample-asset URL on first `sabrina avatar run`. Cost: network dependency at first run; URL bit-rot risk. Ruled out.

The two picks are independent; (a)+(a) is the spec's default. If Eric picks (b) on Q2, A3's commit grows by a git-LFS setup step but the code surface is unchanged.

---

## (a)/(b) split framing (Sabrina-specific)

Per `roles/spec-writer.md` step 5: this item IS mixed-surface. The split is:

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`:** all files listed under "Proposed approach" above. Ships under Partial DoD; lands as `[linux-shipped]` in QUEUE/DONE; commit on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` in the body. The `FakeRig` test path is what makes this Linux-runnable without `live2d-py` installable in the sandbox; the real adapter behind `load_rig(settings)` is exercised by P4.A4's Windows session.

- **(b)-half — `[windows-required]`:** the five items listed under "(b)-half" above. Owned by the existing **P4.A4** queue item (no new stage). Promotion of A3 from `[linux-shipped]` to `[done]` happens when A4 fires. The decision doc P4.A4 files covers A1+A2+A3 collectively per the v1.0 component-Gate-1 pattern; no separate decision doc per Axx sub-stage.

The Planner can cite this split when promoting P4.A3 from `[ ]` to `[in-progress]` per `roles/planner.md` step 3.

## Notes on what this spec deliberately is NOT

- **Not the lip-sync wiring.** `ParamMouthOpenY` is set to a placeholder zero in the `speaking` state's param snapshot. Driving the mouth from speaker amplitude is a follow-up item (call it P4.A5 if-and-when authored; the April cue-track research already covers the design at 30 Hz). A3 leaves the seam clean: `set_parameter("ParamMouthOpenY", 0.0)` is just one entry in `PARAM_MAP["speaking"]`, replaceable by a streaming amplitude source without touching the dispatcher.
- **Not the cue-track dispatcher.** The April research sketched a `CueDispatcher` for per-utterance cue scheduling (`emotion` / `gesture` / `gaze` / `pause` cues from the brain's reply). A3 ships only the *state* dispatcher — per-state parameter snapshots driven by `StateChanged` events. Cue-track-from-reply is a later item; the directory layout (`avatar/dispatcher.py`) leaves room for a sibling `avatar/cue_dispatcher.py` without restructuring.
- **Not a Live2D editor / authoring tool.** Parameter values are entered as data in `PARAM_MAP` or `[avatar.expressions]`. Tuning the rig (eye-target ranges, breath rate, micro-blink probabilities) lives in Cubism Editor or in `live2d-py`'s built-in auto-effects (auto-blink, auto-breath both first-class per the April research). A3 just sets parameter values; it doesn't redefine them.
- **Not the voice_loop integration.** That single conditional line lives in P4.A4's Windows diff alongside the `[avatar] enabled = true` toml flip. A3 does not touch `voice_loop.py`.
- **Not a decision doc.** The decision doc lands at P4.A4 covering A1+A2+A3 per `rebuild/decisions/` precedent.
- **Not a refactor of `bus.py` or `events.py`.** The new `BargeInDetected` subscription is additive — `bus.subscribe("barge_in_detected")` already works against the existing bus API. No bus-side changes.
- **Not the always-on-top click-through Windows validation.** That's P4.A4's gate; A3's window-flag setup matches A2's exactly, just with `QOpenGLWidget` as the central widget instead of `QLabel`.

## Verification checklist (for the Worker pulling this)

- [ ] Read this spec end-to-end.
- [ ] Read `rebuild/drafts/research/2026-05-12-p4a2-avatar-pyqt-skeleton-spec.md` (A2 surface that A3 builds on).
- [ ] Read `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` (April research; load-bearing for window-flag preamble + timing budgets + per-state vocabulary).
- [ ] Read `sabrina-2/src/sabrina/events.py:55-63` (StateChanged shape) and `events.py` for `BargeInDetected` (the additional subscription A3 adds).
- [ ] Read `sabrina-2/src/sabrina/state.py` (StateName) — assert PARAM_MAP key-set matches.
- [ ] Confirm A2 has shipped as `[linux-shipped]` before pulling — A3 has hard file deps on A2's `window.py`, `runner.py`, and `AvatarConfig` model. If A2 is still `[ ]` or `[in-progress]`, defer A3 to next slot.
- [ ] Confirm Eric has ratified A1's (a)+(a)+(a) picks (or the spec's recs are accepted by silence per the OPEN-DECISIONS S11 bulk-ratify mechanism).
- [ ] Author the four new files + edit the four existing files per "Proposed approach" above.
- [ ] Apply the CLAUDE.md edit-tool-truncation discipline: AST-parse every edited Python file post-edit; bash heredoc + `os.fsync()` rewrite recovery path if Edit drops bytes; verify `cli.py` + `config.py` tail integrity (both >300 lines).
- [ ] Run the Linux Partial-DoD gates per "Concrete DoD" items 10-12; capture the regression count against the worker-baseline numbers in JOURNAL.
- [ ] File two NEEDS-INPUT entries (Q1 expression-slot binding, Q2 placeholder rig commit policy) with `[from: worker / 2026-05-DD HH:MM]` headers; ship the (a)-half against (a)+(a) without waiting.
- [ ] Stage commit on the existing `automation/worker-2026-05-07-8am` branch (do NOT `git checkout -b` per the FUSE-leak forensics from worker-8am 2026-05-07).
- [ ] Append JOURNAL.md per the standard Worker JOURNAL shape; mark `[linux-shipped]` if the commit lands, `[in-progress]` if the `.git/index.lock` is still present per the canonical lock-bail entry pattern.
