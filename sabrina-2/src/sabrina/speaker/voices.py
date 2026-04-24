"""Download Piper voice models on demand.

Sources from the rhasspy/piper-voices Hugging Face repo:
  https://huggingface.co/rhasspy/piper-voices/tree/main

Each voice has two files: <name>.onnx (weights, ~60 MB) and <name>.onnx.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from sabrina.logging import get_logger

log = get_logger(__name__)

_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


@dataclass(frozen=True)
class VoicePreset:
    id: str  # e.g. "en_US-amy-medium"
    language: str  # e.g. "en_US"
    name: str  # e.g. "amy"
    quality: str  # "low" | "medium" | "high"
    description: str

    @property
    def hf_path(self) -> str:
        # HF repo layout: <lang_group>/<locale>/<voice>/<quality>/<id>.onnx
        # e.g. en/en_US/amy/medium/en_US-amy-medium.onnx
        lang_group = self.language.split("_", 1)[0]
        return f"{lang_group}/{self.language}/{self.name}/{self.quality}/{self.id}.onnx"


# Hand-picked defaults for English. Add more as needed.
PRESETS: dict[str, VoicePreset] = {
    "amy-medium": VoicePreset(
        id="en_US-amy-medium",
        language="en_US",
        name="amy",
        quality="medium",
        description="Female, neutral US English. Clear, pleasant, good default.",
    ),
    "amy-low": VoicePreset(
        id="en_US-amy-low",
        language="en_US",
        name="amy",
        quality="low",
        description="Faster / smaller version of amy. Slightly rougher.",
    ),
    "lessac-medium": VoicePreset(
        id="en_US-lessac-medium",
        language="en_US",
        name="lessac",
        quality="medium",
        description="Female, warm tone. Alternative to amy.",
    ),
    "ryan-medium": VoicePreset(
        id="en_US-ryan-medium",
        language="en_US",
        name="ryan",
        quality="medium",
        description="Male, neutral US English.",
    ),
    "libritts_r-medium": VoicePreset(
        id="en_US-libritts_r-medium",
        language="en_US",
        name="libritts_r",
        quality="medium",
        description="Multi-speaker model; more variety in intonation.",
    ),
    "hfc_female-medium": VoicePreset(
        id="en_US-hfc_female-medium",
        language="en_US",
        name="hfc_female",
        quality="medium",
        description="Female, natural-sounding US English. Often preferred over amy.",
    ),
    "kathleen-low": VoicePreset(
        id="en_US-kathleen-low",
        language="en_US",
        name="kathleen",
        quality="low",
        description="Female, warm and friendly. Smaller/faster model.",
    ),
    "kristin-medium": VoicePreset(
        id="en_US-kristin-medium",
        language="en_US",
        name="kristin",
        quality="medium",
        description="Female, conversational. Good expressive range.",
    ),
    "joe-medium": VoicePreset(
        id="en_US-joe-medium",
        language="en_US",
        name="joe",
        quality="medium",
        description="Male, deeper voice. Good alternative to ryan.",
    ),
    "alba-medium": VoicePreset(
        id="en_GB-alba-medium",
        language="en_GB",
        name="alba",
        quality="medium",
        description="Female, British English. Pleasant RP accent.",
    ),
    "alan-medium": VoicePreset(
        id="en_GB-alan-medium",
        language="en_GB",
        name="alan",
        quality="medium",
        description="Male, British English. Calm, authoritative.",
    ),
}


def list_presets() -> list[VoicePreset]:
    return list(PRESETS.values())


def download_voice(preset_key: str, out_dir: Path) -> Path:
    """Download a voice preset. Returns path to the .onnx model."""
    if preset_key not in PRESETS:
        raise KeyError(
            f"Unknown voice preset {preset_key!r}. Known: {', '.join(PRESETS)}"
        )
    preset = PRESETS[preset_key]
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / f"{preset.id}.onnx"
    config_path = out_dir / f"{preset.id}.onnx.json"

    _fetch(f"{_HF_BASE}/{preset.hf_path}", model_path)
    _fetch(f"{_HF_BASE}/{preset.hf_path}.json", config_path)
    return model_path


def _fetch(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        log.info("voice.skip_existing", path=str(dest))
        return
    log.info("voice.downloading", url=url, dest=str(dest))
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=65536):
                f.write(chunk)
    tmp.replace(dest)
