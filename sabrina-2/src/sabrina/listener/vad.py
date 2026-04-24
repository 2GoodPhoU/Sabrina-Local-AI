"""Silero VAD + AudioMonitor for barge-in (decision 009).

Two classes:

    SileroVAD      — stateful, frame-by-frame voice detector. Wraps the
                     `silero-vad` pip package (ONNX). Returns True once
                     `min_speech_ms` of continuous speech has accumulated.

    AudioMonitor   — sounddevice InputStream that runs during the voice
                     loop's `speaking` state. Feeds VAD on each callback,
                     trips a CancelToken on detection, and buffers the
                     captured audio so the voice loop can re-transcribe
                     without making the user press PTT again.

Both are "cheap to start, cheap to stop" — voice_loop spins them up on
entry to speaking and tears them down on exit. No long-lived threads
beyond the sounddevice callback thread that sounddevice manages.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import sounddevice as sd

from sabrina.brain.protocol import CancelToken
from sabrina.logging import get_logger

log = get_logger(__name__)


# Silero VAD's native frame size at 16 kHz. Model is trained on this;
# other sizes work but 512 is the documented sweet spot.
_FRAME_SAMPLES = 512
_SAMPLE_RATE = 16000


class SileroVAD:
    """ONNX-backed Silero VAD. Stateful across calls to `feed()`.

    Usage:
        vad = SileroVAD(threshold=0.5, min_speech_ms=300)
        vad.reset()                       # between speaking phases
        fired = vad.feed(chunk_float32)   # True once continuous speech >= min_speech_ms

    The model is loaded lazily on first `feed()` call — keeps VAD cost off
    the cold path for non-barge-in runs.
    """

    def __init__(self, threshold: float = 0.5, min_speech_ms: int = 300) -> None:
        self._threshold = float(threshold)
        self._min_speech_samples = int(min_speech_ms * _SAMPLE_RATE / 1000)
        self._model: Any | None = None
        self._speech_samples = 0
        self._pending: np.ndarray = np.zeros(0, dtype=np.float32)

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Lazy import — keeps torch/onnxruntime off cold path. silero-vad pip
        # package ships ONNX weights; no network call on first load.
        from silero_vad import load_silero_vad  # type: ignore[import-not-found]

        log.info("vad.loading", backend="silero-vad")
        self._model = load_silero_vad(onnx=True)
        log.info("vad.ready", threshold=self._threshold)

    def reset(self) -> None:
        """Clear VAD state. Call between speaking phases so dead-zone
        silence from the previous turn doesn't bleed into this one."""
        self._speech_samples = 0
        self._pending = np.zeros(0, dtype=np.float32)
        if self._model is not None:
            reset = getattr(self._model, "reset_states", None)
            if reset is not None:
                try:
                    reset()
                except Exception as exc:  # noqa: BLE001
                    log.debug("vad.reset_failed", err=str(exc))

    def feed(self, chunk: np.ndarray) -> bool:
        """Feed a float32 mono 16 kHz chunk. Return True once min_speech_ms
        of continuous speech has accumulated.

        Internally buffers sub-frame-size remainders — callers can pass any
        chunk size.
        """
        self._ensure_loaded()
        import torch  # lazy — avoids a torch import at package-load time

        if chunk.size == 0:
            return False
        buffer = np.concatenate([self._pending, chunk.astype(np.float32, copy=False)])
        while buffer.size >= _FRAME_SAMPLES:
            frame = buffer[:_FRAME_SAMPLES]
            buffer = buffer[_FRAME_SAMPLES:]
            frame_t = torch.from_numpy(frame)
            prob = float(self._model(frame_t, _SAMPLE_RATE).item())
            if prob >= self._threshold:
                self._speech_samples += _FRAME_SAMPLES
                if self._speech_samples >= self._min_speech_samples:
                    self._pending = buffer
                    return True
            else:
                # Silence resets the running speech tally; bursts of noise
                # and coughs won't accumulate across a silent gap.
                self._speech_samples = 0
        self._pending = buffer
        return False


class AudioMonitor:
    """Always-on mic capture + VAD during the voice loop's `speaking` state.

    On each sounddevice callback:
    - if still inside the `dead_zone_ms` at the start of speaking, do nothing
      (VAD would trip on TTS onset bleeding into the mic otherwise);
    - otherwise, buffer the chunk and feed it to VAD.

    When VAD fires:
    - sets `cancel_token.cancel()`;
    - stops feeding VAD (we only need to fire once);
    - keeps capturing audio so the voice loop can re-transcribe the user's
      barge-in utterance without asking them to press PTT.

    `stop()` returns the accumulated audio, or `None` if VAD never fired.
    """

    def __init__(
        self,
        vad: SileroVAD,
        cancel_token: CancelToken,
        *,
        device: int | str | None = None,
        dead_zone_ms: int = 300,
    ) -> None:
        self._vad = vad
        self._cancel = cancel_token
        self._device = device
        self._dead_zone_ms = int(dead_zone_ms)
        self._stream: sd.InputStream | None = None
        self._start_t: float = 0.0
        self._captured: list[np.ndarray] = []
        self._detected: bool = False

    def start(self) -> None:
        """Open the input stream. Idempotent — calling twice is a no-op
        after the first call until stop() runs."""
        if self._stream is not None:
            return
        self._start_t = time.monotonic()
        self._captured = []
        self._detected = False
        self._vad.reset()

        def _callback(indata, _frames, _time_info, status) -> None:  # noqa: ANN001
            if status:
                log.debug("vad.audio_status", status=str(status))
            elapsed_ms = (time.monotonic() - self._start_t) * 1000
            if elapsed_ms < self._dead_zone_ms:
                return  # dead zone — suppress TTS onset bleed
            chunk = indata[:, 0].copy()  # (frames, channels) → (frames,)
            self._captured.append(chunk)
            if self._detected:
                return
            try:
                fired = self._vad.feed(chunk)
            except Exception as exc:  # noqa: BLE001 — VAD errors mustn't kill the callback
                log.warning("vad.feed_failed", err=str(exc))
                return
            if fired:
                self._detected = True
                self._cancel.cancel()
                log.info("bargein.detected")

        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=_callback,
            device=self._device,
            # ~64 ms blocks — big enough to hold several 512-sample frames,
            # small enough that detection latency stays under ~100 ms on top
            # of the min_speech_ms threshold.
            blocksize=1024,
        )
        self._stream.start()

    def stop(self) -> np.ndarray | None:
        """Close the stream. Returns captured audio iff VAD fired, else None."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("vad.stop_failed", err=str(exc))
            self._stream = None
        if not self._detected or not self._captured:
            return None
        return np.concatenate(self._captured)

    @property
    def detected(self) -> bool:
        """Whether VAD fired during this speaking phase. Read after stop()."""
        return self._detected
