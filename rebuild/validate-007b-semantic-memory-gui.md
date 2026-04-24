# Decision 007b — Semantic memory GUI + compaction — Windows validation procedure

**Purpose:** confirm the Memory-tab GUI extensions and the auto-
compaction loop work end-to-end on Eric's Windows box before we call
decision 007b validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.
007b implementation has landed per
`rebuild/drafts/semantic-memory-gui-plan.md` (schema migration to add
`kind` + `summarized_at`, `memory/compact.py`, `sabrina memory-compact`
CLI verb, GUI three-sub-frame Memory tab, `[memory.compaction]` block,
voice-loop summary injection). Decision 007 must already be validated
(this builds on its migrations and tests).

---

## Step 0 — Sanity-check the schema migration idempotency

Before touching anything else, prove the new columns exist and the
migration doesn't re-run destructively.

```powershell
uv run python -c "import sqlite3; c = sqlite3.connect('data/sabrina.db'); print('user_version:', c.execute('PRAGMA user_version').fetchone()[0]); print('columns:', [r[1] for r in c.execute('PRAGMA table_info(messages)').fetchall()])"
```

**Success:** `user_version: 1` and the columns list includes `kind`
and `summarized_at`. The existing `id, session_id, ts, role, content`
columns are also present.

**Failure signal A:** `user_version: 0` — the migration didn't run.
That means the GUI/CLI still opened the store with the old shape, and
`kind` and `summarized_at` don't exist. Open `sabrina voice` once
briefly (runs `MemoryStore.__init__` which runs the migration) then
rerun.

**Failure signal B:** `operational error: duplicate column name: kind`
— the migration ran twice, which means `PRAGMA user_version` wasn't
guarding correctly. Capture the full error.

---

## Step 1 — `uv sync` and `uv run pytest -q`

```powershell
uv sync
uv run pytest -q
```

**Success:** existing 70+ tests pass, plus the 007b block (~11 new
tests):

- `test_memory_store_kind_migration_idempotent`
- `test_memory_store_search_excludes_summaries`
- `test_memory_store_load_summaries_oldest_first`
- `test_memory_store_count_uncompacted`
- `test_compaction_skips_short_sessions`
- `test_compaction_marks_originals_and_writes_summary`
- `test_compaction_summary_not_searchable`
- `test_voice_loop_loads_summaries_into_system`
- `test_auto_compaction_skipped_below_threshold`
- `test_auto_compaction_runs_in_background_when_threshold_met`
- `test_gui_memory_tab_renders_all_subframes`

---

## Step 2 — Confirm CLI parity: `sabrina memory-stats` has new lines

```powershell
uv run sabrina memory-stats
```

**Success:** output now includes two new lines at the bottom:

```
Memory at .../sabrina-2/data/sabrina.db
  messages:    N
  embeddings:  N  (100% of messages)
  vec dim:     384
  summaries:   0
  uncompacted: N
```

`summaries: 0` expected on first run. `uncompacted: N` equals `messages`
until compaction runs.

**Failure signal:** missing lines → `memory-stats` verb didn't get
the 007b additions. Check `cli.py` (or `cli/memory.py` post-split).

---

## Step 3 — GUI renders without crash

```powershell
uv run sabrina settings-gui
```

