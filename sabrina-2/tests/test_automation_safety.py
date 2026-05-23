"""P4.B1 Automation safety primitives — kill-switch + dry-run + scaffold.

Eighteen tests covering the (a)-half DoD from
``rebuild/drafts/research/2026-05-08-p4b1-automation-safety-primitives-spec.md``.

Test groups:

1. KillSwitch surface: trip flag, ``.check()`` raise/no-raise,
   listener factory wiring (start/stop/fire callback).
2. dry_run module: ``dry_run_wrap`` returns synthetic shape and
   doesn't invoke underlying handler; ``is_dry_run`` resolves
   from settings with True default.
3. Scaffold: ``noop_action`` returns ok-shape; ``NOOP_ACTION_SPEC``
   round-trips via ``to_anthropic_dict()``.
4. ClaudeBrain dispatch integration: dry-run wins / dry-run False
   passes through / kill-switch trip wins / dry-run + kill-switch
   ordering case.
"""

from __future__ import annotations

import json

import pytest

from sabrina.automation import dry_run as dry_run_mod
from sabrina.automation import kill_switch as ks_mod
from sabrina.automation.dry_run import dry_run_wrap, is_dry_run
from sabrina.automation.kill_switch import (
    DEFAULT_KILL_SWITCH_HOTKEY,
    KillSwitch,
    KillSwitchTripped,
    _NoopListener,
)
from sabrina.automation.scaffold import NOOP_ACTION_SPEC, noop_action

# ---------------------------------------------------------------------------
# Fakes mirroring the test_smoke.py tool-dispatch suite. Re-declared here so
# this file is self-contained — test_smoke.py's _Fake* classes are private.
# ---------------------------------------------------------------------------


class _FakeBlock:
    __slots__ = ("type", "text", "id", "name", "input")

    def __init__(self, type_, *, text=None, id=None, name=None, input=None):
        self.type = type_
        self.text = text
        self.id = id
        self.name = name
        self.input = input

    def model_dump(self):
        d = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.id is not None:
            d["id"] = self.id
        if self.name is not None:
            d["name"] = self.name
        if self.input is not None:
            d["input"] = self.input
        return d


