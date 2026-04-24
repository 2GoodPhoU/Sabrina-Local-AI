# Automation — Windows validation procedure

**Purpose:** confirm the automation safety infrastructure (dry-run,
allow-list + append, kill-switch, audit log) and the first three tools
(`list_files`, `launch_app`, `list_open_windows`) work end-to-end on
Eric's Windows box before we call the automation decision validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.
Automation implementation has landed per `rebuild/drafts/automation-plan.md`
(`automation/` package — `guards.py`, `kill_switch.py`, `confirm.py`;
`tools/files.py`, `tools/apps.py`, `tools/windows.py`; new events;
`[automation]` config block; `sabrina allow` + `sabrina audit` CLI
verbs). Tool-use protocol must be in place (automation tools are
tools). Barge-in must have shipped for spoken-confirmation; pre-barge-
in deployments use the GUI-modal fallback per the plan.

**Cross-reference:** this doc exercises the hybrid allow-list learning
path (spoken "remember" appends to TOML while preserving comments).
The tomlkit-canary test for comment preservation is covered at the
unit-test level in step 2; manual verification in step 8. The
allow-list-append correctness is the single highest-risk behavior in
this whole plan.

---

## Step 0 — Sanity-check automation deps

```powershell
uv run python -c "import pygetwindow, psutil, tomlkit; print('ok', pygetwindow.__version__, psutil.__version__, tomlkit.__version__)"
```

**Success:** prints `ok` with version strings.
**Failure signal:** `ImportError` → `uv sync` didn't install. Re-run
step 1.

---

## Step 1 — `uv sync` and `uv run pytest -q`

```powershell
uv sync
uv run pytest -q
```

**Success:** existing tests pass, plus the automation block (~12 new
tests):

- `test_guards_allow_listed_passes_silently`
- `test_guards_out_of_scope_denies_cleanly`
- `test_guards_confirmation_yes_remember_appends_tomlkit`
- `test_guards_confirmation_no_declines_without_side_effects`
- `test_guards_timeout_declines`
- `test_kill_switch_sets_event_and_publishes`
- `test_list_files_enforces_root_allow_list`
- `test_launch_app_resolves_allow_list_entry`
- `test_list_open_windows_filters_hidden_and_zero_area`
- `test_tomlkit_append_preserves_neighboring_comments`  ← the canary
- `test_audit_log_rolls_at_5mb`
- `test_confirm_gui_modal_fallback_when_barge_in_absent`

**Special attention: `test_tomlkit_append_preserves_neighboring_comments`
must pass.** This is the contract that every novel-tool "remember"
flow depends on. If it regresses, allow-list learning is off the
table for this ship.

**Failure signal:** any red. The tomlkit-canary failure is the one
that blocks the ship; others can be patched with follow-ups.

---

## Step 2 — Configure `[automation]` block

Edit `sabrina-2/sabrina.toml`. Start with a known-good allow-list that
includes a seeded VS Code entry so step 4 has something to trigger
silently:

```toml
[automation]
enabled = true
audit_log = "logs/automation.log"
kill_switch_hotkey = "<ctrl>+<shift>+<esc>"
confirm_mode = "hybrid"

# Comment above list_files — this comment is the canary for the
# tomlkit append test. If it's gone after step 8, the append path
# rewrote the file from scratch instead of round-tripping.
[automation.tools.list_files]
trigger = "find files"
confirm_policy = "never"
roots = [
    "C:/Users/eric/Projects",
    "C:/Users/eric/Documents",
    "C:/Users/eric/Downloads",
]

[automation.tools.launch_app]
trigger = "open applications"
confirm_policy = "allow_listed"

[[automation.tools.launch_app.apps]]
name = "VS Code"
path = "C:/Users/eric/AppData/Local/Programs/Microsoft VS Code/Code.exe"
added_at = "2026-04-23T00:00:00Z"

# Comment below the seeded entry — second canary.

[automation.tools.list_open_windows]
trigger = "list what's on screen"
confirm_policy = "never"
```

Save. Verify:

```powershell
uv run sabrina config-show | findstr /i automation
uv run sabrina allow list
```

**Success:** `sabrina allow list` prints the seeded VS Code entry and
the three tools' trigger phrases. `config-show` reflects all the
values.

---

## Step 3 — `list_files` end-to-end via voice

```powershell
uv run sabrina voice
```

Hold PTT, ask: *"what Python files did I touch in my Projects folder in
the last week?"* Release.

