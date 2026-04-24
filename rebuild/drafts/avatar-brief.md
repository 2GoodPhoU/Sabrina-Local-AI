# Avatar — capability brief (not a plan)

**Date:** 2026-04-23
**Status:** Brief. Research-only. No implementation proposed.
Eric reads this, reacts, and if the direction is worth pursuing a real
plan draft follows later.

## The point of an avatar

Today Sabrina has a console and a settings window. Voice in, voice
out, nothing on screen. Decision 005 notes: "[avatar is] pure UX polish,
zero capability added." Decision 006 keeps it deferred. The roadmap's
original component 6 sketched a PyQt6 frameless/always-on-top/click-
through window that reacts to `StateChanged` events.

The open question for Eric is which *rendering approach* to pick. The
five realistic routes trade art-asset lift for code-lift. There's no
wrong answer — they're different engineering commitments with
different creative ceilings.

## The five options

### 1. Sprite-based (QPixmap animation)

- **What it is:** Pre-drawn images for each state (idle, listening,
  thinking, speaking), displayed in a PyQt6 frameless window. Swap
  frames at N fps for simple animation loops.
- **Code lift:** ~200 lines. PyQt6 already flagged as the avatar
  dep. Glue is minimal.
- **Art lift:** low-to-medium. ~5-15 static frames per state, or loops
  of ~15 frames each. Can live with 30×30-px pixel art or 512×768
  hand-drawn — art style is unconstrained.
- **Ceiling:** Doesn't breathe, doesn't blink, doesn't react to
  audio amplitude. Looks like a 2003 desktop companion.
- **Fit:** Lowest-commitment way to validate "should Sabrina have a
  face at all."

### 2. Live2D (via the Cubism SDK)

- **What it is:** 2D rigged puppet. Industry-standard for VTubers.
  Deformation on bones gives convincing head turns, eye blinks, lip
  sync from TTS audio amplitude. Models are `.model3.json` files
  with layered artwork.
- **Code lift:** medium. Cubism SDK for Native is C++; there's
  `live2d-py` (ctypes wrapper, MIT license, active). Integrate
  inside a PyQt6 `QOpenGLWidget`. ~400-700 lines.
- **Art lift:** high without assets, or "free" with pre-made ones.
  Pre-built Live2D models are plentiful (itch.io, DeviantArt,
  commissionable). Building one from scratch is a few hours in
  Live2D Cubism Editor with PSD prep.
- **Licensing:** free for apps with annual revenue below Live2D's
  threshold (which Sabrina trivially satisfies — personal tool).
  Read the Cubism SDK license on ship.
- **Ceiling:** Very high. Lip sync, blinking, head tracking, emotes.
  What most VTuber streams you've seen look like.
- **Fit:** The default "if I want Sabrina to feel alive" pick.

### 3. VRM (via the VRoid ecosystem)

- **What it is:** 3D character format. Unity / Unreal / Godot / Three.js
  all consume `.vrm` files. Paired with a motion protocol (VMC,
  iFacialMocap) for expressions.
- **Code lift:** high. Python VRM libraries are thin; the practical
  path is embedding a web viewer (`QWebEngineView`) with `three.js`
  + `@pixiv/three-vrm`. ~500 lines of JS + ~300 lines of Python
  bridge.
- **Art lift:** low (VRoid Studio generates competent avatars in an
  afternoon) to medium (import + rig a custom model).
- **Ceiling:** 3D — head turns, full-body, bone physics, shader
  effects. Fully overkill for a desktop chip, but the option exists.
- **Fit:** Only pick if Eric wants a 3D vibe. The browser-embed
  complexity is the real downside.

### 4. Native 3D in a GL window (Panda3D or raw OpenGL)

- **What it is:** Ship a 3D renderer as a Python dep, render directly
  to a PyQt6 `QOpenGLWidget`, drive animation from Sabrina events.
- **Code lift:** very high. 1000+ lines and a real 3D scene-graph
  learning curve.
- **Art lift:** very high unless Eric already has rigged models.
- **Ceiling:** infinite (it's 3D).
- **Fit:** basically never, for a personal tool. Call it out for
  completeness; skip.

### 5. Browser-embed with a prebuilt Live2D web viewer

- **What it is:** Use `QWebEngineView` to host a tiny HTML file with
  `pixi-live2d-display`. Sabrina pipes events into the page via
  `QWebChannel` or plain `window.sabrina = {...}` injection.
- **Code lift:** low-to-medium. The "renderer" is 100 lines of HTML
  + 150 lines of Python glue.
- **Art lift:** same as #2 (Live2D model).
- **Ceiling:** same as #2 at the cost of another dep
  (QtWebEngine, ~200 MB).
- **Fit:** If #2's `live2d-py` turns out painful to integrate, this
  is the escape hatch. Worse "native feel" but easier stack.

## Things the plan should also touch (whatever renderer)

These are engineering invariants, not option-dependent:

- **Frameless, always-on-top, click-through** (except when the user
  hovers the avatar — then opacity bumps up and clicks register).
- **Subscribes to `StateChanged` events.** `idle → listening` cue,
  `thinking` spinner/glow, `speaking` lip-sync (tied to TTS audio
  amplitude via `SpeakStarted` / `SpeakFinished`).
- **Runs as a sibling process** supervised the same way as the voice
  loop. Supervisor-autostart plan covers this; the avatar process
  doesn't need its own restart logic.
- **Dies gracefully** if audio/event bus is down. A crashed avatar
  should never kill the voice loop.

## Cost/benefit snapshot

| Option | Code lift | Art lift | Ceiling | Honest recommendation |
|---|---|---|---|---|
| 1. Sprites | Low | Low | Low | Pick for cheap "it has a face" MVP. |
| 2. Live2D native | Medium | Medium-High | Very high | Default if Eric wants alive-feeling. |
| 3. VRM | High | Medium | Very high | Only if 3D matters for its own sake. |
| 4. Native 3D | Very High | Very High | Infinite | Skip. |
| 5. Live2D via web | Low-Medium | Medium-High | Very high | Pick if #2's native path stalls. |

## Not addressed in this brief

- The TTS lip-sync protocol. PiperSpeaker emits `SpeakStarted`/
  `SpeakFinished` with duration; going from there to actual viseme
  streams needs a real audio-amplitude hook or a phoneme track from
  Piper's output. Research deferred to the real plan.
- Where the model file lives in the repo. If Eric picks Live2D, the
  model goes under `assets/avatar/` and gets excluded from the wheel
  (it's a runtime asset).
- Multi-monitor behavior. Does she float next to the mouse? Snap to
  a corner? Per-monitor pinned? All reasonable; UX call.
- The old repo's `services/presence/` supposedly has reusable art.
  Hasn't been verified in the rebuild. If Eric wants to reuse those
  assets, verifying their shape (spritesheet dimensions, format,
  licensing origin) is step zero of the real plan.

## What would make a good plan draft after this

Eric answers three questions:

1. Which option (1-5)?
2. Is there existing art (from the old repo or commissioned) or does
   the plan include "source art too"?
3. Is the avatar required for daily-driver, or is it "phase 2 after
   the real work is done"?

Any of those answered unlocks a 400-600 line plan doc in the style of
the others.
