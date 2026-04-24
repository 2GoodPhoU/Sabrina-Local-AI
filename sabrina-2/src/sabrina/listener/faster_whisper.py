"""faster-whisper backend.

CTranslate2-backed Whisper runner. On an RTX 4080 with `base.en` +
`int8_float16`, expect ~0.05-0.1 RTF (20x real-time) for short utterances.

Model load is ~1-3s on first call; the instance holds the loaded model so
subsequent transcriptions skip that cost.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from sabrina.listener.protocol import Segment, Transcript
from sabrina.logging import get_logger

if TYPE_CHECKING:
    import numpy as np

log = get_logger(__name__)


class FasterWhisperListener:
    def __init__(
        self,
        model: str = "base.en",
        device: str = "auto",
        compute_type: str = "float16",
        beam_size: int = 5,
        language: str | None = "en",
    ) -> None:
        # Lazy-import so the bare module can be imported on boxes without the
        # faster-whisper install (e.g. during test collection).
        from faster_whisper import WhisperModel  # noqa: PLC0415

        log.info(
            "fw.loading",
            model=model,
            device=device,
            compute_type=compute_type,
        )
        t0 = time.monotonic()
        # Resolve device="auto" ourselves so we can log what we actually picked.
        resolved_device = device
        if device == "auto":
            resolved_device = _detect_device()
        self._model = WhisperModel(
            model,
            device=resolved_device,
            compute_type=compute_type,
        )
        self._beam_size = beam_size
        self._language = language or None
        self.name = f"faster-whisper:{model}@{resolved_device}"
        log.info("fw.loaded", name=self.name, took_s=round(time.monotonic() - t0, 3))

    async def transcribe(
        self,
        audio: Path | object,
        *,
        language: str | None = None,
    ) -> Transcript:
        lang = language if language is not None else self._language
        start = time.monotonic()
        result = await asyncio.to_thread(self._transcribe_sync, audio, lang)
        result_text, result_lang, result_prob, audio_dur, segs = result
        return Transcript(
            text=result_text,
            language=result_lang,
            language_prob=result_prob,
            audio_duration_s=audio_dur,
            transcribe_duration_s=time.monotonic() - start,
            segments=segs,
        )

    def _transcribe_sync(
        self,
        audio: Path | object,
        language: str | None,
    ) -> tuple[str, str, float, float, tuple[Segment, ...]]:
        # faster-whisper accepts str path, numpy array, or binary file-like.
        arg = str(audio) if isinstance(audio, Path) else audio
        segments_gen, info = self._model.transcribe(
            arg,
            beam_size=self._beam_size,
            language=language,
            vad_filter=False,  # keep simple; VAD is its own component
        )
        segs: list[Segment] = []
        text_parts: list[str] = []
        for s in segments_gen:
            segs.append(Segment(start_s=s.start, end_s=s.end, text=s.text))
            text_parts.append(s.text)
        return (
            "".join(text_parts).strip(),
            info.language,
            float(info.language_probability),
            float(info.duration),
            tuple(segs),
        )


def _detect_device() -> str:
    """Return 'cuda' if a CUDA-capable GPU is visible, else 'cpu'.

    faster-whisper bundles ctranslate2 which exposes this without needing a
    full torch install. We try a cheap check and fall back gracefully.
    """
    try:
        import ctranslate2  # noqa: PLC0415

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception as exc:  # noqa: BLE001
        log.debug("fw.cuda_detect_failed", err=str(exc))
    return "cpu"
