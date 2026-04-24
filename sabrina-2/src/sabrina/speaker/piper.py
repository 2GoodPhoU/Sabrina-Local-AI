"""Piper TTS backend (local, high quality).

Calls the `piper` binary as a subprocess with `--output_raw`, reads int16 PCM
bytes from stdout, and plays them through sounddevice.

Why subprocess and not the Python package: piper-tts on PyPI has Python-version
gaps and sometimes missing Windows wheels. The standalone binary is stable
across platforms and its CLI is a documented contract.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from sabrina.brain.protocol import CancelToken
from sabrina.logging import get_logger
from sabrina.speaker.protocol import SpeakResult

log = get_logger(__name__)


class PiperNotInstalled(RuntimeError):
    pass


async def _poll_and_stop(token: CancelToken, speaker: "PiperSpeaker") -> None:
    """Poll a CancelToken every ~30ms; call speaker.stop() when it fires.

    Lives at module scope (vs. inline in speak()) so it's unit-testable.
    Shared by both Piper and SAPI; the 8-line duplication is smaller than
    introducing a new shared module purely for this helper.
    """
    try:
        while not token.cancelled:
            await asyncio.sleep(0.03)
        await speaker.stop()
    except asyncio.CancelledError:
        # Expected teardown path when speak() finishes normally.
        raise


async def _cleanup_poll_task(task: "asyncio.Task[None] | None") -> None:
    """Cancel and drain the cancel-token poll task. Swallows CancelledError."""
    if task is None:
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


class PiperSpeaker:
    def __init__(
        self,
        voice_model: Path | str,
        binary: str | None = None,
        output_device: int | str | None = None,
        length_scale: float = 1.0,
        speaker_id: int | None = None,
    ) -> None:
        self._binary = self._resolve_binary(binary)
        self._voice_model = Path(voice_model).resolve()
        if not self._voice_model.is_file():
            raise FileNotFoundError(
                f"Piper voice model not found: {self._voice_model}. "
                "Run `sabrina tts download-voice` to fetch one."
            )
        self._config = self._load_config(self._voice_model)
        self._sample_rate: int = self._config.get("audio", {}).get("sample_rate", 22050)
        self._length_scale = length_scale
        self._speaker_id = speaker_id
        self._device = output_device
        self._proc: asyncio.subprocess.Process | None = None
        # Include speaker index in name when pinned, so logs disambiguate voices
        # from multi-speaker models like libritts_r.
        suffix = f"#{speaker_id}" if speaker_id is not None else ""
        self.name = f"piper:{self._voice_model.stem}{suffix}"

    @staticmethod
    def _resolve_binary(binary: str | None) -> str:
        if binary:
            p = Path(binary)
            if not p.is_file():
                raise PiperNotInstalled(f"Configured piper binary not found: {p}")
            return str(p)
        found = shutil.which("piper")
        if not found:
            raise PiperNotInstalled(
                "`piper` binary not found on PATH. Run `install-piper.ps1` or set "
                "SABRINA_TTS__PIPER__BINARY in .env to its path."
            )
        return found

    @staticmethod
    def _load_config(voice_model: Path) -> dict:
        cfg = voice_model.with_suffix(voice_model.suffix + ".json")
        if not cfg.is_file():
            # Try alternate: <stem>.onnx.json -> <stem>.json
            alt = voice_model.with_name(voice_model.stem + ".json")
            if alt.is_file():
                cfg = alt
            else:
                raise FileNotFoundError(
                    f"Piper voice config not found next to model: expected {cfg}"
                )
        return json.loads(cfg.read_text(encoding="utf-8"))

    async def speak(
        self,
        text: str,
        *,
        voice: str | None = None,
        cancel_token: CancelToken | None = None,
    ) -> SpeakResult:
        if not text.strip():
            return SpeakResult(
                engine=self.name, duration_s=0.0, sample_rate=self._sample_rate
            )

        # Spawn a background poller that calls self.stop() as soon as the
        # cancel_token is tripped. Cheap — one asyncio task per speak() call
        # that sleeps 30ms between checks. Torn down in `finally`.
        poll_task: asyncio.Task[None] | None = None
        if cancel_token is not None:
            poll_task = asyncio.create_task(_poll_and_stop(cancel_token, self))

        start = time.monotonic()
        args = [
            self._binary,
            "--model",
            str(self._voice_model),
            "--output_raw",
            "--length_scale",
            str(self._length_scale),
        ]
        if self._speaker_id is not None:
            args.extend(["--speaker", str(self._speaker_id)])
        log.debug("piper.spawn", args=args)
        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await self._proc.communicate(text.encode("utf-8"))
        except asyncio.CancelledError:
            await self.stop()
            raise
        finally:
            self._proc = None

        if stderr:
            log.debug("piper.stderr", data=stderr[-512:].decode(errors="replace"))

        audio = np.frombuffer(stdout, dtype=np.int16)
        if audio.size == 0:
            log.warning("piper.empty_output", text=text[:60])
            await _cleanup_poll_task(poll_task)
            return SpeakResult(
                engine=self.name, duration_s=0.0, sample_rate=self._sample_rate
            )

        # If cancel fired before playback started, skip it.
        if cancel_token is not None and cancel_token.cancelled:
            await _cleanup_poll_task(poll_task)
            return SpeakResult(
                engine=self.name,
                duration_s=time.monotonic() - start,
                sample_rate=self._sample_rate,
                samples=int(audio.size),
            )

        try:
            await asyncio.to_thread(
                sd.play, audio, self._sample_rate, device=self._device
            )
            await asyncio.to_thread(sd.wait)
        except asyncio.CancelledError:
            sd.stop()
            raise
        finally:
            await _cleanup_poll_task(poll_task)

        return SpeakResult(
            engine=self.name,
            duration_s=time.monotonic() - start,
            sample_rate=self._sample_rate,
            samples=int(audio.size),
        )

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
        sd.stop()
