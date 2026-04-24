# Semantic memory GUI + summary compaction (component 007b)

**Date:** 2026-04-23
**Status:** Draft. Fully specified; implementable in one session. No Eric
blockers.
**Closes:** decision 007's "settings GUI 007b" follow-up, plus the
"summary compaction" thin spot listed in decisions 006 and 007.

## The one-liner

Finish decision 007's loose ends: extend the Memory tab in the settings
GUI to expose every `[memory.semantic]` knob, a test-query field, and
one-button reindex + compact actions. In the same session, add an
automatic summary-compaction loop that runs at startup when the
un-compacted turn count exceeds a threshold (default 200), rolls those
old turns into summary rows, and plumbs the summaries into the system
prompt so Sabrina keeps the gist of old conversations without the
token cost of the full transcript.

## Scope

In:
- Memory tab GUI extensions: three sub-frames ("Semantic retrieval",
  "Compaction", "Test retrieval"). Inline stats readout.
- New column `kind TEXT NOT NULL DEFAULT 'turn'` on `messages` (via
  one migration). New optional column `summarized_at TEXT NULL` for
  provenance tracking.
- `memory/compact.py` (~150 lines): the compaction algorithm.
- `sabrina memory-compact` CLI verb (auto/manual unified surface).
- `[memory.compaction]` config block.
- Voice-loop integration: if compaction summaries exist, inject them
  as a "So far in our prior conversations..." block at the head of
  the system prompt — separate from the semantic-retrieval block
  (decision 007) and independent of it.
- Startup-threshold auto-trigger (non-blocking; runs in background on
  voice-loop start).
- Tests: schema migration, compaction algorithm, auto-trigger gate,
  GUI sub-frame rendering, voice-loop summary-injection path.

Out:
- Live retrieval feed in the GUI ("show me what just got retrieved").
  Instead: a test-retrieval field the user types into — same utility,
  less eventing complexity. Live feed can land later as a `voice_loop`
  → GUI bus event.
- Deleting compacted originals. Mark-only. Disk is cheap.
- Cross-session summary aggregation ("the summary of the summaries").
  One level is enough until we have enough data to see a problem.
- Automatic re-summarize on semantic-model change. When a user runs
  `memory-reindex --drop`, summaries stay. Rebuilding summaries uses
  the same `memory-compact` verb; documented but not automated.

## Files to touch

```
sabrina-2/src/sabrina/
├── memory/
│   ├── compact.py                # NEW, ~150 lines
│   └── store.py                  # +kind column migration,
│                                 # +kind filter in search(),
│                                 # +load_summaries(),
│                                 # +count_uncompacted()
├── voice_loop.py                 # +inject summaries at top of system prompt
├── gui/settings.py               # +three sub-frames on Memory tab
├── cli.py                        # +sabrina memory-compact verb
└── config.py                     # +CompactionConfig under MemoryConfig
sabrina-2/
├── sabrina.toml                  # +[memory.compaction]
└── tests/test_smoke.py           # +compact/gui/migration tests
```

One new file, `memory/compact.py`. Keep it ≤200 lines. No new top-level
abstractions; compaction is "one function + a small helper," not a new
component.

## Schema migration

```sql
-- Additive. Safe to run on an existing DB.
ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'turn';
ALTER TABLE messages ADD COLUMN summarized_at TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_kind ON messages(kind);
```

`kind` has two values in scope: `'turn'` (user/assistant dialogue, the
default — every existing row gets this) and `'summary'` (compaction
output). The `role` column stays what it is — summaries use `role='system'`
so `StoredMessage.to_message()` keeps working.

`summarized_at` is set on `kind='turn'` rows when a compaction run folded
them into a summary. It's purely informational — nothing reads it
programmatically except the GUI stats panel.

Migration runs from `MemoryStore.__init__` via `PRAGMA user_version`
guard so repeat opens are no-ops:

