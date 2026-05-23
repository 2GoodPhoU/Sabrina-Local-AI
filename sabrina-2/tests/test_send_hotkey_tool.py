"""P4.B2 ``send_hotkey`` ToolSpec — unit tests.

Fourteen tests per spec at
``rebuild/drafts/research/2026-05-09-p4b2-send-hotkey-toolspec-spec.md``
§ "Concrete DoD" item 5.

Test groups:

1. Data loader: ``_SHORTCUTS`` is populated, ``"copy"`` resolves,
   values are frozen tuples (not mutable lists).
2. Handler dispatch: factory-injection seam routes the keypress call;
   success-shape returns; empty-name defensive path; over-padded kwargs
   tolerated; unknown-name path raises ``UnknownShortcutError``;
   backend-error path raises ``KeypressBackendError``.
3. ToolSpec round-trip: ``to_anthropic_dict()`` and ``to_mcp_dict()``
   shape match the existing fingerprint (``test_smoke.py:1869-1965``).
4. Conditional registration: ``BUILTIN_TOOLS`` excludes the spec when
   disabled and includes it when ``send_hotkey_enabled=True``.
5. ClaudeBrain dispatch composition: dry-run wrap of ``send_hotkey``
   yields the synthetic shape from P4.B1 and does not invoke the
   keypress factory — the kill-switch + dry-run primitives compose
   cleanly with the new tool.
"""

from __future__ import annotations

import asyncio

import pytest

from sabrina.tools import _builtin_tools
from sabrina.tools import hotkey as hotkey_mod
from sabrina.tools.hotkey import (
    SEND_HOTKEY_SPEC,
    HotkeyError,
    KeypressBackendError,
    UnknownShortcutError,
    _SHORTCUTS,
    send_hotkey,
)


# ---------------------------------------------------------------------------
# Test fakes
# ---------------------------------------------------------------------------


class _RecordingKeypress:
    """Captures each call to the keypress backend.

    Replaces ``_KEYPRESS_FACTORY`` for the duration of a test; never
    imports pynput's Controller. ``raises`` lets a test simulate a
    backend failure.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.raises = raises

    def __call__(self, tokens) -> None:  # type: ignore[no-untyped-def]
        self.calls.append(tuple(tokens))
        if self.raises is not None:
            raise self.raises


@pytest.fixture
def recording_keypress(monkeypatch: pytest.MonkeyPatch) -> _RecordingKeypress:
    """Install a fresh ``_RecordingKeypress`` as the module's factory."""
    fake = _RecordingKeypress()
    monkeypatch.setattr(hotkey_mod, "_KEYPRESS_FACTORY", fake)
    return fake


# ---------------------------------------------------------------------------
# Group 1: data loader
# ---------------------------------------------------------------------------


def test_shortcuts_loaded_from_yaml() -> None:
    assert isinstance(_SHORTCUTS, dict)
    assert len(_SHORTCUTS) > 0
    # Anchor entry: "copy" must always be in the table (legacy parity).
    assert _SHORTCUTS["copy"] == ("ctrl", "c")


def test_shortcuts_values_are_frozen_tuples() -> None:
    """Every value is a ``tuple`` of strings, not a ``list`` (mutability guard)."""
    for name, tokens in _SHORTCUTS.items():
        assert isinstance(tokens, tuple), f"{name!r} is not a tuple"
        assert all(isinstance(t, str) for t in tokens), (
            f"{name!r} has non-string tokens: {tokens!r}"
        )


# ---------------------------------------------------------------------------
# Group 2: handler dispatch
# ---------------------------------------------------------------------------


def test_send_hotkey_dispatches_to_keypress_factory(
    recording_keypress: _RecordingKeypress,
) -> None:
    asyncio.run(send_hotkey(name="copy"))
    assert recording_keypress.calls == [("ctrl", "c")]


def test_send_hotkey_returns_success_shape(
    recording_keypress: _RecordingKeypress,
) -> None:
    result = asyncio.run(send_hotkey(name="copy"))
    assert result == {"success": True, "name": "copy", "tokens": ["ctrl", "c"]}


def test_send_hotkey_unknown_shortcut_raises_unknown_shortcut_error(
    recording_keypress: _RecordingKeypress,
) -> None:
    with pytest.raises(UnknownShortcutError) as excinfo:
        asyncio.run(send_hotkey(name="totally-not-a-shortcut"))
    err = excinfo.value
    # ``.available`` carries the sorted list so the model can self-correct.
    assert "copy" in err.available
    # Sorted contract — verify by re-sorting the tuple matches its own order.
    assert list(err.available) == sorted(err.available)
    # Exception inherits HotkeyError + Exception so claude.py's
    # ``except Exception`` branch catches it.
    assert isinstance(err, HotkeyError)
    assert isinstance(err, Exception)


def test_send_hotkey_unknown_shortcut_does_not_call_keypress_factory(
    recording_keypress: _RecordingKeypress,
) -> None:
    with pytest.raises(UnknownShortcutError):
        asyncio.run(send_hotkey(name="foo"))
    assert recording_keypress.calls == []


