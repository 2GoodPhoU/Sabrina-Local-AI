"""Pluggable speech-to-text backends.

Every backend implements the `Listener` protocol in protocol.py. Sabrina
depends only on the protocol; concrete engines (faster-whisper today,
whisper.cpp later) live behind it.
"""

from sabrina.listener.protocol import Listener, Segment, Transcript
from sabrina.listener.vad import AudioMonitor, SileroVAD
from sabrina.listener.wake_word import WakeWordDetector, WakeWordMonitor

__all__ = [
    "AudioMonitor",
    "Listener",
    "Segment",
    "SileroVAD",
    "Transcript",
    "WakeWordDetector",
    "WakeWordMonitor",
]
