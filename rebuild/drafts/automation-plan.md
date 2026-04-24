# Automation plan — safety infrastructure + first three tools

**Date:** 2026-04-23
**Status:** Draft. One decision flagged for Eric's confirmation at the
top (allow-list learning recommendation). Implementable as a 2-3
session arc.
**Supersedes:** [`automation-brief.md`](automation-brief.md) (kept for
history).
**Prerequisites:**
- Tool use in `Brain` protocol must land first (`tool-use-plan.md`).
  Automation tools ARE tools in the tool-use protocol.
- Barge-in must land for the full spoken-confirmation UX. Before
  barge-in ships, the fallback is a GUI modal; documented below.
**Closes:** ROADMAP component 9 (the deferred-hardest item). Makes
Sabrina a real assistant.

## Confirm-or-override recommendation (top of plan per Eric's request)

**Plan's call on allow-list learning: the "hybrid / middle path."**

- `sabrina.toml` is the source of truth for what Sabrina may do.
- On first invocation of a tool+arguments combination not in the
  allow-list, Sabrina speaks a confirmation: *"I haven't done that
  before — should I, and should I remember?"*
- User says "yes and remember" (or equivalent — the grammar matcher
  is spelled out below) → tomlkit appends a new allow-list entry,
  preserving comments and formatting.
- User says "yes, just this time" → execute once, do not append.
- User says "no" or stays silent for 5 s → decline, log.

