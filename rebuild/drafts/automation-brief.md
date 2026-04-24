# Automation — capability brief (not a plan)

**Date:** 2026-04-23
**Status:** Brief. Research-only. No implementation proposed.
Automation is the broadest component in the roadmap and the highest-
risk. This brief lays out the *shape* of the decision so Eric can
react; picking categories happens after.

## Why this brief isn't a plan yet

Every earlier shipped component was a unit: TTS, ASR, Memory, Vision.
Each had one job. Automation is twelve jobs in a trench coat. The
categories below each deserve their own 200-line plan. Picking the
starting set is the real decision.

## The twelve categories, grouped

Ordered within each group roughly by value per risk.

### Table stakes — read-only or nearly so

These are "Sabrina can tell the user things"; no state mutated. Safe
to ship first.

1. **File system read** — list files, read file contents, search by
   name/extension. `pathlib` + `glob`. Risk: accidentally reading
   sensitive files; mitigated with a config-level allow-list of
   roots (e.g. `C:\Users\eric\Projects`).
2. **Clipboard read** — already landing via tool-use plan; listed
   here for completeness.
3. **App window enumeration** — "what apps are open right now?" via
   `pygetwindow` or `uiautomation`. No mutation. Already adjacent to
   `vision-polish-plan.md`'s window capture.
4. **Screenshot** — already in vision; tool-use could expose it as a
   tool too.
5. **System state read** — battery level, WiFi status, CPU load,
   volume level. Via `psutil` + `winreg`. Read-only, safe.

### Low-risk mutations — user has to consent per class

Each call mutates something, but the class is contained and the
damage is reversible.

6. **File system write** — create/update/delete files within the
   allow-listed roots. Risk: mis-targeting (nuking real data).
   Mitigation: dry-run mode + confirmation prompt. Same shape as
   rsync's `--dry-run` → user approves → for-real run.
7. **Clipboard write** — set the clipboard contents. Risk: overwrites
   whatever was there. Mitigation: confirmation on first use per
   session.
8. **App launch** — `subprocess.Popen` or `ShellExecute`. Risk: low;
   launching apps is safe unless you launch a batch file. Mitigation:
   allow-list of known apps configured in `sabrina.toml`.
9. **Media keys** — volume up/down, play/pause via Windows
   multimedia keys. Risk: nil. Even a confused Sabrina hitting
   pause is recoverable.

### Medium risk — requires active user attention

Mutates user's focused context. Has to be opt-in per session and
unambiguous.

10. **Keyboard + mouse automation** — pyautogui / pynput. Risk: high
    at the primitive level (one wrong coordinate and you've clicked
    "Delete Everything"). Mitigation: the old roadmap's destructive-
    action allow-list + kill-switch design. Even then, this is the
    primitive that should *never* be exposed as a raw tool to the
    brain; it's a building block for higher-level tasks.
11. **UI Automation (read + click)** — `uiautomation` or
    `pywinauto`. Lets Sabrina read the structured widget tree of a
    window, click by label, enter text by role. Risk: higher than
    clipboard/files because it crosses application boundaries; lower
    than raw mouse/keyboard because "click the button labeled 'OK'"
    is more robust than "click at (847, 312)."
12. **Browser automation** — Playwright (recommended over Selenium
    for stability). The Chrome MCP pattern that this system already
    supports is the reference; inside Sabrina, a Playwright-driven
    subprocess could do form-fill, read page text, navigate. Risk
    is real but contained (browser sandbox).

### Adventurous — big surface, narrow uses

Skip unless a concrete user scenario demands it.

13. **Registry / system-settings mutation** — change power plan,
    toggle notifications, etc. via `winreg`. Risk: permanent system
    state. Skip.
14. **PowerShell execution** — run an arbitrary script. Maximum
    flexibility. Maximum footgun. The answer is "no" until there's
    a reason.
15. **Home automation** — Home Assistant, Hue, Kasa. Integrations
    range from trivial (Kasa has a Python SDK) to multi-day (HA
    requires a running HA instance). Value per-integration is high
    but the plumbing lifts are per-platform. Skip unless Eric has a
    specific lighting/speaker story.

## The design patterns that apply to all of these

These would ship as infrastructure *before* any specific category.

### Dry-run mode

Every mutating tool supports `dry_run=True` that describes what it
*would* do but doesn't do it. The tool-use plan proposes surfacing
this automatically: the first invocation of a new tool prints a
dry-run and asks "proceed? [y/n]" spoken via TTS or via a GUI
confirmation window.

### Destructive-action allow-list

Config enumerates what's reachable. File ops constrained to
specific roots. App launches constrained to a short list of
executables. Anything else raises. This is the single best guardrail
against "Sabrina deleted my Desktop because I wasn't clear."

### Kill-switch

A global hotkey (e.g. Ctrl+Shift+Escape) immediately aborts any
in-flight automation and returns Sabrina to idle. pyautogui has a
built-in fail-safe (move mouse to corner aborts); similar pattern,
plus a hotkey.

### Audit log

Every mutating action writes a line to `logs/automation.log` with
timestamp + tool + arguments + dry-run-output + success/failure.
Eric can grep it and see exactly what Sabrina has ever done.

### Confirmation UX

For novel tool × argument combinations, spoken confirmation before
execution ("You want me to delete C:\Users\eric\Projects\old_repo?
Say 'yes' to confirm") with a 5-second timeout. For repeat
invocations of known-safe patterns, silent execution.

## Table-stakes starting set — a recommendation shape

If Eric wanted a starter set that delivers real value while staying
safe, three picks get you most of the distance:

1. **File system read** (category 1) — lets Sabrina answer "where did
   I put that Python script last month" without opening Explorer.
2. **App launch** (category 8, allow-listed) — the classic voice-
   assistant move. "Sabrina, open VS Code."
3. **UI Automation read** (category 11, read-only mode) — lets Sabrina
   answer questions about the focused window's structure without
   mouse/keyboard.

These all extend the tool-use plan's pattern naturally (each is a new
ToolSpec) and none of them can cause data loss. Confirmation UX and
audit logs apply.

The next step up — file system write (category 6) — is the first
mutation and deserves its own plan on its own. Each step up from
there is more work per unit of value.

## What makes this different from the other components

The shipped components each had one user-visible behavior at the
end of their plan. Automation has a spectrum: the user-visible
behavior depends on how many categories you turn on. Eric could
ship (1, 2, 3) from "Table stakes" and be a user-visibly better
daily-driver in three sessions. Or he could ship all 15 categories
in three months and have a real agent.

## What would make a good plan draft after this

Eric picks:

1. A starter set of 2-4 category numbers from the list above.
2. Whether shipping the infrastructure (dry-run, allow-list, kill-
   switch, audit log) happens in the same session as the starter
   set, or before it.
3. Whether voice confirmation or GUI confirmation is the default UX
   for novel invocations.

Each of those is a one-line answer and unlocks a 500-line plan doc.

## What's intentionally missing

- No specific tool APIs proposed. That's plan-work.
- No voice-phrase mapping ("open Photoshop" → ToolSpec args).
- No "Sabrina as a full agent" vision statement. That's a later
  aspiration; this brief is about what's implementable safely this
  year.
- No cross-category integrations. "Sabrina reads the calendar and
  launches the Zoom app at meeting time" is three categories at
  once; that plan comes after the primitives exist.
