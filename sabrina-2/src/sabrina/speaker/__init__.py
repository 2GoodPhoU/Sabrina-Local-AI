"""Pluggable text-to-speech backends.

Every backend implements the `Speaker` protocol in protocol.py. The rest of
Sabrina only depends on the protocol, never on a concrete engine.
"""

from sabrina.speaker.protocol import Speaker, SpeakResult

__all__ = ["Speaker", "SpeakResult"]
