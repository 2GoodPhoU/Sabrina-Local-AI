"""Sentence embeddings for semantic memory.

Two backends:

  * `OnnxMiniLMEmbedder` (default) -- pure ONNX Runtime + HF tokenizers.
    No torch, no sentence-transformers. ~80 MB model, ~5-10 MB runtime
    deps. The model + tokenizer download lazily on first use to
    `<project_root>/data/embedder/<model_id>/`. See
    `rebuild/drafts/research/2026-04-25-stack-alternatives-survey.md`
    section 6 for why we moved off sentence-transformers.

  * `SentenceTransformerEmbedder` (legacy fallback) -- the original
    sentence-transformers wrapper. Kept reachable via the
    `[memory.semantic.embedder] backend = "sentence-transformers"`
    config knob in case the ONNX path goes sideways. Requires the
    optional `legacy-embedder` install extra (which pulls torch).

Both implement the `Embedder` Protocol below: same interface, identical
output shape (384-dim float vector, L2-normalized).

Why a class (not free functions): we want to (a) hide the one-time
model load behind the first call, (b) expose a `.warmup()` helper the
voice loop can await in the background before the first user turn,
(c) let tests substitute a fake without monkeypatching globals.

Threading: ONNX Runtime releases the GIL inside its C extension; same
for sentence-transformers. Callers embed from async code via
`asyncio.to_thread(embedder.embed, text)`.

Downloading models in code (CLI):
    sabrina download-models embedder
or simply let the first `sabrina memory-reindex` (or first voice-loop
turn with semantic on) trigger the lazy fetch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

from sabrina.logging import get_logger

log = get_logger(__name__)

# The roadmap pick. 384 dims, ~80 MB on disk, ~20 ms per sentence on CPU,
# sub-5 ms on a 4080. Swap via config if a better small model lands.
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_DIM = 384

# Where downloaded ONNX weights + tokenizer live by default. Resolved
# relative to the project root if a `sabrina.toml` is found, else the cwd.
# Override with `SABRINA_EMBEDDER_CACHE_DIR` env var.
_DEFAULT_CACHE_SUBDIR = Path("data") / "embedder"

# HuggingFace download URLs. The ONNX export is published in the same
# model repo by sentence-transformers (under `onnx/`). The tokenizer is
# the standard HF tokenizer.json at the repo root.
_HF_RESOLVE_BASE = "https://huggingface.co/{model}/resolve/main"
_DEFAULT_ONNX_PATH = "onnx/model.onnx"  # 90 MB float32
_TOKENIZER_PATH = "tokenizer.json"


@runtime_checkable
class Embedder(Protocol):
    """A synchronous text embedder.

    Implementations return plain Python lists of floats so they can be
    serialized into sqlite-vec without a numpy round-trip at the call
    site. (numpy is fine inside the implementation.)
    """

    model_name: str
    dim: int

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    def warmup(self) -> None: ...


# --------------------------------------------------------------------------
# ONNX path (default)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _DownloadSpec:
    """Where to fetch the model + tokenizer for an embedder identifier."""

    model_id: str  # HF repo id, e.g. "sentence-transformers/all-MiniLM-L6-v2"
    onnx_relpath: str = _DEFAULT_ONNX_PATH
    tokenizer_relpath: str = _TOKENIZER_PATH


def _project_data_root() -> Path:
    """Resolve `<project_root>/data/embedder/`. Mirrors voices/ pattern."""
    env_override = os.environ.get("SABRINA_EMBEDDER_CACHE_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "sabrina.toml").is_file():
            return (candidate / _DEFAULT_CACHE_SUBDIR).resolve()
    return (cwd / _DEFAULT_CACHE_SUBDIR).resolve()


def _local_dir_for(model_id: str) -> Path:
    """Per-model cache directory. Slashes in `model_id` become subdirs."""
    return _project_data_root() / model_id


def _fetch(url: str, dest: Path) -> None:
    """Single-file download. Skips if dest exists and non-empty."""
    if dest.exists() and dest.stat().st_size > 0:
        log.info("embed.download_skip_existing", path=str(dest))
        return
    log.info("embed.downloading", url=url, dest=str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=65536):
                f.write(chunk)
    tmp.replace(dest)


def ensure_onnx_assets(model_id: str = DEFAULT_MODEL) -> tuple[Path, Path]:
    """Return (onnx_path, tokenizer_path), downloading on first use.

    Idempotent. Safe to call from CLI (`sabrina download-models`) or
    lazily from `_ensure_loaded`.
    """
    spec = _DownloadSpec(model_id=model_id)
    cache_dir = _local_dir_for(model_id)
    onnx_path = cache_dir / "model.onnx"
    tok_path = cache_dir / "tokenizer.json"
    base = _HF_RESOLVE_BASE.format(model=model_id)
    _fetch(f"{base}/{spec.onnx_relpath}", onnx_path)
    _fetch(f"{base}/{spec.tokenizer_relpath}", tok_path)
    return onnx_path, tok_path


def _default_onnx_providers() -> list[str]:
    """Pick CPU by default; CUDA EP if present (and the user installed it)."""
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]
    except ImportError:
        return ["CPUExecutionProvider"]
    available = set(ort.get_available_providers())
    if "CUDAExecutionProvider" in available:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class OnnxMiniLMEmbedder:
    """Embedder backed directly by ONNX Runtime + HF tokenizers.

    Output is mean-pooled over tokens (attention-mask-weighted), then
    L2-normalized -- the exact recipe sentence-transformers applies for
    `all-MiniLM-L6-v2`. Cosine similarity vs. the legacy backend agrees
    to within ~1e-3 (see `test_onnx_embedder_round_trip`).

    Runtime cost: ~5 MB onnxruntime + ~3 MB tokenizers wheel, vs.
    sentence-transformers' ~700 MB torch transitive dep.
    """

    def __init__(
        self, model_name: str = DEFAULT_MODEL, *, providers: list[str] | None = None
    ) -> None:
        self.model_name = model_name
        self.dim = DEFAULT_DIM if "MiniLM-L6" in model_name else 0
        self._providers = providers
        self._session = None  # onnxruntime.InferenceSession
        self._tokenizer = None  # tokenizers.Tokenizer
        self._input_names: tuple[str, ...] = ()

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        import onnxruntime as ort  # type: ignore[import-not-found]
        from tokenizers import Tokenizer  # type: ignore[import-not-found]

        onnx_path, tok_path = ensure_onnx_assets(self.model_name)
        log.info("embed.loading", model=self.model_name, backend="onnx")
        providers = self._providers or _default_onnx_providers()
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 1
        sess_options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(onnx_path), sess_options=sess_options, providers=providers
        )
        self._input_names = tuple(i.name for i in self._session.get_inputs())
        self._tokenizer = Tokenizer.from_file(str(tok_path))
        # MiniLM-L6 caps at 256 tokens (sentence-transformers default).
        self._tokenizer.enable_truncation(max_length=256)
        self._tokenizer.enable_padding(
            pad_id=0, pad_type_id=0, pad_token="[PAD]", direction="right"
        )
        log.info(
            "embed.ready", model=self.model_name, dim=self.dim, providers=providers
        )

    def warmup(self) -> None:
        """Force model load + a single dummy encode so the first real call is fast."""
        self._ensure_loaded()
        self.embed("warmup")

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._ensure_loaded()
        import numpy as np

        encs = self._tokenizer.encode_batch(texts)
        max_len = max(len(e.ids) for e in encs) if encs else 1
        input_ids = np.zeros((len(encs), max_len), dtype=np.int64)
        attention_mask = np.zeros((len(encs), max_len), dtype=np.int64)
        token_type_ids = np.zeros((len(encs), max_len), dtype=np.int64)
        for i, enc in enumerate(encs):
            n = len(enc.ids)
            input_ids[i, :n] = enc.ids
            attention_mask[i, :n] = enc.attention_mask
            token_type_ids[i, :n] = enc.type_ids
        feeds: dict[str, object] = {}
        for name, value in (
            ("input_ids", input_ids),
            ("attention_mask", attention_mask),
            ("token_type_ids", token_type_ids),
        ):
            if name in self._input_names:
                feeds[name] = value
        outputs = self._session.run(None, feeds)
        last_hidden = outputs[0]
        # Mean pooling over tokens, weighted by attention mask. Mirrors
        # sentence-transformers' Pooling(pooling_mode_mean_tokens=True).
        mask = attention_mask.astype(np.float32)[:, :, None]
        summed = (last_hidden * mask).sum(axis=1)
        counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = summed / counts
        # L2-normalize so cosine similarity == dot product.
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        norms = np.clip(norms, a_min=1e-12, a_max=None)
        normed = pooled / norms
        return [[float(x) for x in row] for row in normed]


# --------------------------------------------------------------------------
# Legacy sentence-transformers path (opt-in via config)
# --------------------------------------------------------------------------


class SentenceTransformerEmbedder:
    """Legacy embedder backed by sentence-transformers.

    Kept available for users who want to fall back if the ONNX path
    breaks. Requires the optional `legacy-embedder` install extra
    (`uv sync --extra legacy-embedder`).
    """

    def __init__(
        self, model_name: str = DEFAULT_MODEL, *, device: str | None = None
    ) -> None:
        self.model_name = model_name
        self._device = device
        self._model = None
        self.dim = DEFAULT_DIM if "MiniLM-L6" in model_name else 0

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]

        log.info(
            "embed.loading",
            model=self.model_name,
            device=self._device or "auto",
            backend="sentence-transformers",
        )
        self._model = SentenceTransformer(self.model_name, device=self._device)
        if hasattr(self._model, "get_embedding_dimension"):
            get_dim = self._model.get_embedding_dimension
        else:
            get_dim = self._model.get_sentence_embedding_dimension
        reported = int(get_dim() or 0)
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


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------


def build_embedder(
    model_name: str = DEFAULT_MODEL, *, backend: str = "onnx"
) -> Embedder:
    """Construct the configured embedder.

    `backend` is one of:
      * "onnx" (default) -> `OnnxMiniLMEmbedder`
      * "sentence-transformers" -> `SentenceTransformerEmbedder` (legacy)

    Backend is normally read from `settings.memory.semantic.embedder.backend`
    in `cli.py`. Tests can pass it directly.
    """
    if backend == "onnx":
        return OnnxMiniLMEmbedder(model_name=model_name)
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder(model_name=model_name)
    raise ValueError(
        f"Unknown embedder backend {backend!r}. Try 'onnx' or 'sentence-transformers'."
    )