def test_send_hotkey_empty_name_returns_error_shape(
    recording_keypress: _RecordingKeypress,
) -> None:
    result = asyncio.run(send_hotkey(name=""))
    assert result["success"] is False
    assert "non-empty string" in result["error"]
    # Defensive path: factory is never called.
    assert recording_keypress.calls == []


def test_send_hotkey_extra_kwargs_tolerated(
    recording_keypress: _RecordingKeypress,
) -> None:
    """Model-emitted over-padding (``extra="ignored"``) must not blow up."""
    result = asyncio.run(send_hotkey(name="copy", extra="ignored", foo=42))
    assert result["success"] is True
    assert recording_keypress.calls == [("ctrl", "c")]


def test_send_hotkey_keypress_backend_error_raises_keypress_backend_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _RecordingKeypress(raises=RuntimeError("backend missing"))
    monkeypatch.setattr(hotkey_mod, "_KEYPRESS_FACTORY", fake)
    with pytest.raises(KeypressBackendError) as excinfo:
        asyncio.run(send_hotkey(name="copy"))
    assert "backend missing" in str(excinfo.value)
    # Factory WAS invoked — error happens inside the backend, not before it.
    assert fake.calls == [("ctrl", "c")]


# ---------------------------------------------------------------------------
# Group 3: ToolSpec round-trip
# ---------------------------------------------------------------------------


def test_send_hotkey_spec_round_trips_to_anthropic_dict() -> None:
    spec_dict = SEND_HOTKEY_SPEC.to_anthropic_dict()
    assert spec_dict["name"] == "send_hotkey"
    assert isinstance(spec_dict["description"], str)
    assert spec_dict["description"]  # non-empty
    schema = spec_dict["input_schema"]
    assert schema["type"] == "object"
    assert schema["required"] == ["name"]
    # Q2 (a): the ``name`` field is an enum of known shortcut names.
    name_prop = schema["properties"]["name"]
    assert name_prop["type"] == "string"
    assert "enum" in name_prop
    assert "copy" in name_prop["enum"]
    # Enum is sorted (spec § "Proposed approach" → `known_names = sorted(_SHORTCUTS)`).
    assert name_prop["enum"] == sorted(name_prop["enum"])


def test_send_hotkey_spec_round_trips_to_mcp_dict() -> None:
    mcp = SEND_HOTKEY_SPEC.to_mcp_dict()
    # MCP variant uses ``inputSchema`` (camelCase); same shape otherwise.
    assert mcp["name"] == "send_hotkey"
    assert "inputSchema" in mcp
    assert "input_schema" not in mcp
    assert mcp["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# Group 4: conditional registration
# ---------------------------------------------------------------------------


def test_send_hotkey_not_in_builtin_tools_when_disabled() -> None:
    """Default ``sabrina.toml`` has ``send_hotkey_enabled = false``.

    The module-level ``BUILTIN_TOOLS`` reflects the on-disk default, so
    a fresh import does NOT include ``send_hotkey``.
    """
    from sabrina.tools import BUILTIN_TOOLS

    assert all(spec.name != "send_hotkey" for spec in BUILTIN_TOOLS)


def test_send_hotkey_in_builtin_tools_when_enabled() -> None:
    """``_builtin_tools(settings=...)`` honours injected settings.

    Tests can call the function with a constructed ``Settings`` (or any
    object exposing ``.tools.send_hotkey_enabled``) so the registry's
    conditional branch is exercised without re-importing the module.
    """

    class _FakeTools:
        send_hotkey_enabled = True

    class _FakeSettings:
        tools = _FakeTools()

    tools = _builtin_tools(settings=_FakeSettings())
    assert any(spec.name == "send_hotkey" for spec in tools)
    # ``write_clipboard`` still registered alongside.
    assert any(spec.name == "write_clipboard" for spec in tools)


# ---------------------------------------------------------------------------
# Group 5: ClaudeBrain dispatch composition (dry-run wrap)
# ---------------------------------------------------------------------------


def test_claude_dispatch_dry_run_wraps_send_hotkey(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``dry_run_wrap`` composes cleanly with ``send_hotkey``.

    The P4.B1 (a)-half ships ``dry_run_wrap(handler, name=...)`` which
    returns a coroutine emitting the synthetic dry-run shape and never
    invokes the underlying handler. P4.B2's send_hotkey must compose
    with that wrap without re-implementing the dry-run path.
    """
    from sabrina.automation.dry_run import dry_run_wrap

    fake = _RecordingKeypress()
    monkeypatch.setattr(hotkey_mod, "_KEYPRESS_FACTORY", fake)

    wrapped = dry_run_wrap(send_hotkey, name="send_hotkey")
    result = asyncio.run(wrapped(name="copy"))

    # Synthetic dry-run shape from P4.B1.
    assert result.get("dry_run") is True
    assert result.get("would_have_called") == "send_hotkey"
    assert result.get("input") == {"name": "copy"}
    # Underlying keypress factory MUST NOT have fired.
    assert fake.calls == []


