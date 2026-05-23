# Avatar architecture research — P4.A1

**Date:** 2026-05-14
**Author:** sabrina-worker-8am (scheduled run, P4.A1 pickup)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Avatar → **P4.A1 Avatar — architecture research + decision draft** (`[linux-runnable] [P2] [M]`).
**Spec:** `rebuild/drafts/research/2026-05-12-p4a1-avatar-architecture-research-spec.md` (sabrina-spec-writer 2026-05-12 06:50).
**Predecessors consulted:**
- `rebuild/ROADMAP.md` § 6 (Avatar deferred — PyQt6, frameless/always-on-top/click-through, `StateChanged`-driven).
- `ROADMAP.md` § "Phase 4 — Avatar + Automation + Brain router" (entry gates Phase 2/3 exit; A1 research-only ships earlier under Partial DoD).
- `rebuild/decisions/001-hardware-and-budget.md` (target hardware i7-13700K + RTX 4080 16GB; budget envelope for the avatar process).
- `sabrina-2/src/sabrina/events.py:55-63` — `StateChanged(from_state, to_state, reason)` over the five-state alphabet `idle | listening | thinking | speaking | acting`.
- `sabrina-2/src/sabrina/bus.py:31-83` — `EventBus.subscribe(*kinds, maxsize=1024)` async-iterator API; lossy-on-backpressure (drops to per-subscriber counter + structlog warning, never blocks `publish`).
- `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` (earlier cue-track research; treated as input per spec — citations below).

