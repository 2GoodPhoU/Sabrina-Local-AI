# When you return — Sabrina rebuild quickstart

**Date:** 2026-04-24
**Purpose:** single entry-point for starting a new chat session. Read this
first. Then act.

## State of play

Decision 007 (semantic memory) was validated on Windows earlier this
session (first-audio 1.62s warm). Decision 008 (foundational refactor
bundle) was shipped later the same session — `[schema].version` hook
with empty migration chain + redacting structlog processor + 512-char
value cap + rotating file sink at `logs/sabrina.log` (5 MB × 3). Tests
were added but the code has NOT been smoke-tested end-to-end on Eric's
Windows box yet. That's the first thing to do on return.

## First-time-you-sit-down sequence

**Step 1 — Verify decision 008 in-repo.** From `sabrina-2/`:

```powershell
uv run pytest -q
uv run sabrina voice   # briefly; Ctrl+C
Test-Path .\logs\sabrina.log
Get-Content .\logs\sabrina.log -Tail 5
```

Expected: tests pass (52 now; was 48), voice loop starts, log file
exists and contains JSON-per-line events. Bonus spot check: if any
line contains `api_key` as a key, its value should be `***REDACTED***`.

If anything fails, see "If decision 008 validation fails" at the
bottom.

**Step 2 — Commit 008 once green.** The code landed this session but
hasn't been committed yet (Eric wasn't at the keyboard).

```powershell
git add src/sabrina/config.py src/sabrina/logging.py src/sabrina/memory/embed.py sabrina.toml tests/test_smoke.py ..\rebuild\decisions\008-foundational-refactor-bundle.md ..\rebuild\ROADMAP.md ..\rebuild\when-you-return.md
git status   # verify — nothing else unexpected
git commit --no-verify -m "feat(refactor): schema version + log redaction + rotating file sink (decision 008)"
```

`--no-verify` because `pre-commit` isn't installed in the venv yet —
noted as a thin spot; cheap fix is `uv add --dev pre-commit && uv run
pre-commit install`.

**Step 3 — Delete the now-stale contingency draft.** `rebuild/drafts/
008-sqlite-vec-on-windows.md` was a pre-written fallback in case
`enable_load_extension` was missing on Eric's Python. Validation went
green on 2026-04-24, so its own header says "delete this file."

```powershell
Remove-Item ..\rebuild\drafts\008-sqlite-vec-on-windows.md
```

**Step 4 — Pick next component.** Natural ordering from the master
index (unchanged from last session's menu):

- **Infra-first path:** barge-in → wake-word → supervisor+autostart.
  Shared `AudioMonitor` primitive between barge-in and wake-word is
  why they belong adjacent.
- **Character-first path:** personality → onboarding. Lock in voice +
  first-run state machine before the avatar arc starts.

Don't prescribe. Ask Eric which path; both are ready.

## Decisions awaiting glance-and-approve

Recommendation blocks attached; Eric just needs to eyeball:

- `rebuild/drafts/router-plan.md` — brain router (3 questions).
- `rebuild/drafts/tool-use-plan.md` — Brain protocol tools (3 questions).
- `rebuild/drafts/asr-upgrade-plan.md` — `base.en` → `large-v3-turbo`
  (2 questions).
- `rebuild/drafts/local-vlm-plan.md` — Ollama-hosted VLM (2 questions).
- `rebuild/drafts/vision-polish-plan.md` — no-VLM capture polish
  (1 question).

## Personality plan — calibration callout

`rebuild/drafts/personality-plan.md` has a "Where these signals came
from — explicit vs. assumed" section. The voice was **inferred** from
anti-sprawl premise and decision-doc tone rather than stated by Eric.
Calibrate that section with Eric before shipping — upstream of every
brain prompt and the avatar cue track, so drift here is expensive.

## Thin spots from decision 008 worth tracking

- `pre-commit` hook not installed in venv (bypassed with
  `--no-verify`). Cheap fix as above.
- `Settings.model_config` still has `extra="ignore"`; the audit
  recommended flipping to `"allow"` + warn-log. Deferred to the first
  deprecation that needs it.
- `memory/embed.py` previously emitted a `FutureWarning` about the
  sentence-transformers rename. Fixed in this session (switched to
  `hasattr` so we never touch the deprecated attribute on modern
  installs); unrelated to the bundle but tiny and safe to bundle with
  or ship separately.
- GUI will auto-render the new `[schema]` section as a tab next time
  `gui/settings.py` is edited — needs an explicit blacklist entry.

## If decision 008 validation fails

| Symptom | Likely cause | What to check |
|---|---|---|
| `test_schema_version_present_and_current` fails | TOML `[schema]` block not picked up by pydantic-settings, or `SchemaConfig` default drifted from `CURRENT_SCHEMA_VERSION` | `uv run sabrina config-show \| findstr schema`; should print the block. Python attribute is `settings.schema_` with `alias="schema"` on the Field — `BaseSettings` parent still reserves `schema`, so the trailing underscore is required to suppress the UserWarning. |
| `test_logging_redacts_known_secrets` fails | Processor not registered, or event_dict mutation order changed | Read `logging.py`; check that `redact_secrets` is in the `structlog.configure(processors=...)` list. |
| `test_logging_file_sink_writes` fails (no file) | `setup_logging` didn't create `logs/`; dir permissions on `tmp_path` | `mkdir` logic in `setup_logging` line ~130. |
| `test_logging_file_sink_writes` fails (file empty) | Tee processor didn't fire, or file handler didn't flush | Confirm `_make_file_tee` is in the chain **before** `ConsoleRenderer`. |
| Voice loop crashes at startup | Circular import (config → settings_io → config) | `apply_migrations` imports `settings_io` lazily; verify. |
| Fresh `logs/sabrina.log` file never gets written at runtime | Root logger handlers cleared without re-attach | `setup_logging`'s handler clear-and-add block. |

## Where everything lives

```
rebuild/
├── ROADMAP.md                              # roadmap + progress-at-a-glance
├── decisions/001–008-*.md                  # shipped decisions
├── validate-*.md                           # per-component Windows validation procedures
├── drafts/
│   ├── remaining-components-plan.md        # master planning index
│   ├── *-plan.md                           # per-component plans
│   ├── avatar-animation-graph.svg
│   └── old-repo-migration-audit.md
```

## If you're a new Claude assistant reading this

1. Read the memory index (`MEMORY.md`) and the files it links.
2. Read `rebuild/drafts/remaining-components-plan.md` — the master
   index.
3. Follow Eric's working style below. Don't ask him to re-explain
   context that's in memory or the master index.

## Working-style reminders

- **Decision doc per shipped component.** Match the voice of 002–008:
  terse prose, bullets sparingly, "thin spots" section at end,
  alternatives-to-research list.
- **Anti-sprawl.** No new abstraction until the second caller exists.
  No module past 300 lines without justification in the header.
- **Ship-one-validate-next.** No component starts until the previous
  one is in main with a smoke test.
- **Validation procedure** (`validate-*.md`) ships with each component
  before Eric calls it done on Windows.
- **Recommendations-attached pattern** for drafts with open questions
  — rationale + override path makes review cheap.
- **Additive protocol extensions** over new protocols — `Message.images`
  and `system_suffix` are the patterns.
- **Memory guardrails.** Don't save code patterns, git history, or
  conventions derivable from the repo. Do save surprises, corrections,
  and validated non-obvious calls.
