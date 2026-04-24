"""Push-to-talk: record mic audio while a hotkey is held.

Uses pynput for a global key listener (no admin needed on Windows, unlike
the `keyboard` library). sounddevice captures via callback while the key
is down; we concatenate chunks on release and return a 16 kHz mono
float32 array ready for `Listener.transcribe`.

Hotkey names match pynput.keyboard.Key members: "shift_r", "shift",
"ctrl_r", "alt_gr", "f9", "caps_lock", etc. Single character keys can
be passed as-is (e.g. "t").
"""

from __future__ import annotations

import asyncio
import threading

import numpy as np
import sounddevice as sd

from sabrina.listener.record import SAMPLE_RATE
from sabrina.logging import get_logger

log = get_logger(__name__)


class PushToTalk:
    def __init__(
        self, hotkey: str = "shift_r", input_device: int | str | None = None
    ) -> None:
        self._hotkey = hotkey.lower().strip("<>")
        self._device = input_device
        self._held = threading.Event()  # set while PTT is down
        self._released = threading.Event()  # pulsed on each release
        self._listener = None

    def start(self) -> None:
        # Lazy import keeps this module importable without pynput installed
        # (e.g. during test collection in weird envs).
        from pynput import keyboard  # noqa: PLC0415

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        log.info("ptt.started", hotkey=self._hotkey)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    # --- pynput callbacks (run in the listener thread) --------------------

    def _is_ptt(self, key) -> bool:  # noqa: ANN001 - pynput's Key | KeyCode
        # pynput.keyboard.Key has .name; KeyCode has .char.
        name = getattr(key, "name", None)
        if name is not None:
            return name.lower() == self._hotkey
        char = getattr(key, "char", None)
        if char is not None and len(self._hotkey) == 1:
            return char.lower() == self._hotkey
        return False

    def _on_press(self, key) -> None:  # noqa: ANN001
        if self._is_ptt(key) and not self._held.is_set():
            self._released.clear()
            self._held.set()

    def _on_release(self, key) -> None:  # noqa: ANN001
        if self._is_ptt(key) and self._held.is_set():
            self._held.clear()
            self._released.set()

    # --- async surface ----------------------------------------------------

    async def wait_press(self) -> None:
        await asyncio.to_thread(self._held.wait)

    async def wait_release(self) -> None:
        await asyncio.to_thread(self._released.wait)

    async def record_while_held(
        self,
        max_seconds: float = 30.0,
        trim_ms: int = 150,
    ) -> np.ndarray:
        """Block until PTT press, record until release, return (N,) float32 mono 16 kHz.

        `max_seconds` is a safety cap — if the user wedges the key down, we stop
        capturing after this long. Returns an empty array if no samples captured.

        `trim_ms` drops audio from each end of the clip. Defaults to 150 ms on
        both sides to hide the PTT key-click noise that Whisper otherwise
        transcribes as a spurious word. Set to 0 to disable.
        """
        await self.wait_press()
        chunks: list[np.ndarray] = []

        def _callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("ptt.audio_status", status=str(status))
            # indata shape: (frames, channels). Take channel 0, copy (reused buffer).
            chunks.append(indata[:, 0].copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=_callback,
            device=self._device,
        )
        stream.start()
        try:
            # Race release against the safety timeout.
            await asyncio.wait_for(self.wait_release(), timeout=max_seconds)
        except asyncio.TimeoutError:
            log.warning("ptt.max_seconds_hit", max_s=max_seconds)
        finally:
            stream.stop()
            stream.close()

        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(chunks)
        return _trim_ends(audio, trim_ms=trim_ms)


def _trim_ends(audio: np.ndarray, trim_ms: int) -> np.ndarray:
    """Lop `trim_ms` milliseconds off each end of a 16 kHz mono clip.

    If the clip is shorter than 2*trim_ms + 100ms (i.e. would leave under
    100 ms of real audio), return empty — the user almost certainly just
    tapped the key by accident.
    """
    if trim_ms <= 0 or audio.size == 0:
        return audio
    n_trim = int(round((trim_ms / 1000.0) * SAMPLE_RATE))
    min_keep = int(round(0.1 * SAMPLE_RATE))  # 100 ms
    if audio.size <= 2 * n_trim + min_keep:
        return np.zeros(0, dtype=audio.dtype)
    return audio[n_trim:-n_trim]
