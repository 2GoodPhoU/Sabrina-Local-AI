# Decision 004: Settings GUI (Phase A of Component 4) shipped

**Date:** 2026-04-22
**Status:** Accepted

## Summary

Component 4 (vision) was requested with a GUI preference: Eric asked for a
settings window with voice-command-or-hotkey toggle plus TTS parameters.
Rather than bolt that on after vision, we split the work: Phase A ships
the GUI *first* (so vision slots in as one more tab), Phase B ships the
vision component behind the same settings knobs.

This decision covers Phase A only. Vision knobs exist in the GUI and in
sabrina.toml; their *behaviour* is the Phase B work.

## Surface area

- `sabrina settings` — new CLI command, launches a customtkinter window.
- Tabs: Brain / TTS / ASR / Vision / Memory.
- Writes back to `sabrina.toml` via **tomlkit** (not tomllib), so every
  inline and header comment in the file survives an edit round-trip.
  The comments are Eric's in-file documentation — nuking them would
  silently erase a lot of context, so comment preservation is a
  correctness property, not a polish item.
- Atomic save: writes a sibling temp file and `os.replace()`'s it in.
  A crash or power loss leaves either the old file or the new, never a
  half-written one.

## New config keys (also exposed in the GUI)

```
[vision]
trigger = "both"                   # "voice_phrase" | "hotkey" | "both" | "off"
hotkey  = "<ctrl>+<shift>+v"
model   = ""                       # blank = brain.claude.fast_model
monitor = 1                        # mss monitor index
max_edge_px = 1568
```

These are dormant until Phase B wires them in. The GUI can still read
and write them today, which was a nice-to-have for the Windows-side
testing loop.

## Why customtkinter

- Single pip dep, MIT licensed, ~no startup cost on Windows.
- Native-feeling dark-mode UI without dragging PyQt onto the project.
- Interop with tkinter primitives — easy to extend without a second
  widget ecosystem.

Rejected alternatives: stdlib tkinter (ugly), PyQt6 (too heavy, LGPL
friction), Dear PyGui (great but GPU-bound, overkill for a prefs pane),
Textual (TUI — Eric asked for a GUI).

## Why tomlkit, not tomllib + string munging

tomllib is read-only; tomlkit parses to a structure that *remembers*
where comments live and re-serializes with them intact. That's the whole
point — there's no half-measure between "round-trip comments" and "lose
them", and the comments are the user's inline docs.

## Tests added

- `test_settings_io_preserves_comments_on_roundtrip`
- `test_settings_io_applies_nested_updates`
- `test_settings_io_creates_missing_tables`
- `test_settings_io_writes_atomically_no_tempfile_leftovers`
- `test_vision_config_defaults_load`
- `test_gui_settings_module_imports` — smoke that GUI module is
  importable in headless envs (customtkinter is lazy-imported)
- `test_gui_settings_preset_key_resolution`
- `test_gui_settings_nest_and_coerce`

All existing 23 smoke tests still pass (no behavioural changes to
brain/tts/asr/memory).

## Not changing live

Changes take effect on the next start of the relevant command — the
running `voice` loop won't re-read sabrina.toml. A subtle footer label
in the GUI tells the user this. Live reload is deferred; the asymmetry
isn't worth the complexity of hot-reconfiguring speaker and listener
instances mid-session.

## Next

**Phase B: Vision.** Wire `mss` capture, `Message.images` on the brain
protocol, Claude vision call, and voice-loop integration that honors
`vision.trigger` / `vision.hotkey`. Ship metric: from "look at my
screen" (spoken) or hotkey press, first audible word of Sabrina's
response under 3 seconds for a primary-monitor grab.
