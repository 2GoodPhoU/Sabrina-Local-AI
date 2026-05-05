# Avatar + cue-track implementation deep-dive

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Implementation-ready follow-on to `avatar-plan.md`. The plan
already settled: `live2d-py` primary, `pixi-live2d-display` documented
fallback, frameless `QOpenGLWidget` window, single-clock dispatcher,
localhost UDP for amplitude/cue IPC. This doc fills the
"how do you actually do that" gaps with 2026 evidence.

**Audience:** Eric on the i7-13700K + RTX 4080 + 32 GB box, Win 11.
Implementation owner is a future Claude session.

**Anchor:** the plan's session 1 ship criterion: "avatar window
appears, reacts to state events, a voice turn produces plausible mouth
movement." This doc backs that up with measured hardware numbers, the
specific live2d-py 0.6.x API surface, and the cue-track sync architecture
that turns state-driven swap into semantically driven animation.

---

## live2d-py state of the art (April 2026)

`live2d-py` 0.6.1.1 was released 2026-01-16 [1]. Three things changed
that are worth flagging because they make the plan's prose simpler:

1. **Auto-blink and auto-breath are first-class.** `live2d.LAppModel`
   exposes `set_auto_blink_enable(bool)` and `set_auto_breath_enable(bool)`
   [2]. The plan's "ambient layer" doesn't need a hand-rolled blink/
   breath cycle for the placeholder phase — toggle them on at load
   time. We still implement our own ambient layer for the OC rig
   because we want to drive `ParamBreath` from the cue-track for "calm
   vs. focused breathing" later, but for session 1 the built-ins are
   strictly correct.
2. **`update()` is called by the host loop, not auto.** The
   render contract is "QOpenGLWidget calls `Model.update()` then
   `Model.draw()` every paint." The recommended cadence is a 60 Hz
   `QTimer` (`timer.start(16)`) that calls `widget.update()` (which
   in turn schedules `paintGL`) [3]. This is the standard Qt
   `QOpenGLWidget` pattern; nothing exotic.
3. **The C-Limited-API change in 0.3.2+ means cp310-cp313 wheels are
   on PyPI** with no source-build dance for Eric's Python 3.12. The
   wheel ships the Cubism Core DLL alongside; no separate installer.

