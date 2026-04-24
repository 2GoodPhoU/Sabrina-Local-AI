# Logging vocabulary plan — one canonical namespace before six more land

**Date:** 2026-04-23
**Status:** Draft. Audit + convention + per-plan event pre-declaration.

## Current state — audit

`sabrina-2/src/sabrina/` emits ~24 `log.info / warning / debug`
call sites. Shape is mostly `component.action[.detail]`. Flagged
inconsistencies:

- **Prefix drift.** `fw.*` for faster-whisper but `piper.*` for piper;
  `embed.*` vs `embedder.*` (same module); `rec.*` is unnamespaced.
- **No voice-loop events.** `voice_loop.py` only emits
  embedder/semantic events. `turn.started`, `turn.done`, and
  first-audio latency aren't surfaced structurally.
- **No brain events.** `brain/claude.py` and `brain/ollama.py` import
  `log` but emit nothing. Stream start, first-token, and done are
  invisible.
- **Mixed tense.** `ptt.started` (past), `piper.spawn` (imperative),
  `vision.see` (infinitive). Fix before the count doubles.
- **No `log.error` call sites.** Voice-loop top-level catches
  `Exception` and uses `console.print` — unstructured. Real gap once
  supervisor autostart lands and needs an error trail.

## Canonical vocabulary

Rule: `component.action[.detail]`, lowercase snake_case, past tense for
events (`turn.started`), imperative only for pending intents. Prefix
matches the `sabrina/<folder>/` name.

Rename map (four, no churn): `fw.loaded` → `asr.loaded`;
`fw.cuda_detect_failed` → `asr.cuda_detect_failed`; `rec.start` /
`rec.done` → `asr.rec.started` / `asr.rec.done`;
`embedder.ready` / `embedder.warmup_failed` in `voice_loop.py` →
`embed.*` (the same names `memory/embed.py` already emits). Everything
else already conforms.

## Events per component (existing + pre-declared)

This table is the contract. Plan reviewers check it before inventing
ad-hoc names.

| Component | Events | Level |
|---|---|---|
| voice_loop | `turn.started`, `turn.done`, `turn.first_audio_ms` | info |
| brain.* | `brain.stream.started`, `brain.stream.first_token_ms`, `brain.stream.done`, `brain.retry`, `brain.error` | info / warn / error |
| brain.router *(router-plan)* | `router.decided` (`tier`, `rule`, `score`) | info |
| memory | `memory.opened`, `memory.vec_unavailable`, `memory.cleared` | info / warn |
| memory.embed | `embed.loading`, `embed.ready`, `embed.warmup_failed` | info / warn |
| memory.semantic | `semantic.hits`, `semantic.retrieval_failed`, `semantic.insert_*_failed` | info / warn |
| memory.compaction *(semantic-memory-gui)* | `compaction.started`, `compaction.summary_written`, `compaction.skipped` | info |
| speaker.* | `piper.spawn`, `piper.stderr`, `piper.empty_output`, `sapi.stop_failed` | debug / warn |
| listener.ptt | `ptt.started`, `ptt.audio_status`, `ptt.max_seconds_hit` | info / debug / warn |
| listener.asr | `asr.loaded`, `asr.rec.started`, `asr.rec.done`, `asr.cuda_detect_failed` | info / debug |
| vision | `vision.see`, `vision.hotkey.armed`, `vision.capture.window_unavailable` | info / warn |
| barge-in *(barge-in-plan)* | `bargein.detected`, `bargein.cancelled`, `bargein.dead_zone_active` | info / debug |
| wake-word *(wake-word-plan)* | `wake.detected`, `wake.cooldown_suppressed` | info / debug |
| tools *(tool-use-plan)* | `tool.started`, `tool.done`, `tool.error` | info / error |
| automation *(automation-plan)* | `allow.checked`, `allow.appended`, `kill_switch.fired`, `guard.denied` | info / warn |
| avatar *(avatar-plan)* | `avatar.expression`, `avatar.lipsync.*` | info / debug |
| supervisor *(supervisor-autostart)* | `supervisor.spawned`, `supervisor.child_exit`, `supervisor.backoff`, `supervisor.budget_exceeded` | info / warn / error |
| budget *(budget-and-caching)* | `budget.recorded`, `budget.warn_threshold_crossed` | info / warn |
| state / bus | `state.transition`, `bus.dropped_event` | info / warn |

## Structured fields convention

Core set: `turn_id` (correlation, see below); `model` / `engine` /
`tier` on brain/TTS/router events; `cost_usd`, `cache_hit: bool`,
`cache_read_tokens: int` on `brain.stream.done`; `tool_name`,
`tool_args_redacted: bool` on `tool.*`; `duration_ms` (integer ms,
not float seconds) on any `*.done`; `error: str` on `*_failed` /
`*.error`, truncated at 512 chars. `component` is implicit from
logger name.

## Log levels policy

- **debug** — high-frequency per-chunk detail (piper stderr, audio
  status, VAD chunks). Off in production.
- **info** — turn-scale events, component lifecycle, success paths.
  Default level. First-audio latency (`turn.first_audio_ms`) is info,
  not debug — it's the decision-003 ship metric.
- **warning** — recoverable degradation (sqlite-vec missing, brain
  retries, allow-list denial, cooldown suppression).
- **error** — unhandled exceptions, supervisor budget exceeded, brain
  stream died, tool handler raised. Triggers supervisor respawn.

## Correlation — `turn_id` everywhere

`structlog.contextvars.merge_contextvars` is already in the processor
chain (see `logging.py`). Adding correlation is one bind at the top
of every turn in `voice_loop.py`:
`structlog.contextvars.bind_contextvars(turn_id=uuid.uuid4().hex[:8])`,
cleared in `finally`. Every event emitted from any module during that
turn picks up `turn_id=<id>` automatically; `grep turn_id=abc123
logs/sabrina.log` gives one turn's full timeline. No per-module
plumbing. A future `session_id` bind follows the same pattern.

## Audit log vs. app log — separate sinks

Automation's audit log is a compliance artifact, not debug output.
Two sinks:

- `logs/sabrina.log` — operational / app log. Rotated aggressively
  (5 MB × 3). All `log.*` calls. Add a rotating file handler next to
  the existing Rich console handler in `setup_logging()`.
- `logs/automation.log` — tool-invocation audit. Append-only;
  rotated at 5 MB × 5 (retain longer). Written by
  `automation/audit.py`, not through structlog — fixed JSON-per-line
  schema (pre / post, tool, args, result, duration). Mixing into
  structlog's free-form stream would make it harder to parse.

Third sink, deferred: `logs/supervisor.log` when autostart lands.

## One near-term migration

Four renames above, plus one new call site: `voice_loop.py:375`
replace `console.print(f"\n[red]brain error:[/] {exc}")` with
`log.error("brain.error", error=str(exc))` and keep the console
print for UX. That closes the one gap where an unhandled brain
exception isn't structurally logged.

Scope: four renames + one error call + the contextvars bind = one
session. Land before barge-in; every subsequent plan inherits the
table.
