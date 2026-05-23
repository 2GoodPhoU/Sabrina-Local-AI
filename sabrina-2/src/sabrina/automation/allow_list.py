"""Destructive-action allow-list — third leg of automation safety.

After ``kill_switch`` (P4.B1: trip-mid-action) and ``dry_run`` (P4.B1:
log-without-firing), the allow-list answers a third, different
question: *should this tool be allowed to fire at all?*

A ``destructive`` flag on ``ToolSpec`` (set at registration time) marks
tools whose effects are irreversible-ish — ``send_hotkey`` from P4.B2,
future ``launch_app`` / ``open_file``. At dispatch time, the tool-use
loop in ``brain/claude.py`` calls ``check_allowed(spec, settings)``
*before* the kill-switch and dry-run poll points. If the tool is
destructive AND its name is not in the user's
``[automation] destructive_actions`` allow-list, ``check_allowed``
raises ``DestructiveActionBlocked``; the dispatch error path emits
``ToolUseDone(error="destructive_action_blocked")`` so the model sees
the refusal on the next turn and re-plans without firing the action.

Default-deny posture (spec Q1 (a)): ``destructive_actions = []`` blocks
every destructive tool. A user enabling a dangerous tool has to flip
two flags — the tool-level ``[tools] send_hotkey_enabled = true`` *and*
``[automation] destructive_actions = ["send_hotkey"]``. Three-flip cost
is acceptable because the deliberate audit step is the feature.

Exact-match-only resolution (spec Q2 (a)): no glob, no regex. Each new
destructive tool requires its own explicit entry, so the security
posture doesn't leak forward in time when a future destructive tool
ships under a name a pre-existing glob would have happily matched.

Pattern mirrors P4.B1's ``kill_switch.py`` — typed exception inheriting
``Exception`` (so ``claude.py``'s existing ``except Exception`` branch
already catches it), pure pre-dispatch resolver, module-level
``_RESOLVE_SETTINGS`` injection seam for test-only fakes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from sabrina.logging import get_logger

if TYPE_CHECKING:
    from sabrina.config import Settings
    from sabrina.tools import ToolSpec

log = get_logger(__name__)


class DestructiveActionBlocked(Exception):
    """Raised by ``check_allowed`` when a destructive tool isn't allow-listed.

    Inherits ``Exception`` (not ``BaseException``) so the existing
    ``except Exception`` branch in ``ClaudeBrain.chat``'s tool-dispatch
    loop catches it and surfaces a
    ``ToolUseDone(error="destructive_action_blocked")``. The spec uses
    a separate ``except`` block for clarity (the error message is
    tool-specific), but ``Exception`` inheritance is the defensive
    floor — if the dispatch loop is refactored to merge error paths,
    nothing about this exception forces a special case.

    The payload (``.name``, ``.allow_list``) is what the dispatch error
    path serializes into the ``tool_result`` content. Useful to the
    model: "destructive action 'send_hotkey' blocked; allow-list: []"
    lets the next turn explain the refusal to the user without
    re-discovering which tool was attempted.
    """

    def __init__(self, name: str, *, allow_list: tuple[str, ...] = ()) -> None:
        self.name = name
        self.allow_list = allow_list
        super().__init__(
            f"destructive_action_blocked (tool={name!r}, allow_list={list(allow_list)!r})"
        )


def _default_resolve_settings() -> Settings:
    """Default settings resolver — lazy-loads via ``sabrina.config``.

    Tests override ``_RESOLVE_SETTINGS`` with a factory returning a
    duck-typed fake so unit tests don't have to construct a real
    ``Settings`` (which reads TOML / env). Mirrors the P4.B1
    ``_LISTENER_FACTORY`` and P4.B2 ``_KEYPRESS_FACTORY`` patterns.
    """
    from sabrina.config import load_settings

    return load_settings()


# Module-level injection seam. Tests overwrite this attribute with a
# fake-settings factory before calling ``is_allowed`` / ``check_allowed``
# without a ``settings=`` arg. Type left loose (``Callable[..., Any]``)
# so a duck-typed fake doesn't need to match the ``Settings`` Pydantic
# model exactly — the surface we read is ``settings.automation.destructive_actions``.
_RESOLVE_SETTINGS: Callable[[], Any] = _default_resolve_settings


def is_allowed(spec: ToolSpec, settings: Settings | Any | None = None) -> bool:
    """Pure resolver: True iff ``spec`` is safe to invoke.

    Rules (Q1 (a) + Q2 (a)):

    1. ``spec.destructive`` is False → always passes (non-destructive
       tools never hit the allow-list gate).
    2. ``spec.destructive`` is True AND ``spec.name`` appears verbatim
       in ``settings.automation.destructive_actions`` → passes.
    3. Else (destructive AND not allow-listed) → blocked.

    Defensive on missing ``automation`` field: if the settings shape
    doesn't expose ``automation`` (a partially-constructed test
    fixture, say), the function treats the destructive list as empty
    — default-deny outranks the convenience of a missing-section pass.
    """
    if not getattr(spec, "destructive", False):
        return True

    if settings is None:
        settings = _RESOLVE_SETTINGS()

    automation = getattr(settings, "automation", None)
    if automation is None:
        return False
    raw = getattr(automation, "destructive_actions", None)
    if raw is None:
        return False
    # Exact match only (spec Q2 (a)). Iterating preserves the order
    # the user wrote the list in (no set conversion) so a callable
    # downstream that wants the explicit allow-list can read it.
    return spec.name in raw


def check_allowed(
    spec: ToolSpec, settings: Settings | Any | None = None
) -> None:
    """Raise ``DestructiveActionBlocked`` if ``spec`` is destructive and not
    allow-listed; else return ``None`` silently.

    Mirrors ``KillSwitch.check()`` from P4.B1 — a void method that
    either returns silently or raises a typed exception. The dispatch
    loop in ``brain/claude.py`` calls this before kill-switch poll and
    before the dry-run wrap, so a blocked destructive call never
    reaches the handler at all (regardless of dry-run posture).
    """
    if is_allowed(spec, settings):
        return None

    if settings is None:
        settings = _RESOLVE_SETTINGS()
    automation = getattr(settings, "automation", None)
    raw = getattr(automation, "destructive_actions", None) if automation else None
    allow_list: tuple[str, ...] = tuple(raw) if raw else ()

    log.warning(
        "automation.allow_list.blocked",
        tool=spec.name,
        allow_list=list(allow_list),
    )
    raise DestructiveActionBlocked(spec.name, allow_list=allow_list)
