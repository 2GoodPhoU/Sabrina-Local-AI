"""Conversation-memory store: SQLite with an optional sqlite-vec index.

Two tables:

  messages       - one row per user/assistant/system turn. Existed pre-007.
  vec_messages   - vec0 virtual table from sqlite-vec, one row per embedding.
                   Keyed by message_id (1:1 with messages.id).

Access patterns:
  - append(session_id, role, content, embedding=None)   per turn
  - insert_embedding(message_id, vec)                   async-friendly
  - load_recent(limit)                                  at startup
  - search(query_vec, k, max_distance, exclude_ids)     per turn (semantic)
  - backfill_embeddings(embedder)                       one-shot reindex
  - clear()                                             user reset

Thread / async safety: SQLite writes use the single connection's
per-statement lock. The store is designed for single-process use.
Embedding calls should live on a worker thread (`asyncio.to_thread`).

If sqlite-vec isn't installed, or the Python build doesn't allow
loading SQLite extensions, we log a warning and run in text-only mode.
`search()` then raises a clear error; `append()` still works.
"""

from __future__ import annotations

import sqlite3
import struct
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sabrina.brain.protocol import Message
from sabrina.logging import get_logger

log = get_logger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT    NOT NULL,
    ts         TEXT    NOT NULL,
    role       TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages(ts DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
"""


def _vec_schema(dim: int) -> str:
    """vec0 virtual table DDL. Dim is fixed at creation."""
    return f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS vec_messages USING vec0(
        message_id INTEGER PRIMARY KEY,
        embedding  FLOAT[{dim}]
    );
    """


def _pack_vec(vec: list[float] | tuple[float, ...]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


@dataclass(frozen=True, slots=True)
class StoredMessage:
    id: int
    session_id: str
    ts: datetime
    role: str  # "user" | "assistant" | "system"
    content: str

    def to_message(self) -> Message:
        return Message(role=self.role, content=self.content)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A retrieved message plus its distance from the query vector."""

    message: StoredMessage
    distance: float  # cosine distance, 0 = identical, 2 = opposite


def new_session_id() -> str:
    """Fresh UUID per process — lets us group "this run's" messages."""
    return uuid.uuid4().hex[:12]


class MemoryStore:
    def __init__(self, db_path: Path, *, embedding_dim: int | None = None) -> None:
        db_path = db_path.expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        # `check_same_thread=False` so callers can dispatch embeddings and
        # search through `asyncio.to_thread` without ProgrammingError. We
        # still hold one connection for the store's lifetime and rely on
        # SQLite's internal per-statement mutex for concurrency.
        self._conn = sqlite3.connect(
            str(db_path),
            isolation_level=None,  # autocommit
            check_same_thread=False,
        )
        self._conn.executescript(_SCHEMA)

        self._embedding_dim: int | None = None
        self._vec_enabled = False
        if embedding_dim is not None:
            self._try_enable_vec(embedding_dim)

        log.info(
            "memory.opened",
            path=str(db_path),
            vec_enabled=self._vec_enabled,
            dim=self._embedding_dim,
        )

    def _try_enable_vec(self, dim: int) -> None:
        """Attempt to load sqlite-vec and create the vec table. Swallow failures.

        Failure modes we've seen:
          - sqlite_vec not installed              -> ImportError
          - Python built without load_extension   -> AttributeError / OperationalError
          - sqlite-vec binary missing for platform-> OperationalError
        In every case we log once and fall back to text-only mode so the
        voice loop keeps running.
        """
        try:
            import sqlite_vec  # type: ignore[import-not-found]

            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.executescript(_vec_schema(dim))
            self._embedding_dim = dim
            self._vec_enabled = True
        except (
            Exception
        ) as exc:  # noqa: BLE001 - we want every failure to degrade gracefully
            log.warning("memory.vec_unavailable", error=str(exc), dim=dim)
            self._vec_enabled = False

    # -- properties ----------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    @property
    def vec_enabled(self) -> bool:
        return self._vec_enabled

    @property
    def embedding_dim(self) -> int | None:
        return self._embedding_dim

    # -- writes --------------------------------------------------------------

    def append(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        embedding: list[float] | None = None,
    ) -> int:
        """Insert a message row. Returns the new row id.

        If `embedding` is supplied and the vec table is enabled, the vector
        goes in the same no-isolation "transaction" (SQLite autocommit per
        statement; this is best-effort atomicity — a crash between the two
        statements means the embedding is missing, which `backfill_embeddings`
        can repair).
        """
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unknown role: {role!r}")
        ts = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO messages (session_id, ts, role, content) VALUES (?, ?, ?, ?)",
            (session_id, ts, role, content),
        )
        msg_id = int(cur.lastrowid)
        if embedding is not None and self._vec_enabled:
            self._insert_vec(msg_id, embedding)
        return msg_id

    def insert_embedding(self, message_id: int, embedding: list[float]) -> None:
        """Attach an embedding to an existing message row.

        Used by the voice loop (embed after append, off-thread) and by
        `backfill_embeddings` (retrofit old rows).
        """
        if not self._vec_enabled:
            raise RuntimeError(
                "sqlite-vec is not enabled; cannot store embeddings. "
                "Install sqlite-vec or disable [memory.semantic] in sabrina.toml."
            )
        self._insert_vec(message_id, embedding)

    def _insert_vec(self, message_id: int, vec: list[float]) -> None:
        if self._embedding_dim is not None and len(vec) != self._embedding_dim:
            raise ValueError(
                f"Embedding dim mismatch: got {len(vec)}, expected {self._embedding_dim}. "
                "Changing embedding models requires `sabrina memory-reindex --drop`."
            )
        self._conn.execute(
            "INSERT OR REPLACE INTO vec_messages(message_id, embedding) VALUES (?, ?)",
            (message_id, _pack_vec(vec)),
        )

    # -- reads ---------------------------------------------------------------

    def load_recent(self, limit: int = 20) -> list[StoredMessage]:
        """Return the last `limit` messages across all sessions, oldest-first.

        If `limit` lands mid-turn (i.e. the oldest loaded message is an
        assistant reply with no matching user prompt), we drop it so the
        brain doesn't see dangling assistant context.
        """
        if limit <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id, session_id, ts, role, content FROM messages "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        messages = [_row_to_stored(row) for row in reversed(rows)]
        # Trim leading "assistant" so the history starts on a user turn.
        while messages and messages[0].role == "assistant":
            messages.pop(0)
        return messages

    def search(
        self,
        query_vec: list[float],
        *,
        k: int = 5,
        max_distance: float | None = None,
        exclude_ids: Iterable[int] = (),
    ) -> list[SearchHit]:
        """Top-k nearest messages by cosine distance.

        `max_distance` drops hits above the threshold (0 = identical, 1 = orthogonal,
        ~2 = opposite). Typical values: 0.35 is tight, 0.6 is loose.

        `exclude_ids` is useful to avoid returning the same turns already
        loaded via `load_recent` — callers pass the ids they already have.
        We over-fetch by the size of exclude_ids so filtering still yields k.
        """
        if not self._vec_enabled:
            raise RuntimeError(
                "sqlite-vec is not enabled; search requires it. Either install sqlite-vec "
                "or disable semantic retrieval in config."
            )
        if self._embedding_dim is not None and len(query_vec) != self._embedding_dim:
            raise ValueError(
                f"Query dim {len(query_vec)} != index dim {self._embedding_dim}."
            )

        exclude_set = set(exclude_ids)
        # k-NN happens inside the vec0 virtual table; we subquery it and
        # then join to `messages` for the text. The `k = ?` binding is
        # vec0's hidden input — keeping it inside the inner SELECT
        # avoids any ambiguity with the outer-scope column names.
        # Over-fetch by |exclude| so filtering still yields k results.
        fetch_k = k + len(exclude_set)
        rows = self._conn.execute(
            """
            SELECT m.id, m.session_id, m.ts, m.role, m.content, v.distance
            FROM (
                SELECT message_id, distance
                FROM vec_messages
                WHERE embedding MATCH ? AND k = ?
            ) AS v
            JOIN messages m ON m.id = v.message_id
            ORDER BY v.distance
            """,
            (_pack_vec(query_vec), fetch_k),
        ).fetchall()

        hits: list[SearchHit] = []
        for row in rows:
            msg_id = int(row[0])
            if msg_id in exclude_set:
                continue
            distance = float(row[5])
            if max_distance is not None and distance > max_distance:
                continue
            hits.append(
                SearchHit(
                    message=_row_to_stored(row[:5]),
                    distance=distance,
                )
            )
            if len(hits) >= k:
                break
        return hits

    # -- stats / admin -------------------------------------------------------

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        return int(row[0]) if row else 0

    def recent_ids(self, n: int) -> list[int]:
        """The `n` most-recent message ids. Used by semantic search to
        exclude turns already in the hot window."""
        if n <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id FROM messages ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [int(r[0]) for r in rows]

    def count_with_embeddings(self) -> int:
        if not self._vec_enabled:
            return 0
        row = self._conn.execute("SELECT COUNT(*) FROM vec_messages").fetchone()
        return int(row[0]) if row else 0

    def messages_missing_embeddings(
        self, *, limit: int | None = None
    ) -> list[StoredMessage]:
        """Rows in `messages` with no matching `vec_messages` entry.

        Returns oldest-first so callers can stream progress.
        """
        if not self._vec_enabled:
            # No vec table => every row is "missing"; but backfill is a no-op.
            return []
        q = (
            "SELECT m.id, m.session_id, m.ts, m.role, m.content FROM messages m "
            "LEFT JOIN vec_messages v ON v.message_id = m.id "
            "WHERE v.message_id IS NULL "
            "ORDER BY m.id ASC"
        )
        params: tuple[object, ...] = ()
        if limit is not None:
            q += " LIMIT ?"
            params = (limit,)
        rows = self._conn.execute(q, params).fetchall()
        return [_row_to_stored(row) for row in rows]

    def backfill_embeddings(
        self,
        embedder,  # Embedder protocol from sabrina.memory.embed
        *,
        batch_size: int = 32,
        progress=None,  # optional callable(done, total) for CLI spinner
    ) -> int:
        """Embed every message that doesn't yet have a vector. Returns count written.

        Synchronous on purpose — callers (CLI `memory-reindex`) are happy
        to block. The voice loop never calls this directly.
        """
        if not self._vec_enabled:
            raise RuntimeError("sqlite-vec not enabled; cannot backfill.")
        missing = self.messages_missing_embeddings()
        total = len(missing)
        if total == 0:
            return 0
        done = 0
        for i in range(0, total, batch_size):
            batch = missing[i : i + batch_size]
            vectors = embedder.embed_batch([m.content for m in batch])
            for msg, vec in zip(batch, vectors, strict=True):
                self._insert_vec(msg.id, vec)
            done += len(batch)
            if progress is not None:
                progress(done, total)
        return done

    def drop_vectors(self) -> None:
        """Drop the vec_messages table. Used by `memory-reindex --drop`."""
        if not self._vec_enabled:
            return
        self._conn.execute("DROP TABLE IF EXISTS vec_messages")
        # Recreate so the caller can immediately insert_embedding again.
        if self._embedding_dim is not None:
            self._conn.executescript(_vec_schema(self._embedding_dim))

    def clear(self) -> int:
        """Delete every message (and its embedding). Returns rows removed from `messages`."""
        n = 0
        cur = self._conn.execute("DELETE FROM messages")
        n = cur.rowcount or 0
        if self._vec_enabled:
            self._conn.execute("DELETE FROM vec_messages")
        log.info("memory.cleared", rows=n)
        return n

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _row_to_stored(row: tuple) -> StoredMessage:
    return StoredMessage(
        id=int(row[0]),
        session_id=str(row[1]),
        ts=datetime.fromisoformat(row[2]),
        role=str(row[3]),
        content=str(row[4]),
    )
