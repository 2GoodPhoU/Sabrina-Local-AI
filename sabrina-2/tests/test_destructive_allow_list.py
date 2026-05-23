"""P4.B3 Destructive-action allow-list — sixteen unit tests.

Spec at ``rebuild/drafts/research/2026-05-09-p4b3-destructive-action-allowlist-spec.md``.

Test groups (mirror spec § Concrete DoD #6):

1. ``ToolSpec.destructive`` additive field (4 tests):
   - default False
   - constructible True
   - omitted from ``to_anthropic_dict()``
   - omitted from ``to_mcp_dict()``

2. ``is_allowed`` pure resolver (5 tests):
   - passes non-destructive w/ empty allow-list
   - passes non-destructive w/ unrelated allow-list
   - blocks destructive w/ empty allow-list
   - blocks destructive w/ name not in allow-list
   - passes destructive w/ name in allow-list

3. ``check_allowed`` + ``DestructiveActionBlocked`` (3 tests):
   - returns None on pass
   - raises on block (type, name, allow_list shape)
   - exception's allow_list is an immutable tuple

4. ``ClaudeBrain`` dispatch integration (4 tests):
   - blocks destructive when not allow-listed (handler never invoked)
   - allows destructive when allow-listed
   - block precedes dry-run (ordering case)
   - block precedes kill-switch (ordering case)
"""

from __future__ import annotations

import json

import pytest

from sabrina.automation import allow_list as allow_list_mod
from sabrina.automation.allow_list import (
    DestructiveActionBlocked,
    check_allowed,
    is_allowed,
)
from sabrina.automation.kill_switch import KillSwitch
from sabrina.tools import ToolSpec


# ---------------------------------------------------------------------------
# Fakes — self-contained, mirror test_automation_safety.py + test_send_hotkey_tool.py.
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


# Duck-typed settings fakes — avoid constructing a real ``Settings``
# (which reads TOML/env). Only surfaces the allow-list code reads.
class _FakeAutomation:
    def __init__(self, destructive_actions):
        self.destructive_actions = list(destructive_actions)


class _FakeSettings:
    def __init__(self, destructive_actions):
        self.automation = _FakeAutomation(destructive_actions)


def _make_spec(name: str, destructive: bool, handler=None):
    async def _default_handler(**kwargs):
        return {"ok": True, "echo": kwargs}

    return ToolSpec(
        name=name,
        description=f"test spec {name!r}",
        input_schema={"type": "object"},
        handler=handler or _default_handler,
        destructive=destructive,
    )


# ---------------------------------------------------------------------------
# Group 1 — ToolSpec.destructive field (4 tests)
# ---------------------------------------------------------------------------


def test_toolspec_destructive_defaults_to_false():
    """``ToolSpec(...)`` without ``destructive=`` constructs with False."""
    async def _h(**_kw):
        return {}

    spec = ToolSpec(
        name="x",
        description="x",
        input_schema={"type": "object"},
        handler=_h,
    )
    assert spec.destructive is False


def test_toolspec_destructive_can_be_set_true():
    """``destructive=True`` round-trips through the frozen dataclass."""
    spec = _make_spec("y", destructive=True)
    assert spec.destructive is True


def test_toolspec_destructive_not_in_anthropic_dict():
    """``to_anthropic_dict()`` does not emit the Sabrina-internal flag."""
    spec = _make_spec("z", destructive=True)
    payload = spec.to_anthropic_dict()
    assert "destructive" not in payload
    assert set(payload.keys()) == {"name", "description", "input_schema"}


def test_toolspec_destructive_not_in_mcp_dict():
    """``to_mcp_dict()`` is also Sabrina-internal-flag-free."""
    spec = _make_spec("z", destructive=True)
    payload = spec.to_mcp_dict()
    assert "destructive" not in payload
    assert set(payload.keys()) == {"name", "description", "inputSchema"}


# ---------------------------------------------------------------------------
# Group 2 — is_allowed pure resolver (5 tests)
# ---------------------------------------------------------------------------