**Success:** window opens. Click the "Memory" tab. The tab displays
three section headers ("Semantic retrieval", "Compaction", "Test
retrieval"), each with its controls populated.

Walk the controls briefly:
- Semantic retrieval: `enabled` checkbox, top-K spinbox (shows `5`),
  max-distance slider (shows `0.5`), min-age-turns spinbox (shows
  `20`), stats line, `[Reindex now]` and `[Drop + rebuild]` buttons.
- Compaction: auto-at-startup checkbox, threshold-turns spinbox
  (shows `200`), min-turns-per-session spinbox (shows `10`),
  summarizer optionmenu (shows `Claude Haiku`), stats line,
  `[Compact now]` button.
- Test retrieval: query entry, `[Search]` button, empty results area.

**Failure signal:** crash on tab switch → a widget builder path is
broken on customtkinter for Windows. Capture the traceback from the
spawning shell.

---

## Step 4 — Manual reindex from GUI matches CLI

First, baseline via CLI:

```powershell
uv run sabrina memory-reindex
```

Capture the `Done. Wrote N embedding(s)` line.

Now in the GUI Memory tab, click `[Reindex now]`. A modal appears
streaming the subprocess stdout. Wait for `Done.` to appear.

**Success:** the count reported in the modal matches the CLI's count
exactly. Modal's final line reads `Done. Wrote N embedding(s).` with
the same `N`.

**Failure signal A:** modal hangs without output → line buffering
wrong on the Windows subprocess. Per plan: needs `stdout=subprocess.PIPE,
bufsize=1, text=True`. Verify and patch.
**Failure signal B:** counts differ → GUI is spawning the wrong
python executable or working directory. Check the modal's first line
which should show the exact argv.

---

## Step 5 — Seed DB with enough turns to trigger auto-compaction

The compaction threshold is 200 un-compacted turns by default. To test
auto-trigger without 100+ real voice sessions, seed fake turns.

```powershell
uv run python -c @"
from sabrina.memory.store import MemoryStore
from datetime import datetime, timezone, timedelta
import uuid
store = MemoryStore('data/sabrina.db')
for s in range(3):
    sid = str(uuid.uuid4())
    base = datetime.now(timezone.utc) - timedelta(days=10 + s)
    n_turns = [5, 80, 120][s]  # one short session, two long
    for t in range(n_turns):
        role = 'user' if t % 2 == 0 else 'assistant'
        ts = (base + timedelta(minutes=t)).isoformat()
        content = f'fake-turn-{s}-{t}: discussed topic X' if role == 'user' else f'reply about topic X variant {t}'
        store.append(role=role, content=content, session_id=sid, ts=ts)
print('seeded:', store.count_uncompacted(), 'uncompacted')
"@
```

**Success:** prints `seeded: 205 uncompacted` (5 + 80 + 120 turns,
minus the hot window of `min_age_turns=20` — actually
`205 - 20 = 185`, may or may not cross 200 depending on any prior
real turns in DB). If below 200, repeat with a fourth session. The
threshold number in the seed output is what matters.

**Failure signal:** crash → `store.append` signature mismatch (older
shape). The plan assumes the current `append(role, content,
session_id, ts)` signature.

---

## Step 6 — Dry-run compaction from CLI

```powershell
uv run sabrina memory-compact --dry-run
```

**Success:** prints something like:

```
Dry run. Would compact:
  session <uuid-1>: 80 turns (skipped: below threshold) — NO (5 turns)
  session <uuid-2>: 80 turns — YES
  session <uuid-3>: 120 turns — YES
Would write 2 summary row(s). Would mark 200 turn(s).
```

Short session (5 turns) skipped per `min_turns_per_session=10`. Two
sessions would summarize.

**Failure signal:** short session NOT skipped → `min_turns_per_session`
not threaded into the query. Capture the dry-run output.

---

## Step 7 — Real compaction from CLI

```powershell
uv run sabrina memory-compact
```

**Success:** output streams summarization progress:

```
Compacting 2 session(s) with Claude Haiku 4.5...
  session <uuid-2>: summarizing 80 turns... done (312 chars)
  session <uuid-3>: summarizing 120 turns... done (428 chars)
Wrote 2 summary row(s). Marked 200 turn(s).
```

```powershell
uv run sabrina memory-stats
```

**Success:** `summaries: 2`, `uncompacted: <previous - 200>`.

```powershell
uv run sabrina budget
```

**Success:** today's cost bumped by ~$0.02-0.05 (Haiku pricing on
~8K-10K input tokens across two summaries).

**Failure signals:**
- Haiku call errors → API key / model-string issue. Capture traceback.
- Summary written but originals not marked → the `UPDATE` query for
  `summarized_at` didn't fire. `sabrina memory-stats` would show
  `summaries: 2` but `uncompacted` unchanged.

---

## Step 8 — Summaries don't surface as retrieval hits

This is the contract test: summaries are NOT embedded, NOT searched.
Pick a phrase from one of the seeded turns ("topic X") and search.

```powershell
uv run sabrina memory-search "topic X"
```

**Success:** results are raw `kind='turn'` rows only. Every returned
row's content matches something you seeded in step 5 (e.g.
`fake-turn-1-37: discussed topic X`), **never** a multi-sentence
summary paragraph. Distances and ts are within the seeded range.

**Failure signal:** a result that reads like a compressed summary
("The user and assistant discussed topic X in a long session on ...")
means the `kind='turn'` filter in `search()` was skipped or the
summary got embedded accidentally. Capture the matching row's id and
inspect:

```powershell
uv run python -c "import sqlite3; c = sqlite3.connect('data/sabrina.db'); print(c.execute('SELECT id, kind, role, length(content), substr(content, 1, 80) FROM messages WHERE id = <ID>').fetchone())"
```

`kind` should be `summary` if it's a summary, and the `search()` query
should have filtered it out.

---

## Step 9 — Voice loop injects summaries into system prompt

```powershell
uv run sabrina voice
```

With `SABRINA_LOGGING__LEVEL=DEBUG`, ask any question. In the
structlog output for the brain call, the system prompt passed in
should include:

```
So far in our prior conversations:
- [2026-04-13] The user and assistant discussed topic X in ...
- [2026-04-14] The user and assistant continued about topic X ...
```

**Success:** the prefix text is present. The retrieved-memory block
(if any matched) is still passed separately as `system_suffix`.

**Failure signal:** text missing → `voice_loop.py` isn't calling
`store.load_summaries` at startup, or isn't appending to
`turn_system_stable`. Check log for `voice_loop.summaries_loaded count=2`.

---

## Step 10 — Auto-compaction at threshold

Confirm the threshold gate works: Ctrl+C out of voice, bump the
threshold low so it'll fire.

Edit `sabrina.toml`:

```toml
[memory.compaction]
auto_enabled = true
threshold_turns = 10
min_turns_per_session = 10
```

Seed a fresh un-compacted session (reuse the step 5 snippet with
different sid; ensure at least 15 new un-compacted turns).

