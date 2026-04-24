"""Speaker protocol and result type.

Mirrors the Brain protocol: one method (speak), swappable backends, async, and
cancellable. Cancellation acts as the kill-switch for in-flight speech.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sabrina.brain.protocol import CancelToken


@dataclass(frozen=True, slots=True)
class SpeakResult:
    engine: str  # e.g. "piper:en_US-amy-medium", "sapi:Zira"
    duration_s: float  # wall time from call to playback finished
    sample_rate: int = 0  # 0 if engine doesn't expose it (e.g. SAPI)
    samples: int = 0  # 0 if not applicable


@runtime_checkable
class Speaker(Protocol):
    """A TTS backend that synthesizes and plays audio."""

    name: str  # e.g. "piper:en_US-amy-medium"

    async def speak(
        self,
        text: str,
        *,
        voice: str | None = None,
        cancel_token: CancelToken | None = None,
    ) -> SpeakResult:
        """Synthesize `text` and play it. Returns after playback finishes.

        Cancellation (asyncio.CancelledError) must stop playback promptly.
        If ``cancel_token`` is provided and fires during playback,
        implementations should stop playback and return a best-effort
        ``SpeakResult`` with whatever duration/samples elapsed before cancel.
        """
        ...

    async def stop(self) -> None:
        """Abort any in-flight speech immediately. Safe to call when idle."""
        ...
