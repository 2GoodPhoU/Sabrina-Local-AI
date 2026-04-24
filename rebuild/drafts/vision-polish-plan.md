# Vision polish plan — no-VLM improvements to the existing pipeline

**Date:** 2026-04-23
**Status:** Research + draft. Implementation blocked on one open
question at the top. Research below is settled.
**Closes:** decision 005 thin-spots (single-monitor whole-screen only,
no window/region, no image-in-memory, OCR-pre-pass deferred).
**Scope note:** NO changes to which brain the vision turn goes through.
That's `local-vlm-plan.md`'s concern. This plan is strictly about
capture quality and what gets sent.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Which capture mode is worth shipping first — active-window
   capture, cursor-monitor auto-select, or both?** Active-window
   capture is strictly more useful ("what's this error in my
   terminal" with the IDE also open) and lands in ~60 lines. Cursor-
   monitor auto-select is simpler (~30 lines) and covers the
   multi-monitor case where the user is looking at the "other"
   display. Both? One? The plan below implements both by default
   with a `vision.capture_mode` config knob; confirm or narrow.

   **Recommendation: ship both behind `capture_mode`, default stays
   `"monitor"`.** Total incremental cost is ~90 lines across both
   modes plus one new dep (`pygetwindow`, already pulled in by
   `automation-plan.md`'s `list_open_windows` tool), which keeps the
   plan under the 300-line guardrail for `vision/capture.py`. Shipping
   both together amortizes the config-block + dispatch plumbing into
   one session. Keeping `"monitor"` as the default is the
   no-regression move — decision 005 shipped with whole-monitor and
   nothing about that is broken; the new modes are opt-in per Eric's
   workflow ("window" for the "what's this error" case, "cursor" for
   the multi-monitor case). Override: if Eric wants to trim, cut
   `"cursor"` — it's the lower-value / lower-effort half and the
   90%-case fix is `"window"`.

Everything below reflects this recommendation. OCR pre-pass is
explicitly *in* this plan as an opt-in knob
(`vision.ocr.enabled = false` default).

---

## Context — what vision is today (not what the user's message said)

The master plan's framing (and the user's prompt) mentioned a
"yolov8 pipeline," which is a holdover from the old pre-rebuild
project. The **sabrina-2 rebuild drops YOLO entirely.** Today:

- `vision/capture.py` grabs via `mss`, resizes via PIL, encodes PNG.
- `vision/see.py` attaches the PNG to a `Message.images=(...)` turn
  and streams a reply from Claude (Haiku by default).
- `vision/triggers.py` matches phrases like "look at my screen" to
  decide vision on/off.
- `vision/hotkey.py` arms the next turn via a pynput global hotkey
  (default `Ctrl+Shift+V`).

Nothing uses object detection; nothing uses OCR. The "polish" space is
at the edges of this pipeline, not a replacement of it.

## Research — polish options, ranked by value/effort

### 1. Active-window capture — HIGH value, LOW effort

Capture only the focused window, not the whole monitor. The use case
is everywhere: a full-screen capture with a code editor, an IDE, and
a browser all visible is noisier context than just the focused
window.

- **Implementation:** `pygetwindow>=0.0.9` to fetch the active
  window's bounds. `mss` already supports a rectangle capture via
  `sct.grab({"top", "left", "width", "height"})`.
- **Cost:** ~60 lines. One new dep (pygetwindow, MIT-licensed, pure
  Python). Zero runtime cost.
- **Edge:** Windows DWM may report a window's bounds with shadow-
  margin padding. Solution: clamp to mss's monitor bounds and
  inset-trim ~5 px on all sides for the common case.

### 2. Cursor-monitor auto-select — LOW value, LOW effort

On a multi-monitor setup, default to capturing whichever monitor the
cursor is on right now. Today the config pins `monitor = 1`, which is
wrong half the time for a two-monitor user.

- **Implementation:** `pynput.mouse.Controller().position` returns the
  cursor's screen coordinates; iterate `mss.monitors` to find which
  one contains that point.
- **Cost:** ~30 lines. No new dep (pynput already in use for PTT).

### 3. OCR pre-pass — MEDIUM value, MEDIUM effort

Local OCR extracts the text from the screenshot and attaches it as a
sidecar message ("Text visible on screen: ..."), in addition to the
image. This can reduce tokens sent to Claude (if the model uses the
sidecar instead of re-reading pixels) and helps local VLMs that are
weaker on text.

- **OCR engines surveyed:**
  - **Tesseract** (via `pytesseract`): mature, Windows binary, ~30 MB
    English data. Quality merely OK on UI fonts; good on clean
    documents. Setup friction: need the Tesseract binary installed
    separately (not a pure Python wheel).
  - **easyocr**: PyTorch-based, ~100 MB model download, slow on CPU
    but fine on 4080 (~200 ms). Good on UI text. One command install.
  - **RapidOCR** (`rapidocr-onnxruntime`): ONNX-runtime based (we
    already have onnxruntime). ~50 MB model. Fast, fully Pythonic,
    no external binary. **Best fit for Sabrina.**
- **Implementation:** ~80 lines. `vision/ocr.py` wrapping RapidOCR.
  Optional import guard; if the dep isn't installed, OCR is simply
  off.
- **Integration:** OCR runs once per vision turn *in parallel* with
  the screenshot encode. Results attached as a separate
  `tool_result`-ish string block (but without tool_use; just a
  pre-populated sidecar in the system prompt).

### 4. Region crop on focused UI element — deferred

Using UI Automation (via `pywinauto` or `uiautomation`) to locate the
focused widget within a window is possible but fragile across apps.
Skip; not worth the code.

### 5. Image-in-memory / short-retention store — SMALL VALUE, SMALL EFFORT

Decision 005 thin-spot: Sabrina doesn't remember what we looked at
yesterday. A simple fix: save every captured screenshot to
`data/screenshots/<ts>.png` and prune by age (> 7 days deletes).
Low effort; UX value is unclear because there's no way to refer to
past screenshots by content yet — that would need a VLM-derived
embedding, a much bigger lift.

- **Implementation:** ~40 lines. Save-and-prune in `vision/see.py`'s
  capture path.
- **Plan's call:** ship it as a gated knob (`vision.archive.enabled = false`
  default). Cheap; no downside.

