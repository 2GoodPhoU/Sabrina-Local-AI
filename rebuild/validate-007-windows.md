# Decision 007 — Windows validation procedure

**Purpose:** confirm semantic memory (component 7) works end-to-end on Eric's
Windows box before we call decision 007 validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from `sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.

All commands are copy-pasteable. Each step lists the success signal. The
"If step N fails" section at the bottom maps failure symptoms to likely
causes so you can report back without a second round-trip.

---

## Step 0 — Sanity-check `enable_load_extension` on your Python

Most likely failure mode for this whole feature is a Python build where
`sqlite3.enable_load_extension` is compiled out. Python.org's recent 3.12
Windows installer has it; older installs and some Microsoft-Store Pythons
don't. sqlite-vec rides on it.

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.enable_load_extension(True); print('ok')"
```

**Success:** prints `ok`.
**Failure signal:** `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'`.
**Fix:** switch to uv's managed Python (compiled with extension loading on):

```powershell
uv python install 3.12
uv sync --python 3.12
```

Re-run step 0. If it passes, continue. If not, file decision 008 (draft
already stubbed at `rebuild/drafts/008-sqlite-vec-on-windows.md`) and stop.

---

## Step 1 — `uv sync`

```powershell
uv sync
```

**Success:** finishes without errors. Pulls `sentence-transformers`,
`sqlite-vec`, and torch (~700 MB — first sync is slow). `uv.lock` mtime
bumps (it was last 2026-04-22 23:46 before this session's pyproject
change).
**Failure signal:** resolver errors, wheel-not-found for Windows.
**Fix:** capture the full resolver error; see "If step 1 fails" below.

---

## Step 2 — `uv run pytest -q`

```powershell
uv run pytest -q
```

**Success:** **70+ passed, 0 skipped** in the sqlite-vec block, wall time
under ~5 s. Specifically, these tests must run (not skip) and pass:

- `test_semantic_memory_append_and_search`
- `test_semantic_memory_search_excludes_ids`
- `test_semantic_memory_backfill`
- `test_semantic_memory_dim_mismatch_raises`

Also these two must pass (they test the graceful-degrade branch, so they
pass whether or not sqlite-vec loaded):

- `test_semantic_memory_search_disabled_raises`
- `test_memory_store_append_without_semantic_still_works`

**Failure signal A — skips instead of passes** on the four `_require_sqlite_vec()`
tests. `pytest -q` output would include something like
`5 passed, 4 skipped`. That means `sqlite_vec.load(conn)` failed at
collection time and the tests punted — which means semantic memory will
silently degrade at runtime too. Treat as a failure.

**Failure signal B — real assertion failures.** Capture the full traceback.

---

## Step 3 — Turn semantic memory on

Edit `sabrina-2/sabrina.toml`, change the one line:

```toml
[memory.semantic]
enabled = true
```

Leave everything else (`top_k=5`, `max_distance=0.5`, `min_age_turns=20`)
at defaults. No env var needed.

**Success:** the line now reads `enabled = true`. `sabrina config-show`
will confirm on step 4.

---

## Step 4 — `uv run sabrina memory-stats`

```powershell
uv run sabrina memory-stats
```

**Success:** output includes `vec dim: 384` (not the "disabled" fallback).
Example:

```
Memory at .../sabrina-2/data/sabrina.db
  messages:    N
  embeddings:  0  (0% of messages)
  vec dim:     384
```

`N` should be the count of messages accumulated before 007 shipped — non-zero.
`embeddings: 0` is expected: nothing has been backfilled yet.

**Failure signal:** output says `vec table: disabled (sqlite-vec unavailable or config off)`.
Means `MemoryStore._try_enable_vec` fired the degrade path. Capture the
warning line from the structlog output (search for `memory.vec_unavailable`
— it carries the actual exception). This is the scenario where decision
008 ships.

---

## Step 5 — `uv run sabrina memory-reindex`

```powershell
uv run sabrina memory-reindex
```

**Success:** output like

