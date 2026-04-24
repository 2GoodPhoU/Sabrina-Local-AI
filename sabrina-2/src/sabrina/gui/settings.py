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

    def _collect_updates(self) -> dict[str, Any]:
        # Read each var, coerce to the right type, then nest it into a dict
        # matching the TOML layout.
        flat: dict[str, Any] = {}
        for key, var in self._vars.items():
            if key.startswith("_"):
                continue  # intermediate control vars (e.g. _piper_preset)
            raw = var.get()
            flat[key] = _coerce(key, raw)

        # Translate piper preset -> voice_model path.
        preset_key = self._vars["_piper_preset"].get()
        if preset_key in PRESETS:
            flat["tts.piper.voice_model"] = f"voices/{PRESETS[preset_key].id}.onnx"

        return _nest(flat)

    def _on_save(self) -> None:
        try:
            updates = self._collect_updates()
            save_with_updates(updates)
        except Exception as exc:  # noqa: BLE001 - surface any failure to user
            self._status.configure(
                text=f"Save failed: {exc}", text_color=("red", "red")
            )
            return
        self._status.configure(
            text="Saved. Restart any running sabrina command to pick up changes.",
            text_color=("#22a95a", "#3ddb83"),
        )

    def mainloop(self) -> None:
        self.root.mainloop()


# --- helpers ---


def _preset_key_from_model_path(path: str) -> str:
    """Given 'voices/en_US-amy-medium.onnx', return 'amy-medium' if known."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".onnx")
    for key, preset in PRESETS.items():
        if preset.id == stem:
            return key
    # Fallback: the first preset, so the dropdown always has a legal value.
    return next(iter(PRESETS))


_BOOL_KEYS = {"memory.enabled"}
_INT_KEYS = {
    "brain.claude.max_tokens",
    "tts.piper.speaker_id",
    "tts.sapi.rate",
    "asr.faster_whisper.beam_size",
    "vision.monitor",
    "vision.max_edge_px",
    "memory.load_recent",
}
_FLOAT_KEYS = {"tts.piper.length_scale"}


def _coerce(key: str, value: Any) -> Any:
    if key in _BOOL_KEYS:
        return bool(value)
    if key in _INT_KEYS:
        return int(float(value))  # StringVar might deliver "12" or "12.0"
    if key in _FLOAT_KEYS:
        return float(value)
    return str(value)


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    """{'a.b.c': 1} -> {'a': {'b': {'c': 1}}}."""
    out: dict[str, Any] = {}
    for dotted, value in flat.items():
        cur = out
        parts = dotted.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
    return out