```python
# inside MemoryStore._migrate():
v = self._conn.execute("PRAGMA user_version").fetchone()[0]
if v < 1:
    self._conn.executescript(_MIGRATION_V1)
    self._conn.execute("PRAGMA user_version = 1")
```

## Compaction algorithm — `memory/compact.py`

```python
@dataclass(frozen=True, slots=True)
class CompactionResult:
    summaries_written: int
    turns_compacted: int
    sessions: int

async def compact(
    store: MemoryStore,
    brain: Brain,
    *,
    older_than_turns: int = 200,
    min_turns_per_session: int = 10,
) -> CompactionResult:
    """Group un-compacted turns by session_id, summarize each session's
    block, write one kind='summary' row per summarized session.

    Skip sessions with fewer than min_turns_per_session un-compacted
    turns (not worth the round-trip). Skip the most-recent `older_than_turns`
    turns globally — those are still "live."

    Returns counts for logging + GUI display.
    """
    ...
```

Step-by-step:

1. Query rows where `kind='turn'` and `summarized_at IS NULL`, oldest
   first. Exclude the most-recent `older_than_turns` via `recent_ids`.
2. Group by `session_id`, skipping groups under `min_turns_per_session`.
3. For each group, render a compact transcript ("[date] role: content\n")
   and ask the configured brain to summarize in 3-5 sentences focused on
   facts (names, decisions, preferences). Prompt is a module-level
   constant so it's diff-reviewable.
4. Write one `INSERT INTO messages (session_id, ts, role, content, kind)
   VALUES (?, ?, 'system', ?, 'summary')` per session. `ts` is the
   newest turn's timestamp (so ordering-by-ts places the summary
   "around when it happened").
5. `UPDATE messages SET summarized_at = ? WHERE id IN (...)` for each
   compacted group.
6. Summaries are NOT embedded. They're not meant to surface as
   retrieval matches; they get injected into the system prompt by the
   voice-loop path instead.

**Why NOT embed summaries:**
- Search is for "find me that specific moment"; summaries blur moments.
- A matching summary would push out a matching real turn from top-k.
- One less place to worry about dim migration on model changes.

**Why leave original turns + their embeddings in place:**
- Precise retrieval still wins when it hits. If someone asks "what did
  we say about the budget ceiling," semantic search on the real turn
  beats a sentence of summary.
- No data loss. The user answered "mark, never delete."

### Summarization prompt (module constant)

```text
You are compressing a conversation log for a personal assistant's
long-term memory. Summarize the following in 3-5 sentences, preserving:

- Names, places, specific facts mentioned by the user
- Decisions made (things we agreed on)
- Preferences ("I like X", "I don't want Y")
- Anything the user asked the assistant to remember

Skip pleasantries, the assistant's own uncertainty, and any text that's
obviously ephemeral. Write in the third person ("The user decided...").
```

## Voice-loop injection of summaries

Today's flow:
```
system prompt = _SYSTEM [+ retrieved_block as system_suffix, if any]
```

After 007b:
```
system prompt = _SYSTEM + summaries_block
system_suffix = retrieved_block (if any)
```

`summaries_block` is a stable, rarely-changing appendix to `_SYSTEM` —
it only shifts when compaction runs, which is rare. That's why it lives
in the cacheable head (under prompt caching from the budget plan), not
in `system_suffix` (which changes per turn).

Concretely, `voice_loop` at startup calls `store.load_summaries(limit=50)`
and builds:

```python
summaries_block = ""
if summaries:
    summaries_block = "\n\nSo far in our prior conversations:\n" + "\n".join(
        f"- [{s.ts.date()}] {s.content.strip()}"
        for s in summaries
    )
turn_system_stable = _SYSTEM + summaries_block
# `retrieved_block` still goes in as system_suffix (non-cached).
```

`load_summaries` is a new read method on `MemoryStore`:

