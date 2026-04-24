# Avatar plan — Live2D presence on Windows

**Date:** 2026-04-23
**Status:** Draft. Implementable in a 3-4 session arc. One small
audit finding flagged below (old-repo assets) but no implementation
blockers.
**Supersedes:** [`avatar-brief.md`](avatar-brief.md) (kept for history).
**Closes:** ROADMAP component 6. Daily-driver readiness item "(nice-
to-have) Avatar."

**In this plan:** sessions 1-3 wire a state-driven presence.
Sessions 5+ add a semantically driven cue track — see
"Presence-voice sync / cue track" and "Animation library scope"
below, plus the animation contracts graphed in
[`avatar-animation-graph.svg`](avatar-animation-graph.svg).

## One-line decisions (from Eric)

- **Rendering:** Live2D native via `live2d-py` in a frameless
  `QOpenGLWidget`.
- **First-session art:** audit old repo → fall back to itch.io
  placeholder. Audit done — see finding below.
- **Long-term art:** document the OC pipeline as an appendix (this
  session does not execute any of it).
- **GUI surface:** comprehensive settings tab — every position/
  opacity/behaviour knob the "presence" use case calls for.
- **Session 1 scope:** placeholder model + `StateChanged` →
  expression + `SpeakStarted/Finished` → amplitude-driven lip-sync.

## Old-repo asset audit (what we found, 2026-04-23)

`services/presence/assets/` contains:

```
celebration.gif   4.1 MB     static.png     28 KB
idle.gif          94 KB       talking.gif   53 KB
listening.gif     36 KB       working.gif   201 KB
themes.json
```

All GIFs. Nothing Live2D-compatible (no `.model3.json`, no `.moc3`, no
layered PSD). These assets were for the old project's sprite/GIF-swap
avatar paradigm, which the rebuild explicitly isn't using.

**Consequence:** session 1 pulls an itch.io placeholder Live2D model.
The old GIFs stay archived; not repurposed.

## The one-liner

Ship Sabrina as a visible, always-on desktop presence: a frameless
Live2D character that blinks when idle, follows the cursor with her
gaze, swaps expression on every state transition, and lip-syncs to
Piper's output while speaking. Everything the user can see and tune
about her lives in a new "Avatar" tab in the settings GUI.

## The rendering stack, in one diagram

```
┌────────────────────────────────────────────────────────┐
│  avatar/ (new package)                                 │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │ AvatarWindow : QMainWindow                        │  │
│  │  (frameless, always-on-top, click-through,       │  │
│  │   per-monitor geometry, alpha blending)          │  │
│  │                                                    │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │  AvatarView : QOpenGLWidget                │  │  │
│  │  │    │                                         │  │  │
│  │  │    └─> live2d-py  ──> Cubism SDK (DLL)      │  │  │
│  │  │            │                                  │  │  │
│  │  │            ├─> load model3.json              │  │  │
│  │  │            ├─> frame update (blink/breath)    │  │  │
│  │  │            ├─> expression swap                │  │  │
│  │  │            └─> mouth_open_y  ← audio amplitude│  │  │
│  │  └────────────────────────────────────────────┘  │  │
│  │                                                    │  │
│  │  Event bus subscribers:                            │  │
│  │    StateChanged → expression map                   │  │
│  │    SpeakStarted → start amplitude poll             │  │
│  │    SpeakFinished → close mouth                     │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘

Runs as sibling process to voice_loop. Supervisor (from
supervisor-autostart-plan.md) owns both. Avatar crash ≠ voice death.
```

## Files to touch (session arc)

```
sabrina-2/src/sabrina/
├── avatar/                        # NEW package
│   ├── __init__.py
│   ├── window.py                  # AvatarWindow (frameless, on-top, layered)
│   ├── view.py                    # AvatarView : QOpenGLWidget
│   ├── live2d_bridge.py           # live2d-py wrapper: load, update, expressions
│   ├── amplitude.py               # live PCM amplitude tap for lip sync
│   ├── bus_subscriber.py          # maps events → avatar behaviour
│   └── app.py                     # python -m sabrina.avatar entrypoint
├── cli.py / cli/brain.py          # +sabrina avatar (launch) command
├── gui/settings.py                # +Avatar tab (session 2)
└── config.py                      # +AvatarConfig
sabrina-2/
├── pyproject.toml                 # +PyQt6, +live2d-py
├── sabrina.toml                   # +[avatar] block
├── assets/avatar/placeholder/     # NEW — dropped itch.io model
└── tests/test_smoke.py            # +avatar event-wiring tests (no GL)
```

Guardrail notes:
- `avatar/` sits alongside `brain/`, `listener/`, `speaker/`, etc. —
  a peer subsystem, not a sub-feature.
- Every module stays under 200 lines. `window.py` is the biggest
  (~180 by plan end); split if it passes.

## Protocol / API changes

None at the Brain / Listener / Speaker level. The avatar subscribes
to existing events (`StateChanged`, `SpeakStarted`, `SpeakFinished`);
it adds no required publishers.

**One additive event is worth adding for the expression-debug path:**

```python
class AvatarExpression(_EventBase):
    """Request the avatar show a specific expression. Used by the
    settings GUI's debug panel; may also fire from tool-use in the
    future."""
    kind: Literal["avatar_expression"] = "avatar_expression"
    name: str      # "happy", "thinking", ...
    hold_ms: int = 0   # 0 = until next expression event
```

Additive, zero backward-compat risk.

## Config — the full `[avatar]` block

Every default is justified after the block.

