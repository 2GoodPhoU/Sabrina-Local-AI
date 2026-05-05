"""Validate the structural shape of `sabrina-2/data/shortcuts.yaml`.

Per QUEUE item P5.2, the data file must parse to a mapping of names to
(modifier..., key) tuples of strings. The legacy table at
`services/automation/automation.py:47-65` is the source of truth; this
test guards against drift in the YAML port.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Recognised modifier tokens. Mirrors what pyautogui / keyboard / pynput
# accept and what the legacy table actually uses (no `cmd`/`alt`/`super`
# in the legacy data, so they're omitted to keep the guard tight).
_MODIFIER_TOKENS = frozenset({"ctrl", "shift", "alt", "win"})

_SHORTCUTS_YAML = (
    Path(__file__).resolve().parent.parent / "data" / "shortcuts.yaml"
)


def _load_shortcuts() -> dict[str, list[str]]:
    with _SHORTCUTS_YAML.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict), "shortcuts.yaml must parse to a mapping"
    return data


def test_shortcuts_yaml_exists() -> None:
    assert _SHORTCUTS_YAML.is_file(), f"missing: {_SHORTCUTS_YAML}"


def test_shortcuts_yaml_is_non_empty_mapping() -> None:
    data = _load_shortcuts()
    assert data, "shortcuts.yaml must declare at least one entry"


@pytest.mark.parametrize(
    "name",
    [
        "copy",
        "paste",
        "cut",
        "save",
        "select_all",
        "undo",
        "redo",
        "find",
        "new_tab",
        "close_tab",
        "switch_tab",
        "screenshot",
        "task_view",
        "file_explorer",
        "system_settings",
        "lock_screen",
        "app_search",
    ],
)
def test_legacy_entries_present(name: str) -> None:
    """Every legacy shortcut name carries through to the YAML port."""
    data = _load_shortcuts()
    assert name in data, f"legacy shortcut '{name}' missing from shortcuts.yaml"


def test_every_entry_parses_to_tuple_of_strings() -> None:
    """Each entry decomposes into (modifier..., key) — all strings, len >= 2.

    The DoD frames every entry as a `(modifier, key)` tuple; in practice
    `screenshot` carries two modifiers (win + shift + s), so the guard is
    "non-empty list of strings with at least one modifier and a final key".
    """
    data = _load_shortcuts()
    for name, value in data.items():
        assert isinstance(name, str) and name, (
            f"shortcut name must be a non-empty string, got {name!r}"
        )
        assert isinstance(value, list), (
            f"shortcut '{name}' must be a list, got {type(value).__name__}"
        )
        assert len(value) >= 2, (
            f"shortcut '{name}' must have >= 2 tokens (modifier + key), "
            f"got {value!r}"
        )
        for tok in value:
            assert isinstance(tok, str) and tok, (
                f"shortcut '{name}' has non-string or empty token: {tok!r}"
            )

        # The leading elements are modifiers; the final element is the key.
        modifiers, key = value[:-1], value[-1]
        for mod in modifiers:
            assert mod in _MODIFIER_TOKENS, (
                f"shortcut '{name}' has unknown modifier '{mod}' "
                f"(expected one of {sorted(_MODIFIER_TOKENS)})"
            )
        # The action key itself can be a letter, a named key like 'tab',
        # or any single token; just guard that it's not itself a modifier
        # (a modifier-only chord is not a usable shortcut).
        assert key not in _MODIFIER_TOKENS or len(value) == 1, (
            f"shortcut '{name}' ends in a modifier token '{key}'; "
            "the final token should be the action key"
        )
