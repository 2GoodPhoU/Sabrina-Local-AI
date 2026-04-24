"""Pluggable speech-to-text backends.

Every backend implements the `Listener` protocol in protocol.py. Sabrina
depends only on the protocol; concrete engines (faster-whisper today,
whisper.cpp later) live behind it.
"""

from sabrina.listener.protocol import Listener, Segment, Transcript

__all__ = ["Listener", "Segment", "Transcript"]
