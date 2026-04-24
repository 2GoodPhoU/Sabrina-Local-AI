# Decision 008: Foundational refactor bundle (schema + log privacy + log rotation) shipped

**Date:** 2026-04-24
**Status:** Shipped. Unlocks privacy-posture, config-schema-audit, and logging-vocabulary plans.

## The one-liner

Three small-but-cross-cutting items landed in one session — a
`[schema].version` hook with an empty migration chain, a redacting +
length-capping pair of structlog processors, and a rotating file sink
at `logs/sabrina.log`. Each of the three draft plans that converged
on this bundle can stop saying "…once the logging/config refactor
happens" and move to independently-shippable.

## What shipped

| Piece | Where | Notes |
|---|---|---|
| `[schema]` table + `SchemaConfig` + `CURRENT_SCHEMA_VERSION` | `config.py` + `sabrina.toml` | One field: `version: int = 1`. Field name is `schema_` to avoid pydantic's reserved `schema()`; alias="schema" maps TOML. |
| `apply_migrations()` + `MIGRATIONS: list[(int, fn)]` | `config.py` | Empty list today — the hook lands before the first rename so the rename PR isn't also the PR that builds the machinery. Runs via tomlkit + atomic write. |
| `redact_secrets` structlog processor | `logging.py` | Walks nested dicts; replaces values of `api_key`, `authorization`, `anthropic_api_key`, `password`, `secret`, `token`, and any `*_token` key with `***REDACTED***`. Case-insensitive. |
| `truncate_long_values` structlog processor | `logging.py` | Caps string values at `MAX_VALUE_CHARS = 512` with a `...(truncated)` marker. Top-level only (no recursion cost). |
| `RotatingFileHandler` sink at `logs/sabrina.log` | `logging.py` | 5 MB × 3 rotation. Attached to the stdlib root logger; structlog tees a JSON-per-line copy through a custom processor. |
| `populate_by_name=True` on `Settings.model_config` | `config.py` | Required so the `schema_` / `schema` alias round-trips cleanly through both TOML and env vars. |
| Tests | `tests/test_smoke.py` | 4 added: schema version, redact unit, truncate unit, file-sink end-to-end. |

## Design calls

### Schema version hook, not schema migration engine

Option A was ship nothing yet and build the migration machinery only
when the first rename needs it. Option B was build a generalized
migration framework (up/down, per-section, dependency-ordered). Neither
was picked.

Option C — what shipped — is a minimal forward-only migration list plus
the `[schema].version` field. `MIGRATIONS: list[tuple[int, Callable]]`,
appended to in order, no rollback, no DAG. When the first rename lands,
the author adds one entry and bumps `CURRENT_SCHEMA_VERSION`. When
`apply_migrations` runs, it reads the on-disk version, runs any
newer-than entries, writes back via the existing atomic `settings_io`
pattern.

This is the lightest-weight version of the config-schema-audit plan's
recommendation. No migrations today means no behavior change today —
the code path that reads the TOML, finds nothing to do, and returns
early is the happy path. First real migration exercises the machinery
for real; until then it's paid-for infrastructure.

### Field name `schema_`, TOML key `schema`

Pydantic v2 reserves `schema` on BaseModel (deprecated method, but the
name still aliases when resolving attributes). Using `schema` directly
as a field name works in practice but produces a DeprecationWarning
and is load-bearing on pydantic internals; not worth the fragility.
`schema_: SchemaConfig = Field(..., alias="schema")` with
`populate_by_name=True` gives us the right surface on both sides — TOML
`[schema]` table and Python `settings.schema_.version`.

### Redaction is "replace with marker", not "drop the key"

An event that includes `api_key=...` is still informative even without
the key value — it tells us an auth call happened. Dropping the key
entirely loses that signal. Replacing the value with `***REDACTED***`
preserves the event shape for grep/jq/analysis.

### Two sinks, JSON on disk, pretty on console

The file sink writes JSON-per-line via a custom `_make_file_tee`
processor placed *before* `ConsoleRenderer` in the structlog chain.
Console gets the rendered pretty output as before; disk gets machine-
readable JSON for `grep`, `jq`, or future log-analytics. Same events,
two representations, no format coupling.

### Clear-handlers pattern in `setup_logging`

`setup_logging` is now idempotent — it clears existing handlers on
the stdlib root logger before attaching new ones, and sets
`cache_logger_on_first_use=False` on structlog. Tests can call it
multiple times with different log paths without leaking file handles.
Small thing, but decision 004's settings GUI will need this when it
starts live-reloading config.

## What works well

- **Zero churn for existing callers.** `setup_logging("INFO")` still
  works; the new `log_file=` kwarg is optional and tests use a
  `tmp_path`. Every existing call site in `cli.py` is untouched.
- **Redaction covers the realistic careless cases.** If someone logs
  `api_key=secret.get_secret_value()`, the processor catches it before
  it hits any sink. The catch-all `*_token` matches `refresh_token`,
  `bearer_token`, whatever shows up later.
- **The file is JSON, not `ConsoleRenderer` output.** Pretty-rendered
  text with ANSI colors is hostile to `jq`. Sending the pre-render
  event_dict to the file keeps the tee structured.
- **Guardrail #2 holds.** No new abstraction: three processors, one
  module constant, one `BaseModel` subclass. Everything is a function
  or a dataclass.
- **~145 lines total** (config: ~50, logging: ~90, sabrina.toml: ~5,
  tests: ~75). Under the 150-line target the bundle was planned for
  minus tests.

