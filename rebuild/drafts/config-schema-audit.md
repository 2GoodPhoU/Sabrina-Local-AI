# Config schema audit — governing `sabrina.toml` before it doubles

**Date:** 2026-04-23
**Status:** Draft. Audit + one concrete near-term refactor.
**Why now:** `sabrina.toml` is 114 lines across 12 sections today.
The drafted plans roughly triple that. Stake the governance flag
before the next five component plans land.

## Current state inventory

`sabrina.toml` today (from the live file + `config.py`):

```
[brain]             default
[brain.claude]      model, fast_model, max_tokens
[brain.ollama]      host, model, fast_model
[tts]               default, output_device
[tts.piper]         binary, voice_model, speaker_id, length_scale
[tts.sapi]          voice, rate
[asr]               default, input_device
[asr.faster_whisper] model, device, compute_type, beam_size, language
[vision]            trigger, hotkey, model, monitor, max_edge_px
[memory]            enabled, db_path, load_recent
[memory.semantic]   enabled, embedding_model, top_k, max_distance, min_age_turns
[logging]           level
```

Backed in `config.py` by nested `BaseModel` classes: `ClaudeConfig`,
`OllamaConfig`, `BrainConfig`, `PiperConfig`, `SapiConfig`, `TtsConfig`,
`FasterWhisperConfig`, `AsrConfig`, `VisionConfig`, `MemoryConfig`,
`SemanticMemoryConfig`, `LoggingConfig` — plus the top-level
`Settings(BaseSettings)`. Source precedence: init kwargs > env >
`.env` > `sabrina.toml` > defaults.

## Projected additions (per drafted plans)

| New section | Source plan |
|---|---|
| `[barge_in]` | barge-in-plan.md |
| `[wake_word]` | wake-word-plan.md |
| `[budget]` | budget-and-caching-plan.md |
| `[brain.router]` + `[brain].default = "router"` | router-plan.md |
| `[memory.compaction]` | semantic-memory-gui-plan.md |
| `[vision.ocr]`, `[vision.archive]`, `[vision].capture_mode` | vision-polish-plan.md |
| `[vision.local]`, `[vision].tier` | local-vlm-plan.md |
| `[supervisor]` | supervisor-autostart-plan.md |
| `[avatar]`, `[avatar.expressions]` | avatar-plan.md |
| `[tools]`, `[tools.get_time]`, `[tools.read_clipboard]`, `[tools.search_memory]` | tool-use-plan.md |
| `[automation]`, `[automation.tools.list_files]`, `[automation.tools.launch_app]` + `[[.apps]]`, `[automation.tools.list_open_windows]` | automation-plan.md |

Ship-order is roughly: barge-in → wake-word → budget+caching → tool-
use → router → automation → avatar → supervisor. Every one touches
`sabrina.toml` and `config.py`.

## Schema validation — the existing pattern holds

pydantic-settings is in use via `Settings(BaseSettings)` + nested
`BaseModel` fields. Keep it. Rules for every new section: one
`BaseModel` per TOML section; every field has a default; master
switches default to `enabled = false` when the section depends on
unshipped infrastructure (mirrors `[memory.semantic]` and
`[wake_word]`); `Literal[...]` for enumerable string fields so
pydantic catches `trigger = "allways"` at load time; env-var override
via `SABRINA_<SECTION>__<KEY>` is already wired and works for nested
sections — AoT blocks (`[[...apps]]`) do NOT round-trip via env vars,
so expect GUI or TOML edits for those.

Flat env-var-style schemas were considered and rejected: decision 004
picked nested BaseModel + tomlkit; every shipped section follows it;
changing now churns working code for no gain.

## Defaults + override hygiene

Every field has a default in `config.py` mirrored by a comment in
`sabrina.toml` that survives GUI saves (decision 004). A missing key
uses the default silently; a wrong-type key raises on load; an
unknown key is dropped because `Settings` has `extra = "ignore"` —
kind on typos, bad for migrations. Propose flipping to
`extra = "allow"` plus a post-init warn-log of unknown top-level keys
so deprecations are visible. Array-of-tables: per the tomlkit canary
in `automation-plan.md`, mutating AoT blocks must live at the end of
their subtree; enforce via `append_allow_entry()` sanity check and a
file-header rule.

## Config migration story — the real gap

No story today. Rename a field (e.g. `[memory.semantic] enabled` →
`[memory.embeddings] enabled`), and any user with the old key silently
loses the setting (since `extra = "ignore"`). Proposal — minimal,
one-session scope:

```toml
[schema]
version = 1
```

`config.py` gains `CURRENT_SCHEMA_VERSION = 1` and a
`MIGRATIONS: list[Callable[[TOMLDocument], TOMLDocument]]` list.
`load_settings()` reads raw TOML via tomlkit first, checks
`[schema].version`, runs pending migrations in order (1→2→3→...),
bumps the field, writes atomically (same tempfile+replace as
`settings_io.py`), then hands the document to pydantic. One
migration per rename/move/delete, named
`v1_to_v2_rename_memory_semantic_to_embeddings`. One test per
migration plus one "full chain from v1 to current" guard. Unblocks
every future rename without breaking older configs; document the
"add a migration" rule in `config.py`'s header.

## Sensitive-value handling

`ANTHROPIC_API_KEY` is loaded via `SecretStr` from `.env`; `AliasChoices`
accepts the canonical upstream name. It does not live in
`sabrina.toml`. Keep. Rule for future: any regeneratable secret (API
keys, tokens, passwords) lives in `.env` as `SABRINA_<NAME>`, not
TOML — document in the file header. The settings GUI excludes
`SecretStr` fields de facto today; make it an explicit allow-list so
a new Secret doesn't accidentally surface in a tab.

## Recommended near-term action (one refactor, one session)

Before the next five plans land (barge-in, wake-word, budget, tool-
use, router), do this one pass:

1. **Add `[schema] version = 1` + empty migration chain** to
   `config.py` and `sabrina.toml`. No actual migration yet — the
   purpose is to land the hook so the first real rename isn't also
   the rename that has to build the machinery.
2. **Flip `extra = "ignore"` to `extra = "allow"`** on
   `Settings.model_config`, add a warn-log of unknown top-level keys
   in `load_settings()`. Deprecated keys become visible.
3. **Write a one-paragraph contributor note in `config.py`'s module
   docstring**: one BaseModel per section, every field has a default,
   new sections ship off-by-default when they need external setup,
   AoT blocks live at the end of their subtree, secrets live in
   `.env`. Everything the audit above implies, in one place.
4. **Add `test_schema_version_present_and_current`** —
   `load_settings().schema.version == CURRENT_SCHEMA_VERSION`.

This is a ~100-line diff with three tests. It does not bikeshed the
rest of the file. It lets every subsequent plan add its block without
re-litigating how config grows. Defer the actual migrations until the
first rename; ship the hook now.
