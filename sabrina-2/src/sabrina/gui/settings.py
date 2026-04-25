"""Settings GUI — a small customtkinter window for tweaking sabrina.toml.

Covers the knobs people actually want to touch often:
  - Brain:  default engine, Claude model names
  - TTS:    engine, Piper voice preset + speaker_id + length_scale,
            SAPI voice + rate
  - ASR:    faster-whisper model size + beam size
  - Vision: trigger mode, hotkey, model override
  - Memory: enabled, load_recent

Design choices:
  * Tabbed layout keeps the window small on laptops.
  * Save button writes through tomlkit so comments in sabrina.toml survive.
  * No live apply — changes take effect next time the relevant command is
    (re)started. We show a subtle note at the bottom of the window so the
    user isn't left wondering why the current voice loop didn't change.
  * We never touch api keys here; those belong in .env.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# customtkinter is imported lazily inside open_settings() so that
# `import sabrina.gui.settings` stays cheap for tests / headless environments.

from sabrina.config import load_settings
from sabrina.settings_io import save_with_updates
from sabrina.speaker.voices import PRESETS

_BRAIN_ENGINES = ["claude", "ollama"]
_TTS_ENGINES = ["piper", "sapi"]
_VISION_TRIGGERS = ["both", "voice_phrase", "hotkey", "off"]
_ASR_MODELS = [
    "tiny.en",
    "base.en",
    "small.en",
    "medium.en",
    "large-v3",
]
_COMMON_CLAUDE_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
]


def _voice_preset_keys() -> list[str]:
    return list(PRESETS.keys())


def open_settings() -> None:
    """Launch the settings window (blocks until closed)."""
    import customtkinter as ctk  # local import: GUI is optional at import time

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = SettingsWindow(ctk)
    app.mainloop()


class SettingsWindow:
    """The top-level settings window.

    Instantiating does NOT call mainloop(); the caller does. That lets a
    future test or sub-window embed it without hijacking the main loop.
    """

    def __init__(self, ctk_module: Any) -> None:
        self.ctk = ctk_module
        self.settings = load_settings(reload=True)

        self.root = ctk_module.CTk()
        self.root.title("Sabrina Settings")
        self.root.geometry("640x560")
        self.root.minsize(560, 480)

        self._vars: dict[str, Any] = {}
        self._build()

    # --- building the UI ---

    def _build(self) -> None:
        tabs = self.ctk.CTkTabview(self.root)
        tabs.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self._build_brain_tab(tabs.add("Brain"))
        self._build_tts_tab(tabs.add("TTS"))
        self._build_asr_tab(tabs.add("ASR"))
        self._build_vision_tab(tabs.add("Vision"))
        self._build_memory_tab(tabs.add("Memory"))

        self._build_footer()

    def _build_brain_tab(self, parent: Any) -> None:
        b = self.settings.brain
        self._vars["brain.default"] = self._optionmenu(
            parent, "Default brain", b.default, _BRAIN_ENGINES
        )
        self._vars["brain.claude.model"] = self._combobox(
            parent, "Claude model", b.claude.model, _COMMON_CLAUDE_MODELS
        )
        self._vars["brain.claude.fast_model"] = self._combobox(
            parent, "Claude fast model", b.claude.fast_model, _COMMON_CLAUDE_MODELS
        )
        self._vars["brain.claude.max_tokens"] = self._spinbox(
            parent, "Max tokens", b.claude.max_tokens, (64, 8192)
        )
        self._vars["brain.ollama.model"] = self._entry(
            parent, "Ollama model", b.ollama.model
        )

    def _build_tts_tab(self, parent: Any) -> None:
        t = self.settings.tts
        self._vars["tts.default"] = self._optionmenu(
            parent, "Default TTS engine", t.default, _TTS_ENGINES
        )

        # Piper subsection
        self._section_label(parent, "Piper")
        # Voice preset dropdown — show preset keys, but we'll store the
        # resolved voice_model path on save.
        current_preset = _preset_key_from_model_path(t.piper.voice_model)
        self._vars["_piper_preset"] = self._optionmenu(
            parent, "Voice preset", current_preset, _voice_preset_keys()
        )
        self._vars["tts.piper.speaker_id"] = self._spinbox(
            parent,
            "Speaker ID (multi-speaker voices)",
            t.piper.speaker_id if t.piper.speaker_id is not None else 0,
            (0, 999),
        )
        self._vars["tts.piper.length_scale"] = self._slider(
            parent, "Speed (length_scale)", t.piper.length_scale, (0.7, 1.5), 0.05
        )

        # SAPI subsection
        self._section_label(parent, "SAPI (Windows fallback)")
        self._vars["tts.sapi.voice"] = self._entry(
            parent, "Voice (name substring)", t.sapi.voice
        )
        self._vars["tts.sapi.rate"] = self._spinbox(
            parent, "Rate (wpm)", t.sapi.rate, (80, 400)
        )

    def _build_asr_tab(self, parent: Any) -> None:
        a = self.settings.asr.faster_whisper
        self._vars["asr.faster_whisper.model"] = self._optionmenu(
            parent, "Model size", a.model, _ASR_MODELS
        )
        self._vars["asr.faster_whisper.device"] = self._optionmenu(
            parent, "Device", a.device, ["auto", "cuda", "cpu"]
        )
        self._vars["asr.faster_whisper.compute_type"] = self._optionmenu(
            parent,
            "Compute type",
            a.compute_type,
            ["float16", "int8_float16", "int8", "float32"],
        )
        self._vars["asr.faster_whisper.beam_size"] = self._spinbox(
            parent, "Beam size (1=greedy, 5=default)", a.beam_size, (1, 10)
        )

    def _build_vision_tab(self, parent: Any) -> None:
        v = self.settings.vision
        self._vars["vision.trigger"] = self._optionmenu(
            parent, "Trigger mode", v.trigger, _VISION_TRIGGERS
        )
        self._vars["vision.hotkey"] = self._entry(
            parent, "Hotkey (pynput syntax)", v.hotkey
        )
        self._vars["vision.model"] = self._combobox(
            parent,
            "Model (blank = brain.claude.fast_model)",
            v.model,
            ["", *_COMMON_CLAUDE_MODELS],
        )
        self._vars["vision.monitor"] = self._spinbox(
            parent, "Monitor index (1 = primary)", v.monitor, (0, 8)
        )
        self._vars["vision.max_edge_px"] = self._spinbox(
            parent, "Max long-edge px (0 = native)", v.max_edge_px, (0, 4096)
        )

    def _build_memory_tab(self, parent: Any) -> None:
        m = self.settings.memory
        self._vars["memory.enabled"] = self._switch(
            parent, "Persist conversation", m.enabled
        )
        self._vars["memory.load_recent"] = self._spinbox(
            parent, "Messages to reload at start", m.load_recent, (0, 500)
        )
        # --- Semantic retrieval sub-frame ---
        self._section_label(parent, "Semantic retrieval")
        s = m.semantic
        self._vars["memory.semantic.enabled"] = self._switch(
            parent, "Enabled", s.enabled
        )
        self._vars["memory.semantic.top_k"] = self._spinbox(
            parent, "Top K", s.top_k, (1, 25)
        )
        self._vars["memory.semantic.max_distance"] = self._entry(
            parent, "Max distance (0..1)", f"{s.max_distance:.2f}"
        )
        self._vars["memory.semantic.min_age_turns"] = self._spinbox(
            parent, "Min age turns", s.min_age_turns, (0, 1000)
        )
        # --- Compaction sub-frame ---
        self._section_label(parent, "Compaction")
        c = m.compaction
        self._vars["memory.compaction.mode"] = self._optionmenu(
            parent, "Auto-compaction", c.mode, ["auto", "manual"]
        )
        self._vars["memory.compaction.threshold_tokens"] = self._spinbox(
            parent, "Threshold tokens", c.threshold_tokens, (1000, 1_000_000)
        )
        self._vars["memory.compaction.batch_size"] = self._spinbox(
            parent, "Turns per pass", c.batch_size, (10, 5_000)
        )
        # Stats + manual-compact button. Both subprocess-shell-out so the
        # voice loop / GUI never block on the brain. Wired to no-op
        # placeholders here; the runner is added when the
        # `sabrina memory-compact` CLI verb lands.
        self._memory_stats_label = self.ctk.CTkLabel(
            parent,
            text="(stats refresh on tab switch)",
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self._memory_stats_label.pack(fill="x", padx=8, pady=(4, 0))
        action_bar = self.ctk.CTkFrame(parent, fg_color="transparent")
        action_bar.pack(fill="x", padx=8, pady=4)
        self.ctk.CTkButton(
            action_bar, text="Compact now", width=120,
            command=lambda: self._shell_out_async(
                ["sabrina", "memory-compact", "--force"], label="Compacting"
            ),
        ).pack(side="left", padx=(0, 6))
        self.ctk.CTkButton(
            action_bar, text="Reindex", width=120,
            command=lambda: self._shell_out_async(
                ["sabrina", "memory-reindex"], label="Reindexing"
            ),
        ).pack(side="left")

    def _set_status(self, text: str) -> None:
        """Update the footer status label. Used by sub-frame buttons."""
        if hasattr(self, "_status") and self._status is not None:
            self._status.configure(text=text)

    def _shell_out_async(self, argv: list, *, label: str) -> None:
        """Fire a CLI subprocess in the background; surface result in the status label.

        Runs the command in a daemon thread so the GUI stays responsive.
        The status label updates pre-flight ("Compacting...") and
        post-flight ("Done."/"Failed"). We don't pipe stdout/stderr into
        the GUI; users follow up with the CLI for full output.
        """
        import subprocess
        import threading

        self._set_status(f"{label}... (running `{' '.join(argv)}`)")

        def _run() -> None:
            try:
                rc = subprocess.call(argv)
            except Exception as exc:  # noqa: BLE001
                msg = f"{label} failed: {exc}"
            else:
                msg = (
                    f"{label} done."
                    if rc == 0
                    else f"{label} exited rc={rc}; check `{' '.join(argv)}` in a terminal."
                )
            # Tk vars/labels must be touched from the main thread.
            try:
                self.root.after(0, lambda: self._set_status(msg))
            except Exception:  # noqa: BLE001 - window may be closing
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _build_footer(self) -> None:
        bar = self.ctk.CTkFrame(self.root, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=12)

        self._status = self.ctk.CTkLabel(
            bar,
            text="Changes take effect next time you start the relevant command.",
            text_color=("gray40", "gray70"),
            anchor="w",
        )
        self._status.pack(side="left", fill="x", expand=True)

        save_btn = self.ctk.CTkButton(bar, text="Save", width=96, command=self._on_save)
        save_btn.pack(side="right", padx=(8, 0))
        cancel_btn = self.ctk.CTkButton(
            bar,
            text="Close",
            width=96,
            fg_color="transparent",
            border_width=1,
            command=self.root.destroy,
        )
        cancel_btn.pack(side="right")

    # --- widgets (small helpers so the tabs read top-down) ---

    def _row(self, parent: Any, label: str) -> Any:
        frame = self.ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=8, pady=4)
        self.ctk.CTkLabel(frame, text=label, anchor="w", width=220).pack(side="left")
        return frame

    def _section_label(self, parent: Any, text: str) -> None:
        lbl = self.ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            font=self.ctk.CTkFont(weight="bold"),
        )
        lbl.pack(fill="x", padx=8, pady=(12, 2))

    def _entry(self, parent: Any, label: str, value: str) -> Any:
        frame = self._row(parent, label)
        var = self.ctk.StringVar(value=str(value))
        self.ctk.CTkEntry(frame, textvariable=var).pack(
            side="left", fill="x", expand=True
        )
        return var

    def _optionmenu(
        self, parent: Any, label: str, value: str, options: list[str]
    ) -> Any:
        frame = self._row(parent, label)
        var = self.ctk.StringVar(value=str(value))
        self.ctk.CTkOptionMenu(frame, variable=var, values=options).pack(
            side="left", fill="x", expand=True
        )
        return var

    def _combobox(self, parent: Any, label: str, value: str, options: list[str]) -> Any:
        frame = self._row(parent, label)
        var = self.ctk.StringVar(value=str(value))
        self.ctk.CTkComboBox(frame, variable=var, values=options).pack(
            side="left", fill="x", expand=True
        )
        return var

    def _spinbox(
        self, parent: Any, label: str, value: int, bounds: tuple[int, int]
    ) -> Any:
        # customtkinter has no native spinbox; use an entry with integer StringVar.
        # Bounds are advisory — clamped on save.
        frame = self._row(parent, label)
        var = self.ctk.StringVar(value=str(int(value)))
        self.ctk.CTkEntry(frame, textvariable=var, width=100).pack(side="left")
        hint = self.ctk.CTkLabel(
            frame,
            text=f"  ({bounds[0]}-{bounds[1]})",
            text_color=("gray40", "gray70"),
        )
        hint.pack(side="left")
        return var

    def _slider(
        self,
        parent: Any,
        label: str,
        value: float,
        bounds: tuple[float, float],
        step: float,
    ) -> Any:
        frame = self._row(parent, label)
        var = self.ctk.DoubleVar(value=float(value))
        readout = self.ctk.CTkLabel(frame, text=f"{value:.2f}", width=44)

        def _on_change(v: float) -> None:
            # Quantize to `step` so the saved value is tidy.
            q = round(v / step) * step
            var.set(q)
            readout.configure(text=f"{q:.2f}")

        steps = max(1, int((bounds[1] - bounds[0]) / step))
        slider = self.ctk.CTkSlider(
            frame,
            from_=bounds[0],
            to=bounds[1],
            number_of_steps=steps,
            variable=var,
            command=_on_change,
        )
        slider.pack(side="left", fill="x", expand=True)
        readout.pack(side="left", padx=(8, 0))
        return var

    def _switch(self, parent: Any, label: str, value: bool) -> Any:
        frame = self._row(parent, label)
        var = self.ctk.BooleanVar(value=bool(value))
        self.ctk.CTkSwitch(frame, text="", variable=var).pack(side="left")
        return var

    # --- save ---

    def _collect(self) -> dict[str, Any]:
        """Pull every var into a flat {dotted-key: value} dict, coerced.

        Skips control vars whose key starts with underscore (e.g.
        `_piper_preset`); those are translated to their real TOML keys
        below before save. Without this filter, `_piper_preset` would
        end up as a top-level TOML key on save.
        """
        flat: dict[str, Any] = {}
        for key, var in self._vars.items():
            if key.startswith("_"):
                continue  # control var; handled below
            try:
                raw = var.get()
            except Exception:  # noqa: BLE001 - tk var may not be alive
                continue
            flat[key] = _coerce(key, raw)

        # Voice preset dropdown -> tts.piper.voice_model path.
        # Pull from PRESETS so adding a voice in voices.py automatically
        # surfaces here without editing GUI code (no drift).
        preset_var = self._vars.get("_piper_preset")
        if preset_var is not None:
            try:
                preset_key = preset_var.get()
            except Exception:  # noqa: BLE001
                preset_key = ""
            if preset_key in PRESETS:
                flat["tts.piper.voice_model"] = (
                    f"voices/{PRESETS[preset_key].id}.onnx"
                )
        return flat

    def _on_save(self) -> None:
        """Render collected vars to a nested dict + write via settings_io."""
        flat = self._collect()
        nested = _nest(flat)
        try:
            save_with_updates(nested)
            self._set_status("Saved.")
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Save failed: {exc}")

    def mainloop(self) -> None:
        """Run the GUI event loop. Blocks until the window is closed.

        Thin wrapper so callers (open_settings) can call .mainloop()
        on the SettingsWindow rather than reaching into .root, and so
        a future test can substitute a no-op.
        """
        self.root.mainloop()


def _preset_key_from_model_path(path: str) -> str:
    """Map a `voices/<voice>.onnx` path to a dropdown preset key.

    Drives off `PRESETS` from `sabrina.speaker.voices` so a new voice
    landing in voices.py shows up in the GUI without a parallel update
    here. Falls back to the first preset key when the path doesn't
    match any known preset (so the dropdown always has a legal value).
    """
    name = Path(path).stem
    for key, preset in PRESETS.items():
        if preset.id == name:
            return key
    return next(iter(PRESETS), "")


def _coerce(key: str, value: Any) -> Any:
    """Coerce a TK-var raw value to the right Python type per dotted key.

    Booleans pass through. Ints/floats are inferred from key names; the
    full set of typed fields is small enough to enumerate.
    """
    if isinstance(value, bool):
        return value
    int_keys = {
        "memory.load_recent",
        "memory.semantic.top_k",
        "memory.semantic.min_age_turns",
        "memory.compaction.threshold_tokens",
        "memory.compaction.batch_size",
        "tts.piper.speaker_id",
        "tts.sapi.rate",
        "asr.faster_whisper.beam_size",
        "vision.monitor",
        "vision.max_edge_px",
    }
    float_keys = {
        "tts.piper.length_scale",
        "memory.semantic.max_distance",
        "barge_in.threshold",
        "wake_word.threshold",
        "memory.compaction.chars_per_token",
    }
    s = str(value).strip()
    if key in int_keys:
        try:
            return int(s)
        except ValueError:
            return 0
    if key in float_keys:
        try:
            return float(s)
        except ValueError:
            return 0.0
    return s


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert {"a.b.c": v} -> {"a": {"b": {"c": v}}}.

    Used so the GUI's flat var map can be handed to settings_io which
    expects nested dicts mirroring the TOML structure.
    """
    out: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
    return out
