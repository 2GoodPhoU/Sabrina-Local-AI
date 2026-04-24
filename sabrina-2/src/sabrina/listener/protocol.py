"""Listener protocol and result types.

Input contract for `transcribe()`:
  - pathlib.Path to a .wav/.mp3/.flac/etc file (decoded by the backend), OR
  - numpy.ndarray of float32 mono samples at 16 kHz, shape (N,), range [-1, 1].

The 16 kHz requirement matches Whisper's expected sample rate. Callers that
record from `sounddevice` should request 16000 Hz mono float32 directly — we
don't resample here; garbage in, garbage out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np  # for the Audio type alias


Audio = "Path | np.ndarray"  # documentary only; runtime uses duck typing


@dataclass(frozen=True, slots=True)
class Segment:
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str  # concatenated segment text, stripped
    language: str  # ISO-639-1 code (e.g. "en")
    language_prob: float  # 0..1, backend confidence
    audio_duration_s: float  # length of the input clip
    transcribe_duration_s: float  # wall time spent transcribing
    segments: tuple[Segment, ...] = field(default_factory=tuple)

    @property
    def rtf(self) -> float:
        """Real-time factor. <1 means we transcribe faster than real-time."""
        if self.audio_duration_s <= 0:
            return 0.0
        return self.transcribe_duration_s / self.audio_duration_s


@runtime_checkable
class Listener(Protocol):
    """An ASR backend that transcribes audio to text."""

    name: str  # e.g. "faster-whisper:base.en@cuda"

    async def transcribe(
        self,
        audio: Path | object,  # Path or numpy.ndarray float32 mono 16k
        *,
        language: str | None = None,
    ) -> Transcript:
        """Transcribe `audio`. Blocks until finished; use asyncio.to_thread
        inside the implementation to keep the event loop free."""
        ...