### 6. Multi-window "mosaic" capture — skipped

Capturing multiple windows and stitching them into a single image
(or multi-image turn) is technically possible but complicates the
pipeline meaningfully for niche value. Out of scope.

### 7. Cursor / click-target annotation — deferred

Drawing a visible indicator on the screenshot at the cursor position
(so Sabrina knows where the user was pointing) is a nice UX — and is
real work to make look right. Revisit when someone asks for it.

## The plan's recommended default shape

Ship items 1, 2, 3, and 5 in one session. Config knobs; defaults lean
conservative:

- Active-window: **on** when capture_mode is `window`; default mode
  stays `monitor` for backward compat.
- Cursor-monitor: **on** when capture_mode is `cursor`.
- OCR: **off** by default; `vision.ocr.enabled=true` opts in.
- Archive: **off** by default.

## Scope

In:
- `vision/capture.py` extensions: add `grab_window(...)` +
  `grab_cursor_monitor(...)`; keep `grab(...)` unchanged. Dispatch
  in `capture()` based on `settings.vision.capture_mode`.
- `vision/ocr.py`: new, ~80 lines. `extract_text(image_bytes) -> str`
  wrapping RapidOCR. Optional dep via `importlib` guard.
- `vision/see.py`: if `ocr.enabled`, call `extract_text` in parallel
  with the capture (`asyncio.gather`); attach as a sidecar line on
  the vision system prompt:
  `"OCR of the visible screen:\n<text>\n(OCR may contain errors.)"`.
- `vision/archive.py`: ~40 lines. `save_and_prune(shot, settings)`.
  Called from the capture hot path when `archive.enabled`.
- Config: `vision.capture_mode`, `vision.ocr`, `vision.archive`.
- Deps: `pygetwindow`, `rapidocr-onnxruntime` (optional install extra).
- Tests: capture-mode dispatch, OCR happy path with a stub,
  archive prune logic.

Out:
- Image-in-memory *retrieval* (grep-by-timestamp is all we do; no
  semantic search over screenshots).
