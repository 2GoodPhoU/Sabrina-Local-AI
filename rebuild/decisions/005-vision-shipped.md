# Decision 005: Component 4 (vision) shipped

**Date:** 2026-04-22
**Status:** Accepted

## Summary

Sabrina can see the screen. Two ways in:

- **Voice phrase** — say something like "look at my screen, what's this
  error?" and the voice loop grabs a screenshot for that turn.
- **Hotkey** — press Ctrl+Shift+V (configurable) to *arm* the next
  voice turn. Press, then PTT-speak your question.

Either trigger captures one screenshot with `mss`, downscales it so the
long edge fits inside `vision.max_edge_px` (default 1568 px), encodes to
PNG, and attaches it to the next Claude turn via the vision API. The
rest of the pipeline (sentence-streaming TTS, memory persistence, state
machine) is unchanged — vision is a one-line detour at the top of each
turn.

There's also `sabrina look "question"` — standalone screenshot-and-ask
without going through the voice loop. Great for debugging and for
picking the right `max_edge_px` on different monitors.

## Architecture moves worth preserving

1. **`Message.images` as a tuple on the Brain protocol.** Text-only
   turns stay compact (`{"role", "content": str}`) so the 99% path pays
   nothing. Image turns switch to the content-block form. The
   serialization lives in `brain/claude.py::_render_message` and is
   covered by tests so future tool-use / document turns can piggyback
   on the same conversion pattern.

2. **Vision gets its own ClaudeBrain instance per turn.** The main
   brain may be Ollama; we don't want to force vision through a
   non-multimodal backend. A fresh `ClaudeBrain` with
   `settings.vision.model` (or `brain.claude.fast_model`) is built just
   for the vision turn, then discarded. Cheap — no network on init.

3. **Hotkey arms the next turn, not "click to screenshot".** User
   presses the combo, then speaks normally; the turn after the press
   gets the screenshot. Removes every UX footgun around "what if I
   press the hotkey mid-typing" or "screenshot captured but no
   question asked".

4. **Bias toward false negatives in trigger-phrase detection.** Short
   allowlist of ~18 phrases matched as substrings against the
   lowercased transcript. Good enough, tests guard the negatives,
   future intent classifier can slot behind `should_trigger_vision`.

5. **Downscale before upload.** Claude's vision sweet spot is ~1500 px
   long edge; anything more just costs tokens. A 4K primary monitor
   (3840x2160) becomes 1568x882 ~= 400-700 KB PNG. Round-trip latency
   stays in the single-digit seconds.

6. **Memory only stores text.** Screenshots are ephemeral — we append
   the user's transcript to SQLite (as before) but not the PNG bytes.
   Keeps the store small and means old vision turns don't bloat the
   loaded history.

## New files

- `src/sabrina/vision/capture.py` — `grab()` + `downscale_size()`.
- `src/sabrina/vision/see.py` — one-shot `see(question)` async generator.
- `src/sabrina/vision/triggers.py` — `should_trigger_vision(text)`.
- `src/sabrina/vision/hotkey.py` — pynput-backed arm/consume flag.

## Brain protocol change

`Message.images: tuple[Image, ...] = ()` is additive — existing
constructors still work unchanged. Text-only backends (Ollama) just
ignore the field; Claude switches to the content-block serialization
when images are present.

## Config knobs (all editable in the settings GUI)

```
[vision]
trigger = "both"     # voice_phrase | hotkey | both | off
hotkey  = "<ctrl>+<shift>+v"
model   = ""         # blank = brain.claude.fast_model
monitor = 1
max_edge_px = 1568
```

## Tests added

- `test_message_carries_images_by_default_empty`
- `test_claude_render_message_text_only_stays_compact`
- `test_claude_render_message_image_turn_builds_blocks`
- `test_vision_should_trigger_positive_phrases`
- `test_vision_should_trigger_negative_phrases`
- `test_vision_downscale_math_within_budget_is_passthrough`
- `test_vision_downscale_math_preserves_aspect_and_caps`
- `test_vision_hotkey_arm_and_consume`
- `test_vision_see_module_rejects_missing_api_key`

## Ship criterion — proposed

> From "look at my screen, X" spoken -> first audible word of
> Sabrina's response, under 3 seconds on the primary monitor
> (fast_model = Haiku 4.5).

Haiku's first-token latency on vision calls has been running
400-700ms in our prior eyeballed tests; capture is ~50ms; encode is
~100-200ms; PTT release to transcription is ~100ms. 3s is conservative.
Measure on first real run and tighten if warranted.

## Not handled (deferred)

- **Region / window capture.** Today it's whole-monitor. Tools like
  mss support rectangles; adding a "screenshot this window" path
  becomes useful once we have window metadata (Windows UIA / pygetwin).
- **OCR pre-pass.** Claude's vision is good enough that a local OCR
  layer isn't earning its keep. Revisit if token cost becomes a
  problem on heavy usage.
- **Image memory.** We don't rehydrate old screenshots on reload.
  Short-lived context only.
- **Barge-in on vision turns.** Same story as text — Sabrina
  finishes speaking before listening. Component 6.

## Next

Open design question: **Component 5 is either local VLM fallback
(llava via Ollama, same protocol) or wake-word (openWakeWord so PTT
becomes optional)**. Wake-word is the bigger UX win day-to-day;
local VLM is the better offline story. Ask user next pass.
