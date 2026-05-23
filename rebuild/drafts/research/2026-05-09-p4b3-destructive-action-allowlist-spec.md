# P4.B3 — Destructive-action allow-list config — spec

**Date:** 2026-05-09
**Author:** sabrina-spec-writer (06:50 scheduled run, actual wall-clock late after the planner)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Automation → **P4.B3 Automation — destructive-action allow-list config** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-05-08-p4b1-automation-safety-primitives-spec.md` — kill-switch + dry-run + scaffold spec. Names destructive-action allow-list as the third leg of automation safety. The (a)-half also reserves the `destructive_actions: list[str] = []` field on `AutomationConfig` as the P4.B3 forward-compat hook.
- `rebuild/drafts/research/2026-05-09-p4b2-send-hotkey-toolspec-spec.md` — first real action ToolSpec spec. Names `send_hotkey` as a destructive ToolSpec; the allow-list determines whether it can fire. P4.B2's spec defers allow-list membership to this doc.
- `rebuild/drafts/research/2026-04-26-toolspec-first-three.md` — side-effect taxonomy. Three classes: `read-only`, `read-fs`/`write-clipboard` (low-risk), `execute-OS` (destructive). Allow-list applies to the third class.
- `ROADMAP.md` § "Phase 4" — automation = "most-dangerous-component-last". The third leg of safety alongside kill-switch + dry-run.
- `CLAUDE.md` "Phase-4 design" — explicitly calls out kill-switch + dry-run + destructive-action allow-list as the three guards.
- `sabrina-2/src/sabrina/tools/__init__.py:35-72` — `ToolSpec` dataclass (`name`, `description`, `input_schema`, `handler`). Adding a fifth field is the change surface. Frozen + slotted; the addition is one line.
- `sabrina-2/src/sabrina/automation/__init__.py` and `automation/{kill_switch,dry_run,scaffold}.py` — P4.B1 (a)-half scaffold. The allow-list guard is a sibling `automation/allow_list.py` module.
- `sabrina-2/src/sabrina/brain/claude.py:174-237` — current dispatch loop after P4.B1 (a)-half lands. The allow-list check fires *before* dispatch (before kill-switch, before dry-run wrap), so a blocked destructive call never invokes the handler at all.
- `sabrina-2/src/sabrina/config.py` — `AutomationConfig` already has `destructive_actions: list[str] = []`. P4.B3 wires it into the runtime guard; no schema change needed.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, `voice_loop.py` runtime path. P4.B3 does NOT change `claude.py` dispatch ordering — the allow-list check is one new line at the top of the existing tool-dispatch branch, before the dry-run wrap. P4.B3 does NOT add a new event type.

---

## What this item is

The allow-list is the third leg of automation safety. After kill-switch (P4.B1: trip-mid-action) and dry-run (P4.B1: log-without-firing), the allow-list answers a different question: *should this tool be allowed to fire at all?* A `destructive` flag on `ToolSpec` marks tools whose effects are irreversible-ish (`send_hotkey` from P4.B2, future `launch_app`, future `open_file`). At runtime, the brain's tool-dispatch loop checks: if the tool is destructive AND its name is not in the user's `[automation] destructive_actions` allow-list, raise `DestructiveActionBlocked` — the dispatch error path catches it and emits `ToolUseDone(error="destructive_action_blocked")` so the model can re-plan without the action firing. Linux-runnable Partial-DoD ship covers the protocol field, the guard module, the dispatch-loop wire-up, the config-driven allow-list resolution, and the four error-path branches. Real keypress validation (the actual proof that a blocked `send_hotkey` doesn't fire) is folded into P4.B4 alongside the kill-switch + dry-run quartet.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/tools/__init__.py` — extend `ToolSpec` dataclass with one additive field:
  - `destructive: bool = False` — declarative tag at registration time. Defaults to False so existing `write_clipboard` ToolSpec doesn't need to change. Spec rationale: per-spec is the right home (not per-handler) because the *spec* is what the brain sees; the handler is private. Frozen + slotted dataclass tolerates the additive field without a schema-version bump.
  - `to_anthropic_dict()` and `to_mcp_dict()` are unchanged — `destructive` is a Sabrina-internal runtime concern; it's not part of the Anthropic SDK's tool surface or the MCP wire format.
  - Update the existing `_builtin_tools()` factory: `write_clipboard` keeps `destructive=False` (default; explicit in the constructor for documentation). When P4.B2 registers `SEND_HOTKEY_SPEC`, that spec carries `destructive=True`.
