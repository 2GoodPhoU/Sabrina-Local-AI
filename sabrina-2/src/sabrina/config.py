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


class BrainPersonaConfig(BaseModel):
    """Per-rule knobs for the Ollama persona-projection layer (P4.C1).

    Each flag gates one of the four active rules in
    ``brain.persona.project_ollama_text``. Default = all on. Disable
    individually if a rule misfires on Eric's actual usage; full
    bypass is via ``OllamaBrain(project=False)``.
    """

    ollama_strip_closing_offer: bool = True
    ollama_dehydrate_lists: bool = True
    ollama_dedup_apologies: bool = True
    ollama_truncate_long_replies: bool = True


class BrainRouterConfig(BaseModel):
    """Routing policy for the P4.C2 brain router.

    The router (``sabrina.brain.router.Router``) implements the ``Brain``
    protocol and dispatches to ``ClaudeBrain`` or ``OllamaBrain`` per
    ``policy``. ``policy`` defaults to ``claude_default`` so adding the
    block (or upgrading config schema) doesn't change today's behavior.

    - ``policy`` — ``force_local`` always Ollama; ``claude_default``
      always Claude (today's behavior); ``cost_aware`` swaps to Ollama
      once rolling MTD crosses ``[budget].warn_usd_monthly``.
    - ``enable_claude`` / ``enable_ollama`` — kill one backend without
      uninstalling it (e.g. Ollama not running on a fresh box). Both
      default True.

    Per Eric's 2026-05-15 dashboard answer at NEEDS-INPUT.md:143 (spec
    Q1 (b)), the router reads ``[budget].warn_usd_monthly`` directly —
    no per-router threshold override. Single source of truth; routing
    flip and budget warn are always pinned together.
    """

    policy: Literal["force_local", "claude_default", "cost_aware"] = "claude_default"
    enable_claude: bool = True
    enable_ollama: bool = True


class BrainConfig(BaseModel):
    default: Literal["claude", "ollama"] = "claude"
    claude: ClaudeConfig = ClaudeConfig()
    ollama: OllamaConfig = OllamaConfig()
    persona: BrainPersonaConfig = BrainPersonaConfig()
    router: BrainRouterConfig = BrainRouterConfig()


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


class RetrievalScoringConfig(BaseModel):
    """Park-style hybrid retrieval scoring weights.

    Final score per hit: ``alpha*recency + beta*importance + gamma*relevance``,
    each term in [0, 1]. Defaults are 1/1/1 — equal weight, easy mental
    model. Increase `alpha` to bias toward fresher turns; lower `gamma`
    to soften the cosine-only ranking.

    See `rebuild/drafts/research/2026-04-26-memory-architecture-evolution.md`
    for the rationale and the canonical Park et al. formulation.
    """

    # Recency weight (alpha). Exponential decay with `recency_half_life_days`.
    alpha: float = 1.0
    # Importance weight (beta). Multiplied with the per-message importance
    # column (default 0.5; 0..1 once LLM-rating lands).
    beta: float = 1.0
    # Relevance weight (gamma). Multiplied with `1 - cosine_distance`.
    gamma: float = 1.0
    # Half-life for the recency decay, in days. After this many days a
    # turn's recency contribution drops to 0.5; after 2x to 0.25; etc.
    recency_half_life_days: float = 30.0


class SemanticMemoryConfig(BaseModel):
    enabled: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 5
    max_distance: float = 0.5
    min_age_turns: int = 20
    embedder: EmbedderConfig = EmbedderConfig()
    retrieval: RetrievalScoringConfig = RetrievalScoringConfig()


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


class BudgetConfig(BaseModel):
    # Daily-driver budget thresholds (decision 001: target $0,
    # warn $10/mo, ceiling $100/mo). Values are USD month-to-date.
    # The (a)-half writes the per-turn JSONL log under ``log_dir`` and
    # exposes ``sabrina budget today/month/show`` for read-side queries;
    # the (b)-half wires the warn-threshold structlog line through the
    # voice loop. Enforcement at the ceiling is P4.C2 router work.
    target_usd_monthly: float = 0.0
    warn_usd_monthly: float = 10.0
    ceiling_usd_monthly: float = 100.0
    # Where the per-month JSONL files land. Empty = use the platform
    # default (~/.sabrina/budget). The CLI honors the
    # ``SABRINA_BUDGET_LOG_DIR`` env var directly so tests can pin this
    # without a config edit.
    log_dir: str = ""


class AutomationConfig(BaseModel):
    # Phase-4 automation safety primitives (P4.B1). Three guard rails
    # the most-dangerous-component-last framing per ROADMAP §"Phase 4"
    # requires before any real-action ToolSpec ships:
    #
    # - ``dry_run`` (default True forever per spec Q2 (a)) — every
    #   automation handler the brain dispatches gets wrapped in
    #   ``dry_run_wrap`` before invocation; the wrapper logs the would-be
    #   call and returns a synthetic dry-run shape. Eric flips this
    #   to False in TOML once Windows e2e validation (P4.B4) is in
    #   the bag.
    # - ``kill_switch_enabled`` — registers a global hotkey (default
    #   ``<ctrl>+<alt>+k``) that aborts a running automation handler.
    #   Linux/sandbox installs use a no-op stub via the
    #   ``_LISTENER_FACTORY`` injection seam; pynput.GlobalHotKeys
    #   only fires on Windows.
    # - ``destructive_actions`` — forward-compat hook for the P4.B3
    #   allow-list. Default empty so the schema bump is paid here once,
    #   not again when P4.B3 ships its runtime guard.
    dry_run: bool = True
    kill_switch_enabled: bool = True
    kill_switch_hotkey: str = "<ctrl>+<alt>+k"
    destructive_actions: list[str] = Field(default_factory=list)


class WriteClipboardToolConfig(BaseModel):
    enabled: bool = True
    # Hard cap; handler also clamps internally. Keep in sync with the
    # ToolSpec input_schema's maxLength.
    max_bytes: int = 100_000


class ToolsConfig(BaseModel):
    # Master switch for the tool-use surface. Off by default until the
    # brain wires tool-call handling end-to-end (per
    # `rebuild/drafts/tool-use-plan.md`). Even with `enabled=false`, the
    # `BUILTIN_TOOLS` registry is importable so tests + `sabrina
    # tool-test` (when shipped) still work.
    enabled: bool = False
    # Allow-list of tool names. Empty list = all registered tools allowed.
    allowed: list[str] = Field(default_factory=lambda: ["write_clipboard"])
    write_clipboard: WriteClipboardToolConfig = WriteClipboardToolConfig()
    # P4.B2 send_hotkey ToolSpec — registers the keyboard-shortcut
    # action handler into ``BUILTIN_TOOLS`` when True. Flat-flag shape
    # per spec Q3 (a); flip to True only after P4.B4's Windows e2e
    # validation lands. Default False keeps the dangerous-tool surface
    # gated on a config edit Eric can audit.
    send_hotkey_enabled: bool = False


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
    budget: BudgetConfig = BudgetConfig()
    automation: AutomationConfig = AutomationConfig()
    tools: ToolsConfig = ToolsConfig()
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
