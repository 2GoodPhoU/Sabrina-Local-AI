"""Long-term conversation memory.

SQLite-backed message log + optional sqlite-vec semantic index. On
startup, recent turns are loaded into the brain's history so
conversations survive restarts; when semantic memory is enabled,
top-k relevant older turns get retrieved per user turn and injected
into the system prompt.
"""

from sabrina.memory.embed import (
    DEFAULT_DIM,
    DEFAULT_MODEL,
    Embedder,
    SentenceTransformerEmbedder,
    build_embedder,
)
from sabrina.memory.store import MemoryStore, SearchHit, StoredMessage

__all__ = [
    "DEFAULT_DIM",
    "DEFAULT_MODEL",
    "Embedder",
    "MemoryStore",
    "SearchHit",
    "SentenceTransformerEmbedder",
    "StoredMessage",
    "build_embedder",
]
