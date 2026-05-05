# Memory architecture beyond semantic retrieval — what comes next

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Where Sabrina's memory wants to go after `compaction.py`
just shipped. Episodic, importance, multi-tier decay, procedural,
identity, forgetting curves — what's earned its place in 2026 and
what's still hype. Implementation tier proposal grounded in the
existing sqlite-vec + MiniLM + compaction stack, not a green-field
rewrite.

**Anchor:** [decision 007](../../decisions/007-semantic-memory-shipped.md)
shipped sqlite-vec + `all-MiniLM-L6-v2` retrieval; the
just-landed `memory/compaction.py` (still uncommitted per
`ACTION_ITEMS.md`) folds old turns into single summary rows. That's
two of the four pillars in the 2026 agent-memory state of the art.
This doc maps the other two and proposes which of them earn a v1.

**Audience:** Eric, Sunday morning.

---

## Where we are today

Two layers, both real:

1. **Rolling text window.** Last N turns loaded verbatim into
   each call. Fast, dumb, works.
2. **Semantic retrieval.** Per-turn embed the user message,
   K-NN against a sqlite-vec index of every prior message,
   inject the top-k as an "Earlier in our conversations…" block
   in the system prompt. Decision 007.

And one in-flight:

3. **Compaction.** When the un-compacted turn body exceeds a
   token threshold, fold the oldest batch into a single
   `kind='summary'` row (excluded from semantic search, prepended
   to the system prompt). This is the v1 of "long histories
   shouldn't grow unbounded" — the simplest thing that could
   work, ship-and-validate.

Conspicuously *not* present, none of which the rebuild needs *yet*:

- Memory of *events* as scenes (episodic memory in the strict
  sense). Today every turn is a chunk; nothing names a coherent
  conversation as a unit.
- Importance-weighted retrieval. Hits are scored on cosine
  distance only; recency and importance don't enter.
- Multi-tier decay. There is one summarization tier; old
  summaries themselves never get re-compacted.
- Procedural memory. Sabrina remembers *that* you discussed a
  way to do X; she doesn't remember *how* you taught her to do
  X.
- Identity memory. There is no "who is Eric" entity row that
  evolves over months; a profile fact emerges only by happening
  to be in a recent enough turn or a recent enough summary.
- Explicit forgetting. Nothing ever leaves; the index just
  grows.

The 2026 agent-memory ecosystem (Mem0, Letta, Zep, A-Mem) has
flavors of all six. Below: which are worth the ramp, in what
order.

---

## Episodic memory — events, not chunks

The current store treats memory as a flat sequence of text
messages. Episodic memory in the human sense is *events* —
something happened at a place/time with participants, retrievable
as a scene. The 2026 line on this is sharper than it was a year
ago: episodic is "the missing piece for long-term LLM agents"
[1], episodic memory in agents specifically means "memory of
particular past events which one participated in personally" —
not facts, not chunks, scenes [4].

The concrete shape, in literature: a memory record is a *struct*
not a string — `{"when": ts, "where": surface_or_app,
"who": [participants], "what": short_description, "raw_refs":
[message_ids]}` — and retrieval works on the struct, not on
embeddings of the raw text. WorldMM's three-mode design
(episodic + semantic + visual) gets a measurable accuracy lift
over a vector-only baseline by exactly this distinction [5].
Video-EM's event-centric framing makes the same argument for
long-form video: "encode each event as a grounded episodic
memory with explicit temporal indices" [6].

**For Sabrina specifically.** "Where" is mostly trivial (the
surface is the voice loop, occasionally the GUI), so the value
comes from "when" and "what." A single voice-loop session is
already a natural episode boundary — it starts, runs ~15 min to
a few hours, ends. The `compaction.py` summary row already
captures the "what" of older episodes; what's missing is making
the episode an addressable unit. Adding `episode_id` to messages
+ a `episodes` table with `started_at`, `ended_at`,
`title_summary`, `n_turns`, `participants` (Register A/B/C from
the personality plan) is roughly 30 lines of SQL + one helper.
Retrieval then becomes "find the episode" → "fetch the relevant
turns within it," instead of "find a turn floating in
nothing." Closer to how a person actually recalls a conversation.

Cost: small, additive. Doesn't replace semantic search; layers
under it.

---

## Importance tagging

Today every message gets an embedding and lives forever in the
index. Importance tagging is the move that makes the index pay
attention to what the agent actually cares about.

**The Park et al. canonical formula** [2]:

