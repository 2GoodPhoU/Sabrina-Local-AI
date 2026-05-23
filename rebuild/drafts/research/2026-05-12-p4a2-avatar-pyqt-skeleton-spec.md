# P4.A2 — Avatar PyQt6 skeleton + StateChanged subscriber — spec

**Date:** 2026-05-12
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Avatar → **P4.A2 Avatar — PyQt6 skeleton + StateChanged subscriber** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors / canon to consult:**
- `rebuild/drafts/research/2026-05-12-p4a1-avatar-architecture-research-spec.md` (companion spec for P4.A1, same slot). P4.A2 is built against P4.A1's recommendations; the three load-bearing picks are (a) `live2d-py` (deferred to A3, irrelevant here), (a) full click-through with kill-button elsewhere, (a) in-process subscriber via `qasync`.
- `sabrina-2/src/sabrina/events.py:55-63` — `StateChanged(from_state, to_state, reason)` event shape. Subscriber filter target.
- `sabrina-2/src/sabrina/bus.py:31-83` — `EventBus.subscribe("state_changed")` async-iterator API. Lossy-on-backpressure; the avatar is a low-stakes subscriber and can drop frames without affecting voice.
- `sabrina-2/src/sabrina/state.py` (StateName: `idle | listening | thinking | speaking | acting`). The five states A2 will eventually drive on the rig in A3.
- `sabrina-2/src/sabrina/logging.py` — `get_logger(__name__)` + `redact_secrets` processor. Avatar logger must use this; no new `logging.getLogger` calls.
- `sabrina-2/src/sabrina/cli.py` — typer app surface. P4.A2 ships a new `sabrina avatar` subcommand that launches the skeleton window standalone.
- `pyproject.toml` (root + `sabrina-2/pyproject.toml`) — dependency additions land here. PyQt6 + qasync are new top-level deps; both are well-maintained and Windows-x64-wheel-available.
- `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` — cue-track design; A2 does not consume cues yet (that's A3), but the StateChanged subscriber wiring is what A3 builds on.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. The Qt window can be exercised headlessly under `QT_QPA_PLATFORM=offscreen`. The Windows-required behaviors (real frameless/always-on-top/click-through validation on Win11) are reserved for P4.A4 — A2 ships under Partial DoD, A4 promotes A2/A3 to `[done]` after the one Windows e2e session.

Off-limits: `rebuild/decisions/`, legacy root-level dirs, `voice_loop.py` runtime path (no event-bus changes in A2 — only a new subscriber), `pre-commit-config.yaml`.

---

## What this item is

The Avatar component's first writable surface. The QUEUE entry frames a "minimal frameless click-through window that subscribes to `StateChanged` and prints state transitions; no Live2D rig yet." That description maps cleanly to: a new `sabrina-2/src/sabrina/avatar/` package, a `window.py` module exposing an `AvatarWindow` class (frameless PyQt6 `QMainWindow` or `QWidget` with the three window flags + click-through attribute set), an asyncio↔Qt bridge via `qasync`, a `bus.subscribe("state_changed")` consumer that logs each transition + sets a placeholder visible state indicator (a plain-text label or colored rectangle), and a `sabrina avatar` CLI subcommand that starts the skeleton standalone for development.

The skeleton is intentionally hollow on the rig side — it renders a placeholder per state, not a Live2D model. The point of A2 is to prove the wire-up (window flags + event bus subscription + Qt event loop + asyncio bridge) under Linux Partial DoD before A3 invests in the Live2D rig. If A2's wire-up is wrong, A3's work compounds the wrongness; landing A2 cleanly first contains the failure surface.

A2 does **not** instantiate from `voice_loop.py`. The voice loop has no awareness of the avatar yet — that wiring is part of A3 (when the rig is on) or A4 (the Windows e2e + promotion ship). For A2, the only entry points are the unit tests and the `sabrina avatar` CLI command.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/avatar/__init__.py` (new package marker, ~15 lines) — module docstring naming the three current responsibilities (window flags, event-bus subscriber, placeholder per-state indicator) and the explicit non-responsibilities (Live2D rig: A3; voice_loop integration: A4; click-through Windows validation: A4).
- `sabrina-2/src/sabrina/avatar/window.py` (new, ~180 lines):
  - `class AvatarWindow(QMainWindow)` — frameless, always-on-top, click-through. Constructor takes `bus: EventBus`, `settings: Settings`, optional `parent: QWidget | None = None`.
  - Window flags applied in `__init__`: `Qt.WindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)`. Attributes: `setAttribute(Qt.WA_TranslucentBackground)` and `setAttribute(Qt.WA_TransparentForMouseEvents)` — the full click-through path per P4.A1 §2 recommendation. Click-through is whole-window; opaque-region-accepts-clicks is deferred to a future iteration if Eric overrides P4.A1's Q2 pick.
  - Placeholder UI: a single `QLabel` whose text is the current state name (`idle` / `listening` / `thinking` / `speaking` / `acting`) and whose background color cycles per state. No image, no animation — A3 replaces the QLabel with the rig surface.
  - Subscriber wiring: an `async def _consume(self) -> None` coroutine that iterates `self._bus.subscribe("state_changed")` and calls `self._on_state_changed(ev)` per event. Hooked into the Qt event loop via `qasync.asyncSlot` or an `asyncio.create_task` on the qasync-managed loop.
  - `def _on_state_changed(self, ev: StateChanged) -> None` — updates the QLabel text + background. Logs `avatar.state_changed` at INFO with `from_state` / `to_state` / `reason`. No exceptions raised — a malformed event logs at WARNING and is dropped (consistent with `bus.py`'s lossy-on-backpressure posture).
  - `def closeEvent(self, event)` — cancels the consumer task cleanly; emits `avatar.closed` at INFO.
- `sabrina-2/src/sabrina/avatar/runner.py` (new, ~60 lines):
  - `async def run_avatar_window(bus: EventBus, settings: Settings) -> None` — the qasync entry point. Constructs `QApplication`, instantiates `AvatarWindow`, runs the qasync loop until the window closes.
  - `def main(settings: Settings | None = None) -> int` — sync wrapper that the CLI calls. Sets `QT_QPA_PLATFORM=offscreen` if `os.environ.get("SABRINA_AVATAR_HEADLESS") == "1"` (test entry point); otherwise leaves the platform default alone. Returns exit code.
- `sabrina-2/src/sabrina/cli.py` — additive `sabrina avatar` subcommand. Two verbs:
  - `sabrina avatar run` — calls `avatar.runner.main(settings)` in the foreground. Voice loop is NOT started; this is the avatar-skeleton-only entry point for development.
  - `sabrina avatar dry-run` — instantiates `AvatarWindow` in offscreen mode, publishes one fake `StateChanged(idle → listening)` to the bus, asserts the label updates, exits with rc=0. Used by the integration test below as a smoke check.
- `sabrina-2/src/sabrina/config.py` — additive `AvatarConfig` Pydantic model:
  - `enabled: bool = False` (off by default; flipped only by P4.A4 after Windows validation).
  - `window_size: tuple[int, int] = (256, 256)` (placeholder; A3 reads this).
  - `position: Literal["bottom-right", "bottom-left", "top-right", "top-left", "center"] = "bottom-right"` (placeholder; A3 reads this).
  - Wired into `Settings.avatar` (Pydantic field).
- `sabrina-2/sabrina.toml` — new `[avatar]` block with the four defaults above. Lives between `[brain.persona]` (added by P4.C1) and `[tts]`.
- `sabrina-2/tests/test_avatar_skeleton.py` (new, ~250 lines, ~12 tests):
  - `test_avatar_window_flags_applied_at_init` — instantiate under `QT_QPA_PLATFORM=offscreen`; assert `windowFlags()` contains `FramelessWindowHint | WindowStaysOnTopHint | Tool`; assert `testAttribute(WA_TranslucentBackground)` and `testAttribute(WA_TransparentForMouseEvents)` are True.
  - `test_avatar_window_default_state_is_idle` — assert the initial QLabel text is `"idle"` before any StateChanged event lands.
  - `test_avatar_consumer_updates_label_on_state_changed` — publish a `StateChanged(from_state="idle", to_state="listening")` via a real `EventBus`; pump the qasync loop one tick; assert label text is `"listening"`.
  - `test_avatar_consumer_handles_each_state_name` — parametrize over all five `StateName` values; assert label updates each time. Sanity check for full state-coverage; protects against typos in the per-state branch.
  - `test_avatar_consumer_logs_state_change_at_info` — capture logs; assert `avatar.state_changed` line emits with the expected `from_state` / `to_state` / `reason` fields.
  - `test_avatar_consumer_drops_malformed_event_logs_warning` — publish a non-`StateChanged` event via raw dict; assert the consumer logs at WARNING and continues (does not raise).
  - `test_avatar_consumer_cancels_cleanly_on_close` — open the window, register the consumer, close the window; assert the consumer task is cancelled and the consumer coroutine raised `CancelledError` exactly once.
  - `test_avatar_consumer_survives_publish_backpressure` — publish 10000 StateChanged events as fast as the bus allows; assert no exception escapes the consumer; assert the dropped-event log line fires (consistent with `bus.py`'s `bus.dropped_event` shape).
  - `test_cli_avatar_dry_run_exits_zero` — invoke `sabrina avatar dry-run` via typer's CliRunner with `SABRINA_AVATAR_HEADLESS=1`; assert rc=0; assert stdout contains the success line.
  - `test_avatar_config_defaults` — instantiate `Settings()` with `[avatar]` block absent from toml; assert all four fields default to the documented values.
  - `test_avatar_config_round_trips_through_toml` — write a custom `[avatar]` block to a temp toml; instantiate `Settings`; assert the values round-tripped correctly.
  - `test_avatar_runner_main_returns_zero_when_window_closes_cleanly` — invoke `runner.main(settings)` under offscreen; programmatically close the window after one tick; assert rc=0.
- `pyproject.toml` (project root) — add `PyQt6` + `qasync` to `[project.optional-dependencies].avatar`. **NOT** in core deps — the avatar must be optional so a `sabrina voice` install without the avatar extras still works. The `sabrina-2/pyproject.toml` mirrors this addition.
- `sabrina-2/.gitignore` — no change (no new artifacts).

**(b)-half — `[windows-required]`. Reserved for P4.A4 (no new stage):**

- Real frameless/always-on-top/click-through validation on Windows 11. Specifically: window stays on top across `cmd.exe`, browsers, full-screen video, and `sabrina voice` itself; click-through allows mouse events to pass to the app underneath; always-on-top survives focus changes.
- `voice_loop.py` wiring — `if settings.avatar.enabled: tasks.append(asyncio.create_task(run_avatar_window(bus, settings)))`. Single conditional line.
- Decision doc filing (`rebuild/decisions/0XX-avatar-architecture.md`, decision-doc voice) — references A1's research doc + states the v1 picks ratified.
- `[avatar] enabled = true` toml flip.

The (b)-half is owned by P4.A4 in the existing QUEUE; A2's spec touches it only by setting up the seams.

## Dependencies

- **P4.A1** (avatar architecture research) — load-bearing for the three picks the spec assumes. Specifically: §1 SDK pick is irrelevant here (deferred to A3); §2 click-through policy is the (a) full-click-through path; §3 IPC architecture is the (a) in-process via qasync path. If Eric overrides any of these before A2 is pulled, the spec needs a refresh — see "Open NEEDS-INPUT" below.
- **No other queue items.** A2 stands alone among the (a)-half Linux-runnable diffs.
- **Phase 3 (a)-half** — already in `main` per DONE.md 2026-05-05 (commit `acd6725`). The brain/tool surface is stable.

The diff partition is independent of all current `[in-progress]` lock-blocked Worker diffs (P0 cli/config truncation fix, P5.4, P5.5, P5.1, P2.7, P2.2, P4.B1, P4.C1, P4.C2, P5.3). Zero file overlap with any of them — `avatar/` is a new package; `cli.py` and `config.py` edits are additive in regions outside the lock-blocked diffs.

## Concrete DoD

The QUEUE Partial-DoD DoD ("`sabrina-2/src/sabrina/avatar/window.py` launches a frameless PyQt6 window; subscribes to the event bus and logs each `StateChanged`; closes cleanly; unit test against a mocked event bus") gets sharpened to:

1. **Files exist:** `sabrina-2/src/sabrina/avatar/__init__.py`, `avatar/window.py`, `avatar/runner.py`, `sabrina-2/tests/test_avatar_skeleton.py`.
2. **`AvatarWindow` instantiable under offscreen** — `QT_QPA_PLATFORM=offscreen python -c "from sabrina.avatar.window import AvatarWindow; from sabrina.bus import EventBus; from sabrina.config import Settings; from PyQt6.QtWidgets import QApplication; app = QApplication([]); w = AvatarWindow(EventBus(), Settings.model_construct()); print('ok')"` exits 0 and prints `ok`.
3. **Window flags applied** — assertions in `test_avatar_window_flags_applied_at_init` pass.
4. **State subscriber working** — `test_avatar_consumer_updates_label_on_state_changed` passes; the label text updates within one qasync loop tick of the `StateChanged` publish.
5. **Per-state coverage** — `test_avatar_consumer_handles_each_state_name` passes for all five `StateName` values (no missing branch, no typo).
6. **Logging integrated** — `test_avatar_consumer_logs_state_change_at_info` passes; the logger is `get_logger(__name__)`, not `logging.getLogger`.
7. **Backpressure tolerated** — `test_avatar_consumer_survives_publish_backpressure` passes; the lossy-on-backpressure semantics from `bus.py` work as documented.
8. **CLI subcommand works** — `sabrina avatar dry-run` (under `SABRINA_AVATAR_HEADLESS=1`) exits 0.
9. **`python -m compileall sabrina-2/src sabrina-2/tests` clean.**
10. **AST-parse spot check** — `cli.py`, `config.py` (the two edited core files) both parse cleanly; both >300 lines so tail-integrity check per CLAUDE.md applies.
11. **`pytest sabrina-2/tests/test_avatar_skeleton.py -v`** passes 12/12 under the Cowork Linux/3.10 sandbox with `QT_QPA_PLATFORM=offscreen` exported. If PyQt6 is not pip-installable into the sandbox (Python 3.10 + sandbox restrictions), the entire P4.A2 (a)-half retargets to Eric's Windows session as a `[windows-required]` item — see "Bailout conditions" below.
12. **No regression** — `pytest sabrina-2/tests/test_smoke.py` post-diff matches pre-diff PASS/SKIPPED/FAIL counts (the four pre-existing failures from worker baselines unchanged).
13. **Commit on `automation/<role>-2026-05-DD-<slot>` branch** with `Windows-pending: e2e` in the body. Windows DoD checklist captured in JOURNAL.md per Partial-DoD protocol.

## Open NEEDS-INPUT for Eric

Two picks the Worker can't make without Eric's call. The spec recommends an answer for each.

1. **PyQt6 dependency tier** — core (a) or optional extra (b)?
    - (a) Core dep: `PyQt6` + `qasync` in `[project.dependencies]`. Simplest; every `sabrina voice` install gets the avatar binary regardless. Cost: ~50 MB extra wheel install on every box. Recommendation: **(b) optional extra**.
    - (b) Optional extra under `[project.optional-dependencies].avatar`. Install via `uv pip install -e .[avatar]`. Pure voice-loop users skip the install. Spec recommends this — matches the "Avatar is nice-to-have" framing in `rebuild/ROADMAP.md` §198.
    - (c) Vendored / lazy-imported: ship `PyQt6` as a runtime check inside `avatar/__init__.py` with a helpful "uv pip install sabrina[avatar]" error message. Cost: more code; weirder failure surface.
2. **Headless test platform pick** — `QT_QPA_PLATFORM=offscreen` (a) or `xvfb` virtual display (b)?
    - (a) Offscreen: PyQt6's built-in offscreen platform plugin. No X11 server needed. Most CI-friendly. Recommendation: **(a)**.
    - (b) Xvfb: spin up a virtual X11 display in test fixtures. Heavier; depends on `xvfb-run` being on the test host (not guaranteed in Cowork sandbox).
    - (c) Skip Qt tests in headless: mark `requires_display` per the `requires_gpu` precedent in P5.5. Cost: skips 9 of the 12 tests in the Cowork sandbox; defers their gate to Windows.

Worker can ship the (a)-half against (b)+(a) without waiting; if Eric overrides before pull, Worker reroutes per the answer here.

## (a)/(b) split framing (Sabrina-specific)

Per `roles/spec-writer.md` step 5: this item IS mixed-surface (it has a Linux-runnable code half AND a Windows-required validation half). The split is:

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`:** all files listed under "Proposed approach" above. Ships under Partial DoD; lands as `[linux-shipped]` in QUEUE/DONE; commit on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` in the body.
- **(b)-half — `[windows-required]`:** the four items listed under "(b)-half" in Proposed approach. Owned by the existing **P4.A4** queue item (no new stage). Promotion of A2 from `[linux-shipped]` to `[done]` happens when A4 fires.

The Planner can cite this split when promoting P4.A2 from `[ ]` to `[in-progress]` per `roles/planner.md` step 3.

## Notes on what this spec deliberately is NOT

- **Not the Live2D rig.** The placeholder QLabel is intentional. A3 replaces it with a real rig surface.
- **Not the voice_loop integration.** That's a one-line conditional in `voice_loop.py` that A4 ships alongside the Windows validation. A2 does not touch `voice_loop.py`.
- **Not the decision doc.** The decision doc lands at A4 per `rebuild/decisions/` precedent.
- **Not a refactor.** No existing `.py` file is restructured. The edits to `cli.py` and `config.py` are pure additions (new typer subcommand; new Pydantic model + Settings field).
- **Not a click-through-with-opaque-buttons implementation.** Per P4.A1 §2 recommendation (a), the entire window is click-through. Eric's override on P4.A1 Q2 retargets this — see the predecessor spec.

## Verification checklist (for the Worker pulling this)

- [ ] P4.A1 research doc shipped + Eric has answered (or the spec recs (a)/(a)/(a) are accepted by silence).
- [ ] Read this spec end-to-end.
- [ ] Read `sabrina-2/src/sabrina/bus.py:31-83` and `events.py:55-63`.
- [ ] Verify PyQt6 + qasync are installable into the Cowork Linux/3.10 sandbox. If not, bail per the "Bailout" note in DoD #11 — A2 retargets fully to Windows.
- [ ] Author the four new files + edit cli.py / config.py / sabrina.toml / pyproject.toml per the file list.
- [ ] Run the 12-test suite under `QT_QPA_PLATFORM=offscreen`; all must pass.
- [ ] Run combined regression on test_smoke + test_avatar_skeleton + all other test_* files Worker baselines have touched recently; no regression on the established PASS counts.
- [ ] Commit on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` + the Windows DoD checklist verbatim from the (b)-half framing above in the JOURNAL entry.
- [ ] Mark `[in-progress] [linux-runnable] [partial-dod-eligible]` in QUEUE (Planner converts to `[linux-shipped]` if commit lands).

## Bailout conditions (Worker stops, writes to NEEDS-INPUT, exits)

- PyQt6 doesn't install into the Cowork Linux/3.10 sandbox (wheel ABI mismatch, build-from-source failure, or `qasync` install fails). The (a)-half retargets fully to Eric's Windows session. File a NEEDS-INPUT entry naming the install error and bail.
- `qasync` + `bus.subscribe` integration produces a deadlock or runaway-task issue under offscreen — surfaces as a hanging test. File a NEEDS-INPUT entry describing the deadlock shape and ship the spec retargeted to side-process IPC per P4.A1 §3 (b) override.
- Eric has answered P4.A1 with a non-(a) pick on §3 IPC architecture (side-process). The spec is wrong; retire it and write a new one for the side-process path before pulling A2.
