"""Dry-run wrapper — let the brain "perform" actions without side effects.

When ``[automation] dry_run = true`` (the default), every automation
``ToolHandler`` the brain dispatches is wrapped in ``dry_run_wrap``
before invocation. The wrapper logs the would-be call at INFO and
returns a synthetic result of the shape::

    {"dry_run": True, "would_have_called": "<tool_name>", "input": {...}}

The model sees this as the ``tool_result`` content on the next round
trip and keeps reasoning about the conversation as if the action had
succeeded — useful for shaking out the dispatch path before any real
side effect exists.

Defense-in-depth posture (spec Q2 (a)): default True forever. A
misconfigured ``[tools] enabled = true`` plus a misregistered
destructive-action list, on a hosted automation install, won't fire
real actions until Eric explicitly flips ``dry_run = false`` in TOML.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from sabrina.logging import get_logger

if TYPE_CHECKING:
    from sabrina.config import Settings
    from sabrina.tools import ToolHandler

log = get_logger(__name__)


# Sentinel shape returned by ``dry_run_wrap``-produced handlers. The
# three keys are the contract surface; tests assert exact membership.
# Module-level constant rather than a dataclass to keep the wrapped
# handler's return type compatible with ``dict[str, Any]`` — every
# existing handler returns a plain dict; we don't redefine the shape.
DRY_RUN_RESULT_SHAPE: dict[str, Any] = {
    "dry_run": True,
    "would_have_called": "",  # filled per-call in dry_run_wrap
    "input": {},  # filled per-call in dry_run_wrap
}


def dry_run_wrap(handler: ToolHandler, *, name: str = "") -> ToolHandler:
    """Return a coroutine that logs the call and emits the dry-run shape.

    The original handler is NOT invoked — that's the whole point. ``name``
    is recorded in the synthetic result so the model sees which tool
    "would have" run; defaults to empty string so callers that only
    have the handler can still wrap, but the dispatch loop in
    ``brain/claude.py`` should always pass the real spec name.

    Pure-function wrapper. No state. The wrapped coroutine accepts the
    same ``(input_dict)`` shape as the underlying handler — kwargs only,
    matching the ``ToolHandler = Callable[..., Awaitable[dict[str, Any]]]``
    type alias in ``sabrina.tools``.
    """

    @functools.wraps(handler)
    async def _wrapped(**kwargs: Any) -> dict[str, Any]:
        log.info(
            "automation.dry_run.would_call",
            tool=name or getattr(handler, "__name__", "<unknown>"),
            input=kwargs,
        )
        return {
            "dry_run": True,
            "would_have_called": name
            or getattr(handler, "__name__", "<unknown>"),
            "input": dict(kwargs),
        }

    return _wrapped


def is_dry_run(settings: Settings | Any) -> bool:
    """Single source of truth for whether to wrap handlers in dry-run mode.

    Reads ``settings.automation.dry_run``. Defaults True if for any
    reason the field is missing from a partially-populated test
    fixture (defense-in-depth — a settings shape that doesn't yet
    have ``automation`` should not silently drop the protection).
    """
    automation = getattr(settings, "automation", None)
    if automation is None:
        return True
    return bool(getattr(automation, "dry_run", True))
