# P4.B2 — `send_hotkey` ToolSpec backed by `data/shortcuts.yaml` — spec

**Date:** 2026-05-09
**Author:** sabrina-spec-writer (06:50 scheduled run, actual wall-clock late after the planner)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Automation → **P4.B2 Automation — `send_hotkey` ToolSpec backed by `data/shortcuts.yaml`** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-05-08-p4b1-automation-safety-primitives-spec.md` — kill-switch + dry-run + scaffold spec. P4.B2 is the first real action ToolSpec that rides on top of those primitives. The (a)-half from P4.B1 ships `dry_run_wrap`, `KillSwitch`, and the `dry_run`/`kill_switch` kwargs on `ClaudeBrain.chat`; P4.B2 plugs into both seams without re-implementing them.
- `rebuild/drafts/research/2026-04-26-toolspec-first-three.md` — side-effect taxonomy. `send_hotkey` is `execute-OS`, the most dangerous side-effect class; the kill-switch + dry-run + (eventual) destructive-action allow-list (P4.B3) are the layered guards.
- `sabrina-2/data/shortcuts.yaml` — the canonical name → key-token-list mapping shipped by P5.2 (in DONE). Seventeen entries today (`copy`, `paste`, `cut`, `save`, `select_all`, `undo`, `redo`, `find`, `new_tab`, `close_tab`, `switch_tab`, `screenshot`, `task_view`, `file_explorer`, `system_settings`, `lock_screen`, `app_search`). Source: legacy `services/automation/automation.py:47-65` (off-limits).
- `sabrina-2/tests/test_shortcuts_yaml.py` — structural validator already shipped. Asserts the file exists, parses to a non-empty mapping, and that every entry is a list of strings with modifiers-first / key-last shape. P4.B2's runtime loader can presume that shape and skip re-validating it; P4.B2's test instead asserts that loader behavior matches the yaml-validator's promises.
- `sabrina-2/src/sabrina/tools/__init__.py` — `ToolSpec` base + `BUILTIN_TOOLS` list + `find()` lookup + `_builtin_tools()` lazy-import factory pattern. `send_hotkey` follows the same shape as `write_clipboard`: a sibling module under `sabrina-2/src/sabrina/tools/` exposing the async handler + a registration entry in `_builtin_tools()`.
- `sabrina-2/src/sabrina/tools/clipboard.py` — only existing handler. Two-tier import shape (`pyperclip` primary, native subprocess fallback) is the template P4.B2's keypress backend follows.
- `sabrina-2/src/sabrina/brain/claude.py:174-237` — current dispatch loop after P4.B1 (a)-half lands. Already wires `dry_run_wrap(spec.handler, name=spec.name)` and the `kill_switch.tripped` post-dispatch poll. P4.B2 changes nothing in this file.
- `sabrina-2/src/sabrina/automation/__init__.py` and `automation/{kill_switch,dry_run,scaffold}.py` — P4.B1 (a)-half scaffold. `send_hotkey` is the first non-scaffold consumer.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, `voice_loop.py` runtime path (no event-bus changes; no real keypress validation — that's P4.B4). P4.B2 does NOT register the tool to `BUILTIN_TOOLS` until P4.B4's quartet ships — registration goes behind the `[tools.send_hotkey] enabled` config knob (off by default; same pattern as P4.B1's `noop_action` scaffold, kept off until the dangerous primitives have a Windows e2e under their belt).

---

## What this item is

Component 10 (Automation) ships `send_hotkey` as its first real action ToolSpec. The handler accepts a shortcut name (e.g. `"copy"`), looks the name up in `data/shortcuts.yaml`, and presses the corresponding modifier+key combo on the user's keyboard. On Linux/sandbox the handler is exercised through a stubbed-out keypress backend (a `_KEYPRESS_FACTORY` injection seam, mirroring P4.B1's `_LISTENER_FACTORY` pattern); on Windows the real `pyautogui` (or pick from Q1 below) backend fires the keys. Linux-runnable Partial-DoD ship covers the ToolSpec wire-up, the schema round-trip, the dry-run path, the kill-switch path, the unknown-name error path, and the data-file load + cache. The single thing the (a)-half cannot prove is that an actual `Ctrl+C` on Eric's keyboard triggers a real OS-level copy — that's the P4.B4 quartet ship.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/tools/hotkey.py` (new, ~180 lines):
  - `class HotkeyError(Exception)` — base for the two paths below. Inherits `Exception`, not `BaseException`, so the existing `claude.py:200` `except Exception` branch catches it cleanly without a special case.
  - `class UnknownShortcutError(HotkeyError)` — raised when the input `name` doesn't appear in the loaded shortcut table. Carries `.available: tuple[str, ...]` so the model gets a useful tool_result error message ("unknown shortcut 'foo'; available: copy, paste, cut, ..."). The `claude.py:200-213` error path stringifies into the tool_result content; the available list helps the model self-correct on the next turn without a tool_use round-trip.
  - `class KeypressBackendError(HotkeyError)` — raised when the keypress backend itself errors (PATH issues, permission errors, etc.). Same surface as UnknownShortcutError; just a different cause.
  - `_load_shortcuts() -> dict[str, tuple[str, ...]]` — reads `data/shortcuts.yaml` once at module import time, freezes each value list to a tuple, returns a frozen mapping. Module-level cached constant `_SHORTCUTS: Mapping[str, tuple[str, ...]]`. Path resolution mirrors `tests/test_shortcuts_yaml.py`: `Path(__file__).resolve().parent.parent.parent.parent / "data" / "shortcuts.yaml"`. Spec rationale: load-once is fine because `data/shortcuts.yaml` is a static checked-in file, not user-mutable runtime config; reload-on-change adds complexity without payoff. If a future use case needs hot-reload, the cache is a single module-level dict and trivial to swap.
  - `_KEYPRESS_FACTORY: Callable[[Sequence[str]], None]` — module-level injection seam. Default = a real `pyautogui.hotkey(*tokens)` call (Q1 below picks the backend); tests override with a `_RecordingKeypress` callable that appends each call to a list for assertion. Mirrors the `_LISTENER_FACTORY` pattern from P4.B1's `kill_switch.py`.
  - `async def send_hotkey(name: str = "", **_extra: Any) -> dict[str, Any]` — the handler. Steps: (1) validate `name` is a non-empty string (return `{"success": False, "error": "name must be a non-empty string"}` if not — same defensive shape as `write_clipboard`'s `**_extra` tolerance for over-padding models); (2) look up `name` in `_SHORTCUTS`; raise `UnknownShortcutError(name, available=tuple(_SHORTCUTS))` on miss; (3) call `await asyncio.to_thread(_KEYPRESS_FACTORY, tokens)`; on any exception, raise `KeypressBackendError(str(exc))`; (4) return `{"success": True, "name": name, "tokens": list(tokens)}`. Async-shape via `asyncio.to_thread` matches `write_clipboard` (the keypress call is synchronous; we wrap to keep the brain's event loop responsive).
  - `SEND_HOTKEY_SPEC: ToolSpec` — module-level constant; consumers do `from sabrina.tools.hotkey import SEND_HOTKEY_SPEC`. The `input_schema` carries `{"name": "send_hotkey", "description": "Press a named keyboard shortcut on the user's machine.", "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Shortcut name from the configured table.", "enum": [...known names...]}}, "required": ["name"]}}`. Q2 below picks whether the `enum` enumerates shortcut names from the loaded table or stays freeform.
