"""Typed configuration loader.

Reads sabrina.toml as the base layer. Environment variables (and .env) override.
Env var convention: SABRINA_<SECTION>__<KEY>  (double underscore separates nesting).

Example:
    SABRINA_BRAIN__DEFAULT=ollama
    SABRINA_BRAIN__CLAUDE__MODEL=claude-haiku-4-5-20251001
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class ClaudeConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    fast_model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 1024


class OllamaConfig(BaseModel):
    host: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    fast_model: str = "qwen2.5:7b"


class BrainConfig(BaseModel):
    default: Literal["claude", "ollama"] = "claude"
    claude: ClaudeConfig = ClaudeConfig()
    ollama: OllamaConfig = OllamaConfig()


class PiperConfig(BaseModel):
    binary: str = ""  # empty = use `piper` on PATH
    voice_model: str = "voices/en_US-libritts_r-medium.onnx"
    # Multi-speaker models (libritts_r, etc.) need a speaker index. None means
    # "let Piper pick its default" — fine for single-speaker voices.
    speaker_id: int | None = 0
    length_scale: float = 1.0


class SapiConfig(BaseModel):
    voice: str = ""
    rate: int = 200  # words per minute; SAPI native baseline is ~200


class TtsConfig(BaseModel):
    default: Literal["piper", "sapi"] = "piper"
    output_device: str = ""  # empty = system default; int string or name substring
    piper: PiperConfig = PiperConfig()
    sapi: SapiConfig = SapiConfig()


class FasterWhisperConfig(BaseModel):
    # Model size: tiny | base | small | medium | large-v3.
    # Also accepts a path to a local CT2-converted model directory.
    model: str = "base.en"
    # "cuda" | "cpu" | "auto". cuda pins to GPU 0; set explicitly if multi-GPU.
    device: Literal["cuda", "cpu", "auto"] = "auto"
    # "float16" | "int8_float16" | "int8" | "float32". int8_float16 is a
    # great speed/quality trade on Ampere+; float16 is the quality ceiling.
    compute_type: str = "float16"
    # Beam search width. 1 = greedy (fastest), 5 = openai default (slower, a bit better).
    beam_size: int = 5
    # ISO-639-1 language code, or empty for auto-detect.
    language: str = "en"


class AsrConfig(BaseModel):
    default: Literal["faster-whisper"] = "faster-whisper"
    # Input audio device for `asr-record`. Same rules as tts.output_device.
    input_device: str = ""
    faster_whisper: FasterWhisperConfig = FasterWhisperConfig()


class VisionConfig(BaseModel):
    # How the user invokes a screen-look from the voice loop.
    #   "voice_phrase" - speak a trigger phrase ("look at my screen", etc.)
    #   "hotkey"       - press a dedicated key combo
    #   "both"         - either works
    #   "off"          - disabled
    trigger: Literal["voice_phrase", "hotkey", "both", "off"] = "both"
    # Pynput-style hotkey string. Ignored unless trigger includes "hotkey".
    hotkey: str = "<ctrl>+<shift>+v"
    # Which Claude model to use for vision turns. Empty = use brain.claude.fast_model.
    model: str = ""
    # Monitor index to capture. 0 = virtual "all monitors" screen in mss,
    # 1 = primary, 2+ = secondary displays.
    monitor: int = 1
    # Downscale large screenshots before sending, to keep token cost sane.
    # Longest-edge pixel cap; 0 disables scaling.
    max_edge_px: int = 1568


class SemanticMemoryConfig(BaseModel):
    # Master switch for retrieval augmentation. Off by default so a fresh
    # checkout without sentence-transformers installed still runs.
    enabled: bool = False
    # sentence-transformers model id. Default is the roadmap pick: 384 dims,
    # ~80 MB, ~20 ms/sentence CPU / ~5 ms on a 4080.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # How many retrieved turns to inject per user message.
    top_k: int = 5
    # Cosine distance cutoff — hits further than this are dropped. 0 = identical,
    # ~1 = orthogonal. 0.5 is "meaningfully related", 0.35 is "closely related".
    max_distance: float = 0.5
    # Don't retrieve any of the load_recent turns already in history.
    # Set a floor so semantic memory only surfaces things that *aren't* right there.
    # Counted in number of most-recent turns to exclude (matches load_recent by default).
    min_age_turns: int = 20


class MemoryConfig(BaseModel):
    enabled: bool = True
    # Relative paths resolve to project root.
    db_path: str = "data/sabrina.db"
    # How many past messages to load on startup (most recent).
    load_recent: int = 20
    # Semantic retrieval (sqlite-vec + sentence-transformers). See below.
    semantic: SemanticMemoryConfig = SemanticMemoryConfig()


class LoggingConfig(BaseModel):
    level: str = "INFO"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SABRINA_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        toml_file="sabrina.toml",
        extra="ignore",
    )

    brain: BrainConfig = BrainConfig()
    tts: TtsConfig = TtsConfig()
    asr: AsrConfig = AsrConfig()
    vision: VisionConfig = VisionConfig()
    memory: MemoryConfig = MemoryConfig()
    logging: LoggingConfig = LoggingConfig()
    # Accept either ANTHROPIC_API_KEY (standard Anthropic env var) or the
    # SABRINA_-prefixed form. Loaded from .env or shell environment.
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "SABRINA_ANTHROPIC_API_KEY"),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Precedence (highest to lowest):
        #   init kwargs > env vars > .env file > sabrina.toml > field defaults
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


_cached: Settings | None = None


def load_settings(reload: bool = False) -> Settings:
    """Load settings once (cached). Pass reload=True to force re-read."""
    global _cached
    if _cached is None or reload:
        _cached = Settings()
    return _cached


def project_root() -> Path:
    """Best-effort project root (where sabrina.toml lives)."""
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "sabrina.toml").is_file():
            return candidate
    return cwd
