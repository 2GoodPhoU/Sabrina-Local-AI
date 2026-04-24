# Avatar — Windows validation procedure (session 1 only)

**Purpose:** confirm the session-1 MVP of the Live2D avatar (frameless
always-on-top window, StateChanged → expression swap, SpeakStarted /
SpeakFinished → amplitude-driven lip-sync placeholder) works end-to-end
on Eric's Windows box before we call the session-1 decision validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`. Avatar
session-1 has landed per `rebuild/drafts/avatar-plan.md` (`avatar/`
package, `sabrina avatar-setup` + `sabrina avatar` verbs, `[avatar]`
block in `sabrina.toml`, placeholder model fetched into
`assets/avatar/placeholder/`).

**Out of scope for this doc:** the lip-sync amplitude tap in Piper (ships
session 2; the placeholder uses a sin-wave simulator), the settings GUI
Avatar tab (session 2), the Win32 click-through + Focus Assist polish
(session 3), the OC art pipeline (appendix, run when ready). Each gets
its own validation doc.

---

## Step 0 — Sanity-check PyQt6 + live2d-py import

```powershell
uv run python -c "from PyQt6.QtWidgets import QApplication; import live2d.v3 as live2d; print('ok')"
```

**Success:** prints `ok`. `live2d-py`'s v3 namespace is available and
PyQt6 widgets imports cleanly.

**Failure signal A:** `ImportError: PyQt6` or `ImportError: live2d` →
`uv sync` didn't install. Re-run step 1.
**Failure signal B:** `OSError: [WinError 126] The specified module
could not be found` when importing live2d → the Cubism Core DLL
bundled in the wheel can't load. Usually missing VS C++
redistributable; install the 2015-2022 x64 redistributable.
**Failure signal C:** DLL loads but `v3` namespace missing → old
`live2d-py` version that only supports Cubism v2 models. Bump pin
`>=0.3` in pyproject.toml.

---

## Step 1 — `uv sync` and `uv run pytest -q`

```powershell
uv sync
uv run pytest -q
```

**Success:** existing tests pass, plus the avatar block (~6 new tests;
no tests require a GL context or real model):

- `test_avatar_config_loads_with_defaults`
- `test_avatar_position_preset_resolves_to_xy`
- `test_avatar_respects_taskbar_work_area`
- `test_avatar_subscriber_maps_state_to_expression`
- `test_avatar_amplitude_smoothing`
- `test_avatar_config_roundtrip_preserves_comments`

Session-2/3 tests (GUI avatar tab rendering, Win32 click-through) are
not expected to exist yet.

---

## Step 2 — `sabrina avatar-setup` drops the placeholder model

```powershell
uv run sabrina avatar-setup
```

**Success:** the command downloads the chosen itch.io placeholder
Live2D model into `assets/avatar/placeholder/`. Expected tree after:

```
assets/avatar/placeholder/
├── <model>.model3.json
├── <model>.moc3
├── <model>.2048/
│   └── texture_00.png
└── expressions/
    ├── neutral.exp3.json
    ├── attentive.exp3.json
    ├── thinking.exp3.json
    ├── speaking.exp3.json
    └── working.exp3.json
```

Exact filenames depend on the chosen placeholder; the five expressions
listed in the `[avatar.expressions]` config block must exist as
`*.exp3.json` files in `expressions/`.

**Failure signal A:** network error during download. The setup verb
should print a clear URL + where it would have dropped the file. If a
proxy is blocking itch.io, document the decision doc's manual-drop
instructions.
**Failure signal B:** model downloaded but `expressions/` folder
empty or missing named expressions → the chosen placeholder doesn't
ship the expression set we planned around. Per plan, we mapped to
{neutral, attentive, thinking, speaking, working}. If the placeholder
ships with different names, update
`[avatar.expressions]` to match what's there, or file a follow-up to
pick a different placeholder.

---

## Step 3 — Enable avatar and verify config

```toml
[avatar]
enabled = true
model_dir = "assets/avatar/placeholder"
display = -1
position_preset = "bottom_right"
scale = 1.0
opacity_base = 0.95
always_on_top = true
click_through = false        # session-1 keeps click-through OFF; Win32 tweak lands session-3
lipsync_enabled = true
```

(Other keys at default.)

```powershell
uv run sabrina config-show | findstr /i avatar
```

**Success:** keys load with expected values.