```
score = α·recency + β·importance + γ·relevance
```

Each surfaced as its own number, tunable. Importance comes from
asking the LLM "rate the poignancy of this memory on 1-10";
recency is exponential decay over hours; relevance is the cosine
similarity already computed. Generative-agents' breakup-vs-
breakfast example [2] is still the cleanest argument: cosine
distance can't distinguish them, but human perception does.

**Where 2026 ended up.** Mem0 leans on LLM-extracted importance
implicitly via fact extraction; Zep encodes it through edge
"validity" + frequency in the temporal knowledge graph [11].
The recurring lesson across all of them is that *importance is
not free*: every importance tag costs an LLM call, and naïvely
calling the brain on every turn doubles the latency. The
production pattern is **batched, asynchronous, and cheap** —
either run a small local model on a background thread or batch
several turns at end-of-session.

**For Sabrina specifically.** Three knobs that earn their
keep:

1. *Heuristic floor:* turns where the user said "remember…",
   "important:", or used Eric's existing wake-marker idiom,
   plus turns the brain marked with a `<remember/>` cue (cue
   track is already an LLM-side annotation channel — extending
   to a `<remember/>` tag is one line in the persona block).
2. *LLM-rated:* end-of-session, batch-rate the session's
   turns 1-5 via the same Ollama brain that does compaction.
   Cheap (qwen2.5:7b at ~60 tok/s; a 30-turn session is sub-30s
   of background work).