**Success:**
- Brain decides to call `list_files(root="C:/Users/eric/Projects",
  pattern="*.py", recursive=true)`.
- Because `list_files.confirm_policy = "never"`, no confirmation modal
  or voice prompt fires. Silent execution.
- Reply mentions real Python files with mtimes that make sense.
- `logs/automation.log` has two fresh lines around the invocation:

  ```
  2026-04-23T... tool_invocation_start tool=list_files args={"root":"...","pattern":"*.py",...}
  2026-04-23T... tool_invocation_end tool=list_files status=ok duration_s=0.0xx
  ```

**Failure signal A:** Brain announces "I'll look for Python files..."
then the reply is empty or an error → `list_files` raised inside the
handler. Capture `logs/automation.log` — the `_end` line will have
`status=error error=...`.
**Failure signal B:** out-of-scope path → Brain picked a root like
`C:/` or `C:/Windows` not in the allow-list; `list_files` correctly
denied with `status=denied reason=out_of_scope`. Brain should then
apologize and ask. If the Brain executed regardless, guards.py isn't
wired in front of the handler.

---

## Step 4 — `launch_app` silent path (seeded entry)

Still in `sabrina voice`. Ask: *"open VS Code"*.

**Success:**
- Because VS Code is in the allow-list, no confirmation.
- VS Code launches (new window appears).
- Reply is terse, e.g. *"VS Code is opening now."*
- `logs/automation.log` logs the invocation with `status=ok` and a
  PID.

**Failure signal A:** confirmation fires despite the allow-list entry
→ matching logic is off (name case-insensitive? leading/trailing
whitespace in the stored name?). Check `sabrina allow list` output
against what the Brain sent.
**Failure signal B:** VS Code doesn't launch → subprocess flags are
wrong, or the path in the TOML is stale (check `Test-Path` on it).
**Failure signal C:** VS Code launches but Sabrina exits with it →
`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` flags missing from
Popen.

---

## Step 5 — `launch_app` novel-invocation confirmation (hybrid path)

Still in `sabrina voice`. Ask: *"open Notepad"*.

Notepad isn't in the allow-list. Per `confirm_mode = "hybrid"`:
Sabrina should ask a confirmation question. Pre-barge-in: a GUI modal
appears with three buttons ("Do it once", "Do it & remember", "Cancel").
Post-barge-in: Sabrina speaks *"I haven't opened that before — should
I, and should I remember?"* and listens for ~5 s.

### 5a. Test the "once" branch

If the modal appeared, click "Do it once". If voice, say *"yes, just
this time"*.

**Success:**
- Notepad launches.
- `logs/automation.log` shows `tool_invocation_end tool=launch_app
  status=ok reason=confirmed_once`.
- `sabrina allow list` after (Ctrl+C out of voice first) still shows
  only the seeded VS Code entry — no Notepad added.
- Cat the toml — no new `[[automation.tools.launch_app.apps]]` block.

**Failure signal:** Notepad appended despite "once" → the confirm-
result branching is inverted. Check `guards.py`'s handling of `"yes"`
vs. `"yes_remember"`.

### 5b. Test the "remember" branch (the hybrid-learning test)