```toml
[avatar]
# Master switch. Off for a fresh checkout — users must run
# `sabrina avatar-setup` (drops placeholder model) before enabling.
enabled = false

# Path to the Live2D model's root directory. Must contain a
# *.model3.json. Relative paths resolve to project root.
model_dir = "assets/avatar/placeholder"

# --- where she lives ---

# Which display (0-indexed, same convention as vision.monitor but
# zero-based here to match Qt's QScreen index). -1 = primary.
display = -1

# Quick placement; overrides position_xy when not "custom".
# "top_left" | "top_right" | "bottom_left" | "bottom_right" |
# "center" | "custom"
position_preset = "bottom_right"

# Exact top-left corner in screen coordinates when preset="custom".
position_xy = [0, 0]

# --- how she looks ---

# Rendered size as a fraction of model's native size. 1.0 = full,
# 0.5 = half, 2.0 = 2x. Ranged 0.25..3.0.
scale = 1.0

# Base opacity 0.0..1.0. 1.0 = opaque. Fallthrough when no fade
# rule is active.
opacity_base = 0.95

# Opacity while the cursor is over the avatar's bounding box.
# Set below opacity_base to give "I'm getting out of your way."
opacity_on_hover = 0.35

# After this many seconds with no StateChanged event, fade to
# opacity_idle. 0 disables.
idle_dim_after_s = 120
opacity_idle = 0.55

# --- behavior ---

# Stay on top of other windows.
always_on_top = true

# Clicks pass through to whatever is underneath. Disable during
# expression-debug so you can click to grab focus.
click_through = true

# Drag the avatar with left-click-hold when click_through is off.
draggable = true

# Snap to monitor edges within N px during drag. 0 disables.
snap_edge_px = 24

# Leave room for the Windows taskbar — avoids covering it.
respect_taskbar = true

# When Windows Focus Assist is on ("Do Not Disturb"), hide the
# avatar. Uses Win32 query; polls every 5 s.
hide_in_focus_assist = true

# Clicking the avatar body arms PTT (equivalent to the hotkey).
# Requires click_through = false.
click_to_ptt = false

# --- audio / lip sync ---

# Drive the avatar's mouth from Piper's live audio amplitude.
# Disable for silent-render tests or if the bridge misbehaves.
lipsync_enabled = true

# Smoothing on amplitude → mouth_open (0.0 = snappy, 0.95 = molasses).
lipsync_smoothing = 0.55

# --- expressions map ---

# Which Live2D expression to switch to on each state. Names must
# exist in the model's expressions/ folder. Fall back to "neutral"
# if a name isn't defined.
[avatar.expressions]
idle      = "neutral"
listening = "attentive"
thinking  = "thinking"
speaking  = "speaking"
acting    = "working"
```

### Default justifications

- `enabled=false` — a fresh checkout can't have the placeholder model
  baked in (itch.io license typically forbids redistribution); user
  opts in after `sabrina avatar-setup`.
- `position_preset="bottom_right"` — respects the Windows Start-menu
  habit (bottom-left is high-value real estate; top is for taskbars
  in some configs).
- `scale=1.0` — Live2D models ship sized for a "companion window"
  (~400×600 px at 1.0). Half sane as a default.
- `opacity_base=0.95` — almost-opaque is presence; full-opaque is
  a mascot. Subtle difference, but matters.
- `opacity_on_hover=0.35` — Eric asked for "fade when cursor enters."
  0.35 is ghostly-visible, doesn't block what's underneath.
- `idle_dim_after_s=120` — two minutes is long enough that Eric
  won't notice during a pause but short enough that an abandoned
  Sabrina stops commanding attention.
- `always_on_top=true` — this is the whole point of a presence.
- `click_through=true` — presence shouldn't eat clicks.
- `respect_taskbar=true` — Windows reports the work area; we clip
  to it.
- `hide_in_focus_assist=true` — Eric gets Focus Assist; his avatar
  should get the memo.
- `click_to_ptt=false` — introduces a conflict with `click_through`;
  opt-in only.
- `lipsync_smoothing=0.55` — middle of the range. Looks natural
  without being obviously lagged.

## Lip-sync — the tricky part

The Piper path today: sentence text → subprocess → int16 PCM bytes →
`sounddevice.play`. The avatar needs the amplitude *while it's
playing*, which means tapping the audio stream rather than the
sentence boundaries.

Cleanest implementation:

1. `speaker/piper.py` grows an optional `amplitude_sink: Callable[[float], None]`
   parameter. When set, `PiperSpeaker.speak` computes a moving RMS over
   the int16 buffer as it streams into `sounddevice`, sampled at
   ~30 Hz, and calls `amplitude_sink(rms_normalized)` from the play
   thread.

2. Avatar process subscribes to `SpeakStarted` and opens a small
   UDP/pipe channel (localhost, bound to 127.0.0.1:random) to receive
   amplitudes. Voice loop's speaker dispatches them over that channel.

3. Avatar applies smoothing and maps to `mouth_open_y` parameter.

**Alternative** considered: have the avatar open its own audio
capture on the playback device (Windows WASAPI loopback) and read
Sabrina's output back in from the speakers. Rejected: latency, plus
it captures everything else playing too, plus echo-cancellation is
a project unto itself.

### Structural uncertainty — IPC transport (resolved 2026-04-23)

Payload: one float32 every ~33 ms (30 Hz). Processes: voice_loop
(sender) and avatar (receiver), launched independently by the
supervisor — *not* spawned from the same parent.

Three options weighed against Windows realities:

- **localhost UDP (`127.0.0.1:<port>`).** Zero deps, 10-30 µs
  round-trip on loopback, natural fit for lossy 30 Hz amplitude
  (one dropped frame is invisible). Firewall concern: Windows
  Defender may prompt on the receiver's first bind. Loopback-only
  binds usually pass silently on Windows 10/11, but the behavior
  is inconsistent across Defender versions and OEM security
  layers. One-time approval is sticky. Mitigation: `sabrina
  avatar-setup` can lay down a scoped `netsh advfirewall` rule
  pre-approving `python.exe` for the chosen port range, so the
  first-run UX is clean.
- **`multiprocessing.Queue`.** Ruled out. Queue's pickle+pipe
  overhead is fine (~100-500 µs per small message on Windows),
  but the transport assumes a parent-spawned child. Our avatar
  process is launched by the supervisor as a sibling `python -m
  sabrina.avatar` — there's no shared Queue handle to pass.
  Working around this via a `multiprocessing.managers.BaseManager`
  adds RPC, authentication, and server-lifecycle code for a
  one-way float stream. Not worth it.
- **Named pipe via `win32pipe` (pywin32).** Native Windows IPC,
  no TCP stack, **no firewall involvement at all**. Latency is
  typically below UDP loopback for small messages. Cost: adds
  `pywin32` as a dependency (not currently in the tree —
  `pynput` is what we have), and the API surface is Win32 C
  shape through Python, more code than a socket.