## Thin spots

### Schema / migrations
- **No migrations to exercise the machinery.** The test asserts
  `version == CURRENT_SCHEMA_VERSION` but doesn't run a migration
  round-trip. First real rename will validate end-to-end.
- **`apply_migrations` runs on every `load_settings(reload=True)`.**
  File I/O on every settings load. Fine while the file is a few KB;
  worth a `mtime` cache if we ever load settings on every turn.
- **No `extra="allow"` flip yet.** The audit recommended flipping
  `Settings.model_config` to `extra="allow"` plus a warn-log of unknown
  top-level keys, so deprecated keys become visible. Scope-cut from
  this bundle — ship with the schema version first, flip extra in a
  follow-up when the first deprecation ships.

### Logging
- **`truncate_long_values` is shallow.** Only top-level event-dict
  string values. A deeply-nested tool-call payload could still carry a
  multi-KB field. Acceptable today; tool-use plan's `tool_args_redacted`
  flag is a natural complement when that ships.
- **Redaction key list is a `frozenset`, not configurable.** If a
  future connector introduces a new secret field name (e.g. `cookie`,
  `session_id`), we have to edit `logging.py`. A config-level
  `logging.redact_keys` list is a two-line change when the first such
  key arrives.
- **File sink captures structlog events only via the tee processor.**
  Events logged through the stdlib `logging.info("...")` call path
  land in the file (they go through the root logger's handlers) but
  as plain text, not JSON. Mixed format inside one file. Acceptable
  because structlog is the default in this codebase; stdlib calls are
  rare.
- **Rotation cadence is size-only.** No time-based rotation. 5 MB × 3
  is ~15 MB of log history; for a quiet day that's weeks, for a loud
  debug session it can roll over in an hour. Fine as a default; add
  a time rotator if the debug-session case becomes common.

### Settings GUI
- **New `[schema]` block isn't exposed as a tab.** Correct — the
  field is internal (`Do not edit by hand`). But the existing GUI
  autodiscovers tabs from section names; need to explicitly blacklist
  `schema` when 004's GUI next touches `sabrina.toml`. Thin; one-line
  fix in `gui/settings.py` when the next edit there happens.

## Alternatives worth researching

1. **`structlog.stdlib.LoggerFactory()` + `ProcessorFormatter`.** The
   "official" structlog-stdlib integration, versus the custom tee
   processor we shipped. Cleaner, but non-trivial behavior shift
   (RichHandler receives rendered events, not strings). Revisit if the
   mixed-format issue in the file sink becomes a problem.
2. **JSON structured logging with `orjson` or `msgspec`.** Faster
   than stdlib `json`. Almost certainly not worth the dep just for log
   events.
3. **sentence-transformers warning suppression.** Not part of this
   bundle, but worth noting: `memory/embed.py:77` emits a
   `FutureWarning` about the `get_sentence_embedding_dimension` →
   `get_embedding_dimension` rename. Cheap cleanup when the embedding
   model is next touched.
4. **`[logging].file_path`, `[logging].max_bytes`, `[logging].backup_count`.**
   Three config fields to make rotation tunable from `sabrina.toml` +
   the settings GUI. Not needed today; trivial additive extension when
   the defaults bite.

## Why this one went in one session

Three drafted plans converged on the same ~150-line refactor. Shipping
any one of them in isolation would have copied half of the changes
into that component's PR, fragmenting the logging / config / privacy
story across three commits. Bundling means:

- **One `sabrina.toml` header edit**, not three.
- **One `config.py` header docstring update** documenting contributor
  conventions, not three piecemeal additions.
- **One test section**, not one-per-plan.
- **Every downstream plan starts from a foundation it can assume.**
  The `tool-use-plan.md` can call `log.info("tool.started", args=...)`
  and know arguments are redacted + length-capped without its own
  logic. The `automation-plan.md` can use a separate audit sink and
  not worry about redaction double-dipping.

Bundle-first was the right move here. Future bundles should remain
rare — this one earned it by being foundational.

## Ship criterion check

Decision 006's daily-driver gap list is unchanged; this bundle isn't a
component. It's infrastructure that removes the "…once the refactor
happens" blocker from downstream plans.

## Where the new code lives

```
sabrina-2/src/sabrina/
├── config.py          # +SchemaConfig, +CURRENT_SCHEMA_VERSION, +MIGRATIONS,
│                      #  +apply_migrations, populate_by_name=True
├── logging.py         # +redact_secrets, +truncate_long_values,
│                      #  +_make_file_tee, +RotatingFileHandler, log_file kwarg
sabrina-2/
├── sabrina.toml       # +[schema].version block at top
└── tests/test_smoke.py # +4 tests in "foundational refactor bundle" section
```

## Next session — pick one (unchanged menu)

Bundle shipping doesn't change the menu. The 8 drafted component plans
are all still independently-shippable and their recommended order
still holds:

1. **Barge-in (Silero VAD + cancellable TTS)** — biggest daily-driver
   gap. Needs the `cancel_token` Brain-protocol extension first.
2. **Wake word (openWakeWord)** — hands-free.
3. **Personality plan** — calibration conversation with Eric upstream
   of every brain prompt; worth doing before the avatar arc starts.
4. **Budget tracker + prompt caching** — cost observability; small
   lift.
5. **Local VLM fallback** — privacy + offline vision.
6. **Summary compaction + semantic-memory GUI (007b)** — follow-ups
   to decision 007.