- Per-app capture profiles ("always capture the whole desktop when
  Photoshop is focused").
- UI Automation integration.
- Cursor annotation.

## Files to touch

```
sabrina-2/src/sabrina/
├── vision/
│   ├── capture.py                # +grab_window, grab_cursor_monitor,
│   │                             #  dispatch in grab(...)
│   ├── ocr.py                    # NEW, ~80 lines
│   ├── archive.py                # NEW, ~40 lines
│   └── see.py                    # +ocr sidecar, +archive call
├── cli.py / cli/vision.py        # +`sabrina ocr-test <image>` verb
└── config.py                     # +VisionCaptureConfig, +VisionOcrConfig,
                                   #  +VisionArchiveConfig
sabrina-2/
├── pyproject.toml                # +pygetwindow; +rapidocr-onnxruntime
│                                  #  under an optional extra [vision-ocr]
├── sabrina.toml                  # +new config blocks
└── tests/test_smoke.py           # +vision polish tests
```

## Protocol / API changes

None. `vision/see.see(...)` already returns `AsyncIterator[StreamEvent]`
unchanged.

The OCR sidecar is attached into the `system` parameter that the
`ClaudeBrain` (or local VLM) gets; it doesn't change the `Message`
shape.

## Config additions

```toml
[vision]
# ... existing fields ...

# How to pick pixels for a vision turn:
#   "monitor" = whole display at settings.vision.monitor (current default)
#   "window"  = bounds of the currently focused window
#   "cursor"  = whole monitor the cursor is on right now
capture_mode = "monitor"

[vision.ocr]
# Run local OCR alongside every vision capture. Attaches extracted text
# as a sidecar note on the system prompt. Off by default; opt in if
# you want local VLMs (or cost-sensitive cloud paths) to have the
# text explicitly.
enabled = false
# Cap OCR output length to avoid blowing system prompts out.
max_chars = 4000

[vision.archive]
# Persist every captured screenshot to `data/screenshots/<ts>.png`.
# Prunes files older than `retain_days` on capture.
enabled = false
retain_days = 7
```

## `vision/capture.py` — dispatch sketch

```python
def grab(*, monitor: int = 1, max_edge_px: int = 1568,
         mode: str = "monitor", window_inset_px: int = 5) -> Screenshot:
    if mode == "window":
        return _grab_window(max_edge_px=max_edge_px, inset=window_inset_px)
    if mode == "cursor":
        return _grab_cursor_monitor(max_edge_px=max_edge_px)
    return _grab_monitor(monitor=monitor, max_edge_px=max_edge_px)

def _grab_window(*, max_edge_px: int, inset: int) -> Screenshot:
    import pygetwindow as gw
    win = gw.getActiveWindow()
    if win is None or win.width <= 0 or win.height <= 0:
        log.warning("vision.capture.window_unavailable")
        return _grab_monitor(monitor=1, max_edge_px=max_edge_px)
    box = {"top": win.top + inset, "left": win.left + inset,
           "width": win.width - 2 * inset, "height": win.height - 2 * inset}
    with mss.mss() as sct:
        shot = sct.grab(box)
        ...  # same downscale + PNG encode path

def _grab_cursor_monitor(*, max_edge_px: int) -> Screenshot:
    from pynput.mouse import Controller
    x, y = Controller().position
    with mss.mss() as sct:
        for idx, mon in enumerate(sct.monitors[1:], start=1):
            if mon["left"] <= x < mon["left"] + mon["width"] and \
               mon["top"]  <= y < mon["top"]  + mon["height"]:
                return _grab_index(sct, idx, max_edge_px=max_edge_px)
    return _grab_monitor(monitor=1, max_edge_px=max_edge_px)
```

## `vision/ocr.py` sketch

```python
def extract_text(image_bytes: bytes, max_chars: int = 4000) -> str:
    """Run RapidOCR on a PNG image. Returns concatenated recognized text
    or empty string on any failure."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        log.info("vision.ocr.unavailable")
        return ""
    try:
        ocr = _get_ocr_singleton()
        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        result, _ = ocr(arr)
        if not result:
            return ""
        # result is a list of [bbox, text, confidence]; we just want text
        joined = "\n".join(line[1] for line in result if line[2] > 0.5)
        return joined[:max_chars]
    except Exception as exc:
        log.warning("vision.ocr.failed", error=str(exc))
        return ""
```

The OCR model is lazy-loaded once per process; ~50 MB.

## `see.py` integration

```python
async def see(question, *, settings, ...):
    settings = settings or load_settings()

    # Capture + OCR in parallel. Both are thread-bound; asyncio.gather
    # on to_thread gets us concurrency for free.
    shot_task = asyncio.to_thread(capture, settings)
    if settings.vision.ocr.enabled:
        shot = await shot_task
        ocr_text = await asyncio.to_thread(
            extract_text, shot.data, settings.vision.ocr.max_chars
        )
    else:
        shot = await shot_task
        ocr_text = ""

    if settings.vision.archive.enabled:
        await asyncio.to_thread(archive_save_and_prune, shot, settings)

    system = DEFAULT_VISION_SYSTEM_PROMPT
    if ocr_text:
        system += f"\n\nOCR of the visible screen (may contain errors):\n{ocr_text}"

    # ... existing brain.chat call ...
```

Parallelism is a net negative if OCR is off (one extra
`asyncio.to_thread` overhead) — so branch on the config before
deciding to gather. Simple.

## Test strategy

- `test_capture_mode_monitor_unchanged` — regression: existing tests
  for `grab(monitor=1)` still pass.
- `test_capture_mode_window_uses_active_window_bounds` — monkeypatch
  `pygetwindow.getActiveWindow` to return a fake window with bounds;
  capture `grab(mode="window")`; assert the dimensions match.
- `test_capture_mode_cursor_picks_correct_monitor` — monkeypatch
  `pynput.mouse.Controller().position`; build a fake `sct.monitors`
  list; assert the right index is picked.
- `test_capture_window_falls_back_to_monitor_when_no_active` —
  monkeypatch to return None; assert fallback and a log line.
- `test_ocr_returns_empty_when_library_not_installed` — mock
  `ImportError` on the RapidOCR import; assert empty string.
- `test_ocr_caps_to_max_chars` — stub OCR to return 10k chars; assert
  truncation.
- `test_archive_writes_and_prunes_old_files` — write screenshots
  with spoofed old mtimes; run prune; assert old ones removed, fresh
  one retained.
- `test_see_with_ocr_includes_sidecar_in_system` — stub OCR to
  return canned text; assert the system prompt passed to the stub
  brain contains the OCR line.

Manual smoke:
- Side-by-side: `sabrina look --capture-mode monitor` vs.
  `--capture-mode window` with an editor focused and a Slack window
  visible; confirm the window-mode reply ignores Slack.
- `vision.ocr.enabled=true`, `sabrina look "summarize this email"`
  with Outlook focused; confirm the reply shows signs of the text
  being extracted (e.g. quoting names accurately when the token
  budget is low).
- Cursor mode: move cursor to the second monitor, say
  `sabrina look`; confirm the second monitor was captured.

## Dependencies to add

```toml
"pygetwindow>=0.0.9",   # always required (capture-mode=window)
```

And an optional extra:

```toml
[project.optional-dependencies]
vision-ocr = ["rapidocr-onnxruntime>=1.3"]
```

`rapidocr-onnxruntime` is ~20 MB of Python + ~40 MB of ONNX models
fetched on first run into the user cache. Keeping it optional means
users who don't want OCR don't pay for it.

## Windows-specific concerns

- `pygetwindow`'s Windows backend uses `pywin32`'s `win32gui`; already
  in deps. Works cleanly on Windows 11.
- DWM shadow inset (above) is the practical gotcha; the 5 px default
  handles it for 99% of windows.
- Multi-DPI monitors: `mss` reports raw pixels; `pygetwindow` reports
  DIPs in some configurations. If Eric's second monitor is scaled
  differently, the window-capture bounds may be off by the scale
  factor. Mitigation: the plan's default is monitor-mode; window-mode
  is an opt-in, and we log the effective bounds so mismatches are
  diagnosable.
- RapidOCR's first run downloads ONNX weights into
  `%USERPROFILE%\.cache\rapidocr`. Document in the validation doc.

## Ship criterion

- All new unit tests pass.
- Manual: `sabrina look --capture-mode window` captures only the
  focused window. Editor + IDE + Slack open → reply references only
  the focused one.
- Manual: `sabrina look --capture-mode cursor` on a two-monitor setup
  captures the right monitor depending on cursor location.
- Manual: with `vision.ocr.enabled=true`, a screenshot of a terminal
  error reply includes the error's exact text in the brain's reply.
- `vision.capture_mode=monitor` (default) is unchanged in behavior.
- `vision.ocr.enabled=false` (default) is unchanged in behavior.
- `vision.archive.enabled=true` populates `data/screenshots/` and
  prunes files older than `retain_days`.

## Not in this plan (later)

- Full semantic search over past screenshots (would need a visual
  embedder — a separate, bigger plan).
- Per-app capture profiles.
- Pre-capture region-selection prompt (user draws a box). Way more
  UI than we want; could be a follow-up behind the GUI.
- Click-target annotation.
- Streaming-friendly capture (vision is always one-shot per turn).