```python
def load_summaries(self, *, limit: int = 50) -> list[StoredMessage]:
    """Most recent N kind='summary' rows, oldest-first. Limit guards
    against a runaway summary count."""
    rows = self._conn.execute(
        "SELECT id, session_id, ts, role, content FROM messages "
        "WHERE kind = 'summary' ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_stored(row) for row in reversed(rows)]
```

## Search filtering

`MemoryStore.search()` gains a default filter that excludes `kind='summary'`
rows from retrieval. Summaries don't have vec rows anyway, but the
explicit filter is cheap and future-proofs against "did we accidentally
embed a summary once?"

```python
# Inside search(), after the vec0 k-NN subquery:
"JOIN messages m ON m.id = v.message_id "
"WHERE m.kind = 'turn' "
"ORDER BY v.distance"
```

Existing `test_semantic_memory_*` tests continue to pass because the
default `kind` for every row is `'turn'`.

## Auto-compaction at startup

```python
# voice_loop.py, before the main loop
if settings.memory.compaction.auto_enabled:
    uncompacted = memory.count_uncompacted()
    if uncompacted >= settings.memory.compaction.threshold_turns:
        # Background task — doesn't block voice-loop startup.
        asyncio.create_task(_background_compact(memory, brain, settings, console))
```

`_background_compact`:
- Logs "compaction.started turns=N".
- Calls `compact()`.
- Logs result + publishes a new `CompactionFinished` event on the bus.
- Swallows exceptions (compaction failures must never knock the voice
  loop over). Log loudly so they show up in `logs/`.

**Threshold default: 200 un-compacted turns.** Justification:

- Token footprint: with ~40 tokens/turn average, 200 turns is ~8,000
  tokens. That's ~$0.024 to summarize with Haiku 4.5. Free on Ollama.
- Frequency: a heavy day of voice use is ~50 turns. Threshold at 200
  means compaction runs once every 3-4 days for a daily-driver user,
  not multiple times per day.
- Buffer above `load_recent=20`: 10× headroom between the "hot" window
  and the compaction trigger. Never compact turns the rolling window is
  actively loading.
- Operator-visible: 200 is easy to reason about; turn-count stats are
  already exposed by `sabrina memory-stats`.

Alternatives considered:
- Token count (tokenize, sum). More accurate but requires a tokenizer
  path on the cold boot. Rejected: overhead > value; turn count is
  close enough.
- Age (older than N days). Doesn't correlate with token pressure for a
  spiky usage pattern. Rejected.
- Byte count (`len(content)` summed). Proxy for tokens, no tokenizer
  needed. Reasonable alternative; stayed with turn count because it's
  what `memory-stats` already surfaces.

## Config additions

```toml
[memory.compaction]
# When true (default), Sabrina compacts old turns into summaries at
# voice-loop startup if the un-compacted turn count exceeds the
# threshold below. Runs in the background; no user wait.
auto_enabled = true

# Minimum un-compacted turn count before auto-compaction fires. Only
# turns older than load_recent + min_age_turns are eligible — we never
# compact anything the hot window is using.
threshold_turns = 200

# Minimum turns per session before we bother summarizing. Short
# sessions (5-10 turns) usually aren't worth the summarization token
# spend; keep their raw turns retrievable via semantic search.
min_turns_per_session = 10

# Brain to use for summarization. "claude_fast" uses brain.claude.fast_model
# (Haiku 4.5 by default — ~$0.024 per compaction run at default threshold).
# "ollama" uses brain.ollama.fast_model (free). "claude" uses the main
# brain.claude.model (overkill; noted for completeness).
brain = "claude_fast"
```

## GUI — three sub-frames on the Memory tab

Builds on the existing Memory tab (today: `enabled`, `load_recent`).

### Sub-frame 1: "Semantic retrieval"

Layout: section header, then rows of controls.

