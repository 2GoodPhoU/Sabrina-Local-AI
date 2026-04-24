# Decision 007: Semantic memory (component 7) shipped

**Date:** 2026-04-23
**Status:** Shipped. Component 7 moves from 🟡 partial to ✅ on the roadmap.

## The one-liner

Sabrina now retrieves relevant older turns on every user message via
sqlite-vec + `all-MiniLM-L6-v2`, and injects the top-k results into
the system prompt as compact context lines. The text-only rolling
window still loads the last twenty turns; semantic search layers on
top of it rather than replacing it.

## What shipped

| Piece | Where | Notes |
|---|---|---|
| `Embedder` protocol + sentence-transformers wrapper | `memory/embed.py` | Lazy model load, warmup helper. 384-dim MiniLM-L6 is the default. |
| `vec_messages` vec0 virtual table | `memory/store.py` | Keyed by `message_id`, cosine distance via sqlite-vec `MATCH`. |
| Graceful degrade when sqlite-vec is unavailable | `MemoryStore._try_enable_vec` | Logs once, falls back to text-only. Voice loop keeps running. |
| `MemoryStore.search / backfill_embeddings / recent_ids` | `memory/store.py` | The retrieval surface. |
| `[memory.semantic]` config block | `config.py` + `sabrina.toml` | Off by default until the user opts in + runs reindex. |
| Voice-loop wiring | `voice_loop.py` | Embeds each user turn, pulls top-k hits, appends "Earlier..." block to that turn's system prompt. Embeds the reply back into the index. |
| CLI commands | `cli.py` | `memory-stats`, `memory-reindex [--drop]`, `memory-search "query"`. |
| Tests | `tests/test_smoke.py` | Append + search + backfill + exclude-ids + dim-mismatch + disabled-path. sqlite-vec tests gated behind `importorskip`. |

## Design calls

### Retrieved context goes into the system prompt, not the message history

The three options were (1) prepend to system, (2) splice into the message
list as fake turns, (3) expose as a tool call. (3) is blocked on tool-use
support in the `Brain` protocol (not wired up yet). (2) is tempting but
creates chronology-confusion — the retrieved turns are out of order with
the rolling window, and deduping against `load_recent` turns is fiddly.

(1) won. The retrieved block is a plain-English appendix to the base
system prompt: "Earlier in our conversations you might find relevant:
[date role] snippet". The model reads it as context, not dialogue.
Clean separation, no dedup gymnastics, zero risk of the brain thinking
old retrieved text is the current turn.

### sqlite-vec, one database

The roadmap called for sqlite-vec and that's what we built. Alternatives
considered and declined: a separate `.npy` cache (fine up to ~100K
messages but pulls a second file into the data contract), LanceDB (great
but a bigger dep than we need), plain numpy-in-memory (too slow past a
few thousand rows, and full-DB-scan on every turn is wasteful).

sqlite-vec keeps everything in one file, gets us K-NN in SQL, and —
critically — co-commits with the messages table on append so the
happy-path write is one transaction.

### `all-MiniLM-L6-v2`, 384 dims

Still the roadmap pick. ~80 MB, ~20 ms/sentence on CPU, sub-5 ms on
the RTX 4080. Good enough semantic quality for "remind me of when we
talked about X" retrieval. A few newer models (bge-small, gte-small,
Nomic embed) claim better MTEB scores; they're on the research list
but not worth the swap today.

### Graceful degrade

`MemoryStore._try_enable_vec` catches every failure mode
(`ImportError`, `AttributeError` from Python builds without
`enable_load_extension`, `OperationalError` from a missing extension
binary, and `Exception` as the backstop) and logs once. Result:
if sqlite-vec is broken on Eric's machine for any reason, the voice
loop still runs on text-only memory, `search()` raises a clear error,
and the CLI tells the user what to check.

This matters because the Python `sqlite3` module's
`enable_load_extension` is compiled out on some distributions. We
don't want that to brick Sabrina.

## What works well

- **The "Earlier..." block format is compact and human-readable.** One
  line per hit, date + role + 180-char snippet. The brain doesn't
  hallucinate that these are current turns, and it doesn't burn many
  tokens.
- **Backfill is a one-liner from the CLI.** `sabrina memory-reindex`
  progresses in batches of 32 and prints percentages; repeat-safe,
  `--drop` for model changes.
- **Warmup runs in the background.** The first user turn doesn't wait
  for the 1-2 second torch/ONNX model load — `asyncio.create_task`
  kicks it off at voice-loop startup and it's ready by the time the
  user finishes speaking.
