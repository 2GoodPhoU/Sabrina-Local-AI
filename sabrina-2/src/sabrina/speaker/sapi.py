"""Windows SAPI backend via direct win32com (zero-setup fallback).

Talks to SAPI 5 (`SAPI.SpVoice`) through `win32com.client` directly. No
polling loop (unlike pyttsx3), so init + speak overhead on a cold CLI
invocation is ~300-600 ms instead of several seconds.

Quality is audibly worse than Piper, but it's built into every Windows
install and works when the Piper binary or voice model is missing.

Cancellation:
  stop() issues a SAPI "purge" speak ("" with SVSFPurgeBeforeSpeak) which
  flushes any in-flight speech. The synchronous Speak() call in the worker
  thread returns as soon as the queue is purged.
"""

from __future__ import annotations

import asyncio
import time

from sabrina.brain.protocol import CancelToken
from sabrina.logging import get_logger
from sabrina.speaker.protocol import SpeakResult

log = get_logger(__name__)


# SAPI Speak() flags we actually use (from sapi.h).
_SVSF_DEFAULT = 0
_SVSF_ASYNC = 1
_SVSF_PURGE_BEFORE_SPEAK = 2


def _wpm_to_sapi_rate(wpm: int) -> int:
    # SAPI rate is an int in [-10, 10]. 0 == ~200 wpm (the SAPI baseline).
    # Each step is ~17 wpm. Clamp out-of-range values.
    return max(-10, min(10, round((wpm - 200) / 17)))


class SapiSpeaker:
    def __init__(self, voice: str = "", rate: int = 200) -> None:
        # Lazy-import so non-Windows collectors (pytest on CI, etc.) don't
        # choke just by importing this module.
        import pythoncom  # noqa: PLC0415
        import win32com.client  # noqa: PLC0415

        self._pythoncom = pythoncom
        self._dispatch = win32com.client.Dispatch

        self._voice_pref = voice
        self._sapi_rate = _wpm_to_sapi_rate(rate)

        # Probe once on the main thread to discover the picked voice name
        # so `.name` is informative. We don't hold the engine here — each
        # speak() creates its own inside the worker thread to keep COM
        # apartment rules simple.
        pythoncom.CoInitialize()
        try:
            engine = self._dispatch("SAPI.SpVoice")
            picked = self._apply_voice(engine, voice)
        finally:
            pythoncom.CoUninitialize()
        self.name = f"sapi:{picked}"

        self._speaking_engine = None  # set while a speak() is in flight

    @staticmethod
    def _apply_voice(engine, wanted: str) -> str:
        """Select a voice on `engine` by case-insensitive substring match.

        Returns the name of the voice that ended up active.
        """
        if wanted:
            needle = wanted.lower()
            voices = engine.GetVoices()
            for i in range(voices.Count):
                v = voices.Item(i)
                name = v.GetAttribute("Name") or ""
                if needle in name.lower():
                    engine.Voice = v
                    return name
        try:
            return engine.Voice.GetAttribute("Name") or "default"
        except Exception:  # noqa: BLE001
            return "default"

    async def speak(
        self,
        text: str,
        *,
        voice: str | None = None,
        cancel_token: CancelToken | None = None,
    ) -> SpeakResult:
        if not text.strip():
            return SpeakResult(engine=self.name, duration_s=0.0)

        # Poll cancel_token; on cancel, stop() purges the SAPI queue which
        # unblocks the synchronous Speak() in the worker thread. See the
        # same pattern in piper.py — duplicated here to keep the speaker
        # backends self-contained.
        poll_task: asyncio.Task[None] | None = None
        if cancel_token is not None:

            async def _poll() -> None:
                try:
                    while not cancel_token.cancelled:
                        await asyncio.sleep(0.03)
                    await self.stop()
                except asyncio.CancelledError:
                    raise

            poll_task = asyncio.create_task(_poll())

        start = time.monotonic()
        try:
            await asyncio.to_thread(self._speak_sync, text, voice)
        except asyncio.CancelledError:
            await self.stop()
            raise
        finally:
            if poll_task is not None:
                poll_task.cancel()
                try:
                    await poll_task
                except (asyncio.CancelledError, Exception):
                    pass
        return SpeakResult(engine=self.name, duration_s=time.monotonic() - start)

    def _speak_sync(self, text: str, voice: str | None) -> None:
        self._pythoncom.CoInitialize()
        try:
            engine = self._dispatch("SAPI.SpVoice")
            engine.Rate = self._sapi_rate
            wanted = voice or self._voice_pref
            if wanted:
                self._apply_voice(engine, wanted)
            self._speaking_engine = engine
            # Synchronous Speak: blocks this thread until playback finishes.
            engine.Speak(text, _SVSF_DEFAULT)
        finally:
            self._speaking_engine = None
            self._pythoncom.CoUninitialize()

    async def stop(self) -> None:
        engine = self._speaking_engine
        if engine is None:
            return

        def _purge() -> None:
            self._pythoncom.CoInitialize()
            try:
                engine.Speak("", _SVSF_PURGE_BEFORE_SPEAK)
            finally:
                self._pythoncom.CoUninitialize()

        try:
            await asyncio.to_thread(_purge)
        except Exception as exc:  # noqa: BLE001
            log.debug("sapi.stop_failed", err=str(exc))