3. *Behavioral:* a turn the user re-referenced ("you mentioned
   that earlier") gets +1 importance automatically; mining the
   semantic-retrieval logs for hits that were actually used is
   ~free.

Importance becomes an integer column on `messages`. Retrieval
adds a weighted term. Done in the same shape as Park et al. with
nothing exotic.

---

## Summarization decay — multi-tier, not single-tier

The shipped compaction is one tier: turns → summary. The next
tier is *compacted summaries → super-summary* — daily roll-up,
weekly roll-up, archetypal-pattern roll-up. The literature
converges on this from multiple angles:

- The Recursively Summarizing paper [12] shows recursive
  summary is a strict win over keep-last-N for long-dialogue
  memory; the gain holds at every depth they tested.
- The 2026 production survey [9] lists "hierarchical
  summarization" as a standard pattern: immediate working
  memory → episodic → semantic, each at a different time
  scale.
- Microsoft's compaction guidance [13], Google ADK's [14], and
  the Codex/Claude Code/OpenCode round-up [15] all converge on
  *layered* compaction — tool-result trim first, summary
  second, archive third — rather than one big "compact
  everything" knob.

**For Sabrina specifically.** The natural tiers, given a
single-user voice assistant:

| Tier | What | Trigger | Lives |
|---|---|---|---|
| L0 — raw turns | Verbatim messages | Every turn | Until L1 compaction |
| L1 — session summaries | One row per session | End-of-session OR token threshold | Indefinite (today) |
| L2 — daily reflection | One row per active day | End-of-day cron or first-open-after-midnight | Indefinite |
| L3 — weekly arc | One row per active week | End-of-week | Indefinite |
| L4 — themes / archetypes | Cross-session patterns ("Eric and the audio refactor") | Manual or threshold | Indefinite |

L0 and L1 exist already. L2 is the obvious next step — and is
where the Park-et-al. "reflection" mechanic lands [2]. L3 and L4
are speculative; they earn their place if and only if L2 turns
out to lose detail too fast on its own.

Decay is then per-tier, not per-row: L0 gets pruned aggressively
(deleted after L1 compacts), L1 hangs around but is cheap,
L2/L3/L4 are very small and rarely written. Disk grows
sub-linearly with conversation time, not linearly.

---

## Procedural memory — how vs. what

The current memory remembers *that* Eric said "the wake word
mishears my name as cypress" but not *that he taught Sabrina the
fix*. Procedural memory in the agent-architecture sense [7][8]
is the persistent home for skills and patterns — "when X
happens, do Y," "the way Eric likes commit messages framed."
Voyager's executable-skill library is the canonical demo [16];
LangMem's "procedural memory store" [10] and Letta's
self-editing core memory [3] are the production analogs.

**For Sabrina specifically.** The honest read is that procedural
memory pays off *after* tool use ships, not before. Today the
brain has nothing to "do" — it speaks. Once `tool-use-plan.md`
lands and Sabrina can call get_time / read_clipboard /
search_memory, "Eric prefers I check the clipboard before asking
him to paste" becomes a procedural fact worth saving. Without
tools, procedural memory degenerates into "preferences," which
identity memory (next section) covers more cleanly.

**Recommendation:** flag for the post-tool-use revisit.

---

## Identity memory — a slowly-evolving "who is Eric"

The personality plan locks Sabrina's voice; the inverse — a
durable model of *Eric* — is not a separate project, just the
other half of the same one. Today, "Eric is the user" is implicit
in every system prompt and explicit nowhere; "Eric works on
Sabrina" emerges from retrieval; "Eric's wife's name" would have
to be re-discovered every time it became relevant.

**Where 2026 sits.** Mem0 builds a hierarchical user/session/agent
memory that is exactly this — long-lived knowledge tied to a
person, account, or workspace [17]. The October-2025 paper on
persistent personalized interactions [18] makes user-profile
memory a separate subsystem from conversational recall, on the
explicit grounds that "stable preferences, verified profile
facts, and long-lived project context" decay differently from
conversational chunks. Zep encodes the same idea via entity
nodes in its temporal graph [11].

**For Sabrina specifically.** Tiny scope: one row per
"entity," updated by an end-of-session reflection step. Eric is
the entity that always exists; a row appears for any other named
person Sabrina hears about more than once. The row is a short
JSON blob: `{"name": "...", "facts": ["...", ...],
"last_updated": ts, "evidence": [message_ids]}`. The LLM
*writes* it, not Sabrina-the-coder; whenever the brain notices a
durable fact ("Eric uses an i7-13700K + 4080") it appends to the
row.

Loaded into the system prompt's persona block as a "What Sabrina
knows about Eric" subsection, ~150-300 tokens, capped. This is
the highest-leverage missing primitive — every other memory
improvement compounds with a clean profile.

---

## Forgetting curves — when does Sabrina actually drop knowledge?

The Ebbinghaus-curve writeups [19] are everywhere in 2026 and
mostly miss the point. The Sabrina question isn't "should
embeddings decay" (no — they're cheap) but "should *content* be
hard-deleted, ever." Three takes worth holding:

1. **Hard delete is rare and explicit.** A user-driven "forget
   X" command is the only safe path; entropic deletion erodes
   the assistant's reliability in ways the user can't recover.
   Letta and Mem0 both default to *no* automatic hard delete
   [3][17].
2. **Soft deprioritize is cheap and good.** A memory's recency
   weight in the score formula is a continuous knob; old turns
   stop surfacing in retrieval without ever being deleted.
   This is what Park et al. and downstream Mem0/Zep effectively
   do [2][11][17].
3. **Tier-based eviction is the win.** L0 → L1 compaction
   *is* a forgetting mechanism: the verbatim turns go away,
   the summary stays. Multi-tier decay (above) generalizes
   this. No separate "forgetting subsystem" needed.

**For Sabrina specifically.** Plumb a `sabrina memory-forget
"<pattern>"` CLI verb that hard-deletes matching rows
(everything: messages, embeddings, summaries that mention them,
the entity row's evidence). Beyond that, decay is implicit in
tiering and importance scoring. No Ebbinghaus curve fitting,
no global half-life parameter. The literature loves them; in
practice they're a tunable that's hard to validate and easy to
get wrong.

---

## 2026 state of the art — fast survey

| System | Core idea | Verdict for Sabrina |
|---|---|---|
| **MemGPT / Letta** [3] | OS-style hierarchical memory: core (RAM) / recall (disk) / archival (cold). Self-editing core memory via tool calls. | Architectural inspiration. The hierarchy maps cleanly onto tiered summarization. The self-edit pattern is interesting *post-tool-use*. |
| **Mem0 / Mem0g** [17][20] | Hierarchical user/session/agent memory; fact extraction + key-value + vector + graph hybrid. LongMemEval ~66-68%. | Closest analog to where Sabrina is heading. Worth reading the data model; not worth importing the package. |
| **Zep / Graphiti** [11] | Temporal knowledge graph with `valid_from`/`valid_to` per fact. LongMemEval 63.8% on GPT-4o; best for temporal queries. | Powerful but operationally heavy. The fact-validity-window concept earns its place in Sabrina's identity-memory layer; the rest is overkill. |
| **A-Mem** [21] | Zettelkasten-style: notes with keywords + tags + auto-linking, evolving over time. NeurIPS 2025. | Promising but research-grade. The "auto-link related notes" idea is worth watching once Sabrina has enough notes to link. |
| **LangMem** [10] | LangChain's memory abstraction; explicit semantic / episodic / procedural stores. | Useful taxonomy. The implementation is heavier than Sabrina needs; the *naming convention* is worth adopting. |
| **AgentCore long-term memory** [22] | AWS-hosted memory service; semantic / summary / user-preference tiers. | Reference architecture. Not adoptable; cloud-only. |
| **Generative agents (Park et al.)** [2] | recency × importance × relevance + reflection. 2023 but still load-bearing. | The retrieval-scoring formula is the floor Sabrina should be at. |

The benchmark situation is messier than the writeups admit:
LongMemEval scores are sensitive to evaluation setup (Zep
originally claimed 84%; Mem0 measured 58%; Zep counter-claimed
75%) [20]. None of these are the kind of repeatable benchmark
that should drive an architecture decision for a single-user
assistant. Treat them as directional, not authoritative.

The **proven** primitives across 2026, ranked by how often they
show up:

1. **Score = α·recency + β·importance + γ·relevance.** Universal.
2. **Multi-tier summary hierarchy.** Universal.
3. **User profile / entity memory as a separate store.** Almost
   universal.
4. **LLM self-edits / reflection batches.** Common.
5. **Temporal knowledge graphs.** Used; powerful; heavy.
6. **Zettelkasten auto-linking, importance vectors, biological
   forgetting curves.** Research-tier; not yet table stakes.

---

## Implementation tier proposal — what to build, in order

Layered on what's shipped, anti-sprawl-respecting.

**Tier 1 (next ship after compaction validates).**

- **Importance column on `messages`,** populated by the
  heuristic-floor rules (cue tags, "remember…" idiom,
  re-references). One LLM-rated batch at end-of-session is
  optional; ship the heuristic first.
- **Park-style retrieval scoring** in `MemoryStore.search`:
  the existing cosine becomes the `relevance` term; add
  recency (exp decay) and importance. Three config knobs for
  the weights, defaults α=0.3, β=0.2, γ=0.5.

Estimate: ~80-120 LOC, no new tables, no new dependencies.

**Tier 2 (after Tier 1 validates).**

- **Episodic boundaries:** `episode_id` on `messages` +
  `episodes` table with `started_at`, `ended_at`,
  `title_summary`, `n_turns`, `register` (A/B/C). Episode
  closes when a session ends or when there's a >30 min gap.
- **L2 compaction:** one summary row per active day, written
  on first-open-after-midnight (Sabrina is already running;
  no cron needed). Compaction prompt the same module-constant
  shape as the existing one.

Estimate: ~150-200 LOC, two tables, one async background
task. Reuses the compaction summarizer protocol.

**Tier 3 (the high-leverage one).**

- **Identity memory:** `entities` table, `eric` always
  present, others appear when named twice. Filled by
  end-of-session reflection step (LLM emits structured JSON;
  store appends to the row). Loaded into the persona block of
  the system prompt as a capped "What Sabrina knows about
  Eric" subsection.

Estimate: ~150-200 LOC + one prompt + persona-block edit.
Highest qualitative impact per line of code.

**Tier 4 (probably-defer).**

- **L3 / L4 summaries.** Build only if dogfood shows L2 alone
  loses detail too fast.
- **Procedural memory.** Build *after* tool-use ships.
- **Temporal knowledge graph (Graphiti-style) for entities.**
  Build *if* identity memory's flat row stops scaling — which
  it won't for a single user at conversational scale.

**Tier 5 (probably-don't-build).**

- Ebbinghaus-curve-fit decay. The tiering already does this.
- Auto-linked Zettelkasten note graph (A-Mem). Cool, research-
  grade, no clear win for one user.
- A separate "memory agent" sub-process. Sabrina is one
  process; memory is a module, not a service.

---

## Decisions Eric needs to lock

1. **Adopt the Park scoring formula in v1. (Recommended.)**
   Replacing pure cosine with `α·recency + β·importance +
   γ·relevance` is the single highest-ROI change available
   right now. Three tunables, all in `[memory.semantic]`.
   *Override:* keep cosine-only and revisit after first
   dogfood drift.

2. **Importance via heuristic floor first, LLM rating only if
   the heuristic underperforms. (Recommended.)** Two
   bias-toward-shipping arguments: it's free, and the worst
   case (importance = 0 for all) reduces the formula to recency
   + relevance, which is still better than today. *Override:*
   batch-rate every session via Ollama from day one; costs
   ~30s of background CPU per session.

3. **Identity memory before episodic. (Recommended.)** The
   user-profile entity row is the highest qualitative impact
   per line of code; episode boundaries are nice but the
   summary tier already handles "what was talked about last
   Tuesday" reasonably. *Override:* ship episodes first if
   the dogfood reveals "I keep losing where in the
   conversation we were."

4. **Stay with sqlite-vec + MiniLM-L6. Don't migrate to Mem0 /
   Letta / Zep. (Recommended.)** The 2026 ecosystem is
   maturing but not converged; importing one of those would
   trade understandability for benchmarks Sabrina won't run
   anyway. *Override:* if the planned ONNX-embedder swap
   ([survey](2026-04-25-stack-alternatives-survey.md) §6)
   uncovers a cleaner store while it's open.

5. **No automatic hard-delete; expose a `memory-forget`
   command. (Recommended.)** Decay is implicit in tiering; the
   only deletes that should ever happen are user-driven.
   *Override:* none worth taking until a privacy issue forces
   it.

---

## Sources

[1] Bell et al. — [Position: Episodic Memory is the Missing Piece for Long-Term LLM Agents](https://arxiv.org/pdf/2502.06975).
[2] Park et al. — [Generative Agents: Interactive Simulacra of Human Behavior (memory stream / recency·importance·relevance)](https://dl.acm.org/doi/10.1145/3586183.3606763).
[3] Letta Docs — [MemGPT concepts (core / recall / archival)](https://docs.letta.com/concepts/memgpt/).
[4] atlan — [Episodic Memory for AI Agents: How It Works](https://atlan.com/know/episodic-memory-ai-agents/).
[5] WorldMM — [Dynamic Multimodal Memory Agent for Long Video Reasoning](https://arxiv.org/html/2512.02425).
[6] Video-EM — [Event-Centric Episodic Memory for Long-Form Video Understanding](https://arxiv.org/pdf/2508.09486).
[7] Towards Data Science — [A Practical Guide to Memory for Autonomous LLM Agents](https://towardsdatascience.com/a-practical-guide-to-memory-for-autonomous-llm-agents/).
[8] Phil Schmid — [Memory in Agents, Make LLMs remember.](https://www.philschmid.de/memory-in-agents).
[9] AnalyticsVidhya 2026 — [Architecture and Orchestration of Memory Systems in AI Agents](https://www.analyticsvidhya.com/blog/2026/04/memory-systems-in-ai-agents/).
[10] LangChain — [LangMem: Long-term Memory in LLM Applications](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/).
[11] Rasmussen et al. — [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956).
[12] Wang et al. — [Recursively Summarizing Enables Long-Term Dialogue Memory in Large Language Models](https://arxiv.org/html/2308.15022v3).
[13] Microsoft — [Compaction (Microsoft Agent Framework)](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/compaction).
[14] Google — [Context compression — Agent Development Kit (ADK)](https://google.github.io/adk-docs/context/compaction/).
[15] Justin3go — [Shedding Heavy Memories: Context Compaction in Codex, Claude Code, and OpenCode](https://justin3go.com/en/posts/2026/04/09-context-compaction-in-codex-claude-code-and-opencode).
[16] Wang et al. — [Voyager: An Open-Ended Embodied Agent with Large Language Models (skill library)](https://arxiv.org/abs/2305.16291).
[17] Mem0 — [State of AI Agent Memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026).
[18] Wu et al. — [Enabling Personalized Long-term Interactions in LLM-based Agents through Persistent Memory and User Profiles](https://arxiv.org/abs/2510.07925).
[19] Sachit Mishra — [I built memory decay for AI agents using the Ebbinghaus forgetting curve](https://dev.to/sachit_mishra_686a94d1bb5/i-built-memory-decay-for-ai-agents-using-the-ebbinghaus-forgetting-curve-1b0e).
[20] vectorize.io — [Mem0 vs Letta (MemGPT): AI Agent Memory Compared (2026)](https://vectorize.io/articles/mem0-vs-letta).
[21] Xu et al. — [A-Mem: Agentic Memory for LLM Agents (NeurIPS 2025)](https://arxiv.org/abs/2502.12110).
[22] AWS — [Building smarter AI agents: AgentCore long-term memory deep dive](https://aws.amazon.com/blogs/machine-learning/building-smarter-ai-agents-agentcore-long-term-memory-deep-dive/).
