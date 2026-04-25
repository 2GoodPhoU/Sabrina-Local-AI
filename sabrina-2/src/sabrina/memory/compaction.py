"""Memory compaction: fold old turns into one summary row.

Triggered automatically at startup when the un-compacted turn body
exceeds `[memory.compaction].threshold_tokens` (estimated via cheap
chars/token), or manually via `sabrina memory-compact`. Summary rows
are kind='summary' so semantic search skips them; they're injected at
the head of the brain's system prompt instead.

Anti-sprawl note: this module is the *one* compaction algorithm + a
small helper. The plan called for a richer per-session grouping with
an LLM brain. For the overnight scaffold we keep the trigger logic + a
provider-agnostic summarizer protocol; the LLM-call wiring lands when
Eric reviews and signs off on the brain prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Protocol

from sabrina.config import CompactionConfig
from sabrina.logging import get_logger
from sabrina.memory.store import MemoryStore, StoredMessage

log = get_logger(__name__)


# Module-level summarization prompt (per the plan's "Summarization prompt
# (module constant)" section). Kept here so a diff against the prompt is
# obvious. Brain receives it as the system prompt for a one-shot turn.
SUMMARIZATION_SYSTEM_PROMPT = (
    "You are compressing a conversation log for a personal assistant's "
    "long-term memory. Summarize the following in 3-5 sentences, preserving:\n"
    "- Names, places, and specific facts mentioned by the user\n"
    "- Decisions made (things you agreed on)\n"
    "- Preferences (\"I like X\", \"I don't want Y\")\n"
    "- Anything the user asked the assistant to remember\n\n"
    "Skip pleasantries, the assistant's own uncertainty, and any text "
    "obviously ephemeral. Write in the third person (\"The user decided...\")."
)


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Outcome of one compaction pass.

    `turns_compacted` counts the original turn rows folded.
    `summaries_written` is the number of new summary rows (today: 1 per
    pass, but kept plural to leave room for per-session grouping).
    """

    turns_compacted: int
    summaries_written: int
    skipped_reason: str | None = None  # set when no work was done


class Summarizer(Protocol):
    """Async callable: take a transcript, return a 3-5 sentence summary.

    The Brain protocol from `sabrina.brain.protocol` satisfies this once
    wired: `await brain.chat(...)` collected into a string. We keep the
    protocol minimal so a stub summarizer in tests is one lambda.
    """

    async def summarize(self, transcript: str) -> str:
        ...


def estimate_tokens(chars: int, chars_per_token: float = 4.0) -> int:
    """Rough char-to-token estimator. 4.0 is the OpenAI rule of thumb.

    Off by ~10-30% on real text but more than accurate enough for a
    threshold trigger; the alternative (load tiktoken on every cold
    boot) costs ~50 MB and ~250 ms for no real win.
    """
    return int(chars / max(chars_per_token, 0.1))


def should_compact(store: MemoryStore, cfg: CompactionConfig) -> bool:
    """True iff un-compacted turn body exceeds the configured threshold."""
    if cfg.mode == "manual":
        return False
    chars = store.total_turn_chars(only_uncompacted=True)
    estimated = estimate_tokens(chars, cfg.chars_per_token)
    log.debug(
        "compaction.checked",
        chars=chars,
        estimated_tokens=estimated,
        threshold=cfg.threshold_tokens,
    )
    return estimated >= cfg.threshold_tokens


def render_transcript(turns: list[StoredMessage]) -> str:
    """Compact transcript form the summarizer sees.

    "[YYYY-MM-DD] role: content" per line, oldest-first. Mirrors the
    `_format_retrieved` shape from voice_loop so the brain sees the
    same general layout it's been seeing for retrieved context.
    """
    lines: list[str] = []
    for t in turns:
        stamp = t.ts.strftime("%Y-%m-%d")
        body = t.content.strip().replace("\n", " ")
        lines.append(f"[{stamp}] {t.role}: {body}")
    return "\n".join(lines)


async def compact(
    store: MemoryStore,
    summarizer: Summarizer,
    cfg: CompactionConfig,
    *,
    force: bool = False,
) -> CompactionResult:
    """Run one compaction pass.

    1. If not forced and threshold not met, no-op.
    2. Pull the oldest `batch_size` un-compacted turns.
    3. Render the transcript, ask the summarizer for a 3-5 sentence
       summary, write one kind='summary' row, mark originals.
    4. Return counts.

    Idempotent: running compact() twice when there's nothing fresh
    above threshold is a no-op the second time.
    """
    log.info("compaction.started", mode=cfg.mode, force=force)
    if not force and not should_compact(store, cfg):
        log.info("compaction.skipped", reason="below_threshold")
        return CompactionResult(0, 0, skipped_reason="below_threshold")

    turns = store.oldest_uncompacted_turns(limit=cfg.batch_size)
    if len(turns) < 2:
        # Nothing meaningful to summarize. Don't burn the brain on it.
        log.info("compaction.skipped", reason="no_turns", available=len(turns))
        return CompactionResult(0, 0, skipped_reason="no_turns")

    transcript = render_transcript(turns)
    try:
        summary = await summarizer.summarize(transcript)
    except Exception as exc:  # noqa: BLE001 - never let compaction kill the loop
        log.error("compaction.summarizer_failed", error=str(exc))
        return CompactionResult(0, 0, skipped_reason=f"summarizer_error:{exc}")

    summary = summary.strip()
    if not summary:
        log.warning("compaction.empty_summary")
        return CompactionResult(0, 0, skipped_reason="empty_summary")

    # The summary lives in the most-recent compacted turn's session, with
    # the newest turn's ts so ordering-by-ts places the summary "around
    # when it happened."
    newest = turns[-1]
    when = datetime.now(timezone.utc)
    summary_id = store.append_summary(newest.session_id, summary, ts=newest.ts)
    marked = store.mark_summarized([t.id for t in turns], when=when)
    log.info(
        "compaction.summary_written",
        summary_id=summary_id,
        turns_compacted=marked,
    )
    return CompactionResult(turns_compacted=marked, summaries_written=1)


def make_callable_summarizer(
    fn: Callable[[str], Awaitable[str]],
) -> Summarizer:
    """Adapter so a bare async function can satisfy the Summarizer protocol.

    The Brain wiring (decision pending) will pass a small async helper
    that runs `brain.chat(history=[user_message_with_transcript],
    system=SUMMARIZATION_SYSTEM_PROMPT)` and concatenates the deltas.
    """

    class _Adapter:
        async def summarize(self, transcript: str) -> str:
            return await fn(transcript)

    return _Adapter()