```
[x] Enabled                     (checkbox, memory.semantic.enabled)
Top K:          [5]             (spinbox)
Max distance:   [===O=====] 0.5 (slider 0.1..1.0, step 0.01)
Min age turns:  [20]            (spinbox)
Embedding model: [sentence-transformers/all-MiniLM-L6-v2]  (entry, grey
                                                           unless "Advanced" toggled)
Stats: 1,247 messages, 1,247 embedded (100%)  vec dim=384
  [ Reindex now ]   [ Drop + rebuild ]
```

- "Reindex now" spawns `sys.executable + ["-m", "sabrina", "memory-reindex"]`
  as a subprocess, shows a modal with progress text streamed from
  stdout.
- "Drop + rebuild" prompts a confirm dialog, then runs
  `memory-reindex --drop`. Destructive warning visible.
- Stats refresh on modal close + on tab switch.

### Sub-frame 2: "Compaction"

```
[x] Auto at startup (threshold)    (checkbox, memory.compaction.auto_enabled)
Threshold turns: [200]              (spinbox)
Min turns/session: [10]             (spinbox)
Summarizer:     [Claude Haiku ▼]    (optionmenu: claude_fast | ollama | claude)
Stats: 2,451 turns total · 1,198 un-compacted · last run 2026-04-18
  [ Compact now ]
```

- "Compact now" spawns `sabrina memory-compact --force` (ignores the
  threshold). Shows a modal with streamed output: "Session X:
  summarizing 87 turns..." etc.
- Stats: `total_turns`, `uncompacted_turns`, `last_summary_ts` (max ts
  on `kind='summary'` rows). The CLI `memory-stats` verb gets the
  same numbers for parity.

### Sub-frame 3: "Test retrieval"

```
Query:  [____________________]  [ Search ]
Results:
  d=0.312  [2026-04-20 14:22]        user  how is the voice latency?
  d=0.378  [2026-04-22 09:03]   assistant  First-audio should be under 2s...
  ...
```

- Calls `sabrina memory-search "<q>"` as a subprocess, parses its
  text output, renders into a CTkScrollableFrame.
- Useful for tuning `max_distance` interactively: adjust the slider,
  re-run the query, see what threshold makes sense.

## CLI additions

```
sabrina memory-compact              # respect threshold; no-op if below
sabrina memory-compact --force      # compact everything eligible now
sabrina memory-compact --dry-run    # print what would be compacted, don't write
sabrina memory-compact --session ID # one session only
```

`memory-stats` gets two new lines:

```
  summaries:   3
  uncompacted: 1,198
```

## Test strategy

Fast unit tests:

- `test_memory_store_kind_migration_idempotent` — open store against a
  pre-migration fixture, verify `kind` column appears and `user_version`
  = 1. Open again, verify no-op.
- `test_memory_store_search_excludes_summaries` — insert a summary row
  with a fake vec (if vec enabled), assert `search()` never returns it.
  (sqlite-vec-gated via `importorskip`.)
- `test_memory_store_load_summaries_oldest_first` — direct.
- `test_memory_store_count_uncompacted` — direct.
- `test_compaction_skips_short_sessions` — 3 sessions (5, 8, 50 turns),
  threshold met globally, assert only the 50-turn session gets
  summarized.
- `test_compaction_marks_originals_and_writes_summary` — stub brain
  returning a canned summary string; assert `summarized_at` set on
  the originals + one kind='summary' row inserted.
- `test_compaction_summary_not_searchable` — stub brain; run compaction;
  assert semantic search over the same text doesn't return the summary.
  (Obvious from the filter, but makes the contract test-explicit.)
- `test_voice_loop_loads_summaries_into_system` — stub memory with one
  summary row; run one turn; assert the system prompt passed to
  `brain.chat` contains "So far in our prior conversations:".
- `test_auto_compaction_skipped_below_threshold` — spy on
  `create_task`; voice loop starts with 50 un-compacted turns, threshold
  200; assert no background task spawned.
- `test_auto_compaction_runs_in_background_when_threshold_met` —
  threshold met, assert the task is created and completes without
  blocking startup.