def test_is_allowed_passes_non_destructive_with_empty_allow_list():
    """Non-destructive specs always pass — empty allow-list doesn't matter."""
    spec = _make_spec("write_clipboard", destructive=False)
    settings = _FakeSettings(destructive_actions=[])
    assert is_allowed(spec, settings) is True


def test_is_allowed_passes_non_destructive_with_unrelated_allow_list():
    """Non-destructive specs pass regardless of allow-list contents."""
    spec = _make_spec("write_clipboard", destructive=False)
    settings = _FakeSettings(destructive_actions=["send_hotkey", "launch_app"])
    assert is_allowed(spec, settings) is True


def test_is_allowed_blocks_destructive_with_empty_allow_list():
    """Default-deny posture — destructive spec fails when allow-list is []."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=[])
    assert is_allowed(spec, settings) is False


def test_is_allowed_blocks_destructive_when_name_not_in_allow_list():
    """Destructive spec fails when its name isn't on the list (exact match)."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=["launch_app", "open_file"])
    assert is_allowed(spec, settings) is False


def test_is_allowed_passes_destructive_when_name_in_allow_list():
    """Destructive spec passes when its name is on the allow-list."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=["send_hotkey"])
    assert is_allowed(spec, settings) is True


# ---------------------------------------------------------------------------
# Group 3 — check_allowed + DestructiveActionBlocked (3 tests)
# ---------------------------------------------------------------------------


def test_check_allowed_returns_none_when_allowed():
    """Explicit None-return on pass (mirrors ``KillSwitch.check()``)."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=["send_hotkey"])
    assert check_allowed(spec, settings) is None


def test_check_allowed_raises_destructive_action_blocked_when_blocked():
    """Exception type, ``.name``, and message payload all surface."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=[])
    with pytest.raises(DestructiveActionBlocked) as excinfo:
        check_allowed(spec, settings)
    assert excinfo.value.name == "send_hotkey"
    # Allow-list snapshot rides on the exception (empty here).
    assert excinfo.value.allow_list == ()
    # Message names the tool so the dispatch error path can serialize
    # something useful to the model on the next turn.
    assert "send_hotkey" in str(excinfo.value)


def test_destructive_action_blocked_carries_allow_list():
    """Allow-list snapshot is a tuple (immutable), not a list (defensive)."""
    spec = _make_spec("send_hotkey", destructive=True)
    settings = _FakeSettings(destructive_actions=["launch_app", "open_file"])
    with pytest.raises(DestructiveActionBlocked) as excinfo:
        check_allowed(spec, settings)
    assert isinstance(excinfo.value.allow_list, tuple)
    assert excinfo.value.allow_list == ("launch_app", "open_file")


# ---------------------------------------------------------------------------
# Group 4 — ClaudeBrain dispatch integration (4 tests)
# ---------------------------------------------------------------------------


async def test_claude_dispatch_blocks_destructive_when_not_allowlisted():
    """Destructive spec + empty allow-list → ``ToolUseDone(error=...)``,
    handler never invoked, tool_result content marks ``is_error=True``."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover — must not run
        invoked.append(kwargs)
        return {"ok": True}

    spec = _make_spec("send_hotkey", destructive=True, handler=real_handler)
    settings = _FakeSettings(destructive_actions=[])

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "send_hotkey", {"name": "copy"}),
        _terminal_round("refused."),
    ])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="copy this")],
        tools=[spec],
        dry_run=False,
        settings=settings,
    ):
        events.append(ev)

    assert invoked == [], "destructive handler must not run when blocked"
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "destructive_action_blocked"
    assert done_ev.result is None

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["type"] == "tool_result"
    assert tr["is_error"] is True
    assert "send_hotkey" in tr["content"]


async def test_claude_dispatch_allows_destructive_when_allowlisted():
    """Destructive spec + name in allow-list → handler runs, real result
    rides into the follow-up ``tool_result`` block as on the happy path."""
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):
        invoked.append(kwargs)
        return {"ok": True, "echo": kwargs}

    spec = _make_spec("send_hotkey", destructive=True, handler=real_handler)
    settings = _FakeSettings(destructive_actions=["send_hotkey"])

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "send_hotkey", {"name": "copy"}),
        _terminal_round("done."),
    ])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="copy this")],
        tools=[spec],
        dry_run=False,
        settings=settings,
    ):
        events.append(ev)

    assert invoked == [{"name": "copy"}]
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error is None
    assert done_ev.result == {"ok": True, "echo": {"name": "copy"}}

    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["is_error"] is False
    assert json.loads(tr["content"]) == {"ok": True, "echo": {"name": "copy"}}


