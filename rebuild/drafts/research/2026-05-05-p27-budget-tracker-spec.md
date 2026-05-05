# P2.7 — Budget tracker (telemetry hook + `sabrina budget` CLI) — spec

**Date:** 2026-05-05
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 2 → **P2.7 Budget tracker — telemetry hook + `sabrina budget` CLI** (`[linux-runnable] [partial-dod-eligible] [P1] [M]`).
**Predecessor:** `rebuild/drafts/budget-and-caching-plan.md` (2026-04-23, "ready-to-ship draft"). That doc bundles budget-observability and prompt-caching into one ship. **This spec narrows to the queue entry's scope (budget telemetry only).** Prompt-caching belongs to a Phase-4 router-adjacent ship (decision 001 cost ceiling enforcement plus `cache_control` on the system block); decoupling matches the queue's split between P2.7 (Phase 2 daily-driver readiness) and P4.C2 (router budget gate).
**Scope:** mixed-surface — names the (a) Linux-runnable / (b) Windows-required boundary so the Planner's split authority can stage the (a)-half cleanly. Off-limits: legacy `services/`/`utilities/`, `rebuild/decisions/`.

---

## What this item is

Make Sabrina's Claude spend visible. Today, every `claude.py` turn already carries token counts in `Done.input_tokens` / `Done.output_tokens` (see `sabrina-2/src/sabrina/brain/protocol.py:85-92`) and surfaces them through `ThinkingFinished` (see `sabrina-2/src/sabrina/events.py:46-50`) — but nothing tots them up against the $0/$10/$100 thresholds decision 001 committed to. P2.7 closes Phase-2 daily-driver readiness item #5 by (1) attaching dollar costs to those existing token events, (2) persisting per-turn cost rows to a small log under `~/.sabrina/budget/`, (3) adding a `sabrina budget` typer verb that reads the log and prints daily + month-to-date totals annotated against the $0 target / $10/mo warn / $100/mo ceiling thresholds, and (4) emitting a one-line warn through structlog (NOT through the voice loop — that's Phase-2 follow-on work P2.8) when the rolling month-to-date crosses the warn threshold. The DoD splits cleanly along the partial-DoD seam: everything except the live-Windows-voice-turn validation is Linux-runnable; the Windows e2e is queued separately as P2.8.

## Proposed approach

