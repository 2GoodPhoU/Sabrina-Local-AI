"""Pluggable reasoning backends.

Every backend implements the `Brain` protocol defined in protocol.py.
The rest of Sabrina only depends on the protocol, never on a concrete backend.
"""

from sabrina.brain.protocol import (
    Brain,
    Done,
    Message,
    TextDelta,
    StreamEvent,
)

__all__ = ["Brain", "Done", "Message", "TextDelta", "StreamEvent"]
