"""Unit tests for the brain router (P4.C2).

Covers ``Router.select_backend`` policy resolution under all three
v1 policies (``force_local`` / ``claude_default`` / ``cost_aware``),
the per-backend system-prompt swap, the tools-drop on Ollama, and
the ``make_router_from_settings`` factory wiring. Tests use lightweight
fakes for ``ClaudeBrain`` / ``OllamaBrain`` / ``BudgetLog`` so the
suite runs entirely in-process without anthropic / ollama / network.

Spec: ``rebuild/drafts/research/2026-05-08-p4c2-router-routing-policy-spec.md``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from sabrina.brain.persona import (
    SABRINA_SYSTEM_PROMPT_CLAUDE,
    SABRINA_SYSTEM_PROMPT_OLLAMA,
)
from sabrina.brain.protocol import Brain, Done, Message, TextDelta
from sabrina.brain.router import (
    Router,
    RouterMisconfigured,
    make_router_from_settings,
)

# ---------------------------------------------------------------------------
# Test fakes
# ---------------------------------------------------------------------------


class _FakeBackend:
    """Minimal Brain-protocol stand-in.

    Captures the kwargs each ``chat()`` call received so tests can assert
    the router forwarded ``system`` / ``tools`` / ``max_tokens`` correctly.
    Streams a single TextDelta + Done.
    """

    def __init__(self, name: str, *, reply_text: str = "ok") -> None:
        self.name = name
        self._reply_text = reply_text
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages,
        *,
        system=None,
        max_tokens=None,
        cancel_token=None,
        tools=None,
    ):
        self.calls.append(
            {
                "messages": messages,
                "system": system,
                "max_tokens": max_tokens,
                "cancel_token": cancel_token,
                "tools": tools,
            }
        )
        yield TextDelta(text=self._reply_text)
        yield Done(input_tokens=1, output_tokens=2, stop_reason="end_turn")


class _FakeBudgetLog:
    """Records sum_month / sum_today reads; lets tests script returned MTD."""

    def __init__(self, mtd: float = 0.0) -> None:
        self._mtd = mtd
        self.sum_month_calls = 0

    def sum_month(self, year_month: str | None = None) -> float:
        self.sum_month_calls += 1
        return self._mtd

    def sum_today(self, now=None) -> float:
        return 0.0


def _drain(stream) -> list:
    async def _go():
        out = []
        async for ev in stream:
            out.append(ev)
        return out

    return asyncio.run(_go())


def _claude(name: str = "claude:claude-test") -> _FakeBackend:
    return _FakeBackend(name=name)


def _ollama(name: str = "ollama:fake") -> _FakeBackend:
    return _FakeBackend(name=name)


# ---------------------------------------------------------------------------
# Spec test 1: name encodes policy
# ---------------------------------------------------------------------------


def test_router_name_includes_policy():
    r = Router(claude=_claude(), ollama=_ollama(), policy="force_local")
    assert r.name == "router:force_local"
    r2 = Router(claude=_claude(), ollama=_ollama(), policy="cost_aware")
    assert r2.name == "router:cost_aware"


# ---------------------------------------------------------------------------
# Spec tests 2-5: force_local + claude_default branches + missing-backend
# RouterMisconfigured raises
# ---------------------------------------------------------------------------


def test_force_local_picks_ollama():
    claude = _claude()
    ollama = _ollama()
    r = Router(claude=claude, ollama=ollama, policy="force_local")
    assert r.select_backend() is ollama


def test_force_local_with_no_ollama_raises_router_misconfigured():
    r = Router(claude=_claude(), ollama=None, policy="force_local")
    with pytest.raises(RouterMisconfigured):
        r.select_backend()


def test_claude_default_picks_claude():
    claude = _claude()
    ollama = _ollama()
    r = Router(claude=claude, ollama=ollama, policy="claude_default")
    assert r.select_backend() is claude


def test_claude_default_with_no_claude_raises_router_misconfigured():
    r = Router(claude=None, ollama=_ollama(), policy="claude_default")
    with pytest.raises(RouterMisconfigured):
        r.select_backend()


# ---------------------------------------------------------------------------
# Spec tests 6-10: cost_aware policy branches
# ---------------------------------------------------------------------------


def test_cost_aware_picks_claude_when_mtd_below_threshold():
    claude = _claude()
    ollama = _ollama()
    log = _FakeBudgetLog(mtd=5.0)
    r = Router(
        claude=claude,
        ollama=ollama,
        policy="cost_aware",
        budget_log=log,
        warn_threshold_usd=10.0,
    )
    assert r.select_backend() is claude
    assert log.sum_month_calls == 1


def test_cost_aware_picks_ollama_when_mtd_at_threshold():
    claude = _claude()
    ollama = _ollama()
    log = _FakeBudgetLog(mtd=10.0)
    r = Router(
        claude=claude,
        ollama=ollama,
        policy="cost_aware",
        budget_log=log,
        warn_threshold_usd=10.0,
    )
    # Spec: tied boundaries fall to Ollama (>= comparison).
    assert r.select_backend() is ollama


def test_cost_aware_picks_ollama_when_mtd_above_threshold():
    claude = _claude()
    ollama = _ollama()
    log = _FakeBudgetLog(mtd=15.0)
    r = Router(
        claude=claude,
        ollama=ollama,
        policy="cost_aware",
        budget_log=log,
        warn_threshold_usd=10.0,
    )
    assert r.select_backend() is ollama


def test_cost_aware_with_no_budget_log_picks_claude():
    """Degrade-open: no budget log => claude_default semantics."""
    claude = _claude()
    ollama = _ollama()
    r = Router(
        claude=claude,
        ollama=ollama,
        policy="cost_aware",
        budget_log=None,
        warn_threshold_usd=10.0,
    )
    assert r.select_backend() is claude


def test_cost_aware_with_ollama_disabled_logs_warning_and_picks_claude(monkeypatch):
    """Threshold crossed but no Ollama => degrade-open warning + Claude.

    Patch ``router.log`` with a collector — sabrina.logging renders
    structlog through Rich console (not the stdlib bridge), so caplog
    doesn't catch the keyword payload (cf. test_automation_safety.py).
    """
    captured: list[tuple[str, str, dict]] = []

    class _Collector:
        def warning(self, event: str, **kwargs):
            captured.append(("warning", event, kwargs))

        def info(self, *a, **kw): pass
        def debug(self, *a, **kw): pass
        def error(self, *a, **kw): pass

    from sabrina.brain import router as router_mod

    monkeypatch.setattr(router_mod, "log", _Collector())

    claude = _claude()
    log = _FakeBudgetLog(mtd=15.0)
    r = Router(
        claude=claude,
        ollama=None,
        policy="cost_aware",
        budget_log=log,
        warn_threshold_usd=10.0,
    )
    backend = r.select_backend()
    assert backend is claude
    matches = [
        (level, event, kw) for level, event, kw in captured
        if event == "router.degraded_open"
    ]
    assert matches, f"expected router.degraded_open event; saw {captured!r}"
    _, _, kw = matches[0]
    assert kw.get("reason") == "threshold_crossed_but_no_ollama"
    assert kw.get("mtd") == 15.0
    assert kw.get("threshold") == 10.0


# ---------------------------------------------------------------------------
# Spec test 11: chat routes to selected backend
# ---------------------------------------------------------------------------


def test_chat_routes_to_selected_backend_text_only():
    claude = _claude()
    ollama = _ollama()
    r = Router(claude=claude, ollama=ollama, policy="claude_default")
    events = _drain(r.chat([Message(role="user", content="hi")]))
    # Claude was called, Ollama untouched.
    assert len(claude.calls) == 1
    assert len(ollama.calls) == 0
    # Stream forwarded faithfully.
    text_deltas = [ev for ev in events if isinstance(ev, TextDelta)]
    dones = [ev for ev in events if isinstance(ev, Done)]
    assert len(text_deltas) == 1
    assert len(dones) == 1
    assert dones[0].stop_reason == "end_turn"


# ---------------------------------------------------------------------------
# Spec tests 12-13: per-backend system-prompt swap + explicit-system passthrough
# ---------------------------------------------------------------------------


def test_chat_swaps_system_prompt_per_backend():
    claude = _claude()
    ollama = _ollama()

    # Claude route — should receive the Claude prompt.
    r1 = Router(claude=claude, ollama=ollama, policy="claude_default")
    _drain(r1.chat([Message(role="user", content="hi")]))
    assert claude.calls[-1]["system"] == SABRINA_SYSTEM_PROMPT_CLAUDE

    # Ollama route — should receive the Ollama prompt.
    r2 = Router(claude=claude, ollama=ollama, policy="force_local")
    _drain(r2.chat([Message(role="user", content="hi")]))
    assert ollama.calls[-1]["system"] == SABRINA_SYSTEM_PROMPT_OLLAMA


def test_chat_passes_through_explicit_system_prompt():
    claude = _claude()
    ollama = _ollama()
    r = Router(claude=claude, ollama=ollama, policy="claude_default")
    _drain(
        r.chat(
            [Message(role="user", content="hi")],
            system="custom prompt",
        )
    )
    assert claude.calls[-1]["system"] == "custom prompt"


# ---------------------------------------------------------------------------
# Spec test 14: tools dropped on Ollama route
# ---------------------------------------------------------------------------


def test_chat_drops_tools_when_route_does_not_support(monkeypatch):
    """tools=[NOOP_ACTION_SPEC] + force_local => Ollama receives tools=None.

    Patch ``router.log`` with a collector — same Rich-console reasoning
    as the degraded_open test above.
    """
    from sabrina.automation.scaffold import NOOP_ACTION_SPEC

    captured: list[tuple[str, str, dict]] = []

    class _Collector:
        def info(self, event: str, **kwargs):
            captured.append(("info", event, kwargs))

        def warning(self, *a, **kw): pass
        def debug(self, *a, **kw): pass
        def error(self, *a, **kw): pass

    from sabrina.brain import router as router_mod

    monkeypatch.setattr(router_mod, "log", _Collector())

    claude = _claude()
    ollama = _ollama()
    r = Router(claude=claude, ollama=ollama, policy="force_local")
    _drain(
        r.chat(
            [Message(role="user", content="hi")],
            tools=[NOOP_ACTION_SPEC],
        )
    )
    assert ollama.calls[-1]["tools"] is None
    matches = [
        (level, event, kw) for level, event, kw in captured
        if event == "router.tools_dropped"
    ]
    assert matches, f"expected router.tools_dropped event; saw {captured!r}"
    _, _, kw = matches[0]
    assert kw.get("backend") == "ollama:fake"
    assert kw.get("count") == 1


# ---------------------------------------------------------------------------
# Spec test 15: factory wires both backends per Settings
# ---------------------------------------------------------------------------


def test_make_router_from_settings_wires_both_backends(monkeypatch):
    """Pass a Settings with policy=cost_aware; assert returned Router has
    both backends + the policy + a threshold sourced from [budget]."""
    # Build a minimal Settings that bypasses .env / SABRINA_ANTHROPIC_API_KEY.
    monkeypatch.setenv("SABRINA_ANTHROPIC_API_KEY", "sk-ant-test-dummy")
    monkeypatch.setenv("SABRINA_BRAIN__ROUTER__POLICY", "cost_aware")
    monkeypatch.setenv("SABRINA_BUDGET__WARN_USD_MONTHLY", "7.5")

    from sabrina.config import Settings

    s = Settings()
    assert s.brain.router.policy == "cost_aware"
    assert s.budget.warn_usd_monthly == 7.5

    r = make_router_from_settings(s)
    assert isinstance(r, Router)
    # Both backends wired (factory consults enable_* flags).
    assert r._claude is not None  # noqa: SLF001
    assert r._ollama is not None  # noqa: SLF001
    assert r._policy == "cost_aware"  # noqa: SLF001
    # Threshold sourced from [budget] (spec Q1 (b) per NEEDS-INPUT.md:143).
    assert r._warn_threshold_usd == 7.5  # noqa: SLF001
    # name reflects the configured policy.
    assert r.name == "router:cost_aware"


def test_make_router_from_settings_threshold_sourced_from_budget(monkeypatch):
    """Q1 (b) per NEEDS-INPUT.md:143: router reads [budget].warn_usd_monthly
    directly; BrainRouterConfig no longer carries a per-router override."""
    monkeypatch.setenv("SABRINA_ANTHROPIC_API_KEY", "sk-ant-test-dummy")
    monkeypatch.setenv("SABRINA_BUDGET__WARN_USD_MONTHLY", "12.5")

    from sabrina.config import Settings

    s = Settings()
    assert s.budget.warn_usd_monthly == 12.5

    r = make_router_from_settings(s)
    assert r._warn_threshold_usd == 12.5  # noqa: SLF001


# ---------------------------------------------------------------------------
# Bonus: protocol conformance
# ---------------------------------------------------------------------------


def test_router_implements_brain_protocol():
    """isinstance check via runtime_checkable Brain Protocol."""
    r = Router(claude=_claude(), ollama=_ollama(), policy="claude_default")
    assert isinstance(r, Brain)
