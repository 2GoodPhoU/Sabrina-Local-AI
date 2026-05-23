"""Kill-switch — global-hotkey abort for in-flight automation handlers.

The kill-switch is the single most load-bearing safety primitive per
``rebuild/drafts/research/2026-04-26-threat-model.md``. v1 surface:

- One context manager (``KillSwitch``) per voice-loop run. ``__enter__``
  registers a global hotkey listener; ``__exit__`` unregisters it.
- Inside any automation handler the brain dispatches, the dispatcher
  calls ``ks.check()`` between safe points. ``check()`` raises
  ``KillSwitchTripped`` if the hotkey has fired, the existing
  ``ClaudeBrain.chat`` error branch catches it, and the model sees a
  ``ToolUseDone(error="kill_switch_tripped")`` shape so the next turn's
  context reflects the abort.
- The actual ``pynput.keyboard.GlobalHotKeys`` listener is Windows-only.
  Linux test runs use a no-op stub registered behind ``_LISTENER_FACTORY``
  so the unit tests never import ``pynput``.

Hotkey binding defaults to ``<ctrl>+<alt>+k`` and can be overridden via
``[automation] kill_switch_hotkey`` (spec Q1 (b), per Eric's dashboard
answer at NEEDS-INPUT.md:116 — "Same default as A but the escape hatch
is ~10 lines and matches the existing TOML knob pattern"). The
``config.AutomationConfig.kill_switch_hotkey`` field carries the
override; the voice-loop instantiation reads it and passes it through
``KillSwitch(hotkey=settings.automation.kill_switch_hotkey)``.

Pattern mirrors ``CancelToken`` at ``brain/protocol.py:43-50`` — a
``bool`` flag with read-after-write semantics, atomic in CPython.
The trip handler doesn't need the event loop; the ``pynput`` listener
runs on its own thread and writes the flag.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from sabrina.logging import get_logger

log = get_logger(__name__)


# Default hotkey (spec Q1 (b), per Eric's 2026-05-15 dashboard answer at
# NEEDS-INPUT.md:116). v1 default; ``AutomationConfig.kill_switch_hotkey``
# overrides via toml. Keeping the constant as the resolver fallback means
# code paths that construct ``KillSwitch()`` without a settings handle
# (tests, ad-hoc REPL sessions) still get a sane chord.
DEFAULT_KILL_SWITCH_HOTKEY = "<ctrl>+<alt>+k"


class KillSwitchTripped(Exception):
    """Raised by ``KillSwitch.check()`` when the trip flag is set.

    Inherits ``Exception`` (not ``BaseException``) so the existing
    tool-dispatch ``except Exception`` branch in ``ClaudeBrain.chat``
    catches it and surfaces as ``ToolUseDone(error="kill_switch_tripped")``.
    """


class _Listener(Protocol):
    """Shape any listener factory must satisfy.

    Real ``pynput.keyboard.GlobalHotKeys`` exposes ``.start()`` /
    ``.stop()``. The no-op stub used in tests adds ``.fire()`` so a
    test can simulate a hotkey press programmatically without the
    pynput import.
    """

    def start(self) -> None: ...
    def stop(self) -> None: ...


class _NoopListener:
    """Linux/sandbox stub. Never observes a real hotkey.

    Tests can override the factory to return their own fake instance
    and call ``.fire()`` to simulate a press, but in regular Linux
    runs this listener is what the kill switch instantiates by default
    so production code never touches ``pynput`` outside Windows.
    """

    def __init__(self, on_trip: Callable[[], None]) -> None:
        self._on_trip = on_trip
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def fire(self) -> None:
        """Simulate a hotkey press (test-only)."""
        self._on_trip()


def _default_listener_factory(
    on_trip: Callable[[], None], hotkey: str = DEFAULT_KILL_SWITCH_HOTKEY
) -> _Listener:
    """Build the platform-default listener.

    On Linux / sandbox we always return ``_NoopListener`` so the unit
    tests don't need ``pynput``. On Windows the real factory comes from
    the (b)-half wire-up in P4.B4 — until that ships, the default is
    still the no-op stub (the safety primitive lands cleanly even if a
    pre-P4.B4 install has no working listener).
    """
    return _NoopListener(on_trip)


# Module-level injection seam (spec § "Proposed approach" → kill_switch.py).
# Tests override this attribute to point at a fake factory so the
# context manager calls into a mock instead of the platform default.
# Type left loose (``Any``) so test fakes don't have to match the
# Protocol exactly — the surface they need is ``.start()`` / ``.stop()``,
# nothing else.
_LISTENER_FACTORY: Callable[..., Any] = _default_listener_factory


class KillSwitch:
    """Context manager wrapping the global-hotkey listener for one voice run.

    Single-instance-per-run pattern — the (b)-half will instantiate
    one ``KillSwitch`` in ``voice_loop.py`` and thread it into
    ``ClaudeBrain.chat`` so every tool dispatch shares the same flag.

    Public surface:

    - ``.tripped`` (bool, read-only) — True after the hotkey fires.
    - ``.trip()`` — programmatic trip (what tests call).
    - ``.check()`` — raises ``KillSwitchTripped`` if tripped; else
      returns None. The dispatcher polls this between safe points
      (mirrors ``CancelToken.cancelled`` polling).
    """

    def __init__(self, hotkey: str = DEFAULT_KILL_SWITCH_HOTKEY) -> None:
        self._tripped: bool = False
        self._hotkey = hotkey
        self._listener: _Listener | None = None

    @property
    def tripped(self) -> bool:
        return self._tripped

    def trip(self) -> None:
        """Programmatically set the trip flag.

        Tests call this directly; the listener calls it via the
        ``on_trip`` callback registered at ``__enter__``.
        """
        if not self._tripped:
            log.info(
                "automation.kill_switch.tripped",
                hotkey=self._hotkey,
            )
        self._tripped = True

    def check(self) -> None:
        """Raise ``KillSwitchTripped`` if the flag is set; else return."""
        if self._tripped:
            raise KillSwitchTripped(
                f"kill_switch_tripped (hotkey={self._hotkey})"
            )

    def __enter__(self) -> "KillSwitch":
        # Register the listener via the injection seam. The factory
        # owns the platform-specific import (pynput on Windows, no-op
        # stub on Linux/sandbox).
        self._listener = _LISTENER_FACTORY(self.trip, self._hotkey)
        self._listener.start()
        return self

    def __exit__(
        self, exc_type: object, exc: object, tb: object
    ) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            finally:
                self._listener = None