- `sabrina-2/src/sabrina/tools/__init__.py` — extend `_builtin_tools()` with a conditional registration. Add a `_send_hotkey_enabled()` helper that reads `Settings().tools.send_hotkey_enabled` (default False until P4.B4); if True, append `SEND_HOTKEY_SPEC` to the returned list. Q3 below picks the config-knob shape (single `[tools] send_hotkey_enabled` flag vs. nested `[tools.send_hotkey] enabled`). The module-level `BUILTIN_TOOLS` constant stays as-is; the helper gets called once at module import. Spec rationale: settings-aware registration matches the P4.B1 spec posture for `noop_action` (only register when explicitly enabled) and keeps the dangerous tool gated behind a config flip Eric can audit.
- `sabrina-2/src/sabrina/config.py` — additive field on the existing `ToolsConfig` Pydantic model (one of `tools_config_extends` / `[tools]` block already in `sabrina.toml`; verify shape during the run): `send_hotkey_enabled: bool = False`. No new model; one bool. Schema-version bump unnecessary per decision 008's posture (additive-with-default is back-compat).
- `sabrina-2/sabrina.toml` — additive `send_hotkey_enabled = false` line under the existing `[tools]` block. Spec note for the Worker: if `[tools]` doesn't already have a flat-flag pattern, model the addition on the existing `enabled` flag in the same block (or `[automation]` — the spec defers to the in-tree shape during the Worker run).
- `sabrina-2/tests/test_send_hotkey_tool.py` (new, ~280 lines) — fourteen unit tests:
  - `test_shortcuts_loaded_from_yaml` — `_SHORTCUTS` is a non-empty mapping; `"copy"` maps to `("ctrl", "c")`.
  - `test_shortcuts_values_are_frozen_tuples` — every value is a `tuple`, not a `list` (mutability guard).
  - `test_send_hotkey_dispatches_to_keypress_factory` — fake `_KEYPRESS_FACTORY` records the call; `await send_hotkey(name="copy")` causes one factory call with `("ctrl", "c")`.
  - `test_send_hotkey_returns_success_shape` — returns `{"success": True, "name": "copy", "tokens": ["ctrl", "c"]}`.
  - `test_send_hotkey_unknown_shortcut_raises_unknown_shortcut_error` — `await send_hotkey(name="foo")` raises `UnknownShortcutError`; `.available` includes `"copy"` and is sorted.
  - `test_send_hotkey_unknown_shortcut_does_not_call_keypress_factory` — fake factory never invoked on the unknown-name path.
  - `test_send_hotkey_empty_name_returns_error_shape` — `await send_hotkey(name="")` returns `{"success": False, "error": ...}` without raising and without calling the factory.
  - `test_send_hotkey_extra_kwargs_tolerated` — over-padded model call (`name="copy", extra="ignored"`) succeeds; mirrors the `write_clipboard(**_extra)` defensive shape.
  - `test_send_hotkey_keypress_backend_error_raises_keypress_backend_error` — fake factory raises `RuntimeError("backend missing")`; the handler raises `KeypressBackendError`; `claude.py`'s tool-dispatch error branch catches the base `Exception` and emits `ToolUseDone(error=...)`.
  - `test_send_hotkey_spec_round_trips_to_anthropic_dict` — `SEND_HOTKEY_SPEC.to_anthropic_dict()` matches the existing four `ToolSpec` round-trip tests at `test_smoke.py:1869-1965` (`{name, description, input_schema}` keys with `input_schema.type == "object"`).
  - `test_send_hotkey_spec_round_trips_to_mcp_dict` — `inputSchema` (camelCase) variant per the existing pattern.
  - `test_send_hotkey_not_in_builtin_tools_when_disabled` — with `Settings(tools=ToolsConfig(send_hotkey_enabled=False))`, `BUILTIN_TOOLS` does not include `SEND_HOTKEY_SPEC`. Spec note: this needs a conftest or settings-injection seam; if `_builtin_tools()` reads settings at import time, the test imports the module under a `monkeypatch.setattr(sabrina.config, "_DEFAULT_SETTINGS", ...)` shim. Worker decides the seam during the run.
  - `test_send_hotkey_in_builtin_tools_when_enabled` — symmetric; with `send_hotkey_enabled=True`, the registry includes the spec.
  - `test_claude_dispatch_dry_run_wraps_send_hotkey` — combination case: pull `SEND_HOTKEY_SPEC` into a fake brain stream emitting `tool_use` for `send_hotkey(name="copy")`; with `dry_run=True`, the `tool_result` content is the `dry_run_wrap` synthetic shape (`{"dry_run": True, "would_have_called": "send_hotkey", "input": {"name": "copy"}}`); the underlying `_KEYPRESS_FACTORY` is never invoked. Asserts the dry-run path from P4.B1 composes cleanly with the new tool.