class _FakeUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeFinalMessage:
    def __init__(self, content, stop_reason, usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or _FakeUsage()


class _FakeStream:
    def __init__(self, text_chunks, final):
        self._text_chunks = text_chunks
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def _gen():
            for t in self._text_chunks:
                yield t
        return _gen()

    async def get_final_message(self):
        return self._final


class _FakeMessages:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if not self._scripted:
            raise AssertionError(
                "ClaudeBrain made more stream() calls than the test scripted."
            )
        return self._scripted.pop(0)


class _FakeAnthropicClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


def _make_claude_with(scripted):
    from sabrina.brain.claude import ClaudeBrain

    brain = ClaudeBrain(api_key="sk-ant-test-dummy", model="claude-test")
    brain._client = _FakeAnthropicClient(scripted)
    return brain


# ---------------------------------------------------------------------------
# Group 1 — KillSwitch surface (7 tests)
# ---------------------------------------------------------------------------


def test_kill_switch_starts_untripped():
    """Fresh ``KillSwitch`` enters its context with ``.tripped`` False."""
    with KillSwitch() as ks:
        assert ks.tripped is False


def test_kill_switch_check_does_not_raise_when_untripped():
    """``.check()`` is a no-op when the flag is unset."""
    with KillSwitch() as ks:
        # Should not raise.
        assert ks.check() is None


def test_kill_switch_trip_sets_tripped_flag():
    """Programmatic ``.trip()`` flips the flag idempotently."""
    with KillSwitch() as ks:
        assert ks.tripped is False
        ks.trip()
        assert ks.tripped is True
        # Second trip stays True (no toggle, no exception).
        ks.trip()
        assert ks.tripped is True


def test_kill_switch_check_raises_when_tripped():
    """Post-trip ``.check()`` raises ``KillSwitchTripped`` with the hotkey."""
    with KillSwitch(hotkey="<ctrl>+<alt>+k") as ks:
        ks.trip()
        with pytest.raises(KillSwitchTripped) as excinfo:
            ks.check()
        assert "ctrl" in str(excinfo.value).lower()


def test_kill_switch_listener_factory_is_invoked_on_enter(monkeypatch):
    """``__enter__`` calls the injected factory with the trip callback."""
    instances: list[_NoopListener] = []

    def fake_factory(on_trip, hotkey=DEFAULT_KILL_SWITCH_HOTKEY):
        listener = _NoopListener(on_trip)
        instances.append(listener)
        return listener

    monkeypatch.setattr(ks_mod, "_LISTENER_FACTORY", fake_factory)

    with KillSwitch():
        assert len(instances) == 1
        assert instances[0].started is True


def test_kill_switch_listener_factory_stop_called_on_exit(monkeypatch):
    """``__exit__`` calls ``.stop()`` on the listener even with no trip."""
    instances: list[_NoopListener] = []

    def fake_factory(on_trip, hotkey=DEFAULT_KILL_SWITCH_HOTKEY):
        listener = _NoopListener(on_trip)
        instances.append(listener)
        return listener

    monkeypatch.setattr(ks_mod, "_LISTENER_FACTORY", fake_factory)

    with KillSwitch():
        pass

    assert instances[0].stopped is True


def test_kill_switch_listener_callback_trips_flag(monkeypatch):
    """A listener-side ``.fire()`` call propagates to ``KillSwitch.tripped``."""
    captured: dict[str, _NoopListener] = {}

    def fake_factory(on_trip, hotkey=DEFAULT_KILL_SWITCH_HOTKEY):
        listener = _NoopListener(on_trip)
        captured["listener"] = listener
        return listener

    monkeypatch.setattr(ks_mod, "_LISTENER_FACTORY", fake_factory)

    with KillSwitch() as ks:
        assert ks.tripped is False
        captured["listener"].fire()
        assert ks.tripped is True
        with pytest.raises(KillSwitchTripped):
            ks.check()


# ---------------------------------------------------------------------------
# Group 2 — dry_run module (5 tests)
# ---------------------------------------------------------------------------


async def test_dry_run_wrap_returns_synthetic_shape():
    """Wrapped handler emits ``{dry_run, would_have_called, input}`` exactly."""

    async def real(**kwargs):
        return {"never": "should-be-called"}

    wrapped = dry_run_wrap(real, name="real_action")
    out = await wrapped(content="hello", count=3)
    assert out == {
        "dry_run": True,
        "would_have_called": "real_action",
        "input": {"content": "hello", "count": 3},
    }


async def test_dry_run_wrap_does_not_invoke_underlying():
    """Wrapped handler must not call the real handler — sentinel proves it."""
    invoked: list[bool] = []

    async def real(**kwargs):
        invoked.append(True)
        return {"ok": True}

    wrapped = dry_run_wrap(real, name="real_action")
    await wrapped(x=1)
    assert invoked == []


async def test_dry_run_wrap_logs_would_call_at_info(monkeypatch):
    """``automation.dry_run.would_call`` is emitted on the dry-run path.

    The project's ``sabrina.logging`` renders through structlog's own
    pipeline (not the stdlib bridge), so ``caplog`` doesn't see these
    events. Asserting on the structured event by patching the module
    logger with a list-collector keeps the test platform-agnostic and
    avoids depending on Rich's console formatting.
    """

    captured: list[tuple[str, dict]] = []

    class _Collector:
        def info(self, event: str, **kwargs):
            captured.append((event, kwargs))

        # Soak up other levels harmlessly in case the impl changes.
        def debug(self, *a, **kw): pass
        def warning(self, *a, **kw): pass
        def error(self, *a, **kw): pass

    monkeypatch.setattr(dry_run_mod, "log", _Collector())

    async def real(**kwargs):  # pragma: no cover — wrapped, never called
        return {}

    wrapped = dry_run_wrap(real, name="some_action")
    await wrapped(input_text="abc")

    matches = [
        (event, kw) for event, kw in captured
        if event == "automation.dry_run.would_call"
    ]
    assert matches, f"expected would_call event; saw {captured!r}"
    _, kw = matches[0]
    assert kw.get("tool") == "some_action"
    assert kw.get("input") == {"input_text": "abc"}


def test_is_dry_run_default_is_true():
    """A vanilla ``Settings()`` resolves ``is_dry_run`` to True."""
    from sabrina.config import Settings

    settings = Settings()
    assert is_dry_run(settings) is True


def test_is_dry_run_respects_config_override():
    """``automation.dry_run = False`` flips the resolver to False."""
    from sabrina.config import AutomationConfig, Settings

    settings = Settings(
        automation=AutomationConfig(dry_run=False),
    )
    assert is_dry_run(settings) is False


# ---------------------------------------------------------------------------
# Group 3 — Scaffold (2 tests)
# ---------------------------------------------------------------------------


async def test_noop_action_returns_ok_shape():
    """``noop_action("hello")`` returns the canonical ``{ok, content_length}``."""
    out = await noop_action("hello")
    assert out == {"ok": True, "content_length": 5}


def test_noop_action_spec_round_trips_to_anthropic_dict():
    """``NOOP_ACTION_SPEC.to_anthropic_dict()`` matches the existing
    ``BUILTIN_TOOLS[0]`` shape (parallel to the four ToolSpec round-trip
    tests at ``test_smoke.py:1869-1965``)."""
    payload = NOOP_ACTION_SPEC.to_anthropic_dict()
    assert set(payload.keys()) == {"name", "description", "input_schema"}
    assert payload["name"] == "noop_action"
    assert payload["input_schema"]["type"] == "object"
    assert "content" in payload["input_schema"]["properties"]
    assert payload["input_schema"]["required"] == ["content"]


# ---------------------------------------------------------------------------
# Group 4 — ClaudeBrain dispatch integration (4 tests)
# ---------------------------------------------------------------------------


def _round_with_tool_use(tool_id: str, name: str, tool_input: dict):
    return _FakeStream(
        text_chunks=[],
        final=_FakeFinalMessage(
            content=[
                _FakeBlock(
                    "tool_use",
                    id=tool_id,
                    name=name,
                    input=tool_input,
                ),
            ],
            stop_reason="tool_use",
        ),
    )


def _terminal_round(text: str = "done."):
    return _FakeStream(
        text_chunks=[text],
        final=_FakeFinalMessage(
            content=[_FakeBlock("text", text=text)],
            stop_reason="end_turn",
            usage=_FakeUsage(input_tokens=42, output_tokens=7),
        ),
    )


async def test_claude_dispatch_calls_handler_when_dry_run_false():
    """``dry_run=False`` → real handler runs, real result rides into the
    follow-up ``tool_result`` block."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):
        invoked.append(kwargs)
        return {"ok": True, "content_length": len(kwargs.get("content", ""))}

    from sabrina.tools import ToolSpec

    spec = ToolSpec(
        name="noop_action",
        description="real",
        input_schema={"type": "object"},
        handler=real_handler,
    )

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "noop_action", {"content": "hello"}),
        _terminal_round("done."),
    ])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="run it")],
        tools=[spec],
        dry_run=False,
    ):
        events.append(ev)

    assert invoked == [{"content": "hello"}]
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error is None
    assert done_ev.result == {"ok": True, "content_length": 5}

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["type"] == "tool_result"
    assert tr["is_error"] is False
    assert json.loads(tr["content"]) == {"ok": True, "content_length": 5}


async def test_claude_dispatch_returns_dry_run_shape_when_dry_run_true():
    """``dry_run=True`` → underlying handler skipped; synthetic shape rides
    back to the model and the next round trip sees the dry-run content."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover — must not run
        invoked.append(kwargs)
        return {"ok": True}

    from sabrina.tools import ToolSpec

    spec = ToolSpec(
        name="noop_action",
        description="real",
        input_schema={"type": "object"},
        handler=real_handler,
    )

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "noop_action", {"content": "hello"}),
        _terminal_round("done."),
    ])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="run it")],
        tools=[spec],
        dry_run=True,
    ):
        events.append(ev)

    assert invoked == [], "real handler must not run under dry_run=True"
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error is None
    assert done_ev.result == {
        "dry_run": True,
        "would_have_called": "noop_action",
        "input": {"content": "hello"},
    }

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["is_error"] is False
    payload = json.loads(tr["content"])
    assert payload["dry_run"] is True
    assert payload["would_have_called"] == "noop_action"


