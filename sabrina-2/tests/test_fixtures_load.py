"""Validate the JSON test fixtures ported from legacy `scripts/`.

Per QUEUE item P5.4, two fixtures land under `sabrina-2/tests/data/`:

- `conversation_history.json` — a list of `{role, content}` message dicts;
  the legacy roles are `system`, `user`, `assistant`. P5.5 (pytest
  scaffolding) will read this when constructing fake-brain conversations.
- `default_memory.json` — a top-level mapping describing the persona /
  preferences / capabilities snapshot that the legacy memory store
  bootstrapped from. Used by P5.5 fixtures + any future memory-store
  fixture work.

The test guards against shape drift in either fixture without pinning
to the exact field set (so a future fixture extension doesn't break
this gate).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_DATA_DIR = Path(__file__).resolve().parent / "data"
_CONVERSATION_HISTORY = _DATA_DIR / "conversation_history.json"
_DEFAULT_MEMORY = _DATA_DIR / "default_memory.json"

# The roles the legacy fixture actually uses. Tightening to this set
# guards against accidental new roles slipping in via cargo-culted
# additions (e.g. `tool`, `function`) that the rebuild hasn't committed
# to yet — those would land via P4 brain-router work, not via fixture
# drift.
_LEGACY_ROLES = frozenset({"system", "user", "assistant"})


# --- conversation_history.json --------------------------------------------


def test_conversation_history_exists() -> None:
    assert _CONVERSATION_HISTORY.is_file(), f"missing: {_CONVERSATION_HISTORY}"


def test_conversation_history_parses_as_json_list() -> None:
    with _CONVERSATION_HISTORY.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, list), (
        f"conversation_history.json must parse to a list, "
        f"got {type(data).__name__}"
    )
    assert data, "conversation_history.json must contain at least one message"


def test_conversation_history_message_shape() -> None:
    """Every entry is a `{role: str, content: str}` dict."""
    with _CONVERSATION_HISTORY.open(encoding="utf-8") as fh:
        messages = json.load(fh)
    for idx, msg in enumerate(messages):
        assert isinstance(msg, dict), (
            f"message[{idx}] must be a dict, got {type(msg).__name__}"
        )
        assert "role" in msg, f"message[{idx}] missing 'role'"
        assert "content" in msg, f"message[{idx}] missing 'content'"
        assert isinstance(msg["role"], str) and msg["role"], (
            f"message[{idx}].role must be a non-empty string, got {msg['role']!r}"
        )
        assert isinstance(msg["content"], str), (
            f"message[{idx}].content must be a string, "
            f"got {type(msg['content']).__name__}"
        )


def test_conversation_history_roles_are_legacy_set() -> None:
    """All roles fall in `{system, user, assistant}` — no surprise roles."""
    with _CONVERSATION_HISTORY.open(encoding="utf-8") as fh:
        messages = json.load(fh)
    seen_roles = {m["role"] for m in messages}
    unknown = seen_roles - _LEGACY_ROLES
    assert not unknown, (
        f"conversation_history.json uses unexpected role(s) {sorted(unknown)}; "
        f"legacy fixture only ships {sorted(_LEGACY_ROLES)}"
    )


# --- default_memory.json --------------------------------------------------


def test_default_memory_exists() -> None:
    assert _DEFAULT_MEMORY.is_file(), f"missing: {_DEFAULT_MEMORY}"


def test_default_memory_parses_as_json_object() -> None:
    with _DEFAULT_MEMORY.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), (
        f"default_memory.json must parse to a mapping, "
        f"got {type(data).__name__}"
    )
    assert data, "default_memory.json must declare at least one top-level key"


@pytest.mark.parametrize(
    "key",
    [
        "name",
        "description",
        "personality",
        "user_preferences",
    ],
)
def test_default_memory_carries_load_bearing_keys(key: str) -> None:
    """The legacy fixture's load-bearing keys port through.

    Pinned to the four keys P5.5 fixtures will actually read against
    (persona name + description + personality block + preferences).
    Other top-level keys (`special_capabilities`, `user_defined_traits`,
    `memory_system`) are not pinned here so the fixture can evolve
    without breaking this gate.
    """
    with _DEFAULT_MEMORY.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert key in data, (
        f"default_memory.json missing load-bearing top-level key '{key}'"
    )


def test_default_memory_string_typed_top_level() -> None:
    """`name` and `description` are strings; nested blocks are dicts."""
    with _DEFAULT_MEMORY.open(encoding="utf-8") as fh:
        data = json.load(fh)
    for k in ("name", "description"):
        assert isinstance(data[k], str) and data[k], (
            f"default_memory.json[{k!r}] must be a non-empty string, "
            f"got {data[k]!r}"
        )
    for k in ("personality", "user_preferences"):
        assert isinstance(data[k], dict) and data[k], (
            f"default_memory.json[{k!r}] must be a non-empty mapping, "
            f"got {type(data[k]).__name__}"
        )
