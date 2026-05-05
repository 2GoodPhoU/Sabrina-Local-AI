"""Conversation-memory store: SQLite with an optional sqlite-vec index.

Two tables:

  messages       - one row per user/assistant/system turn. Existed pre-007.
                   Schema v1 (decision pending) adds:
                     kind          TEXT NOT NULL DEFAULT 'turn'   ('turn'|'summary')
                     summarized_at TEXT NULL                      (provenance only)
  vec_messages   - vec0 virtual table from sqlite-vec, one row per embedding.
                   Keyed by message_id (1:1 with messages.id).

Access patterns:
  - append(session_id, role, content, embedding=None)   per turn
  - append_summary(session_id, content)                 from compaction
  - insert_embedding(message_id, vec)                   async-friendly
  - load_recent(limit)                                  at startup
  - load_summaries(limit)                               at startup (compaction read)
  - search(query_vec, k, max_distance, exclude_ids)     per turn (semantic)
                                                        filters out kind='summary'
  - backfill_embeddings(embedder)                       one-shot reindex
  - mark_summarized(ids, when)                          from compaction
  - count_uncompacted() / total_turn_chars()            for compaction trigger
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

# Migration to schema v1: add `kind` (turn|summary) + `summarized_at` columns
# so compaction (see `rebuild/drafts/semantic-memory-gui-plan.md`) can write
# summary rows that retrieval skips, and mark originals as folded.
# `ALTER TABLE ... ADD COLUMN` is O(1) on SQLite. Idempotent via
# `PRAGMA user_version`.
_MIGRATION_V1 = """
ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'turn';
ALTER TABLE messages ADD COLUMN summarized_at TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_kind ON messages(kind);
"""

# Migration to schema v2: add `importance REAL DEFAULT 0.5` column for
# Park-style retrieval scoring (`α·recency + β·importance + γ·relevance`).
# 0.5 is the neutral midpoint — until LLM-rating lands, every existing
# row scores neutrally and the formula reduces to recency + relevance,
# which is still a strict win over cosine-only.
# See `rebuild/drafts/research/2026-04-26-memory-architecture-evolution.md`
# Tier 1.
_MIGRATION_V2 = """
ALTER TABLE messages ADD COLUMN importance REAL NOT NULL DEFAULT 0.5;
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


def _recency_score(message_ts: datetime, *, now: datetime, half_life_days: float) -> float:
    """Exponential-decay recency term for Park-style retrieval.

    Returns 1.0 for a message dated `now`, 0.5 after `half_life_days`,
    0.25 after 2x, etc. Older-than-now timestamps (which can happen with
    clock skew or a restored DB) clamp to 1.0; future timestamps clamp
    to 1.0 too. Half-life <= 0 disables decay (always 1.0).
    """
    if half_life_days <= 0:
        return 1.0
    # Both timestamps are tz-aware (we always write isoformat with
    # `datetime.now(timezone.utc)`). If a caller passes a naive `now`
    # we coerce to UTC to keep the math sane.
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if message_ts.tzinfo is None:
        message_ts = message_ts.replace(tzinfo=timezone.utc)
    age_seconds = (now - message_ts).total_seconds()
    if age_seconds <= 0:
        return 1.0
    age_days = age_seconds / 86400.0
    # 0.5 ** (age / half_life). Use math.pow for clarity over **.
    import math

    return math.pow(0.5, age_days / half_life_days)


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


@dataclass(frozen=True, slots=True)
class ScoredHit:
    """A search hit annotated with the Park-style component scores.

    Score = ``alpha*recency + beta*importance + gamma*relevance``. Every
    sub-score is reported so the brain (or a tuner) can see why a hit
    ranked where it did — recency decay vs. importance vs. raw cosine.

    `relevance = 1 - cosine_distance` (clamped to [0, 1]).
    `recency` is the exponential decay term from `_recency_score`.
    `importance` is the per-message column value (0..1).
    `score` is the linear combination using the supplied weights.
    """

    message: StoredMessage
    distance: float
    importance: float
    recency: float
    relevance: float
    score: float


def new_session_id() -> str:
    """Fresh UUID per process - lets us group "this run's" messages."""
    return uuid.uuid4().hex[:12]