- **(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**
  - `sabrina-2/src/sabrina/budget.py` (new, ~150 lines) — cost-table constants for Sonnet 4.6 + Haiku 4.5 + (optional) Opus 4.6, a `compute_cost(input_tokens, output_tokens, model: str) -> float` pure function, a `BudgetLog` class that appends per-turn rows to `~/.sabrina/budget/<YYYY-MM>.jsonl` and reads them back for daily/MTD aggregation, and a `check_thresholds(month_to_date: float, config: BudgetConfig) -> ThresholdState` returning one of `under_target | over_target | over_warn | over_ceiling`. JSONL chosen over SQLite — single-writer, low row count (≤ 1k turns/month at heavy use), trivial to grep, no schema migration tax. Decision-doc voice rationale lives in the new `rebuild/decisions/0XX-budget-tracker.md` file the (b)-half ships.
  - `sabrina-2/src/sabrina/brain/protocol.py` — extend `Done` with `cost_usd: float | None = None` (additive, backward-compatible, mirrors how `input_tokens`/`output_tokens` were added). Do NOT add `cache_read_tokens` here yet — that's the prompt-caching ship and is out of scope.
  - `sabrina-2/src/sabrina/brain/claude.py` — in the existing usage-extraction branch (the path that currently sets `Done(input_tokens=..., output_tokens=..., stop_reason=...)`), call `budget.compute_cost(...)` and pass `cost_usd=` into the `Done`. No changes to `voice_loop.py` from this half — the cost is propagated through `Done` only; the voice-loop wiring of `Done.cost_usd` into `ThinkingFinished.cost_usd` is the (b)-half because it touches `voice_loop.py`.
  - `sabrina-2/src/sabrina/cli.py` — add the `budget` typer verb. Three subcommands at minimum: `sabrina budget today`, `sabrina budget month`, `sabrina budget show <YYYY-MM>`. Read-only against the JSONL log; no live Anthropic call.
  - `sabrina-2/src/sabrina/config.py` — add a `[budget]` block in the Pydantic settings model: `target_usd_monthly: float = 0.0`, `warn_usd_monthly: float = 10.0`, `ceiling_usd_monthly: float = 100.0`, `log_dir: Path = ~/.sabrina/budget`. Default values map decision 001 verbatim.
  - `sabrina-2/sabrina.toml` — add the matching `[budget]` block with the same defaults explicit. Keep the file ASCII-clean.
  - `sabrina-2/tests/` — six tests minimum: cost-table arithmetic for both models, JSONL append-then-read round-trip, day-rollover boundary, month-rollover boundary, threshold-state transitions ({under,over}_target/warn/ceiling), `sabrina budget today` CLI smoke (typer's `CliRunner`).
- **(b)-half — `[windows-required]` (filed separately as the new P2.8, this spec does not pre-stage that item):**
  - `sabrina-2/src/sabrina/voice_loop.py` — propagate `Done.cost_usd` into `ThinkingFinished.cost_usd` at the existing `ThinkingFinished` emission site.
  - `sabrina-2/src/sabrina/events.py` — extend `ThinkingFinished` with `cost_usd: float | None = None`. (This event already carries `input_tokens`/`output_tokens`; the addition is the same shape.) **Note:** this is technically a Linux-runnable file edit, but the only consumer of the new field is the Windows-validated voice loop, and shipping events.py without the matching voice_loop.py wire-up leaves a dead field. Bundle both with the Windows e2e per partial-DoD's anti-dead-field policy.
  - One real Windows voice session that produces ≥ 5 turns and demonstrates: (i) a populated `~/.sabrina/budget/<YYYY-MM>.jsonl`, (ii) `sabrina budget today` reports a non-zero number, (iii) the warn-threshold log line fires when `[budget].warn_usd_monthly` is artificially set to `0.001` for the test.
- **What's deliberately NOT in scope.**
  - Prompt caching (Anthropic `cache_control` on the system block). That's a Phase-4 router-adjacent ship; the queue entry P2.7 doesn't include it; the budget-and-caching-plan from 2026-04-23 bundles them but the queue decomposition split them.
  - Hard kill-switch at the ceiling. The ceiling state is a logged warn only; enforcement waits for P4.C2 ("Router budget-gate hook") which has somewhere to escalate to (Ollama-local). Decision 001's $100 ceiling is observed-not-enforced in P2.7.
  - GUI tab. Phase-2 readiness item #5 says "`sabrina budget` command + monthly tracker" — CLI is sufficient for the readiness gate; GUI is polish.
  - Per-session breakdown. Per-day is enough.
  - Cost table for vision turns separately. The same Sonnet/Haiku per-token rates apply; if vision turns become disproportionately expensive a future spec adds a `vision_input_tokens` column.

## Dependencies

- **Phase 3 (a)-half ClaudeBrain wire-up** — recommended-but-not-required predecessor. The wire-up's brain surface stabilises the file boundary this spec touches in `claude.py`. If P2.7 ships before the (a)-half lands, Worker should target the in-tree shape and accept that a small follow-up rebase may be needed.
- **`rebuild/decisions/001-hardware-and-budget.md`** — source of the threshold defaults ($0/$10/$100). Off-limits to edit; this spec mirrors the numbers verbatim.
- **`rebuild/drafts/budget-and-caching-plan.md`** (2026-04-23, predecessor draft) — provides the cost-table constants for Sonnet 4.6 / Haiku 4.5 the (a)-half consumes. Not authoritative — that doc bundles caching, this spec narrows.
- **`sabrina-2/src/sabrina/brain/protocol.py:85-92`** — `Done` shape; the additive `cost_usd` field lives here.
- **`sabrina-2/src/sabrina/events.py:46-50`** — `ThinkingFinished` shape; the (b)-half's additive field lives here.
- **CLAUDE.md "Partial-DoD tiers"** — defines the (a)/(b) seam. The (a)-half does NOT touch `voice_loop.py`, `events.py` consumer wiring, audio/clipboard/pywin32 paths, or the toml flag-flips that need a Windows runner.
- **Decision-doc voice (`rebuild/decisions/`)** — required for the new decision doc the (b)-half ships (`0XX-budget-tracker.md`). Not authored in this spec; the (b)-half Worker on Windows writes it after the e2e gate fires.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. Files exist or are extended as listed in "Proposed approach" — `budget.py` new, `protocol.py`/`claude.py`/`cli.py`/`config.py`/`sabrina.toml` extended; `voice_loop.py` and `events.py` untouched.
2. `python -m compileall sabrina-2/src` clean.
3. The six new tests in "Proposed approach" all pass under the Cowork Linux/3.10 sandbox.
4. `sabrina budget today` (run with `SABRINA_BUDGET_LOG_DIR=$(mktemp -d)` and a synthetic three-row JSONL written by the test fixture) prints the expected dollar total and exits 0.
5. Pre-existing `sabrina-2/tests/test_smoke.py` tests still pass; ToolSpec round-trip tests at `tests/test_smoke.py:1869-1965` still pass.
6. Commit lands on `automation/<role>-2026-05-MM-Nam` with `Windows-pending: e2e` in the body. Body lists the (b)-half checklist verbatim from this spec's bullets above. Item moves to `[linux-shipped]` in QUEUE/DONE.

**(b)-half DoD (Full DoD per CLAUDE.md, separate queue item P2.8 — promotes the (a)-half to `[done]` when satisfied):**

1. `events.py` extended with `cost_usd` on `ThinkingFinished`; `voice_loop.py` populates it at the existing emission site.
2. One real Windows voice session ≥ 5 turns produces a populated `~/.sabrina/budget/<YYYY-MM>.jsonl`.
3. `sabrina budget today` reports a non-zero, plausible-for-the-session dollar total on the Windows box.
4. Warn-threshold structlog line fires when `[budget].warn_usd_monthly = 0.001` for the test session.
5. `pytest` passes on Windows.
6. Decision doc filed: `rebuild/decisions/0XX-budget-tracker.md`, decision-doc voice, references this spec by filename and the predecessor `budget-and-caching-plan.md`.
7. Voice-loop end-to-end record-sample → STT → brain → TTS validated per CLAUDE.md.

## Open questions for NEEDS-INPUT

One open question worth raising before a Worker picks up the (a)-half. Filed today as a `[from: spec-writer / 2026-05-05 06:50]` entry in NEEDS-INPUT.md.

- **Cost-table source-of-truth.** Should the per-token rates for Sonnet 4.6 / Haiku 4.5 / Opus 4.6 live (a) inline as constants in `budget.py` (cheap, no I/O, easy to read), (b) in `sabrina.toml` under `[budget.cost_table]` (user-tunable, survives Anthropic price changes without a code edit), or (c) in a small `data/anthropic-prices.yaml` file alongside `data/shortcuts.yaml` per P5.2 (consistent-with-the-data-port pattern, but adds a YAML-load step on every cost computation)? **Spec recommends (a)** — voice-loop hot path; price changes are infrequent; user-tuning would be a foot-gun ($0.01 typo costs Eric real money). Worker can ship (a) without waiting for an answer; Eric can override before merge.

Two non-blocking judgment calls a Worker can decide in-line:

- **Sonnet vs. Haiku detection.** The (a)-half needs to know which model produced the tokens to apply the right rate. Either parse the model name out of the existing `tier` field on `ThinkingFinished` (e.g. `"claude:sonnet-4-6"` → `"sonnet-4-6"`) or thread the model string through `Done` directly. Spec recommends parsing `tier`; the format is already structured for this purpose per `events.py` `AssistantReply` example.
- **Log filename.** Per-month (`<YYYY-MM>.jsonl`) vs. per-day (`<YYYY-MM-DD>.jsonl`). Spec picks per-month — month-to-date aggregation is the dominant query, and a single-month file at heavy use (~30 turns/day × 30 days × ~200 bytes/row = ~180 KB/month) is well under any concerning size.
