"""``send_hotkey`` — keyboard-shortcut ToolSpec for the Phase-4 automation surface.

Per the spec at
``rebuild/drafts/research/2026-05-09-p4b2-send-hotkey-toolspec-spec.md``,
``send_hotkey`` is the first real action ToolSpec to ride on top of the
P4.B1 safety primitives (kill-switch + dry-run). The handler accepts a
shortcut name (e.g. ``"copy"``), looks the name up in the data file
``sabrina-2/data/shortcuts.yaml``, and presses the corresponding modifier
+ key combo on the user's keyboard.

Backend pick (spec Q1 (b)): ``pynput.keyboard.Controller`` — pynput is
already in the dep tree post-P4.B1; consolidating keyboard primitives
on one library keeps the surface coherent. A small token-translation
table maps the YAML's friendly tokens (``"ctrl"``, ``"win"``, etc.) to
``pynput.keyboard.Key`` members and bare characters.

Test seam (spec § "Proposed approach" → ``_KEYPRESS_FACTORY``):
module-level callable that the production code dispatches to. Default
fires a real keypress via the pynput Controller; tests override with a
``_RecordingKeypress`` callable that appends each call to a list, so
the unit tests never import pynput's actual keyboard listener.

Schema posture (spec Q2 (a)): the ``SEND_HOTKEY_SPEC.input_schema``
enumerates the known shortcut names so the model emits valid names by
construction. The handler-side ``UnknownShortcutError`` path is
defense-in-depth, not the primary failure handler.

Registration posture (spec § "Scope"): ``SEND_HOTKEY_SPEC`` is
exported but ``tools/__init__.py`` only adds it to ``BUILTIN_TOOLS``
when ``Settings().tools.send_hotkey_enabled`` is True — off by default
until P4.B4's Windows e2e validation ships.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sabrina.tools import ToolSpec


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HotkeyError(Exception):
    """Base class for hotkey-tool errors.

    Inherits ``Exception`` (not ``BaseException``) so the existing
    ``except Exception`` branch in ``ClaudeBrain.chat``'s tool-dispatch
    loop catches it cleanly and surfaces as
    ``ToolUseDone(error=...)``.
    """


class UnknownShortcutError(HotkeyError):
    """Raised when ``send_hotkey(name=...)`` cannot find ``name`` in the table.

    Carries ``.available`` (a sorted tuple of known names) so the
    model gets a useful tool_result error message and can self-correct
    on the next turn without a round-trip.
    """

    def __init__(self, name: str, available: Sequence[str]) -> None:
        self.name = name
        self.available: tuple[str, ...] = tuple(sorted(available))
        super().__init__(
            f"unknown shortcut {name!r}; available: {', '.join(self.available)}"
        )


class KeypressBackendError(HotkeyError):
    """Raised when the keypress backend itself errors (PATH, permission, etc.)."""


# ---------------------------------------------------------------------------
# Shortcut-table loader (run once at module import)
# ---------------------------------------------------------------------------


_SHORTCUTS_YAML = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "shortcuts.yaml"
)


def _load_shortcuts() -> dict[str, tuple[str, ...]]:
    """Read ``data/shortcuts.yaml`` once and freeze each value to a tuple.

    Spec rationale: ``data/shortcuts.yaml`` is a static checked-in file,
    not user-mutable runtime config; load-once is fine. If a future use
    case needs hot-reload, the cache is a single module-level dict and
    trivial to swap.
    """
    import yaml  # type: ignore[import-not-found]

    with _SHORTCUTS_YAML.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise RuntimeError(
            f"shortcuts.yaml at {_SHORTCUTS_YAML} did not parse to a mapping"
        )
    return {str(name): tuple(str(t) for t in tokens) for name, tokens in data.items()}


_SHORTCUTS: Mapping[str, tuple[str, ...]] = _load_shortcuts()


# ---------------------------------------------------------------------------
# Keypress backend (spec Q1 (b): pynput.keyboard.Controller)
# ---------------------------------------------------------------------------


# Token-translation map. The YAML uses friendly modifier strings
# (``"ctrl"``, ``"alt"``, ``"shift"``, ``"win"``) plus single-character
# keys (``"c"``, ``"v"``, ...) and one special key (``"tab"``). pynput's
# ``Key`` enum names match for ctrl/alt/shift/tab; the Windows-key on
# pynput is ``Key.cmd`` (cross-platform alias for the OS meta key).
#
# Unknown modifier tokens (a future YAML entry adding ``"meta"`` etc.)
# resolve to the literal string and pynput's Controller will raise at
# press-time — that surface is exactly the ``KeypressBackendError``
# path documented in the handler.
_MODIFIER_TOKENS: frozenset[str] = frozenset({"ctrl", "alt", "shift", "win"})
_KEY_ALIASES: Mapping[str, str] = {"win": "cmd"}


def _pynput_keypress(tokens: Sequence[str]) -> None:
    """Press the modifier+key chord via pynput's Controller.

    Token order: leading entries are modifiers (held down), final entry
    is the action key. Release happens in reverse order — symmetric
    press/release matches the OS dispatcher's expectation for a real
    Ctrl+C (or longer chord) chord rather than a sequence of keypresses.

    Resolves at call time so this module's import doesn't drag in
    pynput's keyboard controller on the test path — only the production
    backend factory invokes this.
    """
    # Late import: keeps the test path (which overrides
    # ``_KEYPRESS_FACTORY``) from pulling pynput into module import.
    from pynput.keyboard import Controller, Key  # type: ignore[import-not-found]

    if not tokens:
        raise KeypressBackendError("empty token list")

    resolved: list[Any] = []
    for token in tokens:
        if token in _MODIFIER_TOKENS:
            alias = _KEY_ALIASES.get(token, token)
            resolved.append(getattr(Key, alias))
        elif hasattr(Key, token):
            # Non-modifier special key, e.g. ``"tab"`` -> ``Key.tab``.
            resolved.append(getattr(Key, token))
        else:
            # Single character or unrecognised string — pass through.
            # pynput's Controller.press accepts ``str`` for letter keys.
            resolved.append(token)

    controller = Controller()
    pressed: list[Any] = []
    try:
        for key in resolved:
            controller.press(key)
            pressed.append(key)
    except Exception as exc:  # noqa: BLE001 — re-raise as KeypressBackendError below
        # Release whatever we managed to press so the keyboard doesn't
        # latch a modifier on partial failure.
        for key in reversed(pressed):
            try:
                controller.release(key)
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
        raise KeypressBackendError(f"press failed: {exc}") from exc
    # Release in reverse order so modifiers come off last (matching the
    # OS expectation that the action key releases first).
    for key in reversed(resolved):
        try:
            controller.release(key)
        except Exception as exc:  # noqa: BLE001
            raise KeypressBackendError(f"release failed: {exc}") from exc


# Module-level injection seam (mirrors ``_LISTENER_FACTORY`` in
# ``automation/kill_switch.py``). Tests override this attribute to point
# at a recording callable so the unit suite never imports pynput's
# Controller.
_KEYPRESS_FACTORY: Callable[[Sequence[str]], None] = _pynput_keypress


# ---------------------------------------------------------------------------
# Handler + ToolSpec
# ---------------------------------------------------------------------------


async def send_hotkey(name: str = "", **_extra: Any) -> dict[str, Any]:
    """Press a named keyboard shortcut on the user's machine.

    Args:
        name: shortcut name from the configured table
            (``data/shortcuts.yaml``). E.g. ``"copy"``.

    Returns:
        On success: ``{"success": True, "name": str, "tokens": list[str]}``.
        On empty/invalid ``name`` (defensive): ``{"success": False,
        "error": str}`` without raising.

    Raises:
        UnknownShortcutError: when ``name`` is not in the loaded table.
            The ``.available`` attribute carries the sorted list of
            known names for the model to self-correct.
        KeypressBackendError: when the keypress backend itself errors
            (PATH issues, permission errors, etc.). Both error types
            inherit ``HotkeyError`` and ``Exception``, so the existing
            ``except Exception`` branch in ``claude.py``'s dispatch loop
            catches them and surfaces as ``ToolUseDone(error=...)``.

    The brain calls this via the ``ToolSpec`` registry; ``**_extra``
    swallows any unknown kwargs so we don't blow up on a model that
    over-pads the call with unexpected fields. Defensive but cheap —
    mirrors ``write_clipboard``'s pattern.
    """
    if not isinstance(name, str) or not name:
        return {"success": False, "error": "name must be a non-empty string"}
    tokens = _SHORTCUTS.get(name)
    if tokens is None:
        raise UnknownShortcutError(name, available=tuple(_SHORTCUTS))
    try:
        await asyncio.to_thread(_KEYPRESS_FACTORY, tokens)
    except KeypressBackendError:
        # Already the right exception type; re-raise as-is.
        raise
    except Exception as exc:  # noqa: BLE001 — wrap any unexpected backend error
        raise KeypressBackendError(str(exc)) from exc
    return {"success": True, "name": name, "tokens": list(tokens)}


def _build_send_hotkey_spec() -> ToolSpec:
    """Build the ToolSpec.

    The input-schema ``name`` field enumerates loaded shortcut names
    (spec Q2 (a)) so the model emits valid names by construction. The
    enum is constructed at module-import time from the loaded YAML —
    one source of truth; the data file is checked in so the coupling
    is fine.
    """
    known_names = sorted(_SHORTCUTS)
    return ToolSpec(
        name="send_hotkey",
        description=(
            "Press a named keyboard shortcut on the user's machine. "
            "Use this for OS-level actions like copy, paste, switch_tab, "
            "or open file_explorer. The shortcut name must come from the "
            "configured table; pick the closest match by intent."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Shortcut name from the configured table. "
                        "Valid names enumerated below."
                    ),
                    "enum": known_names,
                },
            },
            "required": ["name"],
        },
        handler=send_hotkey,
        # P4.B3: ``send_hotkey`` is the first destructive ToolSpec.
        # Keypress effects are irreversible-ish (the foreground app
        # already processed them by the time the brain learns the
        # action fired). The allow-list at
        # ``sabrina.automation.allow_list`` blocks invocation unless
        # ``settings.automation.destructive_actions`` contains
        # ``"send_hotkey"`` — Eric flips two flags to enable
        # (``[tools] send_hotkey_enabled = true`` AND
        # ``[automation] destructive_actions = ["send_hotkey"]``).
        destructive=True,
    )


SEND_HOTKEY_SPEC: ToolSpec = _build_send_hotkey_spec()