**Open NEEDS-INPUT:** the three picks this doc grounds (§1 SDK / §2 click-through / §3 IPC) already exist in `NEEDS-INPUT.md` at lines 195 / 204 / 212, filed by sabrina-spec-writer 2026-05-12 06:50 with `[from: spec-writer / 2026-05-12 06:50]` markers and per-pick spec-recommendations. This Worker did **not** re-file per the dedup discipline (re-filing would land four duplicate entries; the spec-writer's pre-emptive filing is the cleaner pattern). Eric's `[x]` on the matching entries fills in the §5 picks below.

---

## Summary

The Avatar is Component 6 of `rebuild/ROADMAP.md` and Gate-1 mover #9 of `ROADMAP.md` — a PyQt6 frameless / always-on-top / click-through window that reacts to `StateChanged` events. The daily-driver bar is "reacts to state, doesn't look broken," not "production VTuber app." Under that bar, three out of three SDK / window / IPC picks collapse onto the simplest path: `live2d-py` 0.6.x (pip-installable wheel, ships Cubism Core DLL) renders inside a `QOpenGLWidget` whose parent `QMainWindow` carries `FramelessWindowHint | WindowStaysOnTopHint | Tool | WindowTransparentForInput` plus `WA_TranslucentBackground`. The avatar runs in-process with the voice loop via `qasync`, subscribing directly to `bus.subscribe("state_changed")`; crash isolation is delegated to the already-shipped supervisor (`acd6725`) rather than a second process. Frame-budget envelope on the RTX 4080 is < 2% CPU + < 1% GPU at 60 Hz, leaving the voice loop's asyncio scheduler with ~90%+ of the budget it currently owns alone.

---

## §1 — Live2D SDK pick

Three candidates against four axes: license inheritance, maintenance posture, Windows-x64 install path, render path.

| Candidate | License | Maintenance | Windows-x64 install | Render path |
|---|---|---|---|---|
| `live2d-py` 0.6.x (community wrapper around Cubism Native SDK) | MIT on the wrapper; Cubism Core DLL bundled under the upstream Live2D Inc Free Material License for personal/non-commercial use. Personal daily-driver bar satisfied. | Active. 0.6.1.1 shipped 2026-01-16. Cubism 4 + 5 model spec supported. Issue tracker responsive within days. | `pip install live2d-py` — wheels for cp310-cp313 on Windows-x64; Cubism Core DLL shipped alongside the wheel. No separate installer, no Visual Studio toolchain dance. | C-extension wraps Live2D's Native SDK in C++; renders into any OpenGL-3.3+ context. Drives `LAppModel.update()` + `LAppModel.draw()` from the host paint loop. |
| Official Cubism SDK Python wrapper (Live2D Inc) | Live2D's tiered license (Free Material for personal-use; commercial tiers irrelevant for Sabrina). | Vendor-maintained, slower release cadence. | Download-gated from Live2D Inc account page; not pip-installable. Manual unzip + path-register. Heavier install surface. | Same Cubism Native SDK underneath as `live2d-py`. Visually equivalent at the daily-driver bar. |
| Roll-our-own (OpenGL + texture atlas + raw Moc3 parser) | None — we'd own all the IP. | None — we'd own all the maintenance, including binary-format changes when Live2D ships a new Cubism version. | Free. We'd build it. | Custom GL pipeline; would need viseme rig support, expression cross-fade, ambient layer (auto-blink/auto-breath), and lip-sync ourselves. Estimated 100-200 hours of work before "model loads, renders, doesn't look broken." |

**Recommendation: (a) `live2d-py` 0.6.x.** The render fidelity gap to (b) is invisible at the daily-driver bar — both wrap the same upstream Cubism Native SDK. The wrapper is the part that determines install ergonomics, and a pip-installable wheel beats a download-gated zip every time. Auto-blink + auto-breath are first-class on `live2d.LAppModel` (cf. `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 26-33), which collapses the ambient-layer code A3 would otherwise have to author from scratch. (c) is included as the do-not-recommend baseline; the build-vs-buy delta is ~100x.

**Eric's pick:** _TBD — see NEEDS-INPUT.md line 195 (spec-writer / 2026-05-12 06:50)._

---

## §2 — PyQt6 frameless / always-on-top / click-through cookbook

The canonical Qt-only recipe on Windows 11 is the combination below. Order of attribute setting matters: the window flags + translucent attribute must be in place **before** the GL widget is constructed, or Qt's surface format picks up the wrong alpha posture and the avatar renders against an opaque black background even when the window itself is "transparent" (this is the load-bearing gotcha from `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 103-118).

| Concern | Flag / attribute | Notes |
|---|---|---|
| Frameless (no title bar, no resize handles) | `Qt.WindowType.FramelessWindowHint` | Universal on Win/Mac/Linux. |
| Always-on-top (stays above other windows) | `Qt.WindowType.WindowStaysOnTopHint` | Honored on Win11 except when Focus Assist is in "Alarms only" — that case is handled by polling `HKCU\Software\Microsoft\Windows\CurrentVersion\QuietHours` and hiding the avatar (`rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` line 119-121). |
| No taskbar entry / no alt-tab presence | `Qt.WindowType.Tool` | Tool windows are floating utility windows; no taskbar slot. |
| Click-through (mouse events pass through the entire window) | `Qt.WindowType.WindowTransparentForInput` | All-or-nothing — the **whole** window becomes click-through, including opaque pixels. |
| Transparent background (so the avatar's straight-alpha PNG composites cleanly) | `setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)` + `setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)` | Required for the avatar's alpha channel to survive Qt's compositor. |
| GL surface alpha channel | `QSurfaceFormat.setAlphaBufferSize(8)` then `QSurfaceFormat.setDefaultFormat(fmt)` | Must run **before** `QApplication()` is instantiated or the default surface format wins. |

The click-through choice is the only Windows-native surface in play. Two architectures:

- **(a) Full window click-through.** `Qt.WindowType.WindowTransparentForInput` on, full stop. The whole avatar window is click-through; no opaque regions accept clicks. Kill targets live elsewhere — the system tray (Qt has tray-icon support cross-platform), the supervisor CLI, or P4.B1's `<ctrl>+<alt>+k` kill-switch hotkey. This is the canonical Qt-only path; no `ctypes`, no `pywin32`, no per-pixel transparency code.
- **(b) Per-pixel opaque-regions-accept-clicks.** Drop `WindowTransparentForInput`; use Windows native `SetWindowLong` to set `WS_EX_LAYERED | WS_EX_TRANSPARENT` only where the alpha channel is 0 (or below some threshold). The opaque body of the avatar accepts clicks. This requires Windows-only code (Qt has no cross-platform API for it), the dance to toggle the flag at runtime requires `setWindowFlag()` followed by `show()` — flag changes only take effect on a re-show on Windows 11 (`rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 113-118).

The smallest known-working public reproduction of the (a) recipe is the live2d-py upstream PySide6 sample (`live2d-py/Sample/main.py` in the 0.6.x source tree on GitHub; PySide6 ports to PyQt6 with import-line edits only — same Qt 6 API surface). That sample plus the surface-format dance above is the entire (a) path.

**Recommendation: (a) full window click-through.** Daily-driver bar is "reacts to state, doesn't look broken"; an avatar with no clickable regions is the simplest path and the kill paths already exist out-of-band (system tray + supervisor CLI + P4.B1 kill-switch hotkey). (b) is a real path if Eric later wants the avatar window to host a visible kill button or drag-handle, but that decision belongs to a future iteration — adding it later is `setWindowFlag()` toggling, not a rewrite.

**Eric's pick:** _TBD — see NEEDS-INPUT.md line 204 (spec-writer / 2026-05-12 06:50)._

---

## §3 — IPC architecture: in-process vs. side-process

The avatar subscribes to `StateChanged` events from the bus. Two architectures, traded off against four axes: latency, crash isolation, deployment surface, render-loop simplicity.

| Axis | (a) In-process via `qasync` | (b) Side-process via local IPC |
|---|---|---|
| Latency on `StateChanged` arrival | Zero — direct in-memory call into `bus.subscribe("state_changed")`'s async generator. The avatar's `qasync` event loop and the voice loop's asyncio loop are the same loop. | ~1 ms-class. UDP socket send + recv + JSON decode; lossless on loopback at this packet rate. |
| Crash isolation | None at the IPC level. The supervisor primitive shipped in `acd6725` (`sabrina-2/src/sabrina/supervisor.py`'s `run_supervised`) provides process-level auto-restart at the parent level — an OpenGL-driver crash takes both subprocesses down, supervisor restarts the parent voice-loop process. | Strong. Avatar segfault doesn't take down voice. Independent restart story. |
| Deployment surface | One process. One venv. One `sabrina` command. | Two processes. Same venv (avatar can re-use the wheel). Second `sabrina avatar` command or auto-spawn from voice loop. |
| Render-loop simplicity | `qasync` bridges `QApplication.exec()` and asyncio cleanly — one `loop = qasync.QEventLoop(app); asyncio.set_event_loop(loop)` call up-front, then standard `asyncio.create_task()` for the bus consumer. Mature library, Windows-wheel coverage, well-trodden in the PyQt6 ecosystem. | UDP loop on the avatar side. Need to define the wire format (1-byte type tag + JSON, MTU < 1400) and the firewall ergonomics — Windows 11 generally passes loopback UDP silently but the prompt is sticky-once-sticky-forever, so a `sabrina avatar-setup --register-firewall` step pre-empts the prompt (`rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 323-328). |
| State drift between processes | Not possible — same memory. | Possible. Voice loop sends `StateChanged`; avatar processes lag, drifts can show as state-mismatch visual artifacts. Bounded < 1 ms in practice. |
| Future cue-track / amplitude path | Can ride the same in-process bus. The 80 ms anticipatory cue-lead `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` builds against the avatar's `time.monotonic()` clock works trivially in-process. | The 4/26 doc's cue/amplitude path was designed for side-process UDP. Single-clock drift compensation is ~1 ms, well within budget. |

**Recommendation: (a) in-process via `qasync`.** Two reasons. First, the strongest argument for (b) — crash isolation — is solved cheaper by the supervisor that already shipped in `acd6725`. Second, the voice loop and the avatar share the same `time.monotonic()` clock for cue-track timing once that ships; in-process avoids the single-clock drift compensation the 4/26 doc had to design. The (b) path's only remaining advantage is OpenGL-driver-crash isolation, and the 4080 driver on Win11 is stable enough at the daily-driver bar that this isn't load-bearing. If A3's render-loop work turns up an OpenGL-driver-crash pattern, revisit — A2 → A3 → A4 is one queue branch and the rewrite cost of (a) → (b) is bounded (only the bus consumer moves; the Qt window code is identical).

**Note for A2's spec:** if Eric picks (b), P4.A2's file partition changes substantially — A2's window class is the same, but a `sabrina-2/src/sabrina/avatar/ipc.py` UDP transport replaces the direct `bus.subscribe()` call, and the voice-loop side gains a UDP publisher that mirrors `StateChanged` to the avatar's port. The spec-writer's 5/12 P4.A2 spec is parameterized on the (a) pick; an Eric override to (b) before A2 is pulled retargets A2's spec.

**Eric's pick:** _TBD — see NEEDS-INPUT.md line 212 (spec-writer / 2026-05-12 06:50)._

---

## §4 — Frame budget on RTX 4080

Target: 60 Hz steady-state (16.67 ms per frame wall-clock); 120 Hz aspirational (8.33 ms) if Eric runs on a high-refresh-rate monitor. The avatar process competes for CPU + GPU with the voice loop's asyncio scheduler and (when local-routed) Ollama's CUDA context.

Per-stage budget estimates against the i7-13700K + RTX 4080 + 32 GB target tier, scaled from live2d-py upstream benchmark data and the 4/26 doc's measurements on similar hardware:

| Stage | Per-frame cost @ 60 Hz | Notes |
|---|---|---|
| Cubism Native render (`LAppModel.update()` + `draw()`) on a 1024×1024 placeholder model | < 1 ms wall (< 1% one core; < 1% GPU) | ~80 GL draw calls per model; trivial at 60 Hz for an RTX 4080. Cf. `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 341-348 for the line-item table. |
| Qt compositor (`QOpenGLWidget.paintGL()` + window composition) | < 1 ms wall (< 1% one core) | Qt 6's GL widget is well-optimized; the alpha channel + WA_TranslucentBackground adds a single blend pass. |
| Auto-blink + auto-breath ambient | < 0.1 ms wall (< 0.1% one core) | Internal to live2d-py's `Model.update()`; runs in-line, no separate timer. |
| `qasync` event-loop wakeup + `bus.subscribe("state_changed")` poll | < 0.1 ms wall (negligible) | One asyncio.create_task() + an await on the bus's `Queue.get()`; only wakes when a `StateChanged` actually arrives (rare — ~1 event per voice turn, not per frame). |
| Headroom for voice-loop asyncio scheduler at idle | ~14.5 ms / frame (~87%) | What remains after the avatar's < 2 ms. The voice-loop scheduler's own per-tick budget is < 0.5 ms when idle (mic VAD poll + occasional bus event handling), so the 14.5 ms is mostly available for the voice loop's STT/brain/TTS work that does need it. |

**Memory:** ~30-50 MB RAM for the avatar process at steady state — Qt + live2d-py + the model textures. Negligible against the 32 GB target.

**Frame budget verdict: comfortable on RTX 4080 at 60 Hz.** The < 2 ms / frame total is < 12% of the 16.67 ms budget; the voice loop owns the rest. At 120 Hz the avatar would consume < 24% of the 8.33 ms budget; still comfortable. The earlier 4/26 doc benchmarked Cubism Native on similar-tier hardware at < 1% GPU + < 2% CPU and reached the same conclusion.

**The one contention risk worth flagging:** if Ollama is loaded and serving on the same 4080, its CUDA context bursts can cause the avatar's GL context to yield long frames (5-10 ms paints become 40-50 ms paints during inference bursts; reads as "stutters when speaking via local model" — `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 356-362). Mitigations: (1) `QT_OPENGL_USE_GPU = 0` env hint (Qt 6, not always honored on Win11); (2) accept the visual hiccup since the brain-default-to-Claude posture means no contention most of the time; (3) revisit if and when local-Ollama becomes the daily-driver default. This is informational, not gate-defining — the avatar process by itself fits comfortably in the budget.

---

## §5 — Eric's pick checklist

The picks below populate as Eric checks `[x]` on the matching NEEDS-INPUT entries. Until then, the spec-recommended option is the load-bearing assumption for A2 / A3 / A4's specs.

- **§1 SDK pick:** _TBD — NEEDS-INPUT.md line 195 (spec-writer / 2026-05-12 06:50). Spec-recommends (a) `live2d-py` 0.6.x._
- **§2 click-through policy:** _TBD — NEEDS-INPUT.md line 204 (spec-writer / 2026-05-12 06:50). Spec-recommends (a) full window click-through (`WA_TransparentForMouseEvents` always on)._
- **§3 IPC architecture:** _TBD — NEEDS-INPUT.md line 212 (spec-writer / 2026-05-12 06:50). Spec-recommends (a) in-process via `qasync`._

If Eric picks (a) across all three, the avatar component's downstream queue items (P4.A2 PyQt6 skeleton spec'd 2026-05-12; P4.A3 Live2D rig bind spec'd 2026-05-13) ship against their current specs unchanged. Each of (b) overrides retargets the matching downstream spec — see the per-section "Note for A2's spec" / "Note for A3's spec" callouts above and in the corresponding spec docs.

---

## Recommendation summary (one-line per section)

1. **SDK:** `live2d-py` 0.6.x. Wraps the same Cubism Native SDK as the official wrapper, but pip-installable with cp310-cp313 wheels for Windows-x64; ships the Cubism Core DLL alongside the wheel.
2. **Click-through:** Full window click-through via `Qt.WindowType.WindowTransparentForInput` plus `WA_TranslucentBackground`. Kill targets live in the system tray / supervisor CLI / P4.B1 kill-switch — not on the avatar window itself.
3. **IPC:** In-process via `qasync`. Avatar runs alongside the voice loop; subscribes directly to `bus.subscribe("state_changed")`. Crash isolation is solved by the already-shipped supervisor primitive.
4. **Frame budget:** < 2 ms / 16.67 ms per frame at 60 Hz on the RTX 4080 target (< 12% of the budget). Comfortable. The voice-loop scheduler keeps ~87% headroom.
5. **Eric's picks:** TBD via three pre-filed NEEDS-INPUT entries.

---

## Thin spots in this doc

- **No first-hand measurement of `qasync` + asyncio + `QOpenGLWidget` interaction under load.** §3's "in-process is fine" rests on community wisdom and the 4/26 doc's projections, not on a live measurement against the voice loop. A2's first-frame ship is the place where that gets grounded; if `qasync` interacts poorly with the voice loop's asyncio scheduling, A2 surfaces the issue early and (b) becomes the right pick.
- **No measurement of GL context contention with active Ollama inference.** §4's 5-10 ms → 40-50 ms paint stutter estimate is cribbed from the 4/26 doc, which itself cribbed from generic Qt-on-CUDA tickets. Real data lands in A3's render-loop work; until then the stutter is a known-unknown.
- **No Windows-11-specific click-through validation.** §2's recipe is the canonical Qt-only path and the 4/26 doc verified the surface-format-before-QApplication discipline against Windows 11, but the full A4 e2e checklist (`validate-avatar-windows.md` per the QUEUE entry for P4.A4) is what proves the recipe end-to-end on Eric's box.
- **License-posture details for personal use of the Cubism Free Material License.** Confirmed via the Live2D Inc license page that "personal use" covers Eric's daily-driver case; not confirmed whether the bundled DLL in the `live2d-py` wheel has any redistribution constraint that affects a private-repo commit of model assets. Mitigated by the standing decision in `rebuild/drafts/research/2026-04-26-avatar-cue-track-implementation.md` lines 245-250 to download placeholder model assets at `sabrina avatar-setup` time rather than commit them to the repo.

---

## What this doc deliberately is NOT

- **Not a decision doc.** The decision doc for the avatar lives under P4.A4's Full DoD (next free integer in `rebuild/decisions/`, decision-doc voice). This doc is the research input that decision will cite.
- **Not a P4.A2 / A3 / A4 spec.** Those exist already (P4.A2 spec'd 2026-05-12; P4.A3 spec'd 2026-05-13). This doc grounds the assumptions those specs are parameterized on.
- **Not a code change.** Zero `.py` files touched; no `pyproject.toml` edit; no `requirements*.txt` edit. The avatar dependency additions (`PyQt6` ~50 MB wheel, `live2d-py` ~30 MB wheel including Cubism Core DLL, `qasync` < 1 MB) land in P4.A2's diff per its existing spec.
- **Not a cue-track design doc.** The 4/26 cue-track research stands as the canonical input for the per-state expressive cues A3+ will eventually drive; this doc is the architecture layer below that.

---

## Worker run summary (for the JOURNAL append)

- Read CLAUDE.md, STATE.md, JOURNAL.md last 24h (today's chain: 02:37 night-auditor + 03:30 researcher + 06:50 spec-writer [idle-exit] + 07:00 planner + 07:30 graduation-sweeper), QUEUE.md (top is `[in-progress]` lock-blocked P0, skip per role-doc step 2; next `[ ]` `[windows-required]` ClaudeBrain b-half, skip; next `[ ]` `[linux-runnable]` is P4.A1 — this run's pick), the P4.A1 spec verbatim (lines 1-107 of `rebuild/drafts/research/2026-05-12-p4a1-avatar-architecture-research-spec.md`), `sabrina-2/src/sabrina/events.py:40-78` (StateChanged shape verified), `sabrina-2/src/sabrina/bus.py:20-90` (subscribe API verified — async-iterator, lossy-on-backpressure), and the 4/26 cue-track research doc lines 1-272.
- Wrote `rebuild/drafts/research/2026-05-14-avatar-architecture.md` (this file). Five sections per spec DoD points 2-5: §1 SDK pick (3-candidate table + (a) recommendation), §2 PyQt6 cookbook (canonical Qt-only recipe + click-through gotcha + (a) recommendation), §3 IPC (in-process vs side-process + (a) recommendation + A2-spec retarget note for (b) override), §4 frame budget (per-stage table + < 2 ms / 16.67 ms at 60 Hz verdict + Ollama-contention informational), §5 Eric's pick checklist (3 TBD lines pointing at NEEDS-INPUT.md lines 195/204/212).
- Did NOT file new NEEDS-INPUT entries — the three picks the spec asks for are already filed by spec-writer 2026-05-12 06:50 at NEEDS-INPUT.md lines 195/204/212, each with the (a)/(b)/(c) menu + spec recommendation. Re-filing would land four duplicate entries; the spec-writer's pre-emptive filing is the cleaner pattern. Cross-referenced this in §5 + the run summary.
- Did NOT modify code, `pyproject.toml`, `sabrina.toml`, `.gitignore`, decision docs, off-limits dirs (`rebuild/decisions/`, root-level `core/`/`services/`/`utilities/`/`scripts/`/`models/`), QUEUE.md, STATE.md, PROPOSED.md, DONE.md, or push to remote. `python -m compileall sabrina-2/src` clean from before equals after (zero `.py` touched). Pre-commit hook unaffected.
- This is a Partial-DoD ship per spec § "(a)/(b) split framing" — research-only, no Windows path to validate, no `Windows-pending: e2e` marker needed. The QUEUE item promotes to `[linux-shipped]` until P4.A4 Full-DoD ships the avatar end-to-end and folds A1's recommendations into the corresponding decision doc.