class MemoryStore:
    def __init__(self, db_path: Path, *, embedding_dim: int | None = None) -> None:
        db_path = db_path.expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(
            str(db_path),
            isolation_level=None,  # autocommit
            check_same_thread=False,
        )
        self._conn.executescript(_SCHEMA)
        self._migrate()

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

    def _migrate(self) -> None:
        """Run pending schema migrations idempotently via PRAGMA user_version.

        v0 -> v1: add kind + summarized_at columns. See `_MIGRATION_V1`.
        v1 -> v2: add importance column for Park-style scoring. See
                  `_MIGRATION_V2`.
        """
        row = self._conn.execute("PRAGMA user_version").fetchone()
        v = int(row[0]) if row else 0
        if v < 1:
            try:
                self._conn.executescript(_MIGRATION_V1)
            except sqlite3.OperationalError as exc:
                # Re-running on a DB that already has the columns (e.g. an
                # earlier run that crashed mid-migration but left them in
                # place) shouldn't re-fail. ALTER TABLE ADD COLUMN raises
                # `duplicate column name` in that case; accept and bump.
                if "duplicate column" not in str(exc).lower():
                    raise
                log.debug("memory.migrate.duplicate_column_ok", err=str(exc))
            self._conn.execute("PRAGMA user_version = 1")
            log.info("memory.migrated", to_version=1)
            v = 1
        if v < 2:
            try:
                self._conn.executescript(_MIGRATION_V2)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
                log.debug("memory.migrate.duplicate_column_ok", err=str(exc))
            self._conn.execute("PRAGMA user_version = 2")
            log.info("memory.migrated", to_version=2)

    def _try_enable_vec(self, dim: int) -> None:
        """Attempt to load sqlite-vec and create the vec table. Swallow failures."""
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
        """Insert a turn row. Returns the new row id."""
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Unknown role: {role!r}")
        ts = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO messages (session_id, ts, role, content, kind) "
            "VALUES (?, ?, ?, ?, 'turn')",
            (session_id, ts, role, content),
        )
        msg_id = int(cur.lastrowid)
        if embedding is not None and self._vec_enabled:
            self._insert_vec(msg_id, embedding)
        return msg_id

    def append_summary(
        self,
        session_id: str,
        content: str,
        *,
        ts: datetime | None = None,
    ) -> int:
        """Insert a summary row (kind='summary'). Returns the new id.

        Summary rows are excluded from semantic search and from
        `recent_ids` / `messages_missing_embeddings` (no embedding is
        ever computed for them). They surface only via `load_summaries`.
        """
        ts_iso = (ts or datetime.now(timezone.utc)).isoformat()
        cur = self._conn.execute(
            "INSERT INTO messages (session_id, ts, role, content, kind) "
            "VALUES (?, ?, 'system', ?, 'summary')",
            (session_id, ts_iso, content),
        )
        return int(cur.lastrowid)

    def mark_summarized(self, ids: Iterable[int], *, when: datetime | None = None) -> int:
        """Set summarized_at on the given ids. Returns rows updated."""
        ts_iso = (when or datetime.now(timezone.utc)).isoformat()
        ids_list = list(ids)
        if not ids_list:
            return 0
        # Avoid IN (?, ?, ...) overflow by chunking; SQLite default is 999.
        updated = 0
        for i in range(0, len(ids_list), 500):
            chunk = ids_list[i : i + 500]
            placeholders = ",".join(["?"] * len(chunk))
            cur = self._conn.execute(
                f"UPDATE messages SET summarized_at = ? "
                f"WHERE id IN ({placeholders}) AND kind = 'turn'",
                (ts_iso, *chunk),
            )
            updated += cur.rowcount or 0
        return updated

    def insert_embedding(self, message_id: int, embedding: list[float]) -> None:
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
        """Return the last `limit` turn messages (kind='turn'), oldest-first."""
        if limit <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id, session_id, ts, role, content FROM messages "
            "WHERE kind = 'turn' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        messages = [_row_to_stored(row) for row in reversed(rows)]
        while messages and messages[0].role == "assistant":
            messages.pop(0)
        return messages

    def load_summaries(self, *, limit: int = 50) -> list[StoredMessage]:
        """Most recent N summary rows, oldest-first.

        Summaries are injected at the head of the brain's system prompt.
        Limit guards against runaway count once the user has lots of
        history; default 50 is generous (~50 sessions).
        """
        if limit <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id, session_id, ts, role, content FROM messages "
            "WHERE kind = 'summary' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_stored(row) for row in reversed(rows)]

    def count_uncompacted(self) -> int:
        """Turn rows that haven't been folded into a summary yet."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE kind = 'turn' AND summarized_at IS NULL"
        ).fetchone()
        return int(row[0]) if row else 0

    def total_turn_chars(self, *, only_uncompacted: bool = True) -> int:
        """Sum of content character counts across turn rows.

        Used by the compaction trigger as a cheap proxy for token count.
        Set `only_uncompacted=False` to count everything (e.g. for stats).
        """
        clause = "WHERE kind = 'turn'"
        if only_uncompacted:
            clause += " AND summarized_at IS NULL"
        row = self._conn.execute(
            f"SELECT COALESCE(SUM(LENGTH(content)), 0) FROM messages {clause}"
        ).fetchone()
        return int(row[0]) if row else 0

    def oldest_uncompacted_turns(self, *, limit: int) -> list[StoredMessage]:
        """The `limit` oldest turn rows that are still un-compacted.

        Compaction folds these into a summary. Excludes summary rows.
        """
        if limit <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id, session_id, ts, role, content FROM messages "
            "WHERE kind = 'turn' AND summarized_at IS NULL "
            "ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_stored(row) for row in rows]

    def set_importance(self, message_id: int, importance: float) -> None:
        """Override the per-message importance score.

        Importance is in [0, 1]. The schema stores any REAL value; the
        clamp here is the contract. The brain (or a future LLM-rating
        background job) is the canonical writer.
        """
        importance = max(0.0, min(1.0, float(importance)))
        self._conn.execute(
            "UPDATE messages SET importance = ? WHERE id = ?",
            (importance, message_id),
        )

    def search(
        self,
        query_vec: list[float],
        *,
        k: int = 5,
        max_distance: float | None = None,
        exclude_ids: Iterable[int] = (),
    ) -> list[SearchHit]:
        """Top-k nearest *turn* messages by cosine distance.

        Summary rows (kind='summary') are filtered out -- they're injected
        at the head of the system prompt, not retrieved per-turn.
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
            WHERE m.kind = 'turn'
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

    def search_scored(
        self,
        query_vec: list[float],
        *,
        k: int = 5,
        max_distance: float | None = None,
        exclude_ids: Iterable[int] = (),
        alpha: float = 1.0,
        beta: float = 1.0,
        gamma: float = 1.0,
        recency_half_life_days: float = 30.0,
        now: datetime | None = None,
        candidate_multiplier: int = 4,
    ) -> list[ScoredHit]:
        """Top-k results ranked by ``alpha*recency + beta*importance + gamma*relevance``.

        Distance still drives the candidate pool (sqlite-vec is k-NN
        only); we over-fetch by `candidate_multiplier` so the rerank
        has room to reorder. This is the Park et al. canonical
        retrieval formulation; see
        ``rebuild/drafts/research/2026-04-26-memory-architecture-evolution.md``.

        - `relevance = max(0, 1 - distance)` (cosine distance is in
          [0, 2]; we clamp the negative half so an "anti-relevant" term
          can't drag the score negative).
        - `importance` reads from the per-message column (default 0.5).
        - `recency` uses `_recency_score(...)` (exponential decay).
        - Sort: score desc; ties broken by lower distance (more
          relevant) then higher id (newer).
        """
        if not self._vec_enabled:
            raise RuntimeError(
                "sqlite-vec is not enabled; search_scored requires it."
            )
        if self._embedding_dim is not None and len(query_vec) != self._embedding_dim:
            raise ValueError(
                f"Query dim {len(query_vec)} != index dim {self._embedding_dim}."
            )

        exclude_set = set(exclude_ids)
        # Over-fetch so the rerank can promote older-but-important hits
        # over newer-but-irrelevant ones. 4x is generous without being
        # expensive at single-user scale.
        fetch_k = max(k * candidate_multiplier, k) + len(exclude_set)
        rows = self._conn.execute(
            """
            SELECT m.id, m.session_id, m.ts, m.role, m.content,
                   v.distance, m.importance
            FROM (
                SELECT message_id, distance
                FROM vec_messages
                WHERE embedding MATCH ? AND k = ?
            ) AS v
            JOIN messages m ON m.id = v.message_id
            WHERE m.kind = 'turn'
            ORDER BY v.distance
            """,
            (_pack_vec(query_vec), fetch_k),
        ).fetchall()

        now = now or datetime.now(timezone.utc)
        scored: list[ScoredHit] = []
        for row in rows:
            msg_id = int(row[0])
            if msg_id in exclude_set:
                continue
            distance = float(row[5])
            if max_distance is not None and distance > max_distance:
                continue
            stored = _row_to_stored(row[:5])
            importance_raw = row[6] if row[6] is not None else 0.5
            importance = max(0.0, min(1.0, float(importance_raw)))
            relevance = max(0.0, min(1.0, 1.0 - distance))
            recency = _recency_score(
                stored.ts, now=now, half_life_days=recency_half_life_days
            )
            score = alpha * recency + beta * importance + gamma * relevance
            scored.append(
                ScoredHit(
                    message=stored,
                    distance=distance,
                    importance=importance,
                    recency=recency,
                    relevance=relevance,
                    score=score,
                )
            )
        scored.sort(key=lambda h: (-h.score, h.distance, -h.message.id))
        return scored[:k]

    # -- stats / admin -------------------------------------------------------

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()
        return int(row[0]) if row else 0

    def count_summaries(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE kind = 'summary'"
        ).fetchone()
        return int(row[0]) if row else 0

    def recent_ids(self, n: int) -> list[int]:
        """The `n` most-recent turn-row ids (excludes summaries)."""
        if n <= 0:
            return []
        rows = self._conn.execute(
            "SELECT id FROM messages WHERE kind = 'turn' "
            "ORDER BY id DESC LIMIT ?",
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
        """Turn rows in `messages` with no matching `vec_messages` entry.

        Excludes summary rows -- they're never embedded by design.
        """
        if not self._vec_enabled:
            return []
        q = (
            "SELECT m.id, m.session_id, m.ts, m.role, m.content FROM messages m "
            "LEFT JOIN vec_messages v ON v.message_id = m.id "
            "WHERE v.message_id IS NULL AND m.kind = 'turn' "
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
        if not self._vec_enabled:
            return
        self._conn.execute("DROP TABLE IF EXISTS vec_messages")
        if self._embedding_dim is not None:
            self._conn.executescript(_vec_schema(self._embedding_dim))

    def clear(self) -> int:
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
