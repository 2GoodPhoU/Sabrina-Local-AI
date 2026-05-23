"""Budget telemetry — per-turn cost computation, JSONL log, threshold checks.

Closes Phase-2 daily-driver readiness item #5: make Sabrina's Claude spend
visible. Every `claude.py` turn already carries `input_tokens` /
`output_tokens` on `Done`; this module attaches a dollar cost to those
counts, persists per-turn rows to a small log under
``~/.sabrina/budget/<YYYY-MM>.jsonl``, and exposes the math the
`sabrina budget` CLI verb reads back for daily / month-to-date totals.

Decision-log refs:
- ``rebuild/decisions/001-hardware-and-budget.md`` — sets the $0 target /
  $10 warn / $100 ceiling thresholds the (a)-half mirrors verbatim.
- ``rebuild/drafts/research/2026-05-05-p27-budget-tracker-spec.md`` —
  spec; cost-table source-of-truth pick is (a) inline constants here
  (recommended; voice-loop hot path; ``$0.01`` typo costs real money).

Why JSONL not SQLite: single writer, ~30 turns/day × 30 days × ~200
bytes/row = ~180 KB/month at heavy use; trivial to grep; no schema-
migration tax. If a future Worker hits perf or query needs that justify
SQLite, swap the persistence layer behind ``BudgetLog``.

The (b)-half wires ``Done.cost_usd`` into ``ThinkingFinished.cost_usd``
in ``voice_loop.py`` + ``events.py`` and ships a real Windows voice
session for end-to-end validation. Both are gated behind queue item P2.8.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from sabrina.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Cost table (a)-half: inline constants per spec recommendation (a).
# Rates are USD per 1,000,000 input/output tokens. Source: Anthropic's
# pricing page as of 2026-05. Keep these in sync; on a price change land
# the edit alongside a one-line note in the next decision doc / DECISIONS.md
# entry so the audit trail is intact. A typo here costs Eric real money,
# so changes should land via PR review (per CLAUDE.md), not env-var override.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelCost:
    """Per-million-token rates for one model."""

    input_per_million: float
    output_per_million: float


# Keyed by bare model string AND by ``claude:<model>`` tier string. The
# tier form matches ``Brain.name`` / ``ThinkingFinished.tier`` so callers
# at either layer can lookup without a parse step.
_COST_TABLE: dict[str, ModelCost] = {
    # Sonnet 4.6 — the daily-driver default per [brain.claude].model.
    "claude-sonnet-4-6": ModelCost(input_per_million=3.00, output_per_million=15.00),
    "claude:claude-sonnet-4-6": ModelCost(input_per_million=3.00, output_per_million=15.00),
    # Haiku 4.5 — the fast_model fallback per [brain.claude].fast_model.
    "claude-haiku-4-5-20251001": ModelCost(input_per_million=1.00, output_per_million=5.00),
    "claude:claude-haiku-4-5-20251001": ModelCost(
        input_per_million=1.00, output_per_million=5.00
    ),
    # Opus 4.6 — not currently the default but listed for completeness;
    # decision 001 names a $100/mo ceiling that Opus would burn through
    # fast on heavy use, so the cost table covers it.
    "claude-opus-4-6": ModelCost(input_per_million=15.00, output_per_million=75.00),
    "claude:claude-opus-4-6": ModelCost(input_per_million=15.00, output_per_million=75.00),
}


def compute_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    model: str,
) -> float:
    """Return USD cost for one turn given token counts and a model id.

    ``model`` accepts either the bare model string ("claude-sonnet-4-6")
    or the prefixed tier string ("claude:claude-sonnet-4-6"). Unknown
    models log a one-time warning and return 0.0 — the budget log row
    still lands so the structural data is preserved; a follow-up can
    backfill cost when the rate is added to the table.

    None token counts coerce to 0; safe to pass ``Done.input_tokens``
    directly even when the streaming layer chose not to populate them.
    """
    rates = _COST_TABLE.get(model)
    if rates is None:
        # Strip a possible "claude:" prefix and retry — defensive
        # against a tier passed through that hadn't been double-listed.
        if ":" in model:
            rates = _COST_TABLE.get(model.split(":", 1)[1])
    if rates is None:
        log.warning(
            "budget.compute_cost: unknown model %s; cost defaulting to 0.0", model
        )
        return 0.0
    in_tok = input_tokens or 0
    out_tok = output_tokens or 0
    return (
        in_tok * rates.input_per_million / 1_000_000.0
        + out_tok * rates.output_per_million / 1_000_000.0
    )


# ---------------------------------------------------------------------------
# Threshold state.
# ---------------------------------------------------------------------------


ThresholdState = Literal["under_target", "over_target", "over_warn", "over_ceiling"]


def check_thresholds(
    month_to_date: float,
    *,
    target_usd_monthly: float,
    warn_usd_monthly: float,
    ceiling_usd_monthly: float,
) -> ThresholdState:
    """Bucket a month-to-date total against the four threshold tiers.

    Decision 001: target=$0, warn=$10/mo, ceiling=$100/mo.

    - ``under_target`` — month-to-date is at-or-below the target. Default
      state when the operator has been hands-off / using only Ollama.
    - ``over_target`` — past target, still under the warn line. Expected
      state for normal Claude use.
    - ``over_warn`` — past warn. The voice loop should surface a one-line
      heads-up; the (b)-half wires this through structlog (NOT through
      TTS — Eric's review said "annoying nag" was the failure mode of
      the legacy build).
    - ``over_ceiling`` — past ceiling. P4.C2 (router budget gate) is
      where enforcement lives; P2.7 only logs.

    Tied boundaries fall to the higher tier (>=). Negative MTD coerces
    to 0 — defensive, the JSONL aggregator never produces negatives but
    a manually-edited log might.
    """
    mtd = max(month_to_date, 0.0)
    if mtd >= ceiling_usd_monthly:
        return "over_ceiling"
    if mtd >= warn_usd_monthly:
        return "over_warn"
    if mtd > target_usd_monthly:
        return "over_target"
    return "under_target"


# ---------------------------------------------------------------------------
# Budget log persistence.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BudgetRow:
    """One persisted turn-cost row, decoded from the JSONL log."""

    ts: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class BudgetLog:
    """Append-only per-month JSONL log under a configurable directory.

    File layout: ``<log_dir>/<YYYY-MM>.jsonl``, one JSON object per line:

    .. code-block:: json

        {"ts": "2026-05-06T08:01:23.456789+00:00",
         "model": "claude:claude-sonnet-4-6",
         "input_tokens": 1234, "output_tokens": 567, "cost_usd": 0.012215}

    Read-side helpers (``read_month``, ``sum_today``, ``sum_month``)
    iterate the file lazily and skip malformed lines with a warning;
    a partial write from a crashed process won't poison the aggregate.
    """

    def __init__(self, log_dir: Path | str | None = None) -> None:
        if log_dir is None:
            log_dir = self._default_log_dir()
        self._log_dir = Path(log_dir)

    @staticmethod
    def _default_log_dir() -> Path:
        """Resolve the default ``~/.sabrina/budget/`` location.

        Honors the ``SABRINA_BUDGET_LOG_DIR`` env var so tests can pin
        the log to a tmp path without touching real config.
        """
        env_override = os.environ.get("SABRINA_BUDGET_LOG_DIR")
        if env_override:
            return Path(env_override)
        return Path.home() / ".sabrina" / "budget"

    @property
    def log_dir(self) -> Path:
        return self._log_dir

    def _path_for(self, year_month: str) -> Path:
        return self._log_dir / f"{year_month}.jsonl"

    @staticmethod
    def _year_month(ts: datetime) -> str:
        return ts.strftime("%Y-%m")

    def append(
        self,
        *,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        cost_usd: float,
        ts: datetime | None = None,
    ) -> None:
        """Append one turn row to the current-month JSONL.

        Idempotency note: callers responsible for ensuring exactly-one
        call per turn. The voice loop already emits one ``ThinkingFinished``
        per turn; the (b)-half hooks this append off that single event.
        """
        ts = ts or datetime.now(timezone.utc)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        path = self._path_for(self._year_month(ts))
        row = {
            "ts": ts.isoformat(),
            "model": model,
            "input_tokens": int(input_tokens or 0),
            "output_tokens": int(output_tokens or 0),
            "cost_usd": float(cost_usd),
        }
        # Open for append, line-buffered. A crashed process between turns
        # leaves a complete row (one full line) or no row at all; the
        # read side tolerates a torn final line.
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")

    def read_month(self, year_month: str | None = None) -> list[BudgetRow]:
        """Return every row in ``<log_dir>/<year_month>.jsonl``.

        Default (``year_month=None``) reads the current month. Missing
        files are treated as empty (zero rows) — pre-first-turn months
        report $0 instead of crashing. Malformed lines are skipped with
        a warning and don't abort the load.
        """
        if year_month is None:
            year_month = self._year_month(datetime.now(timezone.utc))
        path = self._path_for(year_month)
        if not path.is_file():
            return []
        rows: list[BudgetRow] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rows.append(
                    BudgetRow(
                        ts=datetime.fromisoformat(obj["ts"]),
                        model=str(obj["model"]),
                        input_tokens=int(obj.get("input_tokens", 0)),
                        output_tokens=int(obj.get("output_tokens", 0)),
                        cost_usd=float(obj.get("cost_usd", 0.0)),
                    )
                )
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                log.warning(
                    "budget.read_month: skipping malformed row at %s:%d (%s)",
                    path,
                    line_no,
                    exc,
                )
        return rows

    def sum_today(self, now: datetime | None = None) -> float:
        """Sum ``cost_usd`` across rows whose ts falls on today's date.

        ``now`` injectable for tests; defaults to UTC now. Day boundary
        is the UTC date — single-user single-timezone deployment, so a
        simple comparison is sufficient.
        """
        now = now or datetime.now(timezone.utc)
        rows = self.read_month(self._year_month(now))
        today = now.date()
        return sum(r.cost_usd for r in rows if r.ts.date() == today)

    def sum_month(self, year_month: str | None = None) -> float:
        """Sum ``cost_usd`` across all rows in the month."""
        rows = self.read_month(year_month)
        return sum(r.cost_usd for r in rows)
