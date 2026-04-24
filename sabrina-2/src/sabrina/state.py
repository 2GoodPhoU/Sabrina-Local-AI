"""Explicit state machine.

Five states, documented transitions. Illegal transitions raise loudly.
Every transition publishes a StateChanged event on the bus.
"""

from __future__ import annotations

from sabrina.bus import EventBus
from sabrina.events import StateChanged, StateName
from sabrina.logging import get_logger

log = get_logger(__name__)


# Directed graph of allowed transitions. Add edges when subsystems need them.
_ALLOWED: dict[StateName, set[StateName]] = {
    "idle": {"listening", "thinking", "speaking", "acting"},
    "listening": {"idle", "thinking"},
    "thinking": {"idle", "speaking", "acting"},
    "speaking": {"idle", "listening", "thinking", "acting"},
    "acting": {"idle", "thinking", "speaking"},
}


class IllegalTransition(RuntimeError):
    pass


class StateMachine:
    def __init__(self, bus: EventBus, initial: StateName = "idle") -> None:
        self._bus = bus
        self._state: StateName = initial

    @property
    def state(self) -> StateName:
        return self._state

    async def transition(self, to: StateName, reason: str = "") -> None:
        frm = self._state
        if to == frm:
            return
        if to not in _ALLOWED.get(frm, set()):
            raise IllegalTransition(
                f"Cannot transition {frm} -> {to} (reason: {reason!r})"
            )
        log.info("state.transition", from_state=frm, to_state=to, reason=reason)
        self._state = to
        await self._bus.publish(
            StateChanged(from_state=frm, to_state=to, reason=reason)
        )