**Decision: default to localhost UDP.** Ship `sabrina avatar-setup`
with an optional `--register-firewall` flag that drops the netsh
rule; document what it does. If the Defender prompt turns out to
be a recurring nuisance on Eric's specific install (validation
task `validate-avatar-windows.md` flags it), fall back to the
named-pipe path — keep `amplitude.py` interface-shaped so swapping
the transport is a one-file change. Decision doc captures this.

## Presence-voice sync / cue track

**Status:** Design approved 2026-04-23. Upgrades the avatar from
"state-driven GIF swap" to "semantically driven animation." Not
in sessions 1-3 above — implement as a session 5+ follow-on once
the OC rig lands, or opportunistically against the placeholder if
its expression/motion library is rich enough. See
[`avatar-animation-graph.svg`](avatar-animation-graph.svg) for the
visual map of what the dispatcher is steering.

### Thesis

Expression and gesture cues belong in Claude's output, not in app
heuristics. The brain already knows when it's pivoting to
reassurance, building to a surprise, or starting a list — and
getting that information any other way (sentiment classifier on
the transcript, ML-predicted facial animation from audio) is
noisier, slower, and more expensive. Let the brain annotate its
own speech.

### Tag vocabulary

Inline, fixed vocabulary in the reply text:

- `<emotion=NAME>...</emotion>` — mood span. Names match the 8
  base expressions: `neutral | happy | sad | surprised |
  thinking | focused | concerned | amused`.
- `<gesture=NAME/>` — one-shot motion, self-closing. Names:
  `nod | shake | tilt_left | tilt_right | blink_long | eye_roll
  | wink | shrug`.
- `<emphasis>...</emphasis>` — subtle body-lean / brow lift on
  the tagged word or clause.
- `<pause=MS/>` — breath-beat in TTS. Integer ms. 50-400
  typical.
- `<gaze=TARGET/>` — redirects eye-tracking for ~1 s: `user |
  away | up | down`. `user` resumes cursor-follow.