async def test_claude_dispatch_returns_kill_switch_error_when_tripped():
    """``KillSwitch.trip()`` between stream and dispatch → ``ToolUseDone`` carries
    ``error="kill_switch_tripped"`` and the underlying handler never runs."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover
        invoked.append(kwargs)
        return {"ok": True}

    from sabrina.tools import ToolSpec

    spec = ToolSpec(
        name="noop_action",
        description="real",
        input_schema={"type": "object"},
        handler=real_handler,
    )

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "noop_action", {"content": "x"}),
        _terminal_round("aborted."),
    ])

    ks = KillSwitch()
    ks.trip()  # already tripped before chat() runs

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="run it")],
        tools=[spec],
        kill_switch=ks,
        dry_run=False,
    ):
        events.append(ev)

    assert invoked == []
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "kill_switch_tripped"
    assert done_ev.result is None

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["is_error"] is True


async def test_claude_dispatch_dry_run_still_honors_kill_switch():
    """``dry_run=True`` AND tripped kill-switch → kill-switch wins (poll
    is pre-dispatch, before the dry-run wrapper would run)."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover
        invoked.append(kwargs)
        return {"ok": True}

    from sabrina.tools import ToolSpec

    spec = ToolSpec(
        name="noop_action",
        description="real",
        input_schema={"type": "object"},
        handler=real_handler,
    )

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "noop_action", {"content": "x"}),
        _terminal_round("aborted."),
    ])

    ks = KillSwitch()
    ks.trip()

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="run it")],
        tools=[spec],
        kill_switch=ks,
        dry_run=True,
    ):
        events.append(ev)

    assert invoked == []
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "kill_switch_tripped"
    # Crucial: the dry-run synthetic shape must NOT appear when kill-switch
    # has won the race. The result is None on this turn.
    assert done_ev.result is None