Rationale: TOML stays human-readable, the allow-list is auditable
with `type sabrina.toml`, and Sabrina gets progressive trust without
a separate DB. Every append shows up in `git diff`. This mirrors the
spirit of decision 004 (settings GUI round-trips TOML while
preserving Eric's comments).

**If Eric wants to override:**
- *Static-only*: drop the "remember" branch. Every novel invocation
  is a one-off; config edits are manual.
- *Learn-always*: drop the "just this time" branch. Every "yes"
  appends.

Default in this plan is the middle path. The grammar lists below are
config-driven so the three branches are all addressable without
structural changes. One `confirm_mode = "hybrid"` knob flips between
them.

## The one-liner

Ship the safety spine first — `automation/guards.py` with dry-run,
allow-list (read + write), kill-switch hotkey, and audit log — then
land three read-or-trivial tools on top of it: `list_files(root)`,
`launch_app(name)`, `list_open_windows()`. Each tool is a new
`ToolSpec` consumed by the Brain via the tool-use protocol. Per-tool
trigger phrasing ("Hey Sabrina, <x>") lives in TOML.

## Scope

In:
- `automation/` package:
  - `guards.py` — dry-run runner, allow-list check + append, audit
    log.
  - `kill_switch.py` — global Ctrl+Shift+Escape hotkey; sets a
    shared cancel flag.
  - `confirm.py` — spoken-confirmation flow (GUI fallback pre-barge-
    in).
- Three tool modules:
  - `tools/files.py` — `list_files(root)`, path allow-list
    constrained.
  - `tools/apps.py` — `launch_app(name)`, allow-list constrained.
  - `tools/windows.py` — `list_open_windows()`, read-only.
- New events: `ToolInvocationStart`, `ToolInvocationEnd`,
  `KillSwitchFired`.
- `[automation]` config block with per-tool `trigger` fields and
  allow-lists.
- Tests: dry-run exercises, allow-list read-write, kill-switch fast-
  path, each tool's behavior, confirmation branching.

Out:
- Keyboard/mouse automation (pyautogui). Intentional — it's the
  highest-damage primitive; ships behind a separate plan once we
  have a concrete user scenario.
- Browser automation (Playwright). Separate plan. The Chrome MCP
  this host ships with is already available to a future agent layer;
  integrating into Sabrina is a follow-up.
- UI Automation (pywinauto/uiautomation) — pull it in when a concrete
  scenario demands it. `list_open_windows` via pygetwindow is enough
  for the first-tier "what's open?" question.
- Registry / PowerShell / home automation.
- Voice-phrase parsing. Tools are called by the Brain through tool-
  use, not by matching the user's literal words. The "trigger"
  config field is the *description* sent to the Brain, not a regex
  over transcribed audio. (Call this out early; it's the single
  most common misconception with tool use.)

## Files to touch

```
sabrina-2/src/sabrina/
├── automation/                   # NEW package
│   ├── __init__.py
│   ├── guards.py                 # ~180 lines — core safety
│   ├── kill_switch.py            # ~60 lines
│   └── confirm.py                # ~120 lines (grows when barge-in
│                                 #  GUI fallback adds the modal)
├── tools/                        # from tool-use-plan.md
│   ├── files.py                  # NEW, ~80 lines
│   ├── apps.py                   # NEW, ~90 lines
│   └── windows.py                # NEW, ~60 lines
├── events.py                     # +ToolInvocationStart/End, +KillSwitchFired
├── voice_loop.py                 # +kill-switch subscriber
├── cli.py / cli/brain.py         # +sabrina allow (list/add/remove),
│                                 # +sabrina audit (tail logs/automation.log)
└── config.py                     # +AutomationConfig
sabrina-2/
├── pyproject.toml                # +pygetwindow, +psutil
├── sabrina.toml                  # +[automation]
├── logs/                         # audit log target; .gitignore'd
└── tests/test_smoke.py           # +automation tests
```

## Protocol / API changes

`ToolSpec` gains two fields (additive extension to the tool-use
plan's definition):

```python
@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]
    # NEW:
    trigger: str = ""           # natural-language anchor; fed to Brain via
                                 #  description if non-empty.
    confirm_policy: Literal["allow_listed", "always", "never"] = "allow_listed"
```

`trigger` is prepended to the description when the Brain sees the
tool's declaration. If Eric configures `trigger = "open applications"`
for `launch_app`, the Brain sees:

> "Trigger phrase: *open applications*. Launch a whitelisted
> application by name. ..."

This is a hint for the Brain's own decision-making, not a runtime
matcher.

`confirm_policy`:
- `allow_listed` (default) — guards.py checks the allow-list; novel
  calls trigger confirmation.
- `always` — every call confirms (useful for newly-landed tools in
  testing).
- `never` — zero confirmation (useful for `list_files` and other
  read-only tools once trusted).

New events:

```python
class ToolInvocationStart(_EventBase):
    kind: Literal["tool_invocation_start"] = "tool_invocation_start"
    tool: str
    args: dict[str, Any]
    dry_run: bool

class ToolInvocationEnd(_EventBase):
    kind: Literal["tool_invocation_end"] = "tool_invocation_end"
    tool: str
    status: Literal["ok", "denied", "error", "killed"]
    duration_s: float
    error: str | None = None

class KillSwitchFired(_EventBase):
    kind: Literal["kill_switch_fired"] = "kill_switch_fired"
```

All additive.

## Config — the `[automation]` block

```toml
[automation]
# Master switch. Off until allow-list has been populated at least once.
enabled = false

# Where the tool audit log lives. Rolled at 5 MB.
audit_log = "logs/automation.log"

# Hotkey (pynput GlobalHotKey syntax). Default Ctrl+Shift+Escape —
# the same keys Windows uses for Task Manager, so it's already a
# "stop what's happening" muscle memory.
kill_switch_hotkey = "<ctrl>+<shift>+<esc>"

# Confirm mode: "hybrid" | "static" | "learn".
# hybrid: novel → confirm+remember-or-once; allow-listed → silent.
# static: novel → confirm once per call, never remember; allow-listed → silent.
# learn:  novel → confirm, always remember on yes.
confirm_mode = "hybrid"

# Per-tool allow-lists. The exact shape depends on the tool.
# ---------------------------------------------------------------

[automation.tools.list_files]
# Trigger phrase fed to the Brain's tool description.
trigger = "find files"
# Confirmation policy — read-only, so no confirmation needed.
confirm_policy = "never"
# Path roots that list_files may search. Queries for paths outside
# these roots raise a clear error before touching the filesystem.
roots = [
    "C:/Users/eric/Projects",
    "C:/Users/eric/Documents",
    "C:/Users/eric/Downloads",
]

[automation.tools.launch_app]
trigger = "open applications"
confirm_policy = "allow_listed"
# Name-to-executable map. The Brain calls launch_app(name="VS Code")
# and guards.py resolves against this map.
[[automation.tools.launch_app.apps]]
name = "VS Code"
path = "C:/Users/eric/AppData/Local/Programs/Microsoft VS Code/Code.exe"
added_at = "2026-04-23T00:00:00Z"

[automation.tools.list_open_windows]
trigger = "list what's on screen"
confirm_policy = "never"
```

`[[automation.tools.launch_app.apps]]` is an array of tables —
tomlkit handles appending to this shape cleanly (see Windows
concerns for the atomic-write pattern).

## Safety infrastructure design

### `guards.py` — the runtime spine

```python
@dataclass(frozen=True)
class GuardResult:
    allowed: bool
    reason: str               # "allow_listed", "never_policy",
                              # "confirmed_once", "confirmed_remembered",
                              # "declined", "killed", "out_of_scope"

async def run_tool(
    spec: ToolSpec, args: dict[str, Any], *,
    cfg: AutomationConfig, settings: Settings,
    confirm: Callable[..., Awaitable[str]] = spoken_confirm,
    bus: EventBus | None = None,
) -> tuple[GuardResult, Any]:
    """Canonical tool-execution pipeline.

    1. Quick scope check (e.g. list_files(root) in cfg.roots?).
    2. Kill-switch check.
    3. Allow-list lookup based on spec.confirm_policy.
    4. If not in list and policy requires it, call confirm(...).
    5. Dry-run preview (every tool can render a one-liner of what
       it's about to do).
    6. Audit log: pre-line.
    7. Execute (await spec.handler(**args)).
    8. Audit log: post-line.
    """
```

Scope check example for `list_files`:

```python
def _check_scope(spec, args, cfg):
    if spec.name == "list_files":
        root = Path(args["root"]).resolve()
        if not any(root.is_relative_to(Path(r)) for r in cfg.tools.list_files.roots):
            return GuardResult(False, "out_of_scope"), None
    return GuardResult(True, "scope_ok"), None
```

### Allow-list append

```python
def append_allow_entry(cfg_path: Path, tool_name: str,
                       entry: dict[str, Any]) -> None:
    """Atomic tomlkit round-trip. Preserves comments.
    Uses the same tempfile+replace dance as settings_io.
    """
```

Shape for `launch_app` append:

```python
append_allow_entry(cfg_path, "launch_app", {
    "name": "Photoshop",
    "path": str(resolved_path),
    "added_at": datetime.now(timezone.utc).isoformat(),
})
```

tomlkit's `array_of_tables.append(item)` preserves formatting. We
set `added_at` so audit diffs are meaningful.

### `kill_switch.py`

Global pynput hotkey listener. When it fires:
- Set a shared `threading.Event` exposed as `KILL_EVENT`.
- Publish `KillSwitchFired` on the bus.
- Voice loop's main turn loop checks `KILL_EVENT.is_set()` between
  stream events and at tool-execution boundaries.
- The current tool handler gets its `asyncio.CancelledError`
  propagated via the `CancelToken` from the tool-use plan. Without
  that token (e.g. a synchronous tool), the next guard-level check
  after completion catches the kill flag.

The kill switch is *advisory* for in-flight tool execution. For a
mis-triggered `launch_app` — you can't un-launch an app; the kill
switch just prevents *further* actions from queuing.

### `confirm.py` — spoken confirmation

```python
async def spoken_confirm(prompt: str,
                         *, speaker: Speaker, listener: Listener,
                         timeout_s: float = 5.0) -> Literal["yes", "yes_remember", "no", "timeout"]:
    """Speak the prompt, record a short reply, parse.

    Grammar:
      "yes" / "ok" / "sure" / "do it" → "yes"
      "yes and remember" / "remember" / "always" → "yes_remember"
      "no" / "cancel" / "don't" / "stop" → "no"
      [silence] → "timeout"
    """
```

This needs barge-in to stop the TTS prompt *while the user answers*
("I haven't done that before — should I, and should I re—" "no").
Without barge-in, we use a GUI modal fallback.

### GUI modal fallback (pre-barge-in)

```python
# A tiny CTkToplevel with three buttons:
#   [Do it once]   [Do it & remember]   [Cancel]
# 5-second auto-cancel timer. Results map to the same Literal above.
```

Appears on the user's focused monitor. Flags the `enabled=false`
state by disabling it until the allow-list is bootstrapped.

## The three initial tools

### `list_files(root, pattern="*", recursive=True, limit=200)`

Scope: `root` must be a substring of one of the `roots` allow-list
entries (resolved + case-insensitive on Windows). Glob pattern is
pattern-matched server-side; limit caps output.

Returns:

```python
{"matches": [
    {"path": "C:/Users/eric/Projects/sabrina-2/src/sabrina/cli.py",
     "size": 12345,
     "mtime": "2026-04-23T12:34:56Z"},
    ...
], "truncated": false}
```

Use case: "Sabrina, what Python files did I touch in Projects
today?" — Brain issues `list_files("C:/Users/eric/Projects",
pattern="*.py")`, filters by mtime in the reply.

### `launch_app(name)`

Looks up `name` in the allow-list's `[[apps]]` array. If found:
`subprocess.Popen([path], creationflags=DETACHED_PROCESS |
CREATE_NEW_PROCESS_GROUP)`. If not found: trigger confirmation; on
"yes and remember," prompt the user once for the path (typed in the
GUI modal or via voice reply with a file-path), append, then launch.

Returns:

```python
{"launched": true, "name": "VS Code", "pid": 12345}
```

### `list_open_windows()`

Zero args. Returns:

```python
{"windows": [
    {"title": "sabrina-2 - Visual Studio Code",
     "app": "Code.exe",
     "bounds": {"top": 100, "left": 100, "width": 1920, "height": 1040},
     "focused": true},
    ...
]}
```

Via `pygetwindow.getAllWindows()` + filter out zero-area and
hidden. Focused window marked with `focused=true`.

## Test strategy

- `test_guards_allow_listed_passes_silently` — allow-list has an
  entry; run; assert `GuardResult(allowed=True, reason="allow_listed")`.
- `test_guards_out_of_scope_denies_cleanly` — `list_files` with a
  path outside `roots`; assert denied reason.
- `test_guards_confirmation_yes_remember_appends_tomlkit` — stub
  confirm returning `"yes_remember"`; run; read the TOML; assert the
  new entry is present and comments before it are intact.
- `test_guards_confirmation_no_declines_without_side_effects` —
  stub returns `"no"`; assert not executed, not appended.
- `test_guards_timeout_declines` — stub returns `"timeout"`; assert
  declined + logged.
- `test_kill_switch_sets_event_and_publishes` — trigger the
  hotkey via a direct call; assert event + publish.
- `test_list_files_enforces_root_allow_list` — various in/out paths.
- `test_launch_app_resolves_allow_list_entry` — stub subprocess;
  assert correct exe path.
- `test_list_open_windows_filters_hidden_and_zero_area` — fake
  pygetwindow list; assert filtering.
- `test_tomlkit_append_preserves_neighboring_comments` — this is
  the single risk; covers the comment-preservation contract.
- `test_audit_log_rolls_at_5mb` — write lines until > 5 MB; assert
  rotation.
- `test_confirm_gui_modal_fallback_when_barge_in_absent` — stub
  settings with barge-in disabled; assert GUI path is used.

Manual smoke (`validate-automation-windows.md`):
- "Hey Sabrina, what Python files in Projects touched today?" —
  `list_files` fires silently, reply lists files.
- "Open VS Code." (first time, no allow-list entry) — Sabrina asks
  "I haven't done that before — should I, and should I remember?";
  user says "yes and remember"; VS Code launches; `sabrina.toml`
  now has the VS Code entry.
- Second "Open VS Code." — launches silently.
- "Open an unknown app." (no path in config) — confirmation with
  path-entry flow; or decline.
- Ctrl+Shift+Esc during a tool invocation — tool stops mid-flight;
  audit log shows the kill.

## Session breakdown

**Session 1 — Safety spine + `list_files` (est. 1 session).**
- `automation/` package: `guards.py`, `kill_switch.py`, `confirm.py`
  (GUI-modal path only; spoken path stubbed).
- New events.
- `tools/files.py`: `list_files`.
- `[automation]` config skeleton.
- `sabrina allow list` / `sabrina audit tail` CLI verbs.
- Ship criterion: `list_files` end-to-end through the tool-use
  protocol; kill switch works; audit log populates.

**Session 2 — `launch_app` + `list_open_windows` (est. 1 session).**
- `tools/apps.py`, `tools/windows.py`.
- Allow-list append via tomlkit (the real test of the hybrid
  confirmation path).
- GUI modal for novel-invocation confirmation.
- Ship criterion: launch-and-remember flow works end-to-end; the
  newly-launched app appears in `list_open_windows` results.

**Session 3 — spoken-confirmation UX, post-barge-in (est. 0.5
session).**
- `confirm.py` spoken path, reusing barge-in's VAD + cancel-token
  to let "no" interrupt the TTS prompt.
- Grammar matcher against the user's reply.
- Ship criterion: the full voice-only flow works with no GUI
  visible.

If barge-in lands *before* session 1, session 3 can roll into
session 2 — the GUI modal becomes the regression-fallback instead
of the default.

## Dependencies to add

```toml
"pygetwindow>=0.0.9",   # list_open_windows; also used by vision-polish
"psutil>=5.9",          # app-pid health checks + system state
```

`tomlkit` already present. `pynput` already present (PTT uses it).

## Windows-specific concerns

- **Kill-switch hotkey vs. Task Manager.** `Ctrl+Shift+Esc` *opens*
  Task Manager at the OS level. Our listener fires first, but Task
  Manager still appears — which is actually fine (Eric wanted a
  "stop," and seeing Task Manager is a useful second-opinion signal).
  Document so it's not a surprise.
- **tomlkit atomic append.** Use the same
  tempfile + `os.replace` pattern `settings_io.py` uses. Windows
  requires the target file to not be open for reading at the moment
  of replace; serialize allow-list appends behind a
  `threading.Lock` to protect against GUI and voice-loop racing.
  See "Structural uncertainty — tomlkit canary result" below before
  designing `sabrina.toml`'s layout.
- **`subprocess.Popen` for launch_app.** Use
  `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` so the launched app
  doesn't inherit our stdio or get killed when Sabrina shuts down.
- **`pygetwindow` window enumeration.** Windows 11 sometimes
  reports zombie windows (e.g. UWP suspended apps). Filter those
  via psutil's `pid_exists` check before including in results.
- **Audit log rotation.** Roll at 5 MB; keep last 5 files. No need
  for a real logging-rotation library — a 30-line helper is fine.

## Structural uncertainty — tomlkit canary result (2026-04-23)

Standalone canary run against tomlkit 0.14.0 using the exact
`[[automation.tools.launch_app.apps]]` shape this plan specifies.
Scripts: `tomlkit_canary.py` (realistic layout) and
`tomlkit_canary_mitigation.py` (restructured layout).

**Canary 1 — realistic layout: FAIL (with caveat).** All comment
*strings* survive the round-trip. But tomlkit parses a comment that
sits textually between the last AoT entry and the next sibling
section header as *trailing content of the AoT*. When we append a
new AoT entry, tomlkit inserts it AFTER that trailing comment,
which orphans the comment onto the new entry and strips it from the
downstream section:

```
# before append
[[automation.tools.launch_app.apps]]
name = "VS Code"
added_at = "..."

# Downstream tool — read-only; no append ever needed.    ← belongs to list_open_windows
[automation.tools.list_open_windows]

# after append
[[automation.tools.launch_app.apps]]
name = "VS Code"
added_at = "..."

# Downstream tool — read-only; no append ever needed.    ← now describes Photoshop! wrong.
[[automation.tools.launch_app.apps]]
name = "Photoshop"
added_at = "..."
[automation.tools.list_open_windows]                      ← lost its comment, no blank-line separator
```

**Canary 2 — mitigation layout: PASS.** If the AoT block is the
*last* thing in its logical section (no sibling comment trailing
it), tomlkit appends cleanly and every comment stays attached to
the right entry.

**What this means for the plan:**

1. `sabrina.toml` must be authored so every `[[automation.tools.X.apps]]`
   AoT block is the last thing in its parent's subtree. Move
   `[automation.tools.list_open_windows]` (and any other static,
   non-mutating tool block) *above* the mutating AoT blocks.
   Document this as a rule in the file header: "mutating AoT blocks
   live at the bottom of their section; do not add new sections
   below them."
2. `append_allow_entry()` gains a sanity check: before dumping,
   assert that the AoT being appended to has no trailing non-AoT
   sibling section in the same parent; raise a clear error
   otherwise. This catches accidental editing.
3. The existing `test_tomlkit_append_preserves_neighboring_comments`
   becomes two tests — the mitigation-layout happy path (passes)
   and the bad-layout sanity-check guardrail (raises).

**Alternatives rejected (for completeness):**
- Manual string splice on `tomlkit.dumps` output — fragile against
  future formatting changes, re-implements half of tomlkit.
- Switch to `rtoml` — same issue, same parser class, and it lacks
  the comment-preservation API tomlkit exposes.
- Plain write-then-reopen with a marker-line splice — works but
  introduces a second TOML-editing code path alongside the one
  `settings_io.py` already uses. Not worth the cost.

Canary scripts kept out of the repo; their purpose was to validate
the plan, not to live in the suite. The two new unit tests above
replace them.

## Open questions (non-blocking)

All high-level decisions are resolved (from Eric's direction plus
this plan). The one remaining "confirm or override" is surfaced at
the very top of this doc and defaults to the plan's recommendation.

A smaller question the plan takes a decision on (flagging here
because it's easy to second-guess): `launch_app`'s
"add a new app" flow. When the user says "yes and remember" for an
app not in the list, we need the *path*. The plan assumes the GUI
modal asks for it (file-picker dialog). In pure-voice flow post-
barge-in, we'd either ask the user to dictate the path (awkward) or
let Sabrina figure it out from the app name via a Windows
well-known-paths search (clever, error-prone). This plan picks the
GUI file-picker even post-barge-in; voice-dictated paths are out
of scope.

## Ship criterion (whole arc)

- Every session's ship criterion met.
- `sabrina allow list` shows the known entries.
- `sabrina audit tail` streams the audit log.
- Kill-switch fires during a real tool invocation and cleanly aborts.
- End-to-end voice test: "Sabrina, list the Python files I touched
  in Projects today" → spoken answer. "Sabrina, open VS Code" (first
  time) → confirm + remember → launch. Restart of Sabrina → "Sabrina,
  open VS Code" → silent launch.
- No regression on voice-loop latency (guards add < 2 ms per tool
  call; audit log writes are async).

## Not in this plan (later)

- Keyboard/mouse primitives.
- Browser automation via Playwright.
- UI Automation clicks (read-only is in scope via `list_open_windows`;
  clicking is not).
- `file_write`, `file_delete`, or any mutating file op.
- Registry / PowerShell / home.
- Cross-session behavior memory ("you opened VS Code 15 times
  yesterday, want a shortcut?").
- Agent-style multi-step planning ("open VS Code, open the
  Sabrina repo, navigate to voice_loop.py"). Tool-use protocol
  supports recursion already; the Brain just does it — no plan
  change required beyond adding the relevant tools.