- `test_gui_memory_tab_renders_all_subframes` — mirror of the existing
  GUI smoke tests; build the tab with a stub settings object, assert
  the expected widget names exist.

Manual smoke (in a new `validate-memory-compact-windows.md` when we
ship):
- Seed a DB with ~300 fake turns across 3 sessions.
- `sabrina memory-compact --dry-run` — confirm three summary groups
  reported.
- `sabrina memory-compact` — confirm summaries written, originals
  marked.
- `sabrina voice` — confirm the first reply incorporates context from
  the summary (ask "what did we decide last time?").
- Open the settings GUI, click through each sub-frame, confirm no
  crashes.

## Step-ordered implementation outline

1. `CompactionConfig` in `config.py` + `[memory.compaction]` block in
   `sabrina.toml`. One commit.
2. Schema migration (kind + summarized_at columns) + `MemoryStore`
   read methods (`load_summaries`, `count_uncompacted`) + the search
   filter. Tests. One commit.
3. `memory/compact.py` with a stub brain test. One commit.
4. `voice_loop.py`: inject summaries into system head; trigger
   auto-compaction when threshold met. Tests. One commit.
5. `cli.py`: `sabrina memory-compact` verb + `memory-stats` updates.
   One commit.
6. GUI: three sub-frames on the Memory tab. One commit (GUI edits tend
   to be big but stay in one file).
7. `validate-memory-compact-windows.md`. One commit.

Keep commits atomic per step.

## Dependencies to add

None. Compaction uses the existing `Brain` protocol and the existing
memory store.

## Windows-specific concerns

- Subprocess-spawn from the GUI: use
  `sys.executable + ["-m", "sabrina", "memory-reindex"]` rather than a
  bare `sabrina` call, to defend against venv mismatch (GUI launched
  from one env, `sabrina` script resolved from another).
- Modal progress window streaming stdout: on Windows, the subprocess's
  stdout needs `stdout=subprocess.PIPE, bufsize=1, text=True`. Without
  line buffering the progress line only surfaces at flush, which feels
  hung.
- SQLite migration: the `ALTER TABLE ... ADD COLUMN` pattern is safe
  across SQLite versions Eric's Python ships with. No lock contention
  because the migration runs inside `MemoryStore.__init__`, before the
  voice loop or GUI opens a second connection.
- The summary `ts` is UTC ISO-8601 like every other `messages.ts`;
  GUI renders local time via Python's `datetime.astimezone()`.

## Open questions (none blocking)

Eric's sign-off resolved all four from the master plan:
- Auto-at-threshold default, toggleable (resolved).
- Summarizer: Haiku default, Ollama override (resolved).
- Per-session granularity (resolved).
- Mark-only, never delete (resolved).

Threshold default (200 turns) is justified above; it's a config knob,
so a wrong default is a setting change, not a redesign.

## Ship criterion

- All new unit tests pass. All existing tests unchanged.
- `sabrina memory-compact --dry-run` on a DB with 300 fake turns
  reports plausible groups.
- `sabrina memory-compact` writes summaries; `memory-stats` afterward
  shows non-zero `summaries` and correct `uncompacted`.
- Fresh voice-loop start with summaries present produces a brain reply
  that references the summarized context when asked
  ("what did we decide last week?").
- GUI Memory tab: all three sub-frames render; buttons work.
- No regression on first-audio latency (summary load is one SELECT at
  startup; background compaction runs after the first turn).

## Not in this plan (later)

- Live GUI feed of the most recent retrieval hits. Easy to add once
  there's a pattern for voice-loop → GUI events (pairs with item #10
  of the master plan — voice-loop polish + `ConfigReloaded`).
- Summary-of-summaries if we ever run long enough for the summary
  count to grow past a page of context.
- Per-summary feedback UI ("was this summary useful?"). Only worth it
  if retrieval quality ever feels off.
- Scheduled compaction (cron-style, not just startup). Startup is
  enough; the supervisor restart cadence plus a threshold trigger
  means summaries stay fresh in practice.
