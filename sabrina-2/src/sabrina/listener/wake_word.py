"""Wake-word detection (openWakeWord).

Runtime piece of the wake-word component (decision pending; see
`rebuild/drafts/wake-word-plan.md`). Two classes:

    WakeWordDetector — stateful, chunk-by-chunk score evaluator. Wraps
                       the `openwakeword` package's `Model` and exposes a
                       `feed()` API that mirrors `SileroVAD.feed()` so
                       both can drive an audio-monitor loop the same
                       way. Returns the score on detection (past
                       cooldown), or None.

    WakeWordMonitor  — sounddevice InputStream that runs during the
                       voice loop's `idle` state. Feeds the detector on
                       each callback and invokes `on_detect(score)`
                       when the wake word fires. Captures recent audio
                       in a ring buffer so the voice loop can hand
                       Whisper a clip starting just before the fire.

Cross-state audio sharing: AudioMonitor (speaking phase, in
`listener/vad.py`) and WakeWordMonitor (idle) open + close their
InputStreams independently. Only one is active at a time — they don't
compete for the device. Unifying them under a shared `_MicMonitor`
base is a follow-up; today the duplication is ~30 lines and the two
fire semantics (cancel-token vs. event) are different enough that the
abstraction would be premature.

Overnight session (2026-04-25) ships this scaffold with the openWakeWord
`hey_jarvis` model that the library bundles. Custom "Hey Sabrina" model
training is Eric's next-day task per `wake-word-plan.md`'s
`tools/wake-training/` section.
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sounddevice as sd

from sabrina.logging import get_logger

log = get_logger(__name__)


# Wake word inference is fed 80 ms chunks at 16 kHz. openWakeWord's docs
# pick this; smaller windows hurt accuracy, larger raise latency.
_FRAME_SAMPLES = 1280
_SAMPLE_RATE = 16000

# Default ring-buffer for capturing audio around a wake event. Big
# enough to hold the wake phrase + the user's follow-up command without
# making the voice loop wait for a PTT press. ~5 s @ 16 kHz mono float32
# is ~320 KB; cheap.
_RING_BUFFER_SECONDS = 5.0


class WakeWordDetector:
    """openWakeWord-backed detector. Consumes float32 mono 16 kHz chunks.

    Usage:
        wake = WakeWordDetector(model="hey_jarvis", threshold=0.5)
        score = wake.feed(chunk_float32)   # returns score on fire, else None
        wake.reset()                       # between idle phases
    """

    def __init__(
        self,
        model: str = "hey_jarvis",
        threshold: float = 0.5,
        cooldown_ms: int = 2000,
    ) -> None:
        self._model_id = model
        self._threshold = float(threshold)
        self._cooldown_s = cooldown_ms / 1000.0
        self._last_fire = 0.0
        self._impl: Any | None = None
        self._pending: np.ndarray = np.zeros(0, dtype=np.float32)

    @property
    def name(self) -> str:
        """Detection name as openWakeWord reports it.

        For the bundled `hey_jarvis` model this is `hey_jarvis`. For a
        custom ONNX file passed by path, openWakeWord uses the file
        basename. Exposed so the voice loop and tests can grep events
        without re-deriving.
        """
        return Path(self._model_id).stem

    def _ensure_loaded(self) -> None:
        if self._impl is not None:
            return
        # Lazy import — keeps openwakeword (and onnxruntime via it) off
        # the cold path for runs that don't enable wake.
        from openwakeword.model import Model  # type: ignore[import-not-found]

        log.info("wake.loading", model=self._model_id, threshold=self._threshold)
        # If the user passed an ONNX path, load that file. Otherwise
        # treat it as a bundled model name (e.g. "hey_jarvis").
        path = Path(self._model_id)
        if path.suffix.lower() == ".onnx" and path.is_file():
            self._impl = Model(
                wakeword_models=[str(path)],
                inference_framework="onnx",
            )
        else:
            # Pass the bundled model name; openwakeword resolves it
            # against its packaged set.
            self._impl = Model(
                wakeword_models=[self._model_id],
                inference_framework="onnx",
            )
        log.info("wake.ready", model=self.name)

    def reset(self) -> None:
        """Clear pending audio + cooldown timer. Call on entry to idle."""
        self._pending = np.zeros(0, dtype=np.float32)
        self._last_fire = 0.0
        if self._impl is not None:
            reset = getattr(self._impl, "reset", None)
            if reset is not None:
                try:
                    reset()
                except Exception as exc:  # noqa: BLE001
                    log.debug("wake.reset_failed", err=str(exc))

    def feed(self, chunk: np.ndarray) -> float | None:
        """Feed a float32 mono 16 kHz chunk. Returns score on fire, else None.

        Buffers sub-frame remainders so callers can pass any chunk size.
        Cooldown enforced internally — repeated frames inside the cooldown
        window return None even if score >= threshold.
        """
        self._ensure_loaded()
        if chunk.size == 0:
            return None
        buffer = np.concatenate([self._pending, chunk.astype(np.float32, copy=False)])
        fire_score: float | None = None
        while buffer.size >= _FRAME_SAMPLES:
            frame = buffer[:_FRAME_SAMPLES]
            buffer = buffer[_FRAME_SAMPLES:]
            # openWakeWord wants int16 PCM (its `predict` API spec).
            frame_i16 = (frame * 32767.0).astype(np.int16, copy=False)
            scores = self._impl.predict(frame_i16)
            score = float(scores.get(self.name, 0.0))
            log.debug("wake.score", score=score)
            if score < self._threshold:
                continue
            now = time.monotonic()
            if now - self._last_fire < self._cooldown_s:
                log.debug("wake.cooldown_suppressed", score=score)
                continue
            self._last_fire = now
            fire_score = score
            # Drain remaining frames this chunk to prevent multi-fire on
            # one phrase; cooldown also catches it but bail early.
            break
        self._pending = buffer
        return fire_score


class WakeWordMonitor:
    """Background mic capture during idle, with wake-word firing.

    Mirrors AudioMonitor's start()/stop() shape so the voice loop can
    treat them symmetrically. On fire, calls `on_detect(score)` from
    the sounddevice callback thread — the callback should be cheap
    (e.g. set an asyncio.Event from a thread-safe wrapper); long work
    belongs on the asyncio loop.

    Captured audio is kept in a ring buffer (`_RING_BUFFER_SECONDS`) so
    the voice loop can pull the trailing few seconds of the user's
    "hey sabrina, what time is it" without missing the wake phrase or
    forcing them to PTT.
    """

    def __init__(
        self,
        detector: WakeWordDetector,
        on_detect: Callable[[float], None],
        *,
        device: int | str | None = None,
    ) -> None:
        self._detector = detector
        self._on_detect = on_detect
        self._device = device
        self._stream: sd.InputStream | None = None
        # Ring buffer sized in samples. deque with maxlen makes append-pop
        # O(1) and trims oldest automatically.
        ring_samples = int(_RING_BUFFER_SECONDS * _SAMPLE_RATE)
        self._ring: deque[np.ndarray] = deque()
        self._ring_max_samples = ring_samples
        self._ring_total_samples = 0
        self._fired = False

    def start(self) -> None:
        """Open the input stream. Idempotent — start-after-start is a no-op."""
        if self._stream is not None:
            return
        self._detector.reset()
        self._ring.clear()
        self._ring_total_samples = 0
        self._fired = False

        def _callback(indata, _frames, _time_info, status) -> None:  # noqa: ANN001
            if status:
                log.debug("wake.audio_status", status=str(status))
            chunk = indata[:, 0].copy()
            # Append + trim. We trim from the head until we're under cap.
            self._ring.append(chunk)
            self._ring_total_samples += chunk.size
            while (
                self._ring_total_samples > self._ring_max_samples and self._ring
            ):
                head = self._ring.popleft()
                self._ring_total_samples -= head.size
            if self._fired:
                return
            try:
                score = self._detector.feed(chunk)
            except Exception as exc:  # noqa: BLE001 — never let detector kill the callback
                log.warning("wake.feed_failed", err=str(exc))
                return
            if score is not None:
                self._fired = True
                log.info("wake.detected", score=round(score, 3))
                # User callback runs from the audio thread; keep it short.
                try:
                    self._on_detect(score)
                except Exception as exc:  # noqa: BLE001
                    log.warning("wake.on_detect_failed", err=str(exc))

        self._stream = sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=_callback,
            device=self._device,
            blocksize=1280,  # one openWakeWord frame; minimizes detection latency
        )
        self._stream.start()

    def stop(self) -> np.ndarray | None:
        """Close the stream. Returns ring-buffer audio if wake fired, else None.

        The returned clip is the last `_RING_BUFFER_SECONDS` of audio,
        which always includes the wake phrase plus whatever the user
        said immediately after. Voice loop hands this to ASR; nothing
        else needs to know about the wake event.
        """
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("wake.stop_failed", err=str(exc))
            self._stream = None
        if not self._fired or not self._ring:
            return None
        return np.concatenate(list(self._ring))

    @property
    def fired(self) -> bool:
        """Whether the wake word fired during this idle phase."""
        return self._fired