```
Loading embedder: sentence-transformers/all-MiniLM-L6-v2 ...
  dim=384
Embedding N message(s) in batches of 32...
  [32/N] ...%
  ...
Done. Wrote N embedding(s).
```

First run also downloads the MiniLM weights (~80 MB) into the HF cache
(`~/.cache/huggingface/hub/` — on Windows this is `%USERPROFILE%\.cache\huggingface\hub`).
`data/sabrina.db` mtime bumps after this (last was 2026-04-22 23:03).

**Failure signals:**
- `sqlite-vec is not available` → shouldn't happen if steps 0/4 passed; otherwise the degrade path fired late.
- HuggingFace download hang / cert error → corporate network / no internet. Capture the stack.
- `ImportError: sentence_transformers` → `uv sync` didn't install it; re-run step 1.

---

## Step 6 — `uv run sabrina memory-search "<real past topic>"`

Pick a topic you actually discussed. Good candidates based on the decision
log: `"brain router"`, `"4080 build"`, `"piper voice choice"`,
`"vision hotkey"`.

```powershell
uv run sabrina memory-search "brain router"
```

**Success:** at least a few hits with distances in a plausible range.

```
  d=0.312  [2026-04-20 14:22]        user  ...
  d=0.378  [2026-04-22 09:03]   assistant  ...
```

Distances ≤ ~0.4 on a clearly-matching query = retrieval is healthy.

**Failure signals:**
- `(no matches)` on a topic you know is in the DB → threshold too tight, or the embeddings were written at a different dim. Try `--max-distance 1.5` to confirm embeddings exist but are being filtered; if that's also empty, there's a dim or index problem.
- All distances near 1.0 across unrelated results → embedding model didn't actually load; could be a dim mismatch between `_vec_schema` and the real model output (would have been logged as `embed.dim_mismatch` during step 5).

---

## Step 7 — One real voice-loop session

```powershell
uv run sabrina voice
```

Hold right-Shift, ask something that should hook something older — e.g.
*"what did we decide about the brain router?"* — release the key.

**Two things to watch for in the terminal output:**

### 7a. The "Earlier in our conversations..." block fires

As the turn is processed you should see a line like:

```
(memory: 3 earlier turn(s) attached)
```

That's the dim console hint from `voice_loop.py` after the retrieved
block is appended to the system prompt. If `SABRINA_LOGGING__LEVEL=DEBUG`
is set in `.env`, the structlog output will also show
`semantic.hits count=3 top_distance=0.3xx`.

**If you don't see either:** the retrieval path didn't engage. Likely
causes are in "If step 7 fails" below.

### 7b. First-audio latency

Baseline before 007 was ~1.85 s. Decision 007's budget: +20–100 ms for
the embed+search. Warm budget ≤ ~2.0 s. Cold-start (first turn after
launch, before warmup finishes) ≤ ~3.5 s.

Measure by ear or by the structlog timings. Report back the warm-turn
first-audio latency — that's the number that goes in the ROADMAP bump.