- `sabrina-2/src/sabrina/automation/allow_list.py` (new, ~120 lines):
  - `class DestructiveActionBlocked(Exception)` — raised inside the tool-dispatch branch when a destructive ToolSpec is invoked but its name is not in the allow-list. Inherits `Exception`, not `BaseException` — `claude.py:200`'s existing `except Exception` branch catches it cleanly. Carries `.name: str` and `.allow_list: tuple[str, ...]` so the error tool_result message names the blocked tool and lists the configured allow-list (helpful to the model: "destructive action 'send_hotkey' blocked; allow-list: []").
  - `def is_allowed(spec: ToolSpec, settings: Settings) -> bool` — pure resolver. Returns True if `spec.destructive is False`, OR if `spec.name in settings.automation.destructive_actions`. The order matters: non-destructive tools always pass the gate; destructive tools require explicit allow-listing. Spec rationale: "default-deny" is the safer posture for automation; legacy code-injection lists generally favor allow-lists over block-lists for irreversible operations.
  - `def check_allowed(spec: ToolSpec, settings: Settings) -> None` — raises `DestructiveActionBlocked(spec.name, allow_list=tuple(settings.automation.destructive_actions))` when `not is_allowed(spec, settings)`. Returns None on pass. Mirrors `KillSwitch.check()` from P4.B1 — a void method that either returns silently or raises a typed exception.
  - Module-level `_RESOLVE_SETTINGS: Callable[[], Settings]` injection seam, default = lazy import + `_default_settings()`. Tests override with a fake-settings factory. Mirrors P4.B1's `_LISTENER_FACTORY` and P4.B2's `_KEYPRESS_FACTORY` patterns.
