"""Mic capture utilities for ad-hoc ASR testing.

Records a fixed-length clip at 16 kHz mono float32 — the format Whisper wants
directly, no resampling. For the real voice loop this will be replaced by a
VAD-driven capture, but for `sabrina asr-record` a fixed duration is fine.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd

from sabrina.logging import get_logger

log = get_logger(__name__)

SAMPLE_RATE = 16000  # Whisper's native input rate


def record_clip(
    duration_s: float,
    device: int | str | None = None,
) -> np.ndarray:
    """Block for `duration_s`, return (N,) float32 mono PCM at 16 kHz."""
    n_frames = int(round(duration_s * SAMPLE_RATE))
    log.info("rec.start", duration_s=duration_s, device=str(device))
    audio = sd.rec(
        n_frames,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()
    log.info("rec.done", samples=int(audio.size))
    return audio.reshape(-1)
