# Decision 008: Foundational refactor bundle — schema versioning, log redaction, rotating file sink

**Date:** 2026-04-24
**Status:** Shipped. Not a new component; the three smallest items from
three different drafted plans (`config-schema-audit`, `privacy-posture`,
`logging-vocabulary`) rolled into one ~150-line refactor so the next
five component plans don't each have to re-litigate how config grows,
how secrets travel, or where app logs land.

## The one-liner

Sabrina's config file now carries a `[schema].version` field and an
empty (for now) migration chain, structlog output now has secrets
redacted and long values truncated before rendering, and all log events
also flow to a rotating `logs/sabrina.log` sink (5 MB × 3) alongside the
existing Rich console output. Everything additive; no behavior changes
for the happy path.

## What shipped

| Piece | Where | Notes |
|---|---|---|
| `SchemaConfig` + `schema_: SchemaConfig = Field(default_factory=SchemaConfig, alias="schema")` on `Settings` | `config.py` | TOML `[schema].version` round-trips through pydantic. Python attribute uses trailing underscore because `BaseSettings` parent class still reserves `schema` (UserWarning otherwise); the alias keeps the TOML key unadorned. `populate_by_name=True` added to `model_config` so both forms are accepted. |
| `CURRENT_SCHEMA_VERSION = 1` + `MIGRATIONS: list[(int, fn)]` | `config.py` | Bump `CURRENT_SCHEMA_VERSION` when appending to `MIGRATIONS`. Empty today — lands the hook before the first real rename. |
| `apply_migrations(toml_path)` called from `load_settings()` | `config.py` | No-op when `MIGRATIONS` is empty. Reads TOML via `tomlkit` (keeps comments), runs pending migrations, bumps version, writes atomically via `settings_io.save_document`. |
| `redact_secrets` structlog processor | `logging.py` | Walks nested dicts; replaces values of `api_key`, `authorization`, `anthropic_api_key`, `password`, `secret`, `token`, and any `*_token` key with `***REDACTED***`. Case-insensitive. |
| `truncate_long_values` structlog processor | `logging.py` | Caps string values at `MAX_VALUE_CHARS = 512` with a `...(truncated)` marker. Non-string values pass through. |
| Rotating file sink | `logging.py` | `RotatingFileHandler("logs/sabrina.log", maxBytes=5MB, backupCount=3)` attached to the root stdlib logger. `setup_logging(level, log_file=None)` accepts a path for tests. |
| Structlog file-tee processor | `logging.py` | After redact + truncate, writes each event as a JSON line to the same file handler. Console path (`ConsoleRenderer`) untouched. |
| `[schema]` block | `sabrina.toml` | Two-line header + `version = 1`. Placed at the top. |
| Tests | `tests/test_smoke.py` | `test_schema_version_present_and_current`, `test_logging_redacts_known_secrets`, `test_logging_truncates_long_values`, `test_logging_file_sink_writes`. |

## Design calls

### Land the migration hook before the first real rename

The point is *not* to migrate anything today. It's to avoid a future PR
that has to rename `[memory.semantic]` *and* invent the machinery to
migrate it in the same patch. The version field + migration list are the
contract; the first caller of that contract (the first rename) is cheap
once the contract exists.

### `MIGRATIONS: list[(int, fn)]` over a registry decorator

Considered: `@migration(1)` decorator + implicit registration. Rejected:
one more level of cleverness for three characters saved. A plain list
is grep-able and orderable.

### Redact by key, not by value heuristic

Considered: regex for `sk-ant-`, hex-blob detectors, etc. Rejected:
false positives and false negatives both, plus slower per-event.
Key-based redaction is deterministic — callers control the key names
and can widen `_SENSITIVE_KEYS` or add a `*_token` sibling rule if a
new shape appears.

### 512-char cap on string values

