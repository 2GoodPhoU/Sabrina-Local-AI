"""Typed configuration loader.

Reads sabrina.toml as the base layer. Environment variables (and .env) override.
Env var convention: SABRINA_<SECTION>__<KEY>  (double underscore separates nesting).

Example:
    SABRINA_BRAIN__DEFAULT=ollama
    SABRINA_BRAIN__CLAUDE__MODEL=claude-haiku-4-5-20251001

Contributor conventions (see `rebuild/decisions/008-*.md`):
- One `BaseModel` per TOML section; every field has a default.
- New sections that depend on unshipped setup ship `enabled: bool = False`
  (mirror `[memory.semantic]`, `[wake_word]`).
- Literal[...] for enumerable string fields so typos fail at load time.
- Secrets live in `.env` as `SABRINA_<NAME>`, loaded via `SecretStr` --
  they never appear in `sabrina.toml`.
- On a rename/move/delete, append a migration to `MIGRATIONS` and bump
  `CURRENT_SCHEMA_VERSION`. See `apply_migrations` below.
"""

from __future__ import annotations

from collections.abc import Callable
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
    model: str = "base.en"
    device: Literal["cuda", "cpu", "auto"] = "auto"
    compute_type: str = "float16"
    beam_size: int = 5
    language: str = "en"


class AsrConfig(BaseModel):
    default: Literal["faster-whisper"] = "faster-whisper"
    input_device: str = ""
    faster_whisper: FasterWhisperConfig = FasterWhisperConfig()


class VisionConfig(BaseModel):
    trigger: Literal["voice_phrase", "hotkey", "both", "off"] = "both"
    hotkey: str = "<ctrl>+<shift>+v"
    model: str = ""
    monitor: int = 1
    max_edge_px: int = 1568


class EmbedderConfig(BaseModel):
    # Implementation backend. "onnx" (default) runs the model directly
    # under onnxruntime + HF tokenizers (no torch). "sentence-transformers"
    # is the legacy fallback; requires the optional `legacy-embedder`
    # install extra. See `rebuild/decisions/drafts/011-onnx-embedder.md`.
    backend: Literal["onnx", "sentence-transformers"] = "onnx"


class SemanticMemoryConfig(BaseModel):
    enabled: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 5
    max_distance: float = 0.5
    min_age_turns: int = 20
    embedder: EmbedderConfig = EmbedderConfig()


class CompactionConfig(BaseModel):
    # Auto-compact old turns into summaries once memory token count
    # exceeds `threshold_tokens`. mode="manual" disables auto; the
    # `sabrina memory-compact` CLI verb (and the GUI button) still work.
    # See `rebuild/drafts/semantic-memory-gui-plan.md`.
    mode: Literal["auto", "manual"] = "auto"
    # Token count above which auto-compaction triggers at startup. ~80
    # tokens per short turn; 50k = ~600 turns of headroom before the
    # context-window cost of even partial loads becomes annoying.
    threshold_tokens: int = 50000
    # How many of the oldest turns to fold into a single summary on
    # each compaction pass. Smaller = more frequent passes, finer-
    # grained summaries. Larger = batch efficiency but coarser memory.
    batch_size: int = 200
    # Approx character-per-token ratio used for the cheap token estimator.
    # 4.0 is the OpenAI rule of thumb; close enough for thresholding.
    chars_per_token: float = 4.0


class MemoryConfig(BaseModel):
    enabled: bool = True
    db_path: str = "data/sabrina.db"
    load_recent: int = 20
    semantic: SemanticMemoryConfig = SemanticMemoryConfig()
    compaction: CompactionConfig = CompactionConfig()


class WakeWordConfig(BaseModel):
    # Master switch. Off until you've trained / tuned a model on your
    # mic + room. Scaffolded with openWakeWord's bundled "hey_jarvis"
    # placeholder; custom "Hey Sabrina" model is a follow-up (see
    # `rebuild/drafts/wake-word-plan.md` and `tools/wake-training/`).
    enabled: bool = False
    # Either a bundled openWakeWord model id ("hey_jarvis", "alexa",
    # "hey_mycroft") OR a path to a custom .onnx file. Paths resolve
    # relative to the project root.
    model: str = "hey_jarvis"
    # Score threshold (0.0-1.0). Lower = more sensitive. openWakeWord
    # ships with 0.5 as a balanced default; use `sabrina wake-test`
    # (when shipped) to tune for your environment.
    threshold: float = 0.5
    # Suppress repeated triggers for this many ms after a fire. Stops
    # the tail of "hey sabrina" from re-triggering mid-utterance.
    cooldown_ms: int = 2000
    # Input audio device override. Empty = use asr.input_device.
    device: str = ""