- **The retrieval path is async-safe.** Every embed + search call
  goes through `asyncio.to_thread`, so the event loop keeps spinning
  (PTT stays responsive, state machine transitions don't block).
- **Guardrail #2 held.** No new abstraction — `Embedder` is a Protocol
  with exactly one implementation, and it's there because tests need
  a stub. `Brain` pattern, repeated.

## Thin spots

Honest list, because we're continuing to track what "could be better"
per-component.

### Embedding model
- **One model hardcoded.** The default is wired to 384 via
  `DEFAULT_DIM`. A different model requires either matching MiniLM's
  dim or the CLI path that eagerly-instantiates the embedder just to
  ask its dim. A small `KNOWN_MODEL_DIMS` lookup or an explicit
  `embedding_dim` config field would be cleaner.
- **sentence-transformers pulls torch (~700 MB).** Fine for the daily-
  driver use case, wasteful for a tiny utility library. An onnxruntime
  + tokenizers-only path would cut it to ~50 MB. On the research list.
- **No reranker.** For "exactly what did we talk about re X?" queries,
  a cross-encoder rerank over the top-20 candidates would sharpen
  precision. Optional; only worth doing if recall feels wrong.

### Index / storage
- **Dim is baked into the vec table.** Switching models requires
  `memory-reindex --drop` + re-embed. Not a correctness problem (we
  validate dim on insert and raise), but a UX papercut.
- **No summary compaction.** Listed as thin in decision 006 and still
  thin. At some point long conversations want a summarizer pass that
  rolls old turns into a summary row so context doesn't grow forever.
  Semantic retrieval *partially* substitutes for this (old turns are
  retrievable without being in the rolling window), but summaries would
  still help token budget.
- **No per-session scoping.** Search is global across every session
  Sabrina has ever had. Usually what we want, but there's no way to
  say "only retrieve from today's conversation" without a code change.
- **Assistant replies are indexed too.** Sometimes useful ("what did
  I say yesterday?") — sometimes noise ("the user's question is what
  matters"). Could be a config toggle.

### Voice-loop integration
- **Retrieval adds ~20-100 ms to first-audio latency.** The user turn
  has to be embedded before the brain call starts (we need the search
  results to build the system prompt). On the 4080 this is fine; on
  CPU-only hardware it'll be more noticeable.
- **No "no relevant match" feedback.** When `max_distance` filters all
  hits, we log it but don't tell the user. Usually correct — a quiet
  behavior is the right default — but for tuning the threshold from the
  GUI, surfacing "we had 5 candidates, all distance > 0.5" would help.
- **The reply is embedded synchronously before returning control.** We
  `await asyncio.to_thread(embedder.embed, reply)` after the brain is
  done. That blocks the loop for ~20ms per turn. Could fire-and-forget
  via `asyncio.create_task`, but then a rapid Ctrl+C might drop the
  embed. Deferred until it's measurably a problem.

### CLI / admin
- **No eviction / retention policy.** Old embeddings stay forever.
  Fine for Eric's single-user scale; would need per-session retention
  for anyone else.
- **`memory-search` doesn't show session context.** Results are single
  turns out of context; sometimes the meaning lives in the prior turn.
  A `--with-neighbors` flag could surface ±1 turn.

## Alternatives worth researching

1. **Reranker (cross-encoder)** for retrieved results — e.g. `bge-reranker-v2-m3`.
   Only if precision feels thin on real queries.
2. **Leaner embedder** — onnxruntime + tokenizers + a MiniLM ONNX, or
   the FastEmbed library. Kills the torch dep. Meaningful for "Sabrina
   on a thin-client laptop" scenarios.
3. **Summary compaction loop** — every N turns, summarize the oldest M
   and store as a `role=system` row with its own embedding. Keeps the
   text-only rolling window useful over very long histories.
4. **Per-session filter + time decay** — boost recency so a semantically
   similar turn from last week ranks above one from last year when both
   match. Optional.
5. **`Message.metadata`** — add a tuple-of-strings metadata slot to
   `Message` so retrieved turns can carry "retrieved" markers, dates,
   or source-session info. Additive extension like `Message.images`.

## Settings GUI

Not done this session — flagged for 007b. The existing Memory tab has
`enabled` and `load_recent` checkboxes; we'd add a sub-frame for
`[memory.semantic]` (enabled, model, top_k, max_distance, min_age_turns)
and a "Reindex now" button that shells out to `sabrina memory-reindex`
with a progress bar. ~30 min of customtkinter.

## Ship criterion check

Decision 006's "daily-driver gap" list:

- [ ] Wake word / global PTT — unchanged.
- [ ] Auto-start on login — unchanged.
- [ ] Crash recovery supervisor — unchanged.
- [ ] Barge-in — unchanged.
- [ ] Budget observability — unchanged.
- [x] *(bonus)* Sabrina remembers you — ✅ shipped this session.

Four of the real gap items remain. Memory going from 🟡 → ✅ isn't one
of them, but it's the roadmap's component 7 finished; nine components,
eight shipped, one deferred (avatar), one deferred-harder (automation).

## Where the new code lives

```
sabrina-2/src/sabrina/memory/
├── __init__.py        # exports Embedder, MemoryStore, SearchHit, ...
├── embed.py           # NEW: SentenceTransformerEmbedder + protocol
└── store.py           # extended: vec0 table, search(), backfill_embeddings()
sabrina-2/src/sabrina/
├── cli.py             # +memory-stats, memory-reindex, memory-search
├── config.py          # +SemanticMemoryConfig nested under MemoryConfig
└── voice_loop.py      # +embedder, +retrieval, +reply embedding
sabrina-2/
├── pyproject.toml     # +sentence-transformers, +sqlite-vec
├── sabrina.toml       # +[memory.semantic] block with comments
└── tests/test_smoke.py # +9 tests for embed/search/backfill/config/voice-loop format
```

## One thing to feel good about

Sabrina can now actually *remember* Eric — not just reload the last
twenty turns, but pull in "that conversation we had three weeks ago
about the 4080 build" when it matters. The diff is under 500 lines of
real code. `Brain` stayed untouched. `Message` stayed untouched. The
voice loop grew by about fifty lines for the retrieval path and the
async embedding writes. Everything degrades gracefully if sqlite-vec
isn't available. Guardrails still holding.

## Next session, pick one (updated menu)

1. **Barge-in (Silero VAD + cancellable TTS)** — closes the biggest
   daily-driver gap. Prerequisite: cancel-token in the Brain protocol.
2. **Wake word (openWakeWord)** — frees hands from PTT.
3. **Local VLM fallback** — privacy + offline vision.
4. **Budget tracker + prompt caching** — small lift, immediate cost
   reduction.
5. **Summary compaction + semantic-memory GUI (007b)** — the natural
   follow-ups to this session.
