"""Sentence embeddings for semantic memory.

Thin wrapper around sentence-transformers. Keeps the heavy imports
(`torch`, `transformers`) behind a lazy first-call so `sabrina --help`
and the voice loop's other commands aren't paying the model-load tax
when semantic memory is off.

Why a class (not free functions): we want to (a) hide the one-time
model load behind the first call, (b) expose a `.warmup()` helper the
voice loop can await in the background before the first user turn,
(c) let tests substitute a fake without monkeypatching globals.

Threading: sentence-transformers is CPU/GPU-bound and releases the
GIL inside its C extensions. Callers embed from async code via
`asyncio.to_thread(embedder.embed, text)`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sabrina.logging import get_logger

log = get_logger(__name__)

# The roadmap pick. 384 dims, ~80 MB on disk, ~20 ms per sentence on CPU,
# sub-5 ms on a 4080. Swap via config if a better small model lands.
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIM = 384


@runtime_checkable
class Embedder(Protocol):
    """A synchronous text embedder.

    Implementations return plain Python lists of floats so they can be
    serialized into sqlite-vec without a numpy round-trip at the call
    site. (numpy is fine inside the implementation.)
    """

    model_name: str
    dim: int

    def embed(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class SentenceTransformerEmbedder:
    """Default embedder backed by sentence-transformers.

    The model is loaded on first use, not at construction. That keeps
    import-time light and makes `SentenceTransformerEmbedder(model)`
    cheap for `sabrina --help`-style invocations that never touch memory.
    """

    def __init__(
        self, model_name: str = DEFAULT_MODEL, *, device: str | None = None
    ) -> None:
        self.model_name = model_name
        self._device = device
        self._model = None  # lazy: sentence_transformers.SentenceTransformer
        # We fill `dim` on first load; expose the default up front so
        # callers (schema creation) can plan before warmup finishes.
        self.dim = DEFAULT_DIM if "MiniLM-L6" in model_name else 0

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Lazy import keeps torch off the hot path for non-memory commands.
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        log.info("embed.loading", model=self.model_name, device=self._device or "auto")
        self._model = SentenceTransformer(self.model_name, device=self._device)
        reported = int(self._model.get_sentence_embedding_dimension() or 0)
        if reported and self.dim and reported != self.dim:
            log.warning(
                "embed.dim_mismatch",
                configured=self.dim,
                actual=reported,
                model=self.model_name,
            )
        if reported:
            self.dim = reported
        log.info("embed.ready", model=self.model_name, dim=self.dim)

    def warmup(self) -> None:
        """Force model load + a single dummy encode so the first real call is fast."""
        self._ensure_loaded()
        # A single-token encode warms CUDA kernels / triggers graph compile on first use.
        self._model.encode("warmup", convert_to_numpy=True, show_progress_bar=False)

    def embed(self, text: str) -> list[float]:
        self._ensure_loaded()
        vec = self._model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return [float(x) for x in vec.tolist()]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        arr = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [[float(x) for x in row.tolist()] for row in arr]


def build_embedder(model_name: str = DEFAULT_MODEL) -> Embedder:
    """Factory; always returns a SentenceTransformerEmbedder today.

    Separate factory so a future decision-doc can swap in (e.g.) an
    onnxruntime-based MiniLM without touching call sites.
    """
    return SentenceTransformerEmbedder(model_name=model_name)