class BargeInConfig(BaseModel):
    enabled: bool = False
    threshold: float = 0.5
    min_speech_ms: int = 300
    dead_zone_ms: int = 300
    continue_on_interrupt: bool = True


class SupervisorConfig(BaseModel):
    # Process supervisor + autostart wiring (see
    # `rebuild/drafts/supervisor-autostart-plan.md`). Two backends:
    #   "task_scheduler" - Windows Task Scheduler, default. Login-time
    #                       trigger, no Windows Service plumbing.
    #   "service"        - nssm-wrapped Windows Service. More robust
    #                       but more setup.
    mode: Literal["task_scheduler", "service"] = "task_scheduler"
    # The name registered with Task Scheduler / nssm. Only changed if
    # multiple Sabrina installs need to coexist.
    task_name: str = "SabrinaAI"
    # Crash recovery budget: at most `restart_max` restarts within
    # `restart_window_s`. Beyond that, supervisor backs off and emits
    # `supervisor.budget_exceeded`.
    restart_max: int = 5
    restart_window_s: int = 300
    # Path to nssm.exe (mode = "service" only). Empty = look on PATH.
    nssm_binary: str = ""


class LoggingConfig(BaseModel):
    level: str = "INFO"


class SchemaConfig(BaseModel):
    version: int = 1


CURRENT_SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, Callable[["TOMLDocument"], "TOMLDocument"]]] = []  # noqa: F821


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SABRINA_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        toml_file="sabrina.toml",
        extra="ignore",
        populate_by_name=True,
    )

    schema_: SchemaConfig = Field(default_factory=SchemaConfig, alias="schema")
    brain: BrainConfig = BrainConfig()
    tts: TtsConfig = TtsConfig()
    asr: AsrConfig = AsrConfig()
    vision: VisionConfig = VisionConfig()
    memory: MemoryConfig = MemoryConfig()
    wake_word: WakeWordConfig = WakeWordConfig()
    barge_in: BargeInConfig = BargeInConfig()
    supervisor: SupervisorConfig = SupervisorConfig()
    logging: LoggingConfig = LoggingConfig()
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
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


_cached: Settings | None = None


def apply_migrations(toml_path: Path | None = None) -> int:
    """Run any pending TOML migrations in order; return the final version.

    Minimal hook (per decision 008): reads `[schema].version` via tomlkit,
    runs each migration whose `from_version` is >= current, bumps the field,
    writes the document back atomically. Returns the resulting version.

    No-op when `MIGRATIONS` is empty or the file is already current.
    """
    from sabrina import settings_io

    path = toml_path or settings_io.toml_path()
    if not path.is_file():
        return CURRENT_SCHEMA_VERSION

    doc = settings_io.load_document(path)
    current = int(doc.get("schema", {}).get("version", 1))
    pending = [(v, fn) for v, fn in MIGRATIONS if v >= current]
    if not pending:
        return current

    for from_version, fn in pending:
        doc = fn(doc)
        current = from_version + 1

    if "schema" not in doc:
        import tomlkit

        doc["schema"] = tomlkit.table()
    doc["schema"]["version"] = current
    settings_io.save_document(doc, path)
    return current


def load_settings(reload: bool = False) -> Settings:
    """Load settings once (cached). Pass reload=True to force re-read."""
    global _cached
    if _cached is None or reload:
        apply_migrations()
        _cached = Settings()
    return _cached


def project_root() -> Path:
    """Best-effort project root (where sabrina.toml lives)."""
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "sabrina.toml").is_file():
            return candidate
    return cwd
ings once (cached). Pass reload=True to force re-read."""
    global _cached
    if _cached is None or reload:
        apply_migrations()
        _cached = Settings()
    return _cached


def project_root() -> Path:
    """Best-effort project root (where sabrina.toml lives)."""
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "sabrina.toml").is_file():
            return candidate
    return cwd