---

## Step 4 — `sabrina avatar` launches the window

Open a second PowerShell. In the first, run the voice loop:

```powershell
uv run sabrina voice
```

In the second:

```powershell
uv run sabrina avatar
```

**Success:** a frameless, transparent-background window appears in the
bottom-right of the primary display. The placeholder model is visible
inside it. Window is on top of all other windows.

**Failure signal A:** no window at all → check the second shell's
output. If you see `avatar.model_load_error`, the `*.model3.json`
manifest couldn't be parsed. Capture the full error.
**Failure signal B:** window appears as an opaque grey rectangle with
the model centered → transparency isn't set. On Windows, this means
the `WA_TranslucentBackground` attribute wasn't applied or the frame-
less window style wasn't set before `show()`. Avatar code needs to
set both.
**Failure signal C:** window appears but the model doesn't — grey/
magenta fill instead → the OpenGL context didn't initialize. Capture
the GL version:

```powershell
uv run python -c "from PyQt6.QtOpenGL import QOpenGLVersionProfile; print('loaded')"
```

---

## Step 5 — `StateChanged` swaps expression

With `sabrina avatar` still running in window 2 and `sabrina voice`
running in window 1:

1. Press PTT in window 1. Say a short question.
2. Watch the avatar's face.

**Success — expression changes at each state transition:**

- PTT press → avatar shows `attentive` expression (listening).
- PTT release → avatar shows `thinking` expression.
- First audio plays → avatar shows `speaking` expression.
- After reply finishes → avatar returns to `neutral` (idle).

The transitions should be snappy (< 100 ms from event to visible
expression change).

**Failure signal A:** expression doesn't change at all → the avatar
process isn't subscribed to the event bus, OR the bus doesn't span
process boundaries. Check the plan: avatar subscribes to the bus; if
the bus is in-process only, cross-process events need a
pub/sub layer. Per the plan, there's an IPC story via UDP for
amplitude; events should use the same channel or a similar one.
Capture the avatar process's structlog — should show
`event.received state_changed ...` lines. If not, the channel is
broken.
**Failure signal B:** expression changes for some states but not
others → the expression map is incomplete in `[avatar.expressions]`
OR a mapped name doesn't exist in the placeholder's expressions
folder. Check the stderr for `avatar.expression_missing name=...`.

---

## Step 6 — Lip-sync placeholder moves the mouth

Session 1's lip-sync uses a sin-wave simulator while Sabrina speaks.
Watch the mouth during the TTS playback.

**Success:** the mouth opens and closes smoothly during speech. The
opening isn't synced to actual phonemes (that lands session 2 with the
Piper amplitude tap) but follows a smooth sin wave at ~2-3 Hz. On
`SpeakFinished`, the mouth closes to neutral and stays shut.

**Failure signal A:** mouth doesn't move → `SpeakStarted` didn't reach
the avatar (same event-bus-across-processes issue as step 5) or the
sin-wave simulator isn't wired to the `ParamMouthOpenY` parameter.
**Failure signal B:** mouth opens and stays open after
`SpeakFinished` → the event arrived but the "close the mouth" path
didn't run. Capture the log.
**Failure signal C:** mouth animates during `thinking` or `idle` too →
the simulator's start/stop gate is broken; it should only run between
`SpeakStarted` and `SpeakFinished`.

---

## Step 7 — Avatar crash doesn't kill the voice loop

Find the avatar process:

```powershell
Get-Process python | Where-Object { $_.MainWindowTitle -like "*sabrina*" -or $_.StartInfo.Arguments -like "*avatar*" }
```

(Or simpler: whichever python PID was most recently spawned — the
one for `sabrina avatar` — from `Get-Process python | Format-Table
Id, StartTime`.)

Kill it:

```powershell
Stop-Process -Id <pid> -Force
```

**Success:** voice process in window 1 keeps running. A new voice turn
still completes normally. `state.transition` events still fire in the
voice loop; they just aren't rendered anywhere visible.

**Failure signal:** voice loop crashes too → the event bus or an IPC
channel doesn't tolerate a vanished subscriber. Capture the voice
loop's traceback. Per plan, the bus publishes fire-and-forget; a
dead subscriber is fine.

---

## Step 8 — Launch order: avatar first, then voice

Close everything. In one shell:

```powershell
uv run sabrina avatar
```