async def test_claude_dispatch_block_precedes_dry_run():
    """Combination case: destructive AND blocked AND ``dry_run=True`` →
    block error wins; the dry-run synthetic shape must NOT be returned.

    Spec rationale: dry-run is a debugging-friendly alternative to
    firing, but if the action is *blocked* the model should learn the
    refusal, not that a dry-run-would-have-fired. The dispatch loop
    polls allow-list first; dry-run wrap never runs.
    """
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover
        invoked.append(kwargs)
        return {"ok": True}

    spec = _make_spec("send_hotkey", destructive=True, handler=real_handler)
    settings = _FakeSettings(destructive_actions=[])

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "send_hotkey", {"name": "copy"}),
        _terminal_round("refused."),
    ])

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="copy this")],
        tools=[spec],
        dry_run=True,  # would have wrapped, but block wins
        settings=settings,
    ):
        events.append(ev)

    assert invoked == []
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "destructive_action_blocked"
    # Crucial: the dry-run synthetic shape must NOT appear.
    assert done_ev.result is None
    # The follow-up tool_result must carry the block reason, not the
    # dry-run synthetic shape.
    calls = brain._client.messages.calls
    last_user = calls[1]["messages"][-1]
    tr = last_user["content"][0]
    assert tr["is_error"] is True
    assert "destructive_action_blocked" in tr["content"]
    assert "dry_run" not in tr["content"]


async def test_claude_dispatch_block_precedes_kill_switch():
    """Combination case: destructive AND blocked AND kill-switch
    UNTRIPPED → block error fires; kill-switch never polled for this tool.

    The allow-list poll is positioned earlier in the dispatch loop so
    the block reason is surfaced specifically (``destructive_action_blocked``,
    not ``kill_switch_tripped``).
    """
    from sabrina.brain.protocol import Message, ToolUseDone

    invoked: list[dict] = []

    async def real_handler(**kwargs):  # pragma: no cover
        invoked.append(kwargs)
        return {"ok": True}

    spec = _make_spec("send_hotkey", destructive=True, handler=real_handler)
    settings = _FakeSettings(destructive_actions=[])

    brain = _make_claude_with([
        _round_with_tool_use("toolu_1", "send_hotkey", {"name": "copy"}),
        _terminal_round("refused."),
    ])

    ks = KillSwitch()
    # NOT tripped — the block reason should win regardless.
    assert ks.tripped is False

    events = []
    async for ev in brain.chat(
        [Message(role="user", content="copy this")],
        tools=[spec],
        kill_switch=ks,
        dry_run=False,
        settings=settings,
    ):
        events.append(ev)

    assert invoked == []
    done_ev = next(ev for ev in events if isinstance(ev, ToolUseDone))
    assert done_ev.error == "destructive_action_blocked"
    assert done_ev.result is None


# ---------------------------------------------------------------------------
# Auto-asyncio marker so the async tests above run cleanly under pytest
# without each one needing ``@pytest.mark.asyncio``.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _swap_default_resolver(monkeypatch):
    """Tests pass ``settings=`` explicitly — neutralize the lazy
    resolver so a leak doesn't accidentally read real TOML/env state.

    The fixture installs a fake-resolver that raises if called; tests
    that exercise the explicit-settings paths never trip it. A test
    that intentionally wanted to verify lazy-resolve would override
    this fixture locally.
    """
    def _raise():  # pragma: no cover — neutralizer; tests pass settings=
        raise AssertionError(
            "_RESOLVE_SETTINGS called during a test that passed settings= "
            "explicitly; check that the explicit path is wired correctly."
        )

    monkeypatch.setattr(allow_list_mod, "_RESOLVE_SETTINGS", _raise)