```powershell
uv run sabrina voice
```

**Success:** within ~2 s of startup, structlog shows:

```
compaction.check uncompacted=<N> threshold=10
compaction.started turns=<N>
...
compaction.finished summaries=1 turns_compacted=<N>
```

Compaction runs in the background — `state.transition from=boot
to=idle` should NOT wait on it. First voice turn works normally during
compaction.

**Failure signal A:** voice loop blocks on startup waiting for
compaction → the `asyncio.create_task` wrapping got lost, compaction
is being awaited synchronously. First-audio latency on the first turn
will be many seconds. Capture timings.
**Failure signal B:** compaction exception knocks the voice loop
over → exception not caught per plan's "swallow exceptions, log
loudly" contract. Capture the traceback.

Revert `threshold_turns` to 200 and `auto_enabled` to your preferred
default after this.

---

## Step 11 — `auto_enabled = false` (manual-only mode)

Edit `sabrina.toml`:

```toml
[memory.compaction]
auto_enabled = false
threshold_turns = 10
```

Seed more un-compacted turns (reuse step 5's snippet).

```powershell
uv run sabrina voice
```

**Success:** no `compaction.started` line appears at startup, despite
`count_uncompacted >> threshold`. The auto-trigger is respecting the
`auto_enabled=false` switch.

`uv run sabrina memory-compact` still works manually (per step 7).

**Failure signal:** auto-compaction runs despite `auto_enabled=false`
→ the gate in `voice_loop.py` is wrong. File a decision.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | `user_version: 0` | Migration didn't run (no one opened MemoryStore since upgrade) | Run `sabrina voice` briefly, re-check |
| 0 | duplicate column error | PRAGMA guard regressed | Full error + `PRAGMA user_version` output |
| 3 | GUI crash on Memory tab | customtkinter widget path broken on Windows | Spawning-shell traceback |
| 4 | Reindex modal hangs | Line-buffering not set on subprocess PIPE | First line of modal showing argv |
| 4 | Counts differ between CLI + GUI | Wrong sys.executable or cwd in GUI spawn | Modal's argv line |
| 6 | Short session not skipped | `min_turns_per_session` not applied | Dry-run output |
| 7 | Originals not marked | UPDATE summarized_at didn't fire | `memory-stats` before/after + `PRAGMA compile_options` |
| 8 | Summary appears in search | `kind='turn'` filter missing or summary got embedded | Row inspection per query in step 8 |
| 9 | Summaries prefix missing | `load_summaries` not called at voice-loop startup | `voice_loop.summaries_loaded` DEBUG line (or absence) |
| 10 | Blocking startup | compaction awaited synchronously | First-audio timing on first turn |
| 10 | Exception kills voice loop | `_background_compact` not catching | Full traceback |
| 11 | Auto fires despite `auto_enabled=false` | Config gate missing | `compaction.check` log line |

---

## Known risks from the pre-validation code audit

1. **First compaction costs real Anthropic money (if summarizer =
   Claude Haiku).** Default per plan is Haiku — ~$0.02-0.05 for two
   sessions of ~100 turns each. If Eric is mid-month and approaching
   the budget ceiling from other work, temporarily flip `summarizer =
   "ollama"` for the validation. Free but slower.
2. **Summary content is model-generated and can hallucinate.** The
   validation intentionally uses fake seeded content with a
   recognizable phrase ("topic X") so the summaries are checkable
   against truth. In production on real conversations, the user's
   trust in summaries is a longer-term concern; surfaces via the
   "per-summary feedback" follow-up listed in the plan's "not in
   this plan" section.
3. **Seeding turns bypasses embedding generation.** Unless you also
   run `memory-reindex` after seeding, the fake rows are un-embedded
   and won't surface in step 8's search. That's fine for the summary-
   exclusion contract; it's tested on the `kind` filter alone.
4. **The `test retrieval` GUI sub-frame runs `sabrina memory-search`
   as a subprocess and parses its text output.** If the CLI's output
   format ever changes, the GUI parsing breaks silently (empty
   results area). No protocol between them. Flagged so future-Eric
   knows the coupling.
5. **`customtkinter`'s modal windows on Windows can fall behind the
   settings window.** If step 4's modal seems to hang, check Alt+Tab
   — it may just be hidden. Not a bug, a UX wart.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line:

```
007b semantic-memory GUI + compaction validated on Windows (i7-13700K
/4080, Python 3.12) <YYYY-MM-DD>: <S> summaries written over <T>
compacted turns, summaries excluded from semantic search, GUI sub-
frames functional, auto-threshold gate honored.
```

`<S>`, `<T>` from step 7.

Commit with message:
```
validate: 007b semantic-memory GUI + compaction on Windows
```

---

## If any step failed

1. Capture per the triage table.
2. The most likely follow-up decision is the GUI subprocess
   integration (step 4) — it's the fragile part. A decision doc
   would capture the proper stdout-streaming pattern for
   customtkinter on Windows.
3. For the summary-search leak (step 8), the fix is a one-line `WHERE
   kind = 'turn'` clause; footnote-on-007b rather than a new numbered
   decision.