Still in voice (or relaunch). Ask: *"open Notepad"* again. Same
confirmation. This time click "Do it & remember" (or say *"yes and
remember"*).

When prompted for the path (modal file picker, or voice-mode's modal
fallback), select `C:\Windows\System32\notepad.exe` (or wherever it
lives on your machine — `where.exe notepad` prints the path).

**Success:**
- Notepad launches.
- `logs/automation.log` shows `reason=confirmed_remembered`.
- `sabrina allow list` (after Ctrl+C) now shows TWO entries: VS Code
  and Notepad. Notepad's `added_at` matches the current UTC time.

---

## Step 6 — `list_open_windows` end-to-end via voice

With Notepad and VS Code launched from steps 4 and 5, in a new
`sabrina voice` session:

Ask: *"what's open on my screen right now?"*

**Success:**
- Brain calls `list_open_windows()` — no args, silent per policy.
- Reply mentions the PowerShell window, VS Code, Notepad, and any
  other real windows. Hidden/zero-area windows (e.g., suspended UWP)
  are filtered out.
- `logs/automation.log` has the `tool_invocation_start`/`_end` pair.

**Failure signal:** reply mentions titles like "Ime" or empty
strings → the filter on zero-area / hidden windows isn't firing.
`pygetwindow`'s `visible` check + `pid_exists` via psutil per the
plan's Windows-specific notes.

---

## Step 7 — Kill-switch during a tool invocation

This is the safety spine's core test. Ctrl+C out of voice, then
restart. We want a tool invocation that takes long enough to
interrupt.

`list_files` on a big directory is a good candidate. Temporarily add
a bigger root to `roots`:

```toml
[automation.tools.list_files]
roots = [
    "C:/Users/eric/Projects",
    "C:/Users/eric/Documents",
    "C:/Users/eric/Downloads",
    "C:/",                        # temporary for kill-switch smoke
]
```

```powershell
uv run sabrina voice
```

Ask: *"list every file in C colon, recursive"*. While the reply is
being composed — or better, while the tool is visibly running —
press **Ctrl+Shift+Esc**. Task Manager will pop (expected; the
hotkey is shared with Windows), and the kill flag fires.

**Success:**
- Tool invocation stops as soon as the kill flag is checked (up to
  the configured check frequency — plan says "between stream events
  and at tool-execution boundaries").
- Reply is short: *"I stopped. Let me know what you need."* (Or
  whatever the shipped prompt-ified brain message is.)
- `logs/automation.log` shows `tool_invocation_end status=killed
  reason=kill_switch_fired`.
- Event bus publishes `KillSwitchFired`.

**Failure signal A:** Task Manager opens but the tool keeps running
to completion → the hotkey listener didn't set `KILL_EVENT`, or
`guards.py` isn't polling it. Capture whether `KillSwitchFired` ever
appeared in the structlog.
**Failure signal B:** hotkey doesn't fire at all → pynput's
`GlobalHotKey` conflict with Task Manager's own handling. Verify the
listener started: look for `kill_switch.listener_started` log line on
voice-loop boot.

Remove the `C:/` root after this step.

---

## Step 8 — Allow-list append preserved the comments (tomlkit canary)

This verifies the single highest-risk behavior: step 5b appended a
Notepad entry to the TOML. Did it preserve the two canary comments
we placed in step 2?

```powershell
type sabrina.toml | Select-String -Pattern "canary", "seeded entry"
```

**Success:** both canary comment lines from step 2 are still present.

```powershell
type sabrina.toml
```

**Success:** the file is visually familiar — indentation preserved,
blank lines between sections preserved, section order unchanged.
The only diff from step 2's state is one new
`[[automation.tools.launch_app.apps]]` block appended after the VS
Code entry.

**Failure signal A:** canary comments are gone → tomlkit's
round-trip didn't preserve them. This is a plan-level contract
failure; treat as a red-flag blocker, not a tune-up. The automation
decision cannot ship without this.
**Failure signal B:** file became a one-line minified mess or
section order reshuffled → we're using vanilla `tomllib` + `toml.dumps`
somewhere instead of `tomlkit`'s document model. Find the path that
isn't going through `append_allow_entry`.

---

## Step 9 — `sabrina audit tail` shows recent invocations

```powershell
uv run sabrina audit tail
```

**Success:** streams the most recent audit lines in chronological
order. Hit Ctrl+C after a moment. Every invocation from steps 3-7
should be present: two or more `list_files` calls, one-or-more
`launch_app` calls (VS Code, Notepad-once, Notepad-remembered), a
`list_open_windows` call, the killed invocation from step 7.

**Failure signal:** `sabrina audit tail` crashes or shows nothing →
log rotation is corrupting the file, or the audit logger isn't
actually writing. Check `logs/automation.log` file size; if it's
growing on each invocation but `tail` doesn't see it, the verb's
implementation is broken.

---

## Step 10 — Audit log rotation at 5 MB

Spot-check — covered by unit test but quick to verify on real disk:

```powershell
(Get-Item logs\automation.log).Length
```

**Success:** under 5 MB. If you want to force rotation for the test,
pad it with synthetic writes:

```powershell
$log = "logs\automation.log"
$filler = "x" * 1024
1..5100 | ForEach-Object { Add-Content -Path $log -Value $filler }
Get-ChildItem logs\automation.log*
```

**Success:** next automation invocation rotates — `logs/automation.log.1`
appears, `logs/automation.log` starts fresh. Keep only last 5 files
per plan.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 1 | tomlkit canary test red | Append path bypasses tomlkit document model | Full traceback |
| 2 | `allow list` missing entries | Config path off or block shape wrong | `config-show` output |
| 3 | out-of-scope not denied | guards.py not wired ahead of handler | automation.log |
| 4 | Confirmation fires on seeded entry | Case/whitespace mismatch on name | `allow list` vs. Brain's args |
| 4 | VS Code launches then dies with Sabrina | Missing `DETACHED_PROCESS` | Popen args in apps.py |
| 5a | "Once" appends to TOML | confirm branching inverted | Full `guards.py` run trace |
| 5b | "Remember" doesn't append | `append_allow_entry` not called | automation.log |
| 6 | Empty / zombie windows in reply | Filter missing | raw `pygetwindow.getAllWindows()` output |
| 7 | Tool runs to completion past kill | KILL_EVENT not polled | structlog for `KillSwitchFired` |
| 7 | Hotkey doesn't fire at all | pynput listener not started | `kill_switch.listener_started` log |
| 8 | Canary comments gone | Append path rewrites file | diff of `sabrina.toml` vs. step 2 |
| 8 | File reshuffled | vanilla `toml` lib used somewhere | git diff + stack trace |
| 9 | `audit tail` crashes | Log-rotation file-handle bug | traceback |
| 10 | No rotation at 5 MB | Size check missing | File listing |

---

## Known risks from the pre-validation code audit

1. **The tomlkit-comment-preservation contract is the whole plan.**
   The hybrid allow-list learning is only trust-worthy if the user
   can read `sabrina.toml` and see exactly what Sabrina has been
   allowed to do. If step 8 fails, the feature ships with a
   "remember" option that silently mangles the user's config — worse
   than no learning at all. Do not ship automation without step 8
   clean. Do not "ship and fix later."
2. **`Ctrl+Shift+Esc` always opens Task Manager at the OS level.**
   Our listener fires first (plan design), but users will see Task
   Manager pop up every time they hit the kill switch. This is
   documented-expected, not a bug. If it bothers the user, the
   hotkey is a config value — pick any pynput-parseable chord.
3. **pygetwindow occasionally reports zombie windows on Windows 11.**
   UWP apps suspended in the background show up with valid handles
   but no active process. The plan's `psutil.pid_exists()` filter
   catches this. If step 6 shows zombies, that filter isn't wired.
4. **Allow-list writes race between the GUI and the voice loop.**
   If the settings GUI is open when an allow-list entry is being
   appended from the voice loop, both processes can write to
   `sabrina.toml` at once. The plan's `threading.Lock` is per-
   process; it doesn't help cross-process. The realistic mitigation
   is: don't edit settings while running voice. Flag to Eric; not
   fixable in this session.
5. **Spoken-confirmation grammar is loose on purpose.** "yeah and
   remember," "sure remember that," "yes and keep that one," all
   should map to `yes_remember`. The plan's spec is indicative, not
   exhaustive. If step 5b fails because your exact wording didn't
   match, that's tunable — log the rejected utterance and widen the
   grammar.
6. **`launch_app` novel-path entry uses a GUI file picker even in
   voice-mode.** Dictating a Windows path by voice is a usability
   dead-end. Expected behavior; documented.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line:

```
Automation + first three tools validated on Windows (i7-13700K/4080,
Python 3.12) <YYYY-MM-DD>: guards (dry-run, allow-list, kill-switch,
audit log) green, list_files / launch_app / list_open_windows E2E via
voice, tomlkit append preserved neighboring comments (canary green),
<N> audit invocations logged.
```

`<N>` from step 9's count of lines in the audit log.

Commit with message:
```
validate: automation + first three tools on Windows (tomlkit canary green)
```

---

## If any step failed

1. Capture per the triage table.
2. The three highest-probability follow-up decisions, by impact:
   - **tomlkit append rewrites or reshuffles (step 8)** — the
     automation decision cannot ship. File a blocking follow-up
     decision doc capturing the exact append-path error and the fix.
   - **Kill-switch doesn't fire (step 7)** — safety-spine
     failure. File a decision doc with the pynput listener debug
     trace. Ship-blocking.
   - **Allow-list case/whitespace match (step 4)** — tune-up, not a
     new decision. Footnote on the shipped decision doc with the
     normalization rule (e.g. "names are case-folded and whitespace-
     stripped before match").
3. For everything else (file filter, audit rotation, spoken grammar),
   prefer footnote-on-shipped-decision over new numbered decisions.
