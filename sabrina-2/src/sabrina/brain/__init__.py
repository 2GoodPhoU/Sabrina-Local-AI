"""Pluggable reasoning backends.

Every backend implements the `Brain` protocol defined in protocol.py.
The rest of Sabrina only depends on the protocol, never on a concrete backend.
"""

from sabrina.brain.protocol import (
    Brain,
    Done,
    Message,
    StreamEvent,
    TextDelta,
)
from sabrina.brain.router import (
    Router,
    RouterMisconfigured,
    make_router_from_settings,
)

__all__ = [
    "Brain",
    "Done",
    "Message",
    "Router",
    "RouterMisconfigured",
    "StreamEvent",
    "TextDelta",
    "make_router_from_settings",
]