**(b)-half — folded into P4.B4, NOT deliverable here:**

- Real `pyautogui.hotkey(*tokens)` (or whichever Q1 picks) exercised on Windows — the (a)-half ships the factory but uses a recording stub in tests.
- `[tools.send_hotkey] enabled = true` flip in `sabrina.toml` — only meaningful once Eric has run a real `Ctrl+C` end-to-end.
- One real Windows session: voice command "copy this to my clipboard" → brain emits `tool_use(name="copy")` → handler fires real keypress → application receives the `Ctrl+C` and copies its selection. Full DoD gate.
- Decision doc (under P4.B4) covering the B1 + B2 + B3 + B4 quartet under one number.

## What's deliberately NOT in scope

- **Multi-key chord sequences** — `data/shortcuts.yaml` today is single-chord (one modifier+key combo per name). Sequences like "Ctrl+K, Ctrl+S" (VS Code save-all) would need a richer schema. Out of scope for v1; the legacy table doesn't have any either.
- **Per-app shortcut routing** — same `copy` chord works across apps because the OS dispatches to the focused window. A future "app-aware" shortcut layer (e.g. press Discord's app-specific message-edit shortcut) would need window-focus introspection. Out of scope; would compose as a sibling tool, not a `send_hotkey` extension.
- **Recording new shortcuts at runtime** — `data/shortcuts.yaml` is checked-in static data. A "remember this chord as 'foo'" UX would compose with PROPOSED #29-style state-file hygiene, not with this handler. Out of scope.
- **Visual / audio feedback after keypress** — no "I copied that" TTS confirmation. The voice loop's existing `ToolUseDone` rendering path handles the status indication; if the brain wants to confirm, it does so through its next text turn naturally. UX polish belongs to P4.B4's voice-loop pass.

## Dependencies

- **P5.2** (shortcut data) — already in DONE; `data/shortcuts.yaml` exists and `tests/test_shortcuts_yaml.py` validates its shape. No additional work needed.
- **P4.B1** (kill-switch + dry-run scaffold) — (a)-half currently in working tree, blocked on the FUSE `.git/index.lock`. Once P4.B1 (a)-half commits, P4.B2 (a)-half is pull-ready; the dispatch-loop seams in `claude.py:174-237` are where dry-run + kill-switch flow through the new tool. If a Worker pulls P4.B2 before P4.B1 commits, the spec instruction is to depend on P4.B1's in-tree files (they are byte-identical to what the next Worker will see) and stage the P4.B2 commit on the existing `automation/worker-2026-05-07-8am` branch — partition-clean against P4.B1's diff (P4.B2 touches new files in `tools/hotkey.py` and `tests/test_send_hotkey_tool.py`; the only `tools/__init__.py` and `config.py`/`sabrina.toml` touches are additive in regions P4.B1 also doesn't modify).
- **Phase 3 (a)-half** — already in `main` (commit `acd6725`). Provides the `tools=` plumbing through `ClaudeBrain.chat`.
- **Phase 3 (b)-half** — NOT a dependency for P4.B2 (a)-half. The (b)-half wires `voice_loop.py` to instantiate the brain with `tools=BUILTIN_TOOLS`; without it, `[tools] enabled = true` doesn't fire from a real voice turn. P4.B2's Linux Partial-DoD ship covers the ToolSpec wire-up regardless; it just can't validate the voice-turn path until Phase 3 (b)-half + P4.B4 both ship on Windows.

## Concrete DoD

A Worker pulling P4.B2 ships the (a)-half when:

1. `sabrina-2/src/sabrina/tools/hotkey.py` exists with `send_hotkey`, `SEND_HOTKEY_SPEC`, `_load_shortcuts`, `_KEYPRESS_FACTORY`, and the three exception classes per the structure above.
2. `sabrina-2/src/sabrina/tools/__init__.py` registers `SEND_HOTKEY_SPEC` conditionally on `Settings().tools.send_hotkey_enabled`; default-False keeps it out of `BUILTIN_TOOLS`.
3. `sabrina-2/src/sabrina/config.py` has `ToolsConfig.send_hotkey_enabled: bool = False` (or the chosen Q3 shape).
4. `sabrina-2/sabrina.toml` adds the matching toml line with `false` default.
5. `sabrina-2/tests/test_send_hotkey_tool.py` exists with the fourteen tests above; all pass under the Cowork Linux/3.10 sandbox.
6. `python -m compileall -q sabrina-2/src sabrina-2/tests` exits 0.
7. AST parses clean for all touched files post-edit (CLAUDE.md edit-truncation guard).
8. `pytest sabrina-2/tests/test_send_hotkey_tool.py -v` reports 14/14 PASS.
9. Combined regression on `test_send_hotkey_tool` + the touched-tests baseline (`test_smoke` claude+tool tests + `test_automation_safety` after P4.B1 (a)-half + `test_shortcuts_yaml`) shows zero new failures relative to the working-tree baseline.
10. Commit message includes `Windows-pending: e2e` in the body and a Windows-side checklist matching this spec's `(b)-half` section in JOURNAL.md.
11. Worker self-review per `roles/worker.md` step 6 reports zero P0/P1 findings and any P2/P3 noted in the JOURNAL run-summary.

The (b)-half / Full DoD gate fires later, off this spec's surface, when Eric runs:

- A real `Ctrl+C` via the tool on his Windows box, in a focused text editor, and confirms the copied text round-trips to a paste in another app.
- `[tools] enabled = true` and `[tools.send_hotkey] enabled = true` (or the Q3-chosen config keys) in `sabrina.toml`.
- One voice session: "copy this" → brain emits `tool_use(send_hotkey, name="copy")` → handler fires → confirmation paste works.
- `pytest` on Windows passes.
- Decision doc filed (the B1+B2+B3+B4 quartet doc per P4.B4).

## Open questions for NEEDS-INPUT

**Q1: Real-keypress backend pick.** Three viable options, all with prior art in the legacy code or in the existing rebuild:

(a) **`pyautogui.hotkey(*tokens)`** — the legacy `services/automation/automation.py:96` shape. Cross-platform. Already a transitive dep via the listener stack? Verify during the run. Pros: simplest API, one function call, cross-platform; cons: pulls a heavier dep, has historical issues with admin-mode-elevated targets (UAC dialogs etc.).

(b) **`pynput.keyboard.Controller` + context-manager press/release** — already a Sabrina dep (P4.B1 (a)-half lists `pynput.keyboard.GlobalHotKeys` in `_LISTENER_FACTORY`). Pros: dep already present; consistent with kill-switch listener; finer-grained control; cons: token-vocabulary is `pynput.keyboard.Key.ctrl` + `'c'` not `"ctrl"` + `"c"`, so the YAML token list needs translation.

(c) **`keyboard` (third-party `keyboard` PyPI package)** — Eric's daily-driver legacy used this for global hotkeys. Pros: simplest token vocabulary (`keyboard.send("ctrl+c")` accepts plus-joined strings — closest to the YAML shape); cons: needs root on Linux to register hooks, but for `send` (not `hook`) it's fine; another dep.

**Spec recommendation: (b)** — pynput is already in the dep tree post-P4.B1, the token-translation table is small and self-documenting, and consolidating on one keyboard library across the kill-switch listener and the keypress backend keeps the surface coherent. Worker can ship the (a)-half against (b) without waiting for an answer; if Eric overrides before pull, Worker reroutes per the answer.

**Q2: Input-schema enum vs freeform string.** Should the `SEND_HOTKEY_SPEC.input_schema.properties.name.enum` enumerate the loaded shortcut names (forcing the model to pick from the table at the API boundary), or stay as a plain `"type": "string"` with the unknown-name path catching mistakes at handler time?

(a) **Enum** — model can't emit an invalid name; tighter feedback loop; lower failure rate. Cost: every yaml change recompiles the schema (the schema is constructed at module import from the loaded table — automatic if `_load_shortcuts()` runs first). Couples the schema to the data file but the data file is checked in, so coupling is fine.

(b) **Freeform** — looser; model can emit anything; handler returns `UnknownShortcutError` with the available list for self-correction. Costs one tool-call round-trip per miss but reduces the schema's surface.

**Spec recommendation: (a)** — the model emits valid names by construction, the unknown-name path becomes a defense-in-depth check rather than the primary failure handler, and the YAML's seventeen entries are well within Anthropic's enum-cardinality comfort zone. Worker can ship the (a)-half against (a) without waiting; if Eric overrides before pull, Worker reroutes.

**Q3: `[tools.send_hotkey] enabled` config-knob shape.** Single flat flag (`[tools] send_hotkey_enabled = false`) vs. nested block (`[tools.send_hotkey] enabled = false`)?

(a) **Flat** — one boolean per tool inside the existing `[tools]` block. Pros: minimal config-schema growth; simpler Pydantic shape (`ToolsConfig.send_hotkey_enabled: bool`); cons: if the tool grows knobs later (e.g. `default_app: str | None`), the config schema needs a Pydantic-model split anyway.

(b) **Nested** — each tool gets its own `[tools.<name>]` block with at minimum `enabled: bool`. Pros: extensible from day one; matches P4.B1's `[automation.kill_switch]` shape; cons: schema bloats with empty single-key models for tools that never grow knobs.

**Spec recommendation: (a)** — `send_hotkey` is unlikely to grow knobs (the YAML is the data, not the config; per-tool defaults like `default_repeat: int` would compose as YAML metadata, not config). If a future tool needs a nested block, that future tool's spec can introduce the migration path. Worker can ship the (a)-half against (a) without waiting.

NEEDS-INPUT entries for Q1/Q2/Q3 below as `[from: spec-writer / 2026-05-09 06:50]`.

## Files this spec deliberately does NOT name

- `voice_loop.py` — Phase 3 (b)-half + P4.B4 territory.
- `events.py` — no new event types; the existing `ToolUseDone` from `claude.py` carries success and error paths.
- `automation/scaffold.py` (`noop_action` etc.) — P4.B1 surface; P4.B2 sits alongside, not on top.
- `rebuild/decisions/` — decision doc lands at P4.B4.

## Composability notes

- **With P4.B1 (a)-half (in-tree, lock-blocked):** zero file overlap. P4.B1 touches `automation/__init__.py`, `automation/{kill_switch,dry_run,scaffold}.py`, `brain/claude.py:174-237`, `config.py` `AutomationConfig`, `sabrina.toml` `[automation]`, `tests/test_automation_safety.py`. P4.B2 touches `tools/hotkey.py`, `tools/__init__.py`, `config.py` `ToolsConfig.send_hotkey_enabled`, `sabrina.toml` `[tools]`, `tests/test_send_hotkey_tool.py`. The two `config.py` and `sabrina.toml` regions sit in separate blocks; concurrent application is partition-clean.
- **With P4.B3 (destructive-action allow-list):** P4.B3's allow-list applies *across* the registry; `send_hotkey` should be on the allow-list when P4.B3 ships (it's destructive — keypresses fire system-level). P4.B2's spec doesn't decide allow-list membership; P4.B3's spec does, and it should reference `SEND_HOTKEY_SPEC` by name.
- **With P4.B4 (Windows e2e):** P4.B4's quartet ship promotes B1 + B2 + B3 from `[linux-shipped]` to `[done]` after the four-tool checklist (kill-switch trip + dry-run hit + destructive-action block + real `send_hotkey` keypress) all fire on Windows.

## Edit-tool truncation hazard reminder

Per CLAUDE.md and the recurring incidents in JOURNAL (worker-9am 2026-05-08 hit it 4x; worker-12pm 2026-05-08 hit it 3x; worker-8am 2026-05-09 hit it 5x): verify file contents post-edit. AST-parse `tools/hotkey.py` and `tests/test_send_hotkey_tool.py` after every Edit-tool call; spot-check the final 20 lines of each file for tail integrity. The recovery path is bash heredoc + Python `os.fsync()` rewrite + AST verification per the documented escape hatch.

## What the Planner does with this spec

Per `roles/spec-writer.md` step 6: this is a draft. The Planner at 07:00 (or whenever it next runs) decides whether to keep the queue entry as-is, add a `**Spec at ...**` pointer line, or surface the open questions to Eric. The spec-writer does NOT promote, does NOT mark done, does NOT approve.