**Bonus smoke:** ask a second question that's semantically close to the
first. Confirm the reply treats retrieved context as *context*, not as
*dialogue* (the brain shouldn't say "as I said earlier..." about a retrieved
turn). This catches regressions where the brain ingests the "Earlier..."
block as a prior turn.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | `AttributeError` on `enable_load_extension` | Python built without SQLite extension support (common on Microsoft-Store Python, some older python.org installers) | Output of `uv run python -c "import sys; print(sys.version); print(sys.executable)"` |
| 1 | `sqlite-vec` wheel not found | sqlite-vec < 0.1.6 has patchy Windows wheels. pyproject pins `>=0.1.6` but a stale resolver cache could miss it. | Full `uv sync` output, plus `uv pip list \| findstr sqlite` |
| 2 | 4 tests skipped instead of passing | sqlite-vec package imports but `sqlite_vec.load(conn)` fails — DLL/binary can't be loaded by this Python | The skip reason (pytest prints it with `-rs`), e.g. `uv run pytest -q -rs` |
| 2 | Real test failure | Regression in store.py or voice_loop.py | Full traceback |
| 4 | `vec table: disabled` | `_try_enable_vec` caught an exception at store construction | The `memory.vec_unavailable` warning line from structlog (`SABRINA_LOGGING__LEVEL=DEBUG`) |
| 5 | Download hang / cert error | Offline or corp-proxy intercept on HuggingFace CDN | `$env:HF_HUB_OFFLINE`, `$env:HTTPS_PROXY` if any, full stack |
| 5 | `dim mismatch` warning in logs | Changed model string without `--drop` | Output of `uv run sabrina memory-reindex --drop` |
| 6 | `(no matches)` on an obvious topic | `max_distance` too tight, or zero embeddings got written | Re-run with `--max-distance 1.5`; if still empty, paste the `memory-stats` output |
| 6 | Uniform ~1.0 distances | Embedder loaded the wrong model / wrong dim | Structlog `embed.dim_mismatch` line + output of `uv run sabrina memory-stats` |
| 7 | No "earlier turns attached" message | `semantic_enabled` guard tripped; see `voice_loop.py:117-123`. Usually `memory.vec_enabled=False` or `settings.memory.semantic.enabled=False`. | Output of `uv run sabrina config-show \| findstr /i semantic` and `memory-stats` |
| 7 | Brain treats retrieved turns as dialogue | `_format_retrieved` header wasn't picked up as context — unlikely but possible if the system prompt got truncated. | Capture the brain's reply verbatim. |

---

## Known risks from the pre-validation code audit

These didn't block shipping but are worth knowing before the run:

1. **First-run HF download is online-only.** Step 5 needs internet. If your
   machine is offline, pre-populate `%USERPROFILE%\.cache\huggingface\hub`
   or step 5 will hang.
2. **Warmup races the first turn.** If you hit PTT within ~1 s of `sabrina voice`
   starting, the first user turn pays the model load inline (1–2 s on top of
   first-audio). Warmup is non-blocking; nothing is broken, but the first
   latency reading won't be representative. Throw away the first turn when
   measuring 7b.
3. **`recent_ids(min_age_turns)` excludes the last 20 turns from retrieval.**
   If your DB has fewer than ~25 total messages, search will usually return
   empty — not a bug, just min_age_turns doing its job. Use `memory-search`
   with the real DB size to confirm.
4. **Dim is keyed off the model *string*.** `_open_memory` in `cli.py`
   short-circuits the dim lookup when the config's `embedding_model` equals
   `DEFAULT_MODEL` exactly. Any deviation (extra whitespace, different prefix)
   falls through to eager embedder construction, which is slow but correct.
   Leaving the default model string alone avoids this.

---

## If all green — the ROADMAP bump

**Do not file a decision doc.** Anti-sprawl: validation of an already-shipped
component doesn't need its own numbered entry. Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line at top to today's date.
2. Append one line at the end of the "Status:" paragraph:

```
Validated on Windows (i7-13700K/4080, Python 3.12) 2026-04-23: sqlite-vec loaded, <N> embeddings backfilled, first-audio <X> s warm.
```

Replace `<N>` with the final count from step 5's "Done. Wrote N embedding(s)"
line, and `<X>` with the warm first-audio latency from step 7b.

Commit with message:
```
validate: decision 007 semantic memory on Windows (N embeddings, Xs warm)
```

Then we move on to barge-in (draft plan at
`rebuild/drafts/barge-in-plan.md` — needs sign-off before I start coding).

---

## If any step failed

1. Capture the output per the triage table above.
2. If the failure matches the sqlite-vec pattern (step 0 or step 4), file
   `rebuild/drafts/008-sqlite-vec-on-windows.md` → `rebuild/decisions/008-sqlite-vec-on-windows.md`
   after filling in the observed error. The draft already lays out the fix
   (uv-managed Python).
3. For anything else, report back with the captured output; we'll write a
   fresh decision 008 that matches the actual failure.