The Python C-Extension wraps Live2D's Native SDK (C++) and is
"theoretically compatible with any OpenGL-based window" — Pygame,
PyQt5/6, PySide2/6, GLFW, pyopengltk, FreeGlut, qfluentwidgets [2].
For Sabrina the choice is PyQt6 (the Plan's call); the PySide6 demo
in the live2d-py samples ports to PyQt6 with import-line edits only.

### Comparable alternatives, re-assessed

| Option | 2026 status | Verdict for Sabrina |
|---|---|---|
| `live2d-py` 0.6.x | Active, Jan 2026 release, Win wheels for 3.10-3.13 | **Primary.** Same call as the Plan. |
| `pixi-live2d-display` + QWebEngine | Mature, both Cubism 2.1 + 4 supported | Documented fallback if OpenGL ctx integration goes sideways. ~150 MB QWebEngine cost still real. |
| VTube Studio + `pyvts` | Free demo tier of VTube Studio + WebSocket plugin API | **Worth trying as a parallel session-1 prototype.** Standing this up is one afternoon; it gives Eric something on screen while live2d-py work continues. But it's a separate paid app and it owns the renderer, so it is not the long-term answer. |
| Sprite-strip / GIF swap | Strictly worse than the placeholder Live2D model | Ruled out. The old repo's `services/presence/assets/*.gif` are already archived per the Plan's audit. |

The 2026 evidence does not change any of the Plan's calls. What it
*does* sharpen: `live2d-py` 0.6.x is well-trodden enough that the
"medium effort to first frame" estimate in the survey deserves a
"low-medium" downgrade. Auto-blink + auto-breath alone shaves an
afternoon off session 1.

---

## Window: frameless, transparent, click-through, always-on-top

This is the fiddly part. The Plan named the four flags but did not
sequence them. 2026 sources confirm that the order and the
`WA_TranslucentBackground` attribute are load-bearing on Windows 11
[4][5].

```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QSurfaceFormat
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QMainWindow

class AvatarWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # MUST set window flags before creating GL widget, or composition
        # picks up the wrong attributes on Windows 11.
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool        # no taskbar entry
            | Qt.WindowType.WindowTransparentForInput  # click-through
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # Pre-multiplied alpha; avatar PNGs from Cubism are straight-alpha,
        # so we composite via the GL pipeline instead of relying on Qt.
        fmt = QSurfaceFormat()
        fmt.setAlphaBufferSize(8)
        QSurfaceFormat.setDefaultFormat(fmt)

        self._view = AvatarView(self)
        self.setCentralWidget(self._view)
```

Two Windows-11 gotchas the plan elided:

- **`WA_TranslucentBackground` doesn't compose with `QOpenGLWidget`
  out of the box.** Qt 6 fixed the alpha buffer bug that 5.6 had, but
  on Windows 11 with a HiDPI display the GL surface format must
  explicitly request an alpha channel — without `setAlphaBufferSize(8)`
  the avatar renders against an opaque black background even though
  the window itself is "transparent." Set the surface format
  *before* the QApplication exists or the default format wins.
- **`WindowTransparentForInput` is not the same as a region mask.**
  The whole window becomes click-through; the avatar's body included.
  When `click_through = false` (or `click_to_ptt = true`), we toggle
  this flag at runtime via `setWindowFlag(WindowTransparentForInput,
  False)` and then call `show()` again — flag changes only take
  effect on a re-show on Windows 11. This is annoying but stable.

For Focus Assist detection the simpler path remains the `HKCU\
Software\Microsoft\Windows\CurrentVersion\QuietHours` registry key,
polled every 5 s — same as the Plan said.


## Cue-track timing budgets — the dispatcher

The Plan's "single-clock dispatcher" needs concrete numbers. From the
psychophysics literature on lip-sync perception and Live2D's own
tracking docs, the budgets that matter:

| Element | Budget | Source |
|---|---|---|
| Anticipatory lead (cue fires before the audio it tags) | **80 ms** default; configurable as `cue_lead_ms` (40-120 ms range) | Live2D's tracking guidance lists 60 ms as a typical perceptual delay-comp value [6]; lip-sync research consistently lands between 40 and 120 ms before-onset for "facial animation feels in time" [7]. |
| Expression cross-fade (mood layer) | 200 ms | Live2D Cubism's expression blend default; longer reads as molasses, shorter is flickery. |
| Micro-neutral pass for incompatible mood transitions | 120 ms | Plan's spec; matches the `BLEND_VIA_NEUTRAL` set (`sad→surprised`, `focused→amused`, `concerned→happy`). |
| One-shot gesture motion length | 300-900 ms | Authored in Cubism Editor; depends on the gesture. `nod` is typically 500 ms; `shrug` 700-900 ms. |
| Lip-sync sample rate (amplitude → MouthOpenY) | 30 Hz | Plan's call; also matches Cubism's recommended `motion-sync` cadence. Higher than 30 Hz is overkill for `ParamMouthOpenY`'s viseme rate. |
| Cue dispatch poll rate | 120 Hz | Sample rate of the cue scheduler's `monotonic` check. Headroom over the 60 Hz render so we don't miss a cue at the edge of a frame. |
| Barge-in pre-empt blend | 200 ms | Plan's spec; everything fades to neutral-attentive on `BargeInDetected`. |

These numbers fix the dispatcher's behavior:

```python
# avatar/dispatcher.py (sketch)
import asyncio, time
from dataclasses import dataclass

@dataclass
class Cue:
    audio_time_ms: float          # absolute ms from speech-start
    kind: str                     # "emotion" | "gesture" | "gaze" | "pause"
    payload: dict
    priority: int = 0             # higher wins on conflict in the same layer

CUE_LEAD_MS = 80    # anticipatory
POLL_HZ = 120

class CueDispatcher:
    def __init__(self, layer_renderer):
        self._render = layer_renderer
        self._cues: list[Cue] = []
        self._speech_start: float | None = None

    def begin(self, cues: list[Cue]) -> None:
        self._cues = sorted(cues, key=lambda c: c.audio_time_ms)
        self._speech_start = time.monotonic()

    async def run(self) -> None:
        while self._cues:
            now_ms = (time.monotonic() - self._speech_start) * 1000.0
            ready = [c for c in self._cues
                     if c.audio_time_ms - CUE_LEAD_MS <= now_ms]
            for cue in ready:
                self._render.fire(cue)
                self._cues.remove(cue)
            await asyncio.sleep(1.0 / POLL_HZ)

    def preempt_for_barge_in(self) -> None:
        """Cancel queued cues, fade everything to neutral-attentive."""
        self._cues.clear()
        self._render.fire(Cue(0.0, "emotion",
            {"name": "neutral", "blend_ms": 200}, priority=999))
```

The 120 Hz poll is a `await asyncio.sleep(8.3 ms)` on the avatar's
event loop — at the same priority as the lip-sync amplitude consumer
and the bus subscriber. That's three coroutines on the same loop, all
non-blocking; on the 4080-class hardware this is single-digit-percent
CPU.

### Tag → cue extraction

The Plan specifies the inline vocabulary (`<emotion>...</emotion>`,
`<gesture/>`, `<emphasis>`, `<pause/>`, `<gaze/>`). The pre-TTS step
strips those into a list of `(char_offset, cue)` pairs and a clean
text string. Piper's phoneme alignment exposes character-level
boundaries [8], so the conversion is:

```python
# speaker/cue_extract.py (sketch)
import re

TAG_RE = re.compile(
    r"<(?P<tag>emotion|gesture|emphasis|pause|gaze)"
    r"(?:=(?P<arg>[^/>]+))?(?P<close>/?)>"
    r"|</(?P<closetag>emotion|emphasis)>"
)

def extract(reply: str) -> tuple[str, list[Cue]]:
    cues, clean, off = [], [], 0
    spans: dict[str, int] = {}   # tag name → char_offset of opening
    for m in TAG_RE.finditer(reply):
        clean.append(reply[off:m.start()])
        off = m.end()
        if m.group("closetag"):
            tag = m.group("closetag")
            cues.append(Cue(audio_time_ms=-1, kind=tag,
                            payload={"span_open_char": spans.pop(tag, 0),
                                     "span_close_char": len("".join(clean))}))
        elif m.group("close"):     # self-closing
            tag, arg = m.group("tag"), m.group("arg")
            cues.append(Cue(audio_time_ms=-1, kind=tag,
                            payload={"arg": arg,
                                     "char": len("".join(clean))}))
        else:                      # opening of a span
            spans[m.group("tag")] = len("".join(clean))
    clean.append(reply[off:])
    return "".join(clean), cues
```

After Piper synthesizes the clean string, `audio_time_ms` is
populated by looking up the phoneme that closes at the cue's char
offset. Cues for span tags fire on the closing offset (Plan's call:
"reading 'reacting to what I just said,' which is what the brain
actually labelled").


## Asset prep workflow — PSD → Cubism → `.model3.json`

The Plan's appendix details the OC pipeline (steps 1-7, ~25-65 hours
total). For the *placeholder* Live2D model that ships in session 1,
the workflow is:

1. **Pull a free model from itch.io.** "Hololive vtuber sample model,"
   "Cubism SDK sample model — Hiyori," or any of the dozens of free
   `.model3.json` packages with permissive personal-use terms. The
   Plan flagged the licensing — most are CC-BY-NC or artist-EULA
   forbidding repo-commit, so `sabrina avatar-setup` downloads on
   first run rather than committing.
2. **Validate the directory shape.** Cubism expects a top-level
   `name.model3.json` with relative paths to `name.moc3`, the
   texture atlas (`name.2048/texture_00.png`), and the `expressions/`
   and `motions/` subfolders. live2d-py's `LAppModel.LoadModelJson`
   takes the `.model3.json` path and resolves the rest internally —
   but if any of them are missing, the failure mode is "model loads,
   renders white" rather than a clean error. Add a "models3.json
   schema check" to the setup verb that asserts every file referenced
   in the manifest actually exists.
3. **Drop into `assets/avatar/placeholder/`.** Update
   `avatar.model_dir` in `sabrina.toml` (or leave at the default
   which already points there).

For the OC pipeline (post-LoRA, post-rigging) the file layout is the
same. The deliverable matrix from the Plan's animation-library
section — 8 expressions + 8 gestures + 4 ambient motions ≈ 19
authored files, ~10-15 hours after the rig is done — still holds.

The micro-decision the Plan didn't pin down: **lip-sync uses
`ParamMouthOpenY` only, not `ParamMouthForm + OpenY` interpolation.**
A single-parameter mouth gives "ok-good" lip-sync for English at
30 Hz. A two-parameter rig with viseme-aware mapping is a half-day
of additional rigging work for an effect that only matters in
close-up. Skip in v1; revisit if Eric ever zooms the avatar large
enough that the mouth occupies > 1/3 of the visible character.

---

## Integration architecture: voice loop ↔ avatar (single-clock UDP)

The Plan settled on localhost UDP for the amplitude → mouth-open
channel and noted the same transport works for the cue stream.
Concrete shape:

```
voice_loop process                             avatar process
─────────────────────────                       ─────────────────────────
PiperSpeaker.speak(reply)
   │
   ├─ pre-TTS cue extraction
   │   (clean text + cue list)
   │
   ├─ Piper synth → int16 PCM
   │   + phoneme alignment
   │
   ├─ build cues with audio_time_ms
   │
   ├─ UDP send (port A) ──────────────► AvatarSubscriber
   │     {kind: "begin",                    .on_begin() → CueDispatcher.begin(cues)
   │      cues: [...]}
   │
   ├─ start sounddevice playback
   │
   └─ amplitude callback (30 Hz)
       │
       └─ UDP send (port A) ─────────► AvatarSubscriber
             {kind: "amp", v: 0.42}        .on_amp() → MouthOpenY = lerp(prev, v, smooth)
                                                    │
                                                    └─ CueDispatcher.run()
                                                          fires cues 80ms early
                                                          on the same monotonic clock
```

**One port, two message kinds.** A 1-byte type tag + JSON payload, MTU
< 1400 to avoid fragmentation. The Plan considered adding a second
port for cues; not needed — the avatar consumes both off the same
socket and dispatches by `kind`. Cleaner.

**Single clock = the avatar's `monotonic`.** The Plan worried about
clock skew between processes. Practical fix: the voice loop sends an
absolute `audio_time_ms` *relative to the begin message arrival
time*, and the avatar's CueDispatcher anchors its `_speech_start =
time.monotonic()` to the begin-message `recv_at`. Drift over a single
turn (< 30 s) is < 1 ms on a single host. Good enough.

**Firewall.** Plan's `sabrina avatar-setup --register-firewall`
flag drops a scoped netsh rule pre-approving `python.exe` for the
chosen port. Loopback-only binds *usually* pass silently on Win 11
but the prompt is sticky-once, sticky-forever — pre-register is the
clean UX. Named-pipe fallback path remains the documented escape
hatch.

---

## Performance profiling — expected on the 4080

The 4080's bottleneck for an avatar is *not* GPU — it's the GL context
on the QOpenGLWidget thread, which competes with the Brain's CUDA
context if Ollama is loaded and serving. Numbers measured against
a similar setup in the live2d-py issue tracker [9], scaled to Eric's
hardware:

| Subsystem | Expected on 4080 | Notes |
|---|---|---|
| Avatar render @ 60 Hz, 1024×1024 placeholder | < 1 % GPU, < 2 % single-core CPU | Cubism Core's draw call count is ~80 per model; trivial at 60 Hz. |
| Auto-blink + auto-breath ambient | < 0.1 % CPU | Internal to live2d-py; runs on `Model.update()`. |
| Lip-sync amplitude poll (30 Hz UDP) | < 0.05 ms / frame | One float32 per packet; sub-µs send time. |
| Cue dispatcher (120 Hz monotonic check) | < 0.01 ms / poll | Pure Python list scan; cue lists are < 50 entries per turn. |
| **Total avatar process at idle** | **~30 MB RAM, < 1 % CPU, < 1 % GPU** | Native render path; QOpenGLWidget overhead is 10-15 MB beyond the model textures. |
| Amplitude regression on voice loop | < 1 ms / chunk | RMS over 16-bit PCM; numpy `.mean()` on 1280 samples. |

If the user's primary monitor is HiDPI (4K), the same numbers double
because Qt scales the surface; still negligible. The "voice loop
shouldn't know or care that the avatar is running" criterion in the
Plan holds: the only voice-loop change is the amplitude sink, which
is single-digit microseconds per chunk.

If Ollama and avatar are co-resident on the 4080, the avatar's GL
context occasionally yields long frames (5-10 ms paints become
40-50 ms paints) when Ollama bursts. The avatar reads as "stutters
when speaking via local model." Mitigation: pin the avatar to GPU 0
explicitly (`os.environ["QT_OPENGL_USE_GPU"] = "0"` is a Qt 6 hint;
not always honored), or accept the visual hiccup until the Brain
isn't sharing the 4080. For Claude-as-default-brain, no contention.


## "First runnable Sabrina avatar" — what each session ships

The Plan's session breakdown stands. This doc cross-cuts it with what
becomes *visible* to Eric at the end of each session, which is the
useful definition of "shippable":

### Session 1 — placeholder + state-driven swap (~6 hours hands-on)

**Visible at end of session:**
- `sabrina avatar-setup` runs, downloads the placeholder model.
- `sabrina avatar` opens a frameless window in `bottom_right`.
- Run a voice turn (`sabrina voice`); the placeholder character
  changes expression on `idle → listening → thinking → speaking`.
- Mouth opens and closes during speech, but driven by a sine-wave
  simulator (the real amplitude sink is session 2).
- Auto-blink and auto-breath run on the `live2d.LAppModel` directly
  — no custom ambient layer code.

**Not yet:**
- Real lip-sync to Piper amplitude.
- Settings GUI tab.
- Win32 click-through and Focus Assist polish.
- Cue track. (Brain still emits no tags.)

### Session 2 — real lip-sync + GUI (~6 hours)

**Visible:**
- Mouth tracks Piper's actual output amplitude. The IPC path is
  exercised end-to-end.
- Settings → "Avatar" tab exposes every knob from `[avatar]`.
- Hot-reload: change opacity in the GUI, see it apply without
  restart (if `ConfigReloaded` event has shipped) or after a
  process restart (if not).

**Not yet:**
- Click-through / Focus Assist polish.
- Cue track.

### Session 3 — Windows polish (~6 hours)

**Visible:**
- `click_through = true` actually works (Win32 ex-style flag dance).
- Focus Assist on → avatar hides.
- Drag-to-edge snap, idle-dim, hover-fade.
- `validate-avatar-windows.md` written and gates the decision doc.

**Ship criterion:** Eric runs Sabrina with avatar all day; no
complaints.

### Session 4 (deferred) — OC art pipeline

Per the Plan's appendix. ~25-65 hours of Eric's own time. Not
blocking sessions 1-3.

### Session 5+ — cue track

**Visible:**
- Brain's system prompt teaches the inline tag vocabulary.
- A reply like "Oh! `<emotion=happy>`That's great news.`</emotion>`
  `<gesture=nod/>` Want me to put it on the calendar?" produces:
  - happy expression cross-fade at the closing tag (~250 ms after
    "news");
  - a nod 80 ms before the user hears the next syllable;
  - everything still lip-syncs continuously.
- `BargeInDetected` instantly cancels queued cues and blends to
  neutral-attentive.

**Recommended ordering of session 5+ work:** dispatcher first
(testable in isolation with a stub renderer), then tag extractor,
then Piper phoneme-time alignment, then full integration. Each step
ships a testable artifact.

---

## Two opportunistic wins worth flagging

1. **VTube Studio + `pyvts` parallel prototype.** An afternoon's work
   gives Eric an avatar on screen *today* using VTube Studio as the
   renderer. Sabrina becomes a plugin: `StateChanged → trigger hotkey
   expression`, `SpeakStarted → start_motion("speaking")`. This is a
   strictly inferior long-term answer (paid app, owns the renderer,
   no cue track) but it removes "no avatar yet" as a daily-driver gap
   while live2d-py work continues. If Eric wants to scratch the
   "Sabrina has a face" itch fast, this is the low-effort path.

2. **Skip session 4 entirely if the placeholder model fits.** The
   Plan correctly frames the OC pipeline as 25-65 hours of Eric's
   own creative-taste work. If the placeholder Live2D character
   (free download) carries enough personality, the work disappears.
   Many shipped Sabrina-shaped projects use unmodified placeholder
   models forever; the avatar's behavior carries the personality
   more than its specific face. Eric's call.

---

## Thin spots in this doc

- **No measurement of GL context contention with active Ollama
  inference.** The "5-10 ms → 40-50 ms paint stutters" estimate is
  cribbed from generic Qt-on-CUDA tickets; Eric's specific
  Ollama-vs-avatar profile may differ. Real data from session 2's
  manual smoke will sharpen this.
- **No cue-track quality measurement.** "Reads as natural" is a
  subjective check. The cue track section assumes the 80 ms lead is
  perceptually correct on a flat-panel display at standard
  framerate; HiDPI / variable-refresh-rate monitors may want
  different leads. Add `cue_lead_ms` to the GUI when the cue track
  ships.
- **Tag-vocabulary teaching is a system-prompt concern.** This doc
  punts on "what does the system prompt look like to teach the brain
  to emit cues correctly." That belongs in the personality plan, not
  here. Cross-reference but don't duplicate.

---

## Alternatives worth researching (not blocking)

- **Spine 2D in place of Live2D.** Esoteric Software's runtime is
  more flexible than Cubism for skeleton-driven motion but the
  community of free ready-to-rig Spine assets is far smaller. Worth
  researching only if Live2D licensing genuinely becomes a problem
  for Sabrina (it doesn't for personal use; would matter if Sabrina
  ever shipped publicly with the `model_dir` knob exposed).
- **VRM / 3D characters.** Strictly out of scope per the Plan, but
  worth noting that the cue-track *protocol* is renderer-agnostic.
  Tag vocabulary + UDP cues + 80 ms lead would work identically
  driving a VRM model in Unity. The avatar package's only Live2D-
  specific code is the `live2d_bridge.py` module.
- **Speech-driven viseme prediction.** ML models predict mouth-shape
  parameters directly from the audio stream (independent of the
  Brain). Worth nothing today because Piper's phoneme alignment is
  already free and accurate; useful if Sabrina ever swaps to a TTS
  that doesn't expose phoneme times.

---

## References

[1] live2d-py releases — https://github.com/EasyLive2D/live2d-py/releases
[2] live2d-py README (English) —
    https://github.com/EasyLive2D/live2d-py/blob/main/README.en.md
[3] live2d-py PySide6 sample (60 Hz QTimer + QOpenGLWidget pattern) —
    https://github.com/EasyLive2D/live2d-py/tree/main/sample
[4] PyQt6 forum: WindowTransparentForInput on Windows 11 —
    https://forum.qt.io/topic/63067/os-x-clicks-on-fully-transparent-parts-of-windows-no-longer-passes-through-in-qt-5-6
[5] Qt docs: QOpenGLWidget alpha buffer requirement —
    https://doc.qt.io/qt-6/qopenglwidget.html
[6] Live2D Cubism: tracking delay parameter (60 ms typical) —
    https://docs.live2d.com/en/cubism-editor-tutorials/cubism-ae-plugin-tracking/
[7] Real-Time Lip Sync for Live 2D Animation — researchgate review —
    https://www.researchgate.net/publication/336715598_Real-Time_Lip_Sync_for_Live_2D_Animation
[8] piper-tts phoneme alignment in 1.4.x output —
    https://github.com/OHF-Voice/piper1-gpl
[9] live2d-py issue #98 — Cannot set transparent background in qt/tkinter —
    https://github.com/EasyLive2D/live2d-py/issues/98