Tags are *additive metadata* — the TTS text with tags stripped
reads exactly the same as the spoken sentence. The brain is
taught the vocabulary in the system prompt with 5-6 short
examples (e.g. "on a rhetorical question consider
`<gesture=tilt_right/>` around the question mark"). No per-turn
enforcement; if the brain returns plain text, the avatar falls
back to state-driven behavior.

### TTS alignment

Piper exposes phoneme boundaries aligned to the input text.
Pipeline:

1. **Pre-TTS tag extraction.** Speaker strips tags, producing
   (a) a clean string for Piper and (b) a list of cue events,
   each stamped with a character offset into the clean string
   and a cue type.
2. **TTS.** Piper generates audio plus phoneme boundaries.
3. **Offset → audio-time mapping.** For each cue, look up the
   phoneme that closes at its character offset; record the
   audio-time (ms from speech start) at which the cue fires.
4. **Fire-on-tag-close.** For span tags (`emotion`,
   `emphasis`), the cue fires at the closing tag — not the
   opening tag, not the sentence boundary. Opening-tag fires
   read as "reacting to what I'm about to say"; closing-tag
   fires read as "reacting to what I just said," which is what
   the brain actually labelled.

### Cue dispatcher

One monotonic clock tracks speech-start time. A background loop
polls the cue list at ~120 Hz and fires each cue `LEAD_MS` before
its scheduled audio time. Default `LEAD_MS = 80`; exposed in the
`[avatar]` config as `cue_lead_ms`. The lead earns "arrives on
the word": human perception gives facial animation 40-120 ms of
pre-rollout — the face starts moving before the sound hits.

Barge-in (`BargeInDetected` event) cancels every queued cue and
schedules one compensating cue: `emotion=neutral` with a 200 ms
blend, marked `priority=preempt`. Any currently-playing one-shot
motion fades out over 80 ms.

### Three animation layers

Live2D composes additive parameter deltas. Three layers, summed:

- **Expression blend layer (mood).** Holds the current emotion
  preset. Cross-fades between presets over ~200 ms
  (configurable as `expression_blend_ms`). A few transitions
  route through a micro-neutral pass — see compatibility below.
- **One-shot gesture layer.** Plays one motion at a time;
  higher-priority gestures interrupt. Motion duration is the
  rigged motion's own length (300-900 ms typical). Deltas are
  additive, so a `nod` while `happy` reads as a happy nod, not
  "replace happy with nod."
- **Ambient layer.** Breath cycle, blink, micro-sway. Runs
  always; damped during speech on any parameter the speech
  layer touches (see priority rules below).

### Expression blend compatibility

Most emotion transitions cross-fade directly. Three pairs
benefit from a ~120 ms micro-neutral pass (fade out to neutral,
then blend into the next) because the direct path flashes
through an uncanny intermediate:

- `sad → surprised` — eye-shape path goes through wide-open
  cleanly after a neutral beat; direct reads as a squint-to-
  bulge glitch.
- `focused → amused` — brow rise from furrow without a pass
  reads as "raise eyebrow angrily."
- `concerned → happy` — mouth-form sign flip plus brow reset
  needs the pause.

All other 56 pairs blend directly. Encode the three as a
`BLEND_VIA_NEUTRAL` set in `avatar/expressions.py`.

### Gesture × mood compatibility

Not every gesture reads well under every mood. Contract:

- `nod` — all 8 moods. Universally affirming.
- `shake` — all except `happy` and `amused` (shake under a
  smile reads as teasing, not "no").
- `tilt_left` / `tilt_right` — all moods. Universally curious.
- `blink_long` — all moods. Reads as "processing,"
  mood-neutral.
- `eye_roll` — only `amused`, `neutral`, `concerned`. Under
  `sad` it reads bitter; under `happy` it reads sarcastic.
- `wink` — only `amused` and `happy`. Everywhere else, creepy.
- `shrug` — all except `surprised` and `focused`. Focused
  shrug reads as disengagement; surprised shrug is physically
  awkward.

The dispatcher silently drops a gesture if the current mood
disallows it and logs the drop at debug level. Do not fall back
to a different gesture — the brain picked the wrong one; it
learns from absence.

### Parameter-conflict priority

Live2D parameters are a shared resource across layers. When two
layers want the same parameter in the same frame, the higher-
priority layer wins on that parameter (not on the whole frame):

| Parameter family | Priority order (high → low) |
|---|---|
| Mouth (MouthOpenY, MouthForm) | speech lip-sync > gesture > mood > ambient |
| Head (AngleX/Y/Z) | gesture > mood > ambient |
| Eyes (EyeOpen, EyeBallX/Y) | gesture > gaze cue > mood > ambient cursor-follow |
| Brows | mood > gesture > ambient |
| Body sway (BodyAngleX/Y/Z) | gesture > mood > ambient |

Barge-in is special: for 200 ms after `BargeInDetected`, the
preempt layer owns every parameter, blending everything to
`neutral-attentive` (neutral mood + listening pose). After 200
ms the normal stack resumes with whatever the new listening
state called for.

### Graceful degradation

If a reply contains zero tags — fallback path, or Ollama-only
mode (see open question) — the avatar behaves exactly as the
session-1 design: expression from `avatar.expressions` on
`StateChanged`, lip-sync on `SpeakStarted`/`SpeakFinished`,
ambient idle. Cue dispatcher is a no-op when the cue list is
empty.

### Open questions

- **Ollama brain parity.** Local fallback brains use smaller
  models that will ignore or malform the tag vocabulary more
  often than Claude does. Two paths: (a) teach the same
  vocabulary in the Ollama system prompt and accept some
  malformed output (the tag parser already tolerates unclosed
  spans), or (b) run Ollama brain tag-free and accept the
  state-based fallback animation. **Lean: (b) for v1** —
  tag-free fallback. The animation-quality delta between
  "state-driven" and "cue-driven" is smaller than the QA cost
  of chasing malformed-tag edge cases on 7B models. Reconsider
  when a 14B+ instruction-tuned local model is the daily
  driver.
- Whether `<emphasis>` gets a subtle audio boost in Piper in
  addition to the body-lean cue. Deferred; not worth the Piper
  build complication in v1.
- Whether to expose `cue_lead_ms` in the GUI. Not in session 3;
  revisit when cue-track lands.

## Animation library scope — what we actually need to author

A common intuition from sprite/video avatar work is: "emotions
× gestures × speaking variants = a big clip matrix." For Live2D
that intuition is wrong, and tracking the wrong scope is the
most likely cost blowup in the OC pipeline.

### Why the matrix is a mirage

A Live2D character is a *single rigged PSD* plus a parameter
set. "Happy and nodding" is not a separate asset from "sad and
nodding"; it's the sum of two independent parameter deltas —
the `happy` expression file and the `nod` motion file — applied
to the one rig. No N×N clip library. One rig and a small
vocabulary of additive parameter files.

This reframes "library scope" from "how many clips?" to "how
many expression and motion files?" — a much smaller question.

### Deliverables on top of the base rig

All counts below assume the base rig from appendix step 5 is
done (8-30 hr one-time). These are the incremental deliverables
for a cue-track-ready character:

| Category | Files | Count | Per file |
|---|---|---|---|
| Base expressions (`.exp3.json`) | neutral, happy, sad, surprised, thinking, focused, concerned, amused | 8 | 15-30 min |
| One-shot gestures (`.motion3.json`) | nod, shake, tilt_left, tilt_right, blink_long, eye_roll, wink, shrug | 8 | 30-60 min |
| Ambient motions (`.motion3.json`) | breath, blink, idle_sway, speaking_sway | 3-4 | 15-30 min |
| **Totals** | | **~19** | **~10-15 hr** |

Expression files are parameter-key JSON — fast to author in the
Cubism Editor once the rig's parameters are defined. Motion
files are short curve timelines over the same parameters; the
Editor's timeline view is straightforward for anyone who
already has the rig in hand.

### What plausibly grows the list (none urgent for v1)

- **Tool-use expression events** — celebration on successful
  automation, skeptical on low-confidence responses — would
  add 2-4 expressions.
- **Language-specific emblematic gestures** — none needed
  unless localizing.
- **Seasonal / outfit swaps** — purely cosmetic; orthogonal to
  cue track.
- **Voice-specific mouth shapes** — three keyframes beyond
  `ParamMouthOpenY` for better English phoneme shaping (noted
  in OC pipeline step 3). `ParamMouthForm + OpenY`
  interpolation handles "good enough" without the extras.

### What doesn't need to grow

- **No clip matrix.** "Happy while speaking and nodding" is
  three additive signals, not a fourth asset.
- **No per-state exclusives.** `listening` doesn't need its
  own animation distinct from the `attentive` expression — the
  state-to-expression mapping in config handles routing.
- **No gesture variants.** One `nod.motion3.json` covers
  affirmation in all contexts. Amplitude / speed shaping
  happens at dispatch-time if at all (not in v1).

### What to visualize, and what not to

The visual map (`avatar-animation-graph.svg`) does *not*
catalog files — that's the table above. It graphs the
*contracts* between layers: which state transitions exist,
which expression transitions need a micro-neutral pass, which
gesture-in-mood combinations the dispatcher allows. Those are
rules that need visual inspection; file counts are boring
bookkeeping.

## GUI — "Avatar" tab

Single tab, three sub-frames matching the config's groupings.

### "Display & placement"

- Monitor dropdown (populated from `QGuiApplication.screens()`,
  labelled by index + primary-flag + resolution).
- Position preset combo box (5 presets + custom).
- Custom-XY pair of spin-boxes (greyed unless preset="custom").
- Scale slider (0.25..3.0, step 0.05).
- Always-on-top checkbox.
- Respect-taskbar checkbox.
- Snap-edge-px spin-box.

### "Opacity & behavior"

- Base opacity slider (0..1).
- Hover-opacity slider (0..1).
- Idle-dim opacity slider + idle-after seconds spin-box.
- Click-through checkbox.
- Draggable checkbox.
- Hide-in-focus-assist checkbox.
- Click-to-PTT checkbox (greyed unless click-through is off).

### "Expressions & lip-sync (debug)"

- Expression-mapping table: row per state, dropdown of model
  expressions (populated from the loaded model's expressions/
  folder).
- "Test expression" — pick an expression from a combo box,
  click "Fire" → publishes `AvatarExpression` to the bus.
- Mute-lipsync checkbox (disables amplitude channel).
- Lip-sync smoothing slider.

All changes write to `sabrina.toml` via `settings_io` (already
tomlkit-round-tripping). Avatar process subscribes to a new
`ConfigReloaded` event (from the voice-loop polish item on the
master plan) and re-reads on save — until that ships, GUI
changes require an avatar process restart. Documented.

## Windows-specific affordances

- **Click-through**: `WS_EX_LAYERED | WS_EX_TRANSPARENT` on the
  avatar's window handle. PyQt6 exposes this via
  `Qt.WindowType.WindowTransparentForInput` plus a `SetWindowLong`
  call for the transparent ex-style.
- **Per-monitor DPI**: Qt handles this if we opt in with
  `QApplication.setHighDpiScaleFactorRoundingPolicy`. Must set
  before `QApplication` instantiation.
- **Taskbar work-area**: `SHAppBarMessage(ABM_GETTASKBARPOS)` or
  the simpler `QScreen.availableGeometry()` (Qt already accounts for
  taskbar). Use Qt's API.
- **Focus Assist detection**: `WNF_SHEL_QUIET_MOMENT_RS_DAILY_ENABLED`
  and siblings via `NtQueryWnfStateData`. Python wrapper:
  `ctypes.windll.ntdll`. Alternative: the Quiet Hours registry key
  under `HKCU\Software\Microsoft\Windows\CurrentVersion\QuietHours`.
  Registry path is simpler; poll every 5 s.
- **Cubism SDK binary**: `live2d-py` ships the DLL in its wheel for
  Windows x86_64, Python 3.12. Verified.

## Test strategy

Tests must not require GL context or a real Live2D model (CI/
headless-friendly):

- `test_avatar_config_loads_with_defaults` — construct `AvatarConfig`
  from a stub TOML; assert every default.
- `test_avatar_position_preset_resolves_to_xy` — pass each preset +
  a fake monitor geometry; assert correct top-left.
- `test_avatar_respects_taskbar_work_area` — fake `QScreen`
  `availableGeometry` smaller than `geometry`; assert clip.
- `test_avatar_subscriber_maps_state_to_expression` — stub bus;
  publish `StateChanged(to="speaking")`; assert expression name
  emitted is from the `expressions` mapping.
- `test_avatar_amplitude_smoothing` — feed a square-wave amplitude
  series; assert exponential-moving-average output.
- `test_avatar_config_roundtrip_preserves_comments` — open the
  template `sabrina.toml`, write a field via `settings_io`, re-read,
  assert comments intact.
- `test_gui_avatar_tab_renders_all_subframes` — construct the tab
  against a stub settings; assert widget tree.

Live2D model loading is a manual smoke in
`validate-avatar-windows.md`:
- `sabrina avatar-setup` drops the placeholder model.
- `sabrina avatar` launches the process; window appears in
  `bottom_right`.
- Drive a voice loop; confirm expression changes on each state
  transition; confirm lip-sync tracks the voice.
- Cursor hover fades; two-minute idle dims.
- Toggle Focus Assist; avatar disappears.

## Session breakdown

**Session 1 — MVP presence (est. 1 session).**
- `avatar/` package skeleton + `AvatarWindow` + `AvatarView` +
  `live2d_bridge.py`.
- Placeholder Live2D model from itch.io dropped via a new
  `sabrina avatar-setup` verb (downloads + extracts under
  `assets/avatar/placeholder/`).
- `bus_subscriber.py` wiring: `StateChanged` → expression,
  `SpeakStarted/Finished` → mouth control (amplitude path stubbed
  with a sin-wave simulator until session 2).
- `sabrina avatar` CLI verb. Supervisor wiring added on the back
  (auto-spawn when `avatar.enabled=true`).
- Ship criterion: avatar window appears, reacts to state events,
  a voice turn produces plausible mouth movement.

**Session 2 — lip-sync + settings GUI (est. 1 session).**
- `speaker/piper.py` amplitude sink.
- `avatar/amplitude.py` UDP receiver + smoothing.
- Settings GUI "Avatar" tab, all three sub-frames.
- Live-reload path via `ConfigReloaded` (or process-restart if
  that event hasn't landed).
- Ship criterion: lip-sync on real Piper audio; every GUI knob
  exercised manually.

**Session 3 — polish + Windows affordances (est. 1 session).**
- Click-through toggle via Win32 ex-style.
- Focus Assist detection.
- Snap-to-edge dragging.
- Click-to-PTT alternative trigger.
- Idle-dim + hover-fade.
- `validate-avatar-windows.md`.
- Ship criterion: Eric runs her for a full day; no complaints.

**Session 4 (optional, separate effort) — Original-Character art
pipeline.** See appendix below. Does not block any session above.

## Dependencies to add

```toml
"PyQt6>=6.7",
"live2d-py>=0.3",       # ctypes wrapper around Cubism SDK, MIT
```

`live2d-py` transitively bundles the Cubism SDK DLL on Windows. No
separate installer.

## Licensing — researched against Live2D's current terms (2026-04-23)

Three parties are involved: Cubism SDK (Live2D Inc.), `live2d-py`
(the Python wrapper), and whatever placeholder/OC model ships in
the model directory. Each has a different license; lumping them is
where projects trip.

**Cubism SDK for Native — Publication License Agreement.**
Live2D gates use-in-released-products on business size and on a
classification called "Expandable Application."

- *General User* = individual, student, group, or entity with
  **annual sales under ¥10,000,000 JPY** (~$65k USD at current
  rates). Eric is a General User. [1]
- A General User who *releases* a non-Expandable application is
  **exempt** from the Publication License Agreement and payment.
  No signup, no royalty. [1][2]
- Personal / non-released development does not require a license
  at all. Eric using Sabrina on his own machine falls entirely
  outside the licensing regime. [2]
- **"Expandable Application"** is the clause that bites avatar
  projects. Live2D defines it as "Derivative Works which use and
  generate any indefinite numbers of models by adding or combining
  files or data (e.g. avatar), or Derivative Works containing
  multiple or other works in one title." Every Expandable
  Application **requires review and a special Publication License
  Agreement even for General Users.** [3]

Sabrina-as-Eric-uses-it is *not* Expandable — it ships a single
character (the OC once rigged, or the placeholder) and the avatar
is a subsystem of a voice assistant, not the product. But the
`avatar.model_dir` config knob lets the user point at any
`*.model3.json`, which is structurally the thing Live2D's clause
targets. Implication for ship: **if Sabrina is ever publicly
released with that knob user-facing, the Expandable-Application
review path is the conservative read.** For Eric's own tool, not
a concern. Document this in the README so a future fork doesn't
stumble in.

**Attribution.** Publishing a product under the General-User
exemption still requires the standard Cubism SDK attribution:
project credits / about page must note "Cubism SDK (c) Live2D
Inc." and link to the SDK page. Not applicable to personal use.

**`live2d-py` license.** The wrapper itself is MIT, distributed by
EasyLive2D on GitHub and PyPI. [4][5] **But** the `live2d-py` wheel
bundles the Cubism Core DLL, and that DLL is proprietary and
governed by the Live2D Proprietary Software License Agreement —
MIT does not apply to it. [5][6] Practical effect on Sabrina: Eric
depends on `live2d-py` in `pyproject.toml`, and the user's install
pulls the DLL through that wheel. Eric's repo does not redistribute
the DLL itself, so his exposure is limited. If Sabrina ever vendored
the DLL directly, that would be SDK redistribution and a separate
conversation.

**Placeholder model.** Most itch.io "free avatar" drops are
CC-BY-NC or artist-specific EULAs; several explicitly forbid
repo-committed redistribution. `avatar-setup` fetches the model on
first run, per the brief — not committed to git. Attribution goes
in the settings "About" tab once that tab exists.

**OC model (post-pipeline).** Eric-authored art under whatever
terms Eric sets. LoRA-derived art is still a live legal question
in some jurisdictions; not blocking here.

**Sources.**

1. Live2D — [SDK Release License (Publication License Agreement)](https://www.live2d.com/en/sdk/license/) — business size classification & General User exemption.
2. Live2D Help — [What is the SDK Release License? In what cases do I need a contract?](https://help.live2d.com/en/sdk/sdk_001/) — development vs. release; exemptions.
3. Live2D — [A. Expandable Applications](https://www.live2d.com/en/sdk/license/expandable/) — the Expandable Application definition and review requirement.
4. EasyLive2D — [live2d-py on GitHub](https://github.com/EasyLive2D/live2d-py).
5. EasyLive2D — [live2d-py LICENSE (MIT)](https://github.com/EasyLive2D/live2d-py/blob/main/LICENSE).
6. Live2D — [Cubism Core SDK Manual](https://docs.live2d.com/en/cubism-sdk-manual/cubism-core/) — Core is proprietary, not under the MIT wrapper's terms.

## Ship criterion (whole arc)

- Every session's ship criterion met.
- `sabrina voice` with avatar enabled: avatar is visible, responds
  to all five states, lip-syncs, fades on hover, dims on idle.
- No regression on first-audio latency (avatar is a sibling process
  subscribing to bus events — the voice loop doesn't know or care
  that it's running).
- Avatar crash does not kill the voice loop. Supervisor restarts
  the avatar independently.

## Not in this plan

- Original-character art production (appendix).
- VRM/3D.
- Multi-character support.
- Reaction-GIF moments on specific events (e.g. celebrate on
  `AssistantReply`).
- Voice-pitch-linked head tilt.
- Per-expression sounds.

---

## Appendix — Original-Character art pipeline (run-when-ready)

None of this executes in the avatar sessions above. It's a standalone
effort Eric runs on the 4080 when he wants to replace the placeholder
with a custom Sabrina. Target: RTX 4080 (16 GB), Windows 11, Python
comfort assumed. Time budget quoted step-by-step and rolled up at
the end.

### Tooling — a single recommendation

**ComfyUI for inference, `kohya_ss` (GUI) for training, Krita for
PSD prep, Live2D Cubism Editor (free tier) for rigging.**

Why not the alternatives:

- **Fooocus** is the lowest-friction path for first-timers but its
  LoRA support is "works, not flexible" and it does not train
  LoRAs at all — for a pipeline that requires ControlNet + IP-Adapter
  + a custom-trained LoRA in the same workflow, ComfyUI's node graph
  is the right shape. [A]
- **Automatic1111** has in-tree LoRA training and a friendlier UI,
  but the ControlNet/IP-Adapter combinations this pipeline uses
  are more fragile there than in ComfyUI, which has broader 2026
  node coverage. [A][B]
- **ComfyUI for training specifically** — there are ComfyUI-native
  training nodes in 2026, but `kohya_ss` is still the gold standard
  for character LoRAs on SDXL and every character-consistency guide
  assumes it. [C]

A single ComfyUI install serves every inference step in the
pipeline; `kohya_ss` lives alongside it in a separate conda/venv.

### Character-consistency technique — LoRA (recommended)

Considered alternatives:

| Technique | Verdict |
|---|---|
| **Pure prompt chaining** | Insufficient. SDXL drifts on hair shape, eye color, outfit across a 20-image expression sheet. Shows within 5-10 generations even with fixed seed. |
| **IP-Adapter only** | Locks *face* well via IP-Adapter Face ID Plus v2, but outfit/color drift remains. Good for hybrid stacking — see below. [D] |
| **LoRA (recommended)** | 15-50 training images of the target character, 1-2k training steps, produces a ~150 MB `.safetensors` that reliably reproduces the character across arbitrary prompts. The standard for the use case. [C][E] |
| **Full finetune (DreamBooth)** | Overkill. Higher-fidelity but 4-8× the training time and a ~6 GB checkpoint. Only worth it if LoRA's drift on extreme expressions turns out to be unacceptable. Skip unless forced. |

**Recommended stack: a custom-trained LoRA + IP-Adapter reference-only
layered on top for each generation** — LoRA locks the character identity,
IP-Adapter enforces the exact face from the canonical reference image
for the expression sheet. This is the 2026-consensus approach. [D][E]

### Step 1 — seed data + character design (1-2 evenings, 4-8 hr)

**Target seed set: 25-40 final training images** (sweet spot is
20-30 face+body shots, 10-15 face close-ups). [C]

**Quality bar.** Every image must:
- Depict the same character — same hair cut/color, eye color, build,
  outfit anchors (one recurring outfit is fine; fully different
  outfits in every shot makes the LoRA learn "any outfit" instead of
  the character).
- Vary angle and expression enough to teach generalization — if every
  training image is front-facing-neutral, the LoRA only does
  front-facing-neutral.
- Be 1024×1024 or larger; SDXL-scale. Smaller images either get
  upscaled (hurts quality) or cropped out.
- Have no watermarks, no third-party logos, no accidental duplicate
  characters in frame.

**Generation workflow.**
1. In ComfyUI, load a character-competent SDXL base. `JuggernautXL`
   or `AnimagineXL-v3.1` are the 2026 defaults for realistic /
   anime respectively.
2. Run an IP-Adapter-reference workflow seeded from a single
   hand-picked "canonical" image of the OC (can be a rough sketch
   or even a Picrew-style export). Generate 80-120 candidates
   varying seed + minor prompt modifiers (angle: "3/4 view",
   "side profile"; outfit: variants; expression: "slight smile",
   "determined"). [D]
3. Cherry-pick 25-40 that feel like the same person. This is the
   taste-call step; there is no automation for it.

**VRAM / timing on 4080:** SDXL + IP-Adapter at 1024×1024 uses
~9-11 GB. Per-image wall-time is ~7-9 s on a 4080 with
`--medvram` off. An evening's batch of 120 images is ~20-25 min
of pure compute plus an hour of cherry-picking.

**Annotation.** Each training image needs a caption. Two conventions:
- BLIP-2 autocaption via ComfyUI's caption node, then manual cleanup.
  Autocaptions over-describe ("a woman with long brown hair wearing
  a black jacket standing in a forest") — keep the detail, but
  strip anything that changes across the set (backgrounds, poses)
  so the LoRA doesn't bake those in.
- Prepend a **trigger token** to every caption. Pick something the
  tokenizer won't split, e.g. `sbrna_oc`. Every generation prompt
  at inference time includes that token.

### Step 2 — LoRA training (45-90 min compute, one evening end-to-end)

**Tool: `kohya_ss` GUI** (bmaltais fork is the 2026 active line). [F]

**Training config (4080 / 16 GB):**

```
Base model: same SDXL checkpoint used in Step 1 (critical — LoRA
            is coupled to base).
Resolution: 1024
Network: LoRA, rank 32, alpha 16  (32/16 is the sweet spot for
         characters; 64/32 tends to memorize rather than generalize)
Optimizer: AdamW8bit
Learning rate: 1e-4 unet, 5e-5 text encoder
Epochs: 10-15
Repeats per image: 10 (for ~30 images → ~3000 steps, in-band with
                  the 1500-3000 recommended range) [E][G]
Batch size: 2 at 1024 with gradient checkpointing on
Mixed precision: bf16
Cache latents: true (saves re-encoding VAE every step)
Cache text encoder: true
```

**Wall time on 4080:** ~45-75 min for ~3000 steps at batch 2 with
gradient checkpointing. [G]

**Overfitting watch.** Save a checkpoint every 2 epochs; sample-
generate at each. If epoch 12 images look *identical* to training
images (background, pose, composition), epoch 8 is the one to keep.

**Output:** `sabrina_oc.safetensors`, ~140-180 MB.

### Step 3 — expression + motion sheet (one evening, 3-5 hr)

With the LoRA loaded in ComfyUI + IP-Adapter using the canonical
reference face, batch-generate the Live2D-rigging sheet.

**Expressions needed for the `avatar.expressions` map** (from the
config section above):
- `neutral` (maps to idle)
- `attentive` (listening)
- `thinking` (thinking)
- `speaking_open`, `speaking_mid`, `speaking_closed` (three mouth
  shapes for lip-sync key frames)
- `working` (acting)

**Plus the ones nice to have for the rig even if not wired to
state events yet:**
- `happy`, `surprised`, `sad`, `confused` — for future tool-use
  expression events.

That's 12-14 distinct expression images. Target: **10 candidate
renders per expression, pick one** → ~120-140 generations.

**Prompt template:**
```
sbrna_oc, <standard character description>, <expression cue>,
front-facing, centered, plain off-white background, flat even
lighting, neck-up, no shadows, same outfit
```

**ControlNet pose lock.** For the motion/turnaround sheet
(`ParamAngleX` key poses at -30 / 0 / +30), add an OpenPose
ControlNet conditioning with a stick-figure skeleton at each
angle. Keeps composition identical so the rig's mesh deformation
has a clean source. [D][H]

**Seed discipline.** Fix the seed within each expression's batch of
10 (lock face). Vary only the expression-cue tokens. Consistency
across the sheet depends on this.

Wall-time: ~5-7 s per image → ~15 min compute, ~2-3 hr picking.

### Step 4 — refinement + PSD layering (1-3 evenings, 6-15 hr)

**Tool: Krita** (free, Windows-native, PSD-compatible). Photoshop
works if already owned.

**Clean-up pass (2-4 hr).** Even with identity-locked LoRA + IP-Adapter,
each chosen image needs touch-ups — eye-symmetry drift, hair-strand
breaks, mouth-corner inconsistency. Budget 10-20 min per expression.

**Layer separation (4-10 hr).** This is the unskippable labor step.
Each final image gets hand-separated into layers that match what
Live2D Cubism expects:
- `hair_back`, `hair_front` (two layers; the Cubism idle motion
  swings them out of phase)
- `body`, `clothes_front`, `clothes_back` (optional physics layer)
- `face_base`
- `eye_L_white`, `eye_L_iris`, `eye_L_lid_upper`, `eye_L_lid_lower`
  (plus same for right eye — 8 layers per eye-pair)
- `brow_L`, `brow_R`
- `mouth_upper_lip`, `mouth_lower_lip`, `mouth_inside`, `teeth`
  (4 layers for ParamMouthOpenY to interpolate cleanly)
- `ear_L`, `ear_R` (if visible)
- `accessory_*` for each hairpin, collar, etc.

Live2D's PSD-prep doc is explicit about layer naming conventions —
Cubism reads them verbatim as mesh IDs. [I][J]

Export as **a single multi-layer PSD per pose**. The rig in Step 5
operates on one canonical PSD; expression images feed in as
expression-specific mesh deformations, not separate PSDs.

### Step 5 — Live2D rigging (8-30 hr, over a week)

**Tool: Live2D Cubism Editor Pro** — FREE for personal use, gated
at trial for commercial use. Confirmed against the license research
above: Eric qualifies as a General User; the free personal tier
applies. [K]

**Parameters to define, at minimum:**
- `ParamAngleX` (-30 to +30) — head yaw
- `ParamAngleY` (-30 to +30) — head pitch
- `ParamAngleZ` (-30 to +30) — head roll
- `ParamEyeLOpen` / `ParamEyeROpen` (0-1) — blinks
- `ParamEyeBallX` / `ParamEyeBallY` (-1 to +1) — gaze direction
  (cursor-follow)
- `ParamBrowLY` / `ParamBrowRY` (-1 to +1) — brow lift
- `ParamMouthForm` (-1 to +1) — smile vs. frown
- `ParamMouthOpenY` (0 to 1) — **the lip-sync parameter**
- `ParamBreath` (0 to 1) — idle breath cycle
- `ParamBodyAngleX` / `...Y` / `...Z` — subtle body sway

**Realistic time estimate.** Every published Live2D guide,
including the Shiralive2D tutorials and the 7-day Viverse
challenge, lands on the same bracket: **a first-time rigger on a
simple character spends 8-12 hours on a minimal rig and 20-30
hours on a polished one, spread across 3-7 evenings.** [L][M][N]
This is not "a long afternoon" — plan it as a week of focused work.

**Auto-rigging tools.** `l2d-auto-rig` and similar projects exist
and produce passable starting drafts by detecting facial landmarks
and generating first-pass parameter key frames. Output is 60-70%
of the way there; a human still has to clean up mesh distortions,
set motion curves, and key the expressions. Saves 3-5 hours off
the low end. Not a substitute for knowing Cubism.

**Expressions (`.exp3.json`).** Each expression in the sheet from
Step 3 becomes a small JSON file mapping parameter → value:
```json
{"Parameters": [
  {"Id": "ParamBrowLY", "Value": 0.8, "Blend": "Add"},
  {"Id": "ParamMouthForm", "Value": 0.6, "Blend": "Add"}
]}
```
Cubism Editor has a GUI for authoring these; the `AvatarExpression`
event names map to the filenames.

**Motions (`.motion3.json`).**
- `idle.motion3.json`: breathing (ParamBreath cycle) + occasional
  eye dart + micro head sway. 10-15 s loop.
- Optional `speaking.motion3.json`: more active body sway + subtle
  head nod when `StateChanged → speaking`.

### Step 6 — asset export (15 min)

Cubism Editor exports:
- `sabrina.model3.json` — manifest (paths to all subparts)
- `sabrina.moc3` — the binary rig (proprietary binary format)
- `sabrina.2048/texture_00.png` — texture atlas (one or more)
- `expressions/*.exp3.json` — expression files
- `motions/*.motion3.json` — motion files
- `physics/sabrina.physics3.json` — optional bone-physics (hair sway)

Drop the whole directory under `assets/avatar/sabrina/`. Update
`avatar.model_dir = "assets/avatar/sabrina"` in `sabrina.toml`.

### Step 7 — validate in-app (30-60 min)

- `sabrina avatar-setup --dir assets/avatar/sabrina` — links and
  validates the model3.json.
- `sabrina avatar` launches with the new model.
- Drive a voice turn; confirm each `StateChanged` transition picks
  the right expression.
- Confirm `ParamMouthOpenY` tracks Piper amplitude during
  `SpeakStarted` → `SpeakFinished`.
- Confirm idle motion loops without pops.
- Any drift gets fixed back in Cubism Editor (steps 5-7 iterate).

### End-to-end time budget

| Step | Hands-on hours |
|---|---|
| 1. Seed data + cherry-pick | 4-8 |
| 2. LoRA training (mostly unattended compute) | 2 |
| 3. Expression sheet generation + pick | 3-5 |
| 4. Clean-up + PSD layering | 6-15 |
| 5. Live2D rigging | 8-30 |
| 6. Export | 0.25 |
| 7. In-app validation + rig iteration | 1-3 |
| **Total** | **~25-65 hours** |

First-time-through lands solidly in the 40-50 hr range. Second
character (reusing the LoRA workflow + rigging muscle memory)
drops to ~15-25 hr.

### Why this is still an appendix, not a session

Steps 1, 3, and 4-7 are hours of creative taste and hand-work Eric
owns. The research here is enough for him to stop worrying about
*which* tools and *how long*; the actual execution is a week of
evenings when he decides it's time.

### Sources

- [A] Tech Tactician — [ComfyUI vs Automatic1111 vs Fooocus comparison](https://techtactician.com/comfyui-vs-automatic1111-vs-fooocus-comparison/).
- [B] PropelRC — [ComfyUI vs Automatic1111 vs Fooocus: Complete 2026 Comparison](https://www.propelrc.com/comfyui-vs-automatic1111-vs-fooocus/).
- [C] Apatero — [ComfyUI LoRA Training Guide 2026 — Character Consistency](https://www.apatero.com/blog/comfyui-lora-training-character-consistency-guide-2026).
- [D] Stable Diffusion Art — [IP-Adapters: all you need to know](https://stable-diffusion-art.com/ip-adapter/).
- [E] Digital Zoom Studio — [Training a Character LoRA with kohya_ss + A1111](https://digitalzoomstudio.net/2026/03/training-a-character-lora-with-kohya_ss-automatic1111/).
- [F] bmaltais — [kohya_ss GUI](https://github.com/bmaltais/kohya_ss).
- [G] Puget Systems — [Stable Diffusion LoRA Training: Consumer GPU Analysis](https://www.pugetsystems.com/labs/articles/stable-diffusion-lora-training-consumer-gpu-analysis/).
- [H] Stable Diffusion Art — [Consistent character from different viewing angles](https://stable-diffusion-art.com/consistent-character-view-angle/).
- [I] Live2D — [Notes on PSD creation (layer-naming conventions)](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/).
- [J] Live2D — [Illustration Processing tutorial](https://docs.live2d.com/en/cubism-editor-tutorials/psd/).
- [K] Live2D — [Cubism Editor product page (FREE tier for personal use)](https://www.live2d.com/en/cubism/about/).
- [L] ShiraLive2D — [Rigging tutorials: beginner-to-pro hour breakdown](https://shiralive2d.com/live2d-tutorials/).
- [M] Viverse — [How to rig a 2D VTuber model in Live2D Cubism](https://news.viverse.com/post/rig-2d-vtuber-model-live2d-cubism).
- [N] R3DHummingbird — [Live2D Cubism 4.0 Cookbook: basic workflow](https://r3dhummingbird.gitbook.io/live2d-cubism-cookbook/modeling-and-rigging/basic-workflow).