Arbitrary but justified: a sentence of prose is ~100-200 chars, a long
tool argument is ~300-500, anything past 512 is almost always a
transcript blob, a screen-frame byte dump, or an exception with
multi-KB context. Cutting at 512 keeps logs skimmable without losing
the event name (which is a key, not a value — keys aren't truncated).

### File-tee processor, stdout-unchanged

Considered: route structlog fully through stdlib (`LoggerFactory()` +
`ProcessorFormatter`) so one path feeds both console and file.
Rejected for now — it's a bigger change and would need ConsoleRenderer
to move into a stdlib formatter, which bends the existing pretty
output. The tee processor is ~20 lines and preserves the console path
byte-for-byte.

### JSON lines in the file, pretty output in the console

File format is JSON per line — `jq` / `grep` friendly, trivially
parseable, carries the structured event dict as-is. Console uses
`ConsoleRenderer(colors=True)` for human readability. Different
audiences, different renders, same data.

## What works well

- **The bundle unblocks five drafted plans.** Every downstream plan
  (barge-in, wake-word, budget, tool-use, automation) was carrying a
  "once the logging/config refactor happens..." caveat. That caveat is
  now gone.
- **No new files in `sabrina/`.** Everything lands in existing modules
  (`config.py`, `logging.py`). Anti-sprawl guardrail #2 held — no new
  abstractions added beyond what the first caller needs.
- **Zero-migration migrations work.** `apply_migrations()` runs on
  every `load_settings()` and is a no-op when `MIGRATIONS` is empty;
  the test that catches regressions here is the one that already
  asserts `s.schema.version == CURRENT_SCHEMA_VERSION`.
- **Tests stay fast.** All four new tests are pure-function or
  `tmp_path`-scoped; no wall-clock waits.

## Thin spots

### Schema / migrations

- **`apply_migrations` is fire-and-forget.** It writes back the bumped
  `[schema].version` but doesn't log what it did. First time a real
  migration runs, we'll want a structured event
  (`config.migration.applied from=N to=M`) so the user sees it.
- **No dry-run.** `apply_migrations(dry_run=True)` would let the CLI
  preview what a pending migration would change. Defer until the first
  real migration lands.
- **Version stored as plain `int`.** Works, but a `(major, minor)`
  scheme would let us distinguish "breaking rename" from "field
  addition". Not needed yet.
- **`extra="allow"` + unknown-key warn-log** was recommended by the
  audit but skipped to keep scope tight. Current behavior (`extra="ignore"`)
  means deprecated keys are silently dropped on read. Worth doing when
  the first real rename lands — otherwise the test for the rename
  itself is masked.

### Log hygiene

- **Key list is hardcoded.** Widening `_SENSITIVE_KEYS` requires a
  source edit. A `[logging].redact_keys: list[str]` config option
  would let users add custom keys without a code change. Not needed
  today (Sabrina is single-user) — worth it if anyone else runs it.
- **Nested redaction only runs on dicts.** A pydantic model in an event
  dict won't have its fields walked. Callers who log whole models will
  leak. Mitigation: callers log scalar kwargs, not whole objects —
  convention, not enforcement.
- **No per-handler level control.** The file handler runs at the same
  level as the root logger. Separating "everything at DEBUG to file,
  INFO to console" is a one-liner we didn't need yet.
- **Rotation is size-based.** 5 MB × 3 = 15 MB cap. Time-based rotation
  (daily) may be nicer for "what did Sabrina do yesterday?" — defer to
  operator need.

### Logging vocabulary (scope-trimmed)

The full `logging-vocabulary-plan.md` includes a rename pass
(`fw.loaded` → `asr.loaded`, etc.), a `turn_id` contextvars bind, and
a brain-events shelf. None of that shipped in this bundle — only the
redaction + file sink. Rename pass is its own cheap-but-touchy chore
(affects grep targets in scripts); flag for a future session as
"logging vocabulary normalization".

## Alternatives worth researching

1. **`structlog.stdlib.ProcessorFormatter` integration.** Route
   structlog entirely through stdlib so there's one path to both sinks.
   Cleaner long-term; worth doing when we add a third sink
   (`logs/automation.log` for tool audit) and the current tee processor
   starts to feel like three tees.
2. **JSON-only "audit" mode.** For compliance-style capture, a
   `[logging].json_only = true` that drops the Rich console renderer
   and writes JSON to both stderr and file. Not for Eric's dev loop,
   but for a future "supervisor runs Sabrina headless" posture.
3. **Automatic PII scrubbing (email/phone regex) on free-text values.**
   Stronger than key-based redaction but expensive and lossy. Only
   interesting if Sabrina is ever used with third-party content (it
   isn't today — the user is the only principal).

## Where the new code lives

```
sabrina-2/src/sabrina/
├── config.py    # +SchemaConfig, +CURRENT_SCHEMA_VERSION, +MIGRATIONS,
│               #  +apply_migrations, +schema field on Settings,
│               #  +populate_by_name=True
└── logging.py   # +_SENSITIVE_KEYS, +MAX_VALUE_CHARS, +TRUNCATION_MARKER,
                 #  +redact_secrets, +truncate_long_values,
                 #  +_make_file_tee, +log_file arg on setup_logging,
                 #  +RotatingFileHandler wiring
sabrina-2/
├── sabrina.toml          # +[schema] block at top
└── tests/test_smoke.py   # +4 tests
```

## Ship-criterion check

Per decision 006's "daily-driver gap" list, this bundle doesn't close
any of them directly — it's infrastructure. But it unblocks the five
plans (barge-in, wake-word, budget, tool-use, automation) that *do*.

Per Eric's working-style guardrails:
- No new abstraction added — `schema`/`MIGRATIONS`/`redact_secrets` are
  all first-use concrete.
- No module past 300 lines — `config.py` is ~240, `logging.py` is
  ~185 (up from ~60 but justified in the new header).
- Test suite still fast (< 5s).
- Atomic commit for the whole bundle.
- Decision doc filed.

## One thing to feel good about

Three drafted plans collapsed into one execution session. Every
downstream plan loses its "once the refactor happens" preamble. The
one rule that's always been worth enforcing — "land the hook before
the first caller needs it" — is now enforced for schema migrations,
too, not just protocols.

## Next session — the menu holds

The menu from decision 007 carries over. The foundational refactor
is done; the two natural next moves are:

- **Infra-first:** barge-in (closes the biggest daily-driver gap,
  needs cancel-token in Brain protocol first) → wake-word →
  supervisor+autostart.
- **Character-first:** personality calibration (the "inferred vs.
  stated" block in `personality-plan.md` needs Eric input) →
  onboarding.

Both plans are ready to review; pick one in the next session.