Avatar window appears but shows no state events (no voice loop
publishing). Expression stays at `neutral`. Then in a second shell:

```powershell
uv run sabrina voice
```

**Success:** avatar picks up state events from the newly-started voice
loop. First PTT press causes the expression to change. This tests that
the avatar's event subscription is durable across publisher-restart,
not tied to a specific voice process.

**Failure signal:** avatar doesn't react → the IPC channel binds once
at startup and doesn't retry. Per plan, this is an acceptable
limitation *if* the supervisor owns both processes (which is the
envisaged deployment) — launch order is controlled. Document in the
decision doc; not a blocker for session 1.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | live2d WinError 126 | VS C++ redist missing | Windows build + DLL path |
| 0 | `v3` namespace missing | old live2d-py | `uv pip show live2d-py` |
| 2 | Model download fails | Proxy/network | Full setup output |
| 2 | `expressions/` missing or mismatched | Placeholder's expression set differs from plan | `ls assets/avatar/placeholder/expressions/` |
| 4 | Opaque grey window | Transparency attr not set | Avatar's window init code + structlog |
| 4 | GL context fail | Qt6 / GPU driver | `QOpenGLContext` version log |
| 5 | No expression changes | Event bus not cross-process | Avatar structlog for `event.received` |
| 5 | Partial expression changes | Expression file missing | `avatar.expression_missing` log |
| 6 | Mouth doesn't move | Lip-sync sim not gated by SpeakStarted | Avatar structlog around `SpeakStarted` |
| 6 | Mouth stuck open | SpeakFinished not received | Same log |
| 7 | Voice crashes with avatar | Bus doesn't tolerate dead subscriber | Voice traceback |
| 8 | Avatar doesn't pick up new voice process | IPC channel one-shot | IPC connection logs |

---

## Known risks from the pre-validation code audit

1. **Placeholder model's expression names may not match the planned
   map.** The `[avatar.expressions]` defaults
   (`neutral`/`attentive`/`thinking`/`speaking`/`working`) were
   plan-side guesses. The actual itch.io placeholder's expressions
   set is whatever the artist shipped. Step 2's "check `expressions/`
   folder" is the moment to fix the map to match reality — edit
   `sabrina.toml`, not the model.
2. **Cross-process event bus isn't a shipped primitive in the
   rebuild.** The plan description says "avatar subscribes to the
   bus," but the existing bus is in-process (`EventBus` in
   `events.py`). Session 1 must either (a) start the avatar in the
   *same* process as the voice loop via a Qt event-loop integration
   with asyncio, or (b) spawn avatar as a sibling process with a
   small UDP pub/sub bridge for events. If you're seeing "no
   expression changes" in step 5, this is likely why — the plan's
   implementation decision on this needs to be visible in whatever
   shipped.
3. **Always-on-top on Windows 11 can be defeated by focus-stealing
   full-screen apps.** If step 4 passes in isolation but the avatar
   disappears behind a maximized game or video, that's expected
   Windows behavior, not a bug. Session 3 adds Focus Assist handling;
   this session doesn't.
4. **Live2D rendering at 60 FPS keeps one CPU core warm (~5-10%).**
   Nothing to do about it at this session; the GPU fraction is
   negligible. Note if Eric notices fan ramp-up.
5. **PyQt6 + asyncio event-loop integration on Windows requires
   `qasync` or similar.** If the avatar is running in the voice-loop
   process and the UI becomes unresponsive during brain calls, that's
   the asyncio bridge being broken. Not a session-1 scope item unless
   it's the deployment path that shipped.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line:

```
Avatar session 1 validated on Windows (i7-13700K/4080, Python 3.12)
<YYYY-MM-DD>: placeholder model loads, 5 expressions swap on state
events, placeholder lip-sync animates, avatar-crash isolation
confirmed.
```

Commit with message:
```
validate: avatar session 1 on Windows (StateChanged → expression)
```

---

## If any step failed

1. Capture per the triage table.
2. The single highest-probability follow-up is the cross-process
   event bus (risk #2 above). If session-1 shipped with in-process
   Qt+asyncio integration and it's broken, the decision doc captures
   the `qasync` introduction. If session-1 shipped with sibling-
   process IPC and it's broken, the decision doc captures the pub/
   sub bridge shape.
3. Expression-name mismatches are config nudges, not new decisions —
   edit `[avatar.expressions]` and footnote the shipped doc.
