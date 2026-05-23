"""Tests for `sabrina.budget` — cost table, JSONL log, threshold checks.

Six logical tests per the P2.7 spec DoD:
1. cost-table arithmetic for both Sonnet 4.6 and Haiku 4.5
2. JSONL append-then-read round-trip
3. day-rollover boundary (`sum_today` ignores yesterday's rows)
4. month-rollover boundary (`sum_month` reads only the requested month)
5. threshold-state transitions ({under,over}_target/warn/ceiling)
6. `sabrina budget today` CLI smoke (typer's CliRunner)

Authored 2026-05-06 by worker-8am for QUEUE.md P2.7 (a)-half. Linux-runnable
under the Cowork sandbox; Windows e2e gates on P2.8 (the (b)-half wire-up).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sabrina.budget import (
    BudgetLog,
    BudgetRow,
    ModelCost,
    check_thresholds,
    compute_cost,
)


# ---------------------------------------------------------------------------
# 1. Cost-table arithmetic.
# ---------------------------------------------------------------------------


class TestComputeCost:
    """compute_cost() returns USD given token counts + model id."""

    def test_sonnet_4_6_input_only(self) -> None:
        # Sonnet $3 per 1M input tokens; 1,000,000 in tokens = $3.00.
        assert compute_cost(1_000_000, 0, "claude-sonnet-4-6") == pytest.approx(3.00)

    def test_sonnet_4_6_output_only(self) -> None:
        # Sonnet $15 per 1M output tokens; 1,000,000 out tokens = $15.00.
        assert compute_cost(0, 1_000_000, "claude-sonnet-4-6") == pytest.approx(15.00)

    def test_sonnet_4_6_realistic_turn(self) -> None:
        # 1234 in, 567 out at Sonnet rates:
        #   in:  1234 / 1e6 * 3.00 = $0.003702
        #   out: 567  / 1e6 * 15.00 = $0.008505
        #   total                   = $0.012207
        assert compute_cost(1234, 567, "claude-sonnet-4-6") == pytest.approx(
            0.012207, rel=1e-6
        )

    def test_haiku_4_5_input_and_output(self) -> None:
        # Haiku $1 in / $5 out per 1M:
        #   1M in + 1M out = $1 + $5 = $6.00
        cost = compute_cost(1_000_000, 1_000_000, "claude-haiku-4-5-20251001")
        assert cost == pytest.approx(6.00)

    def test_tier_prefixed_model_string(self) -> None:
        # Brain.name is "claude:claude-sonnet-4-6" — the tier-prefixed
        # form should resolve to the same rate as the bare model.
        bare = compute_cost(500_000, 100_000, "claude-sonnet-4-6")
        tier = compute_cost(500_000, 100_000, "claude:claude-sonnet-4-6")
        assert bare == tier == pytest.approx(500_000 / 1e6 * 3.0 + 100_000 / 1e6 * 15.0)

    def test_unknown_model_returns_zero(self) -> None:
        # An unknown / future model logs a warning and returns 0.0; the
        # JSONL row still lands so structure is preserved.
        assert compute_cost(999, 999, "claude-mystery-99") == 0.0

    def test_none_token_counts_treated_as_zero(self) -> None:
        # Cancelled mid-stream paths can produce None token counts; that
        # path returns 0.0 rather than raising.
        assert compute_cost(None, None, "claude-sonnet-4-6") == 0.0
        assert compute_cost(None, 100, "claude-sonnet-4-6") == pytest.approx(
            100 / 1e6 * 15.0
        )

    def test_model_cost_dataclass_is_frozen(self) -> None:
        # Defensive: ModelCost is a frozen slots dataclass so callers
        # can't mutate the rate table accidentally.
        rates = ModelCost(input_per_million=1.0, output_per_million=2.0)
        with pytest.raises((AttributeError, Exception)):
            rates.input_per_million = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 2. JSONL append-then-read round-trip.
# ---------------------------------------------------------------------------


class TestBudgetLogRoundTrip:
    """BudgetLog.append → read_month yields the exact same rows."""

    def test_append_one_row_round_trips(self, tmp_path: Path) -> None:
        log = BudgetLog(log_dir=tmp_path)
        ts = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
        log.append(
            model="claude:claude-sonnet-4-6",
            input_tokens=1234,
            output_tokens=567,
            cost_usd=0.012207,
            ts=ts,
        )
        rows = log.read_month("2026-05")
        assert len(rows) == 1
        assert rows[0] == BudgetRow(
            ts=ts,
            model="claude:claude-sonnet-4-6",
            input_tokens=1234,
            output_tokens=567,
            cost_usd=0.012207,
        )

    def test_append_three_rows_round_trip(self, tmp_path: Path) -> None:
        log = BudgetLog(log_dir=tmp_path)
        base = datetime(2026, 5, 6, 9, 0, 0, tzinfo=timezone.utc)
        for i in range(3):
            log.append(
                model="claude:claude-sonnet-4-6",
                input_tokens=100 * (i + 1),
                output_tokens=50 * (i + 1),
                cost_usd=0.001 * (i + 1),
                ts=base + timedelta(minutes=i),
            )
        rows = log.read_month("2026-05")
        assert len(rows) == 3
        # Order preserved (append is sequential).
        assert [r.input_tokens for r in rows] == [100, 200, 300]
        assert [r.output_tokens for r in rows] == [50, 100, 150]
        assert [round(r.cost_usd, 4) for r in rows] == [0.001, 0.002, 0.003]

    def test_jsonl_format_one_object_per_line(self, tmp_path: Path) -> None:
        log = BudgetLog(log_dir=tmp_path)
        ts = datetime(2026, 5, 6, tzinfo=timezone.utc)
        log.append(
            model="claude:claude-sonnet-4-6",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.0001,
            ts=ts,
        )
        log.append(
            model="claude:claude-haiku-4-5-20251001",
            input_tokens=30,
            output_tokens=40,
            cost_usd=0.0002,
            ts=ts,
        )
        path = tmp_path / "2026-05.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert {"ts", "model", "input_tokens", "output_tokens", "cost_usd"} == set(
                obj.keys()
            )

    def test_read_month_handles_missing_file(self, tmp_path: Path) -> None:
        # Pre-first-turn months report empty rather than raise.
        log = BudgetLog(log_dir=tmp_path)
        assert log.read_month("2025-01") == []
        assert log.sum_month("2025-01") == 0.0

    def test_read_month_skips_malformed_lines(self, tmp_path: Path) -> None:
        # A torn/partial line from a crashed write should be skipped, not
        # crash the aggregator.
        log = BudgetLog(log_dir=tmp_path)
        path = tmp_path / "2026-05.jsonl"
        path.write_text(
            (
                '{"ts": "2026-05-06T12:00:00+00:00", '
                '"model": "claude-sonnet-4-6", '
                '"input_tokens": 10, "output_tokens": 20, "cost_usd": 0.001}\n'
                "this-is-not-json\n"
                '{"ts": "2026-05-06T12:01:00+00:00", '
                '"model": "claude-sonnet-4-6", '
                '"input_tokens": 30, "output_tokens": 40, "cost_usd": 0.002}\n'
            ),
            encoding="utf-8",
        )
        rows = log.read_month("2026-05")
        assert len(rows) == 2
        assert [r.input_tokens for r in rows] == [10, 30]


# ---------------------------------------------------------------------------
# 3. Day-rollover boundary.
# ---------------------------------------------------------------------------


class TestSumTodayDayBoundary:
    """sum_today() honors the UTC date boundary."""

    def test_yesterday_excluded_today_included(self, tmp_path: Path) -> None:
        log = BudgetLog(log_dir=tmp_path)
        # "now" pinned to 2026-05-06 12:00 UTC; yesterday = 2026-05-05.
        now = datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)
        yesterday = now - timedelta(days=1)
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=1000,
            cost_usd=0.018,
            ts=yesterday,
        )
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=2000,
            output_tokens=2000,
            cost_usd=0.036,
            ts=now,
        )
        # Same month, so both rows are in the same JSONL.
        assert log.sum_month("2026-05") == pytest.approx(0.054)
        # But sum_today only sees the now row.
        assert log.sum_today(now=now) == pytest.approx(0.036)

    def test_midnight_boundary(self, tmp_path: Path) -> None:
        # 23:59:59 yesterday vs. 00:00:00 today — UTC date comparison.
        log = BudgetLog(log_dir=tmp_path)
        now = datetime(2026, 5, 6, 0, 0, 0, tzinfo=timezone.utc)
        eve = datetime(2026, 5, 5, 23, 59, 59, tzinfo=timezone.utc)
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=100,
            output_tokens=100,
            cost_usd=0.999,
            ts=eve,
        )
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=200,
            cost_usd=0.111,
            ts=now,
        )
        assert log.sum_today(now=now) == pytest.approx(0.111)


# ---------------------------------------------------------------------------
# 4. Month-rollover boundary.
# ---------------------------------------------------------------------------


class TestMonthRollover:
    """sum_month() reads only the named YYYY-MM file."""

    def test_two_months_in_separate_files(self, tmp_path: Path) -> None:
        log = BudgetLog(log_dir=tmp_path)
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=10_000,
            output_tokens=10_000,
            cost_usd=0.18,
            ts=datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc),
        )
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=20_000,
            output_tokens=20_000,
            cost_usd=0.36,
            ts=datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        # Two different files exist on disk.
        assert (tmp_path / "2026-04.jsonl").is_file()
        assert (tmp_path / "2026-05.jsonl").is_file()
        # Each month aggregates only its own file.
        assert log.sum_month("2026-04") == pytest.approx(0.18)
        assert log.sum_month("2026-05") == pytest.approx(0.36)


# ---------------------------------------------------------------------------
# 5. Threshold-state transitions.
# ---------------------------------------------------------------------------


class TestCheckThresholds:
    """check_thresholds() buckets MTD into the four threshold tiers."""

    @pytest.fixture
    def kw(self) -> dict[str, float]:
        return {
            "target_usd_monthly": 0.0,
            "warn_usd_monthly": 10.0,
            "ceiling_usd_monthly": 100.0,
        }

    def test_under_target_at_zero(self, kw: dict[str, float]) -> None:
        assert check_thresholds(0.0, **kw) == "under_target"

    def test_over_target_just_above_zero(self, kw: dict[str, float]) -> None:
        assert check_thresholds(0.01, **kw) == "over_target"
        assert check_thresholds(9.99, **kw) == "over_target"

    def test_over_warn_at_warn_threshold(self, kw: dict[str, float]) -> None:
        # Tied boundaries fall to the higher tier (>=).
        assert check_thresholds(10.00, **kw) == "over_warn"
        assert check_thresholds(50.00, **kw) == "over_warn"
        assert check_thresholds(99.99, **kw) == "over_warn"

    def test_over_ceiling_at_ceiling_threshold(self, kw: dict[str, float]) -> None:
        assert check_thresholds(100.00, **kw) == "over_ceiling"
        assert check_thresholds(150.00, **kw) == "over_ceiling"

    def test_negative_mtd_coerces_to_zero(self, kw: dict[str, float]) -> None:
        # Defensive — a manually-edited log might produce negatives.
        assert check_thresholds(-5.00, **kw) == "under_target"

    def test_custom_thresholds_respected(self) -> None:
        # If Eric raises the warn line to $20, a $15 MTD is over_target,
        # not over_warn.
        state = check_thresholds(
            15.00,
            target_usd_monthly=0.0,
            warn_usd_monthly=20.0,
            ceiling_usd_monthly=200.0,
        )
        assert state == "over_target"


# ---------------------------------------------------------------------------
# 6. CLI smoke — `sabrina budget today` round-trips through CliRunner.
# ---------------------------------------------------------------------------


class TestCliBudgetToday:
    """`sabrina budget today/month/show` print the right numbers."""

    def _seed_log(self, log_dir: Path, now: datetime) -> None:
        """Seed three rows: yesterday, today, today; total today = $0.025."""
        log = BudgetLog(log_dir=log_dir)
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=1000,
            cost_usd=0.005,
            ts=now - timedelta(days=1),
        )
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=1000,
            cost_usd=0.010,
            ts=now,
        )
        log.append(
            model="claude-sonnet-4-6",
            input_tokens=1000,
            output_tokens=1000,
            cost_usd=0.015,
            ts=now,
        )

    def test_budget_today_prints_today_total(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pin the log dir via the documented env-var path, and reload the
        # cached settings so the CLI sees the override.
        monkeypatch.setenv("SABRINA_BUDGET_LOG_DIR", str(tmp_path))
        from sabrina import config as config_module

        config_module._cached = None  # force reload
        # Seed against a synthetic "now"; the CLI will use the real now,
        # so use a date in the recent-enough past that the seeded "today"
        # rows still sit in the same UTC date the CLI reads.
        now = datetime.now(timezone.utc)
        self._seed_log(tmp_path, now)

        from sabrina.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["budget", "today"])
        assert result.exit_code == 0, result.output
        # The two today rows total $0.025; the yesterday row ($0.005)
        # should NOT show up in the today total.
        assert "today: $0.0250" in result.output
        # MTD total is the sum of all three rows.
        assert "month-to-date: $0.0300" in result.output
        # Threshold annotation should be over_target (>$0, < $10).
        assert "[over_target]" in result.output

    def test_budget_show_unknown_month_prints_no_rows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SABRINA_BUDGET_LOG_DIR", str(tmp_path))
        from sabrina import config as config_module

        config_module._cached = None  # force reload

        from sabrina.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["budget", "show", "1999-01"])
        assert result.exit_code == 0, result.output
        assert "no rows for 1999-01" in result.output