- `sabrina-2/src/sabrina/brain/claude.py` — extend tool-dispatch loop one new branch (lines ~155-170, immediately after the `find()` call returns the spec, before the `dry_run_wrap` shim):
  - Insert: `try: check_allowed(spec, settings)` — wrap in the existing `try` block at line 184 OR add a new `try`/`except DestructiveActionBlocked` as a sibling to the existing `except KillSwitchTripped`. Spec recommendation: separate `except` block for clarity and to keep the error-message specific.
  - On block: yield `ToolUseDone(tool_id=tu.id, name=tu.name, result=None, error="destructive_action_blocked")` and append the matching `tool_result` with `is_error: True`. The dispatch loop then continues to the next tool block; the model sees the error on the next round trip and can re-plan.
  - Settings passthrough: extend `ClaudeBrain.chat()` with a `settings: Settings | None = None` kwarg (default None — pass-through preserves today's behavior). When None, `check_allowed` falls through to the `_RESOLVE_SETTINGS` factory.
- `sabrina-2/src/sabrina/automation/__init__.py` — add `from .allow_list import DestructiveActionBlocked, check_allowed, is_allowed` to the package __all__. Mirrors P4.B1's surface re-exports.
- `sabrina-2/sabrina.toml` — no change to schema. The `[automation] destructive_actions = []` line already shipped (or will ship) with P4.B1 (a)-half. Spec note: if P4.B1's commit hadn't yet landed when P4.B3 is pulled, the Worker should verify the field is present and add it if missing — but this is the same byte-identical change P4.B1 (a)-half adds, so partition-clean composition holds.
- `sabrina-2/tests/test_destructive_allow_list.py` (new, ~260 lines) — sixteen unit tests:
  - `test_toolspec_destructive_defaults_to_false` — `ToolSpec(name=..., description=..., input_schema=..., handler=...)` constructs with `destructive=False`.
  - `test_toolspec_destructive_can_be_set_true` — `ToolSpec(..., destructive=True)` round-trips.
  - `test_toolspec_destructive_not_in_anthropic_dict` — `to_anthropic_dict()` output has no `destructive` key (Sabrina-internal field).
  - `test_toolspec_destructive_not_in_mcp_dict` — same for `to_mcp_dict()`.
  - `test_is_allowed_passes_non_destructive_with_empty_allow_list` — non-destructive `write_clipboard`-shaped spec passes when `destructive_actions=[]`.
  - `test_is_allowed_passes_non_destructive_with_unrelated_allow_list` — non-destructive spec passes regardless of allow-list contents.
  - `test_is_allowed_blocks_destructive_with_empty_allow_list` — destructive `send_hotkey`-shaped spec fails when `destructive_actions=[]`.
  - `test_is_allowed_blocks_destructive_when_name_not_in_allow_list` — destructive spec fails when its name isn't on the list.
  - `test_is_allowed_passes_destructive_when_name_in_allow_list` — destructive spec passes when its name is on the list.
  - `test_check_allowed_returns_none_when_allowed` — explicit None-return on pass.
  - `test_check_allowed_raises_destructive_action_blocked_when_blocked` — exception type matches; `.name` and `.allow_list` carry the right payload.
  - `test_destructive_action_blocked_carries_allow_list` — exception's `.allow_list` is a tuple (immutable), not a list (defensive).
  - `test_claude_dispatch_blocks_destructive_when_not_allowlisted` — fake stream emits `tool_use` for a destructive scaffold spec; with `Settings(automation=AutomationConfig(destructive_actions=[]))`, the `tool_result` content is `"destructive_action_blocked"` and `is_error=True`; the underlying handler is never invoked.
  - `test_claude_dispatch_allows_destructive_when_allowlisted` — same fake stream; with `destructive_actions=["scaffold_destructive"]`, the handler runs.
  - `test_claude_dispatch_block_precedes_dry_run` — combination case: destructive spec, blocked, AND `dry_run=True`. The block error wins; the dry-run synthetic shape is NOT returned. Ordering: allow-list before dry-run. Spec rationale: dry-run is a debugging-friendly alternative to firing; if the action is *blocked*, the model should learn it's blocked, not learn that dry-run-would-have-fired. The model's behavior on "I attempted a tool but you've forbidden it" is more useful than "I attempted a dry-run of a tool you've forbidden anyway."
  - `test_claude_dispatch_block_precedes_kill_switch` — destructive spec, blocked, `kill_switch.tripped=False`. Block error fires; kill-switch never asked. (If kill-switch were tripped concurrently, the existing kill-switch check at line 232 still handles it on the post-dispatch poll for non-blocked tools — mutually exclusive paths.)

**(b)-half — folded into P4.B4, NOT deliverable here:**

- One real Windows session: voice command "copy this to my clipboard" → brain emits `tool_use(send_hotkey, name="copy")` → allow-list blocks (default) → brain returns the error to the model → model says "I'm not allowed to do that automatically; you can press Ctrl+C yourself" or similar. Demonstrates the human-readable failure mode.
- A second session: Eric flips `[automation] destructive_actions = ["send_hotkey"]`, runs the same command, and the keypress fires for real. Demonstrates the unblock path.
- Voice-loop renderer of the `destructive_action_blocked` error — UX polish (does the brain's reply read clean?). May need a string template for the model in `claude.py`'s system prompt; that's a separate sharpening.
- Decision doc (under P4.B4) covering the B1 + B2 + B3 + B4 quartet under one number.

## What's deliberately NOT in scope

- **A `destructive_actions` UI in the settings GUI** — sabrina-toml editing is the v1 surface; a tabbed list in `customtkinter` would compose with decision 004 but isn't load-bearing for v1. Out of scope.
- **Dynamic destructive promotion** — the model can't tag a tool destructive at runtime; the static `ToolSpec.destructive` field is the only source of truth. A future "suggested-destructive" mechanism would compose with prompt-side guidance, not with this guard.
- **Per-handler granularity** — the field is on `ToolSpec`, not on individual call inputs. A `send_hotkey(name="screenshot")` is destructive even though "screenshot" is read-only-ish; the spec stays at the tool level because per-input arbitration would re-introduce the model-can-talk-its-way-past-the-guard failure mode.
- **Destructive-action audit log file** — the `DestructiveActionBlocked` exception logs through structlog at WARN level; a separate `~/.sabrina/audit/destructive.log` would compose with the P2.7 budget tracker pattern but is out of scope. JSONL append + threshold review can be a follow-up if Eric wants the visibility.
- **Multi-tier allow-list** ("destructive but pre-confirmed by Eric this session" vs. "always-allowed") — out of scope. v1 is binary: allow-listed or not. A confirmation-gate compose would belong to a separate item once Eric has run the v1 surface for a while.

## Dependencies

- **P4.B1** (kill-switch + dry-run scaffold) — (a)-half currently in working tree, blocked on the FUSE `.git/index.lock`. P4.B3 needs `AutomationConfig.destructive_actions` (added by P4.B1) and the dispatch-loop seams at `claude.py:174-237` (extended by P4.B1). If a Worker pulls P4.B3 before P4.B1 commits, the spec instruction is to depend on P4.B1's in-tree files (byte-identical to what the next Worker will see) and stage the P4.B3 commit on the existing `automation/worker-2026-05-07-8am` branch — partition-clean against P4.B1's diff (P4.B3 touches new file `automation/allow_list.py`, additive `tools/__init__.py:ToolSpec.destructive`, and the dispatch-loop branch in `claude.py:155-170` *above* the P4.B1 dry-run + kill-switch wrap region at 174-237).
- **P4.B2** (`send_hotkey`) — composes well but does NOT block. P4.B3 can ship with `noop_action` from P4.B1's scaffold marked `destructive=True` for the purpose of testing the guard. When P4.B2 lands, `SEND_HOTKEY_SPEC` carries `destructive=True` per P4.B2's spec; the allow-list automatically applies. Order: B1 (a)-half → B3 (a)-half → B2 (a)-half is fine; B1 → B2 → B3 is also fine.
- **Phase 3 (a)-half** — already in `main` (commit `acd6725`).

## Concrete DoD

A Worker pulling P4.B3 ships the (a)-half when:

1. `sabrina-2/src/sabrina/tools/__init__.py` `ToolSpec` carries `destructive: bool = False` as an additive frozen field; existing `write_clipboard` constructor explicitly passes `destructive=False` for documentation.
2. `sabrina-2/src/sabrina/automation/allow_list.py` exists with `DestructiveActionBlocked`, `is_allowed`, `check_allowed`, and the `_RESOLVE_SETTINGS` injection seam per the structure above.
3. `sabrina-2/src/sabrina/automation/__init__.py` re-exports the three public names.
4. `sabrina-2/src/sabrina/brain/claude.py` dispatch loop has one new pre-dispatch branch that calls `check_allowed(spec, settings)` and emits `ToolUseDone(error="destructive_action_blocked")` on raise.
5. `sabrina-2/src/sabrina/brain/claude.py:ClaudeBrain.chat()` accepts a `settings: Settings | None = None` kwarg with pass-through default behavior.
6. `sabrina-2/tests/test_destructive_allow_list.py` exists with the sixteen tests above; all pass under the Cowork Linux/3.10 sandbox.
7. `python -m compileall -q sabrina-2/src sabrina-2/tests` exits 0.
8. AST parses clean for all touched files post-edit (CLAUDE.md edit-truncation guard).
9. `pytest sabrina-2/tests/test_destructive_allow_list.py -v` reports 16/16 PASS.
10. Combined regression on `test_destructive_allow_list` + `test_automation_safety` (P4.B1) + `test_smoke` claude+tool tests + the existing `to_anthropic_dict` round-trip tests at `test_smoke.py:1869-1965` shows zero new failures relative to the working-tree baseline.
11. Commit message includes `Windows-pending: e2e` in the body and a Windows-side checklist matching this spec's `(b)-half` section in JOURNAL.md.
12. Worker self-review per `roles/worker.md` step 6 reports zero P0/P1 findings.

The (b)-half / Full DoD gate fires later, at P4.B4, when Eric runs:

- One real Windows session per the (b)-half list above demonstrating the blocked + unblocked paths for `send_hotkey`.
- `pytest` on Windows passes.
- Decision doc filed (the B1+B2+B3+B4 quartet doc per P4.B4).

## Open questions for NEEDS-INPUT

**Q1: Default-deny vs. default-allow when `destructive_actions` is missing entirely from `sabrina.toml`.** The Pydantic default is `[]` (empty list) which means "deny all destructive actions." But what if the field is absent from the toml entirely (e.g. an older config that predates P4.B1)?

(a) **Default-deny on missing field** — Pydantic's `default=[]` resolves to empty list; allow-list resolution treats empty as deny-all. Older configs blocking destructive ToolSpecs is the safe outcome. Cost: a user who hand-flips `[tools] enabled = true` and `[tools.send_hotkey] enabled = true` will still hit the allow-list block until they also add `[automation] destructive_actions = ["send_hotkey"]`. Three flips, not two.

(b) **Default-allow on missing field, default-deny on empty list** — Pydantic default flips to `None` instead of `[]`; allow-list resolution treats None as "field absent → allow." Cost: the safer default leaks; a user upgrading from an older config inherits the looser behavior silently, opposite of what we want from a safety primitive.

**Spec recommendation: (a)** — default-deny is the right posture for irreversible operations. The "three-flip" cost is acceptable because a user enabling automation should be auditing each action they allow, not relying on a default that ships everything live. Worker can ship the (a)-half against (a) without waiting; if Eric overrides before pull, Worker reroutes per the answer.

**Q2: Allow-list match by name vs. by glob/regex.** Should `destructive_actions = ["send_hotkey"]` match exactly, or should it support `["send_*"]` for forward compatibility with future tools?

(a) **Exact match only** — `name == entry`. Simplest. Cost: each new destructive tool requires an explicit allow-list entry; "I allow all keyboard tools" needs three entries (`send_hotkey`, `send_text`, `repeat_keypress` etc., when they exist).

(b) **Glob match via fnmatch** — `fnmatch.fnmatchcase(name, entry)`. Slightly more expressive. Cost: allows a too-broad pattern to leak future destructive tools that didn't exist when the user wrote the toml; the security posture leaks forward in time.

(c) **Regex match** — `re.fullmatch(entry, name)`. Most expressive. Cost: complex; users have to learn regex; the leak-forward-in-time problem is worse, not better.

**Spec recommendation: (a)** — exact match is the safest posture. Each new destructive tool is a deliberate decision; forcing the user to re-audit when a new tool ships is a feature, not a bug. Worker can ship the (a)-half against (a) without waiting; if Eric overrides before pull, Worker reroutes.

**Q3: `destructive` flag on existing `write_clipboard` — declare false, or omit and rely on default?**

(a) **Explicit `destructive=False`** — the constructor in `_builtin_tools()` carries the field by name. Self-documenting; future readers see the field exists; implies the author considered the question.

(b) **Omit, rely on default** — shorter constructor; Pydantic-style "defaults are conventions" posture.

**Spec recommendation: (a)** — explicit is better than implicit for a safety field. The five lines of the existing `_builtin_tools()` factory are not enough volume to justify hiding the field. Worker can ship against (a) without waiting.

NEEDS-INPUT entries for Q1/Q2/Q3 below as `[from: spec-writer / 2026-05-09 06:50]`.

## Files this spec deliberately does NOT name

- `voice_loop.py` — Phase 3 (b)-half + P4.B4 territory.
- `events.py` — no new event types; the existing `ToolUseDone` from `claude.py` carries the error.
- `automation/scaffold.py` (`noop_action` etc.) — P4.B1 surface; P4.B3 uses it for test-only destructive-spec injection but doesn't modify it.
- `rebuild/decisions/` — decision doc lands at P4.B4.

## Composability notes

- **With P4.B1 (a)-half (in-tree, lock-blocked):** zero file overlap. P4.B1 touches `automation/__init__.py`, `automation/{kill_switch,dry_run,scaffold}.py`, `brain/claude.py:174-237`, `config.py` `AutomationConfig`, `sabrina.toml` `[automation]`, `tests/test_automation_safety.py`. P4.B3 touches `automation/__init__.py` (additive re-export — composes with P4.B1's `__all__` cleanly), `automation/allow_list.py` (new), `tools/__init__.py` (additive `destructive` field on `ToolSpec`), `brain/claude.py:155-170` (new dispatch-loop branch *above* P4.B1's region), and `tests/test_destructive_allow_list.py` (new). Concurrent application is partition-clean — no overlapping line ranges.
- **With P4.B2 (`send_hotkey`):** P4.B2 carries `destructive=True` on `SEND_HOTKEY_SPEC` per P4.B2's spec. When both ship, the default-deny posture means a user enabling `send_hotkey` must also add it to `destructive_actions`. Spec rationale: this is the design intent. The two flags together — `[tools] send_hotkey_enabled = true` AND `[automation] destructive_actions = ["send_hotkey"]` — are the deliberate "I want this and I'm aware it's irreversible" affirmation. Cost is acceptable.
- **With P4.B4 (Windows e2e):** P4.B4's quartet ship promotes B1 + B2 + B3 from `[linux-shipped]` to `[done]` after the four-tool checklist (kill-switch trip + dry-run hit + destructive-action block + real `send_hotkey` keypress) all fire on Windows.

## Edit-tool truncation hazard reminder

Per CLAUDE.md and the recurring incidents in JOURNAL: verify file contents post-edit. AST-parse `tools/__init__.py` (the `ToolSpec` field addition is a structural change to a frozen dataclass — extra-careful here), `automation/allow_list.py`, `brain/claude.py`, and `tests/test_destructive_allow_list.py` after every Edit-tool call. The `claude.py` edit is in the same function the P4.B1 (a)-half edited, just at a different line range; verify the surrounding context is byte-identical to what `git show HEAD:sabrina-2/src/sabrina/brain/claude.py` produces post-P4.B1.

## What the Planner does with this spec

Per `roles/spec-writer.md` step 6: this is a draft. The Planner at 07:00 (or whenever it next runs) decides whether to keep the queue entry as-is, add a `**Spec at ...**` pointer line, or surface the open questions to Eric. The spec-writer does NOT promote, does NOT mark done, does NOT approve.
