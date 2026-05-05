# Research index — 2026-04-26

A navigable map of the research and cleanup work accumulated in the
last 48 hours. Built so Eric can walk in fresh on a Sunday morning,
see what's there, and pick a reading order that matches the goal of
the day.

---

## What this folder is — and isn't

This is a **research corpus**, not a backlog. Every document below
either (a) maps the 2026 state of the art for a Sabrina subsystem,
(b) audits the current code for drift between docs and what
actually shipped, or (c) proposes a measurement layer for something
the spec already locked. None of it has touched code; all of it is
upstream of decisions the rebuild has *not yet* made.

What's **not** in this folder: implementation work, validation
procedures (those are `validate-*.md` at the rebuild root), or
shipped decisions (those are `decisions/NNN-*.md`). The plan files
in `drafts/*-plan.md` are "halfway" — they cite this research and
recommend a path, awaiting Eric's sign-off before code.

The 48-hour window covers the overnight session of 2026-04-25 (one
big stack-alternatives sweep) and the overnight session of
2026-04-26 (six narrower deep-dives plus a cleanup audit and this
new personality-eval research file).

---

## Per-document entries

### 2026-04-25-stack-alternatives-survey.md (~5,200 words)

Ten-subsystem sweep of what Sabrina runs today vs. what else exists
in May 2026 — Piper, faster-whisper, openWakeWord, Silero,
Qwen 2.5, sqlite-vec, Live2D, prompt engineering, MCP, sounddevice.
Per-subsystem keep/switch/watch verdicts.

**Key recommendation:** keep most of the stack; the highest-leverage
potential switch is Piper → Kokoro-82M for TTS naturalness, but
it's discretionary, not urgent.

**Applicable next step:** when ASR or TTS upgrades come up,
re-read § 1 and § 2 first; the alternatives are pre-scored.

### 2026-04-25-sources.md (~340 words)

Flat URL list for the stack survey. Skim-only; useful when a future
session wants to verify a claim from the sweep.

### 2026-04-26-wake-word-training-pipeline.md (~2,900 words)

Concrete, runnable how-to for training the custom "Hey Sabrina"
openWakeWord model. WSL2 with CUDA passthrough, ~30k synthetic
positives via Piper multi-speaker, ~3 hours wall time on the
4080.

**Key recommendation:** ship the bundled `hey_jarvis` model first,
train custom only after the racing-with-PTT integration validates.

**Applicable next step:** when `validate-wake-word.md` runs clean
on Eric's box, this is the pipeline for the v1 → v2 swap.

### 2026-04-26-memory-architecture-evolution.md (~3,200 words)

Where memory wants to go after `compaction.py` shipped — episodic,
importance, multi-tier decay, procedural, identity, forgetting.
Ranks each by leverage-per-line for a single-user assistant.

**Key recommendation:** identity memory (a "who is Eric" entity row)
before episodic; importance tagging next; defer procedural until
tool-use ships; stay with sqlite-vec + MiniLM-L6.

**Applicable next step:** the identity-memory mini-spec is ~30 lines
of SQL; can land alongside any future memory touch.

### 2026-04-26-multi-surface-identity.md (~2,800 words)

How the voice loop, GUI, avatar, and tray icon stay perceptually one
Sabrina rather than a federation. Proposes a `Presence` actor that
owns five identity primitives (mood, activity, attention, topic
handle, surface set) and broadcasts deltas.

**Key recommendation:** build `Presence` *alongside* the avatar work,
not before; lift the avatar's bus subscriber out into a `presence/`
package once the avatar reads identity from somewhere.

**Applicable next step:** read this immediately before starting the
avatar lift session.

### 2026-04-26-toolspec-first-three.md (~2,500 words)

The next 3-5 ToolSpecs after `tool-use-plan.md`'s v1 set
(`get_time / read_clipboard / search_memory`). Side-effect class
taxonomy, MCP shape conformance, per-tool risk tiering.

**Key recommendation:** ship `write_clipboard` next (low-cost,
reversible, exercises write-side without confirmation grammar);
defer `web_search` and `append_note` to confirmation-UX session.

**Applicable next step:** any morning where Eric wants a tool-use
shippable that adds breadth without tripping the confirmation
trip-wire.

### 2026-04-26-avatar-cue-track-implementation.md (~3,300 words)

Implementation deep-dive backing `avatar-plan.md`. live2d-py 0.6.x
specifics, frameless transparent click-through window in PyQt6,
single-clock dispatcher with 80 ms cue lead, asset prep workflow,
performance profile on the 4080.

**Key recommendation:** PyQt6 + live2d-py primary;
pixi-live2d-display + QWebEngine documented fallback; VTube
Studio is an afternoon parallel-prototype option.

**Applicable next step:** reading list for the avatar session 1
("avatar window appears, reacts to state events").

### 2026-04-26-personality-eval-framework.md (~3,400 words, NEW)

Measurement layer for the personality spec. Twelve named failure
modes (sycophant slip, customer-service creep, em-dash vomit, mode-
bleed, …); six eval surface options graded on cost vs. coverage;
three-tier layered eval with concrete `tests/personality/` directory,
`golden_set.yaml`, `pytest -m personality` marker, and `sabrina
personality-eval` CLI verb.

**Key recommendation:** tier 1 (regex smokes) every commit; tier 2
(LLM-as-judge over a 30-50 prompt golden set) weekly + on every
prompt edit; tier 3 (multi-judge consensus + Eric spot-check) on
backend version bumps. Cost ~$0.50/run for tier 2.

**Applicable next step:** lands in the same session as the personality
lift, or the session immediately after — the tier-1 smokes are
~30 lines of pytest and a YAML.

### 2026-04-26-sources.md (~210 words) and 2026-04-26-round2-sources.md (~200 words)

Flat URL lists for the round-1 (wake-word, memory, toolspecs, avatar)
and round-2 (multi-surface, this index) deliverables. Skim-only.

### CLEANUP_FINDINGS_2026-04-26.md (~3,000 words, parent dir)

Read-mostly audit across `sabrina-2/src/`, the test suite, and the
rebuild docs. Found one ship-blocker (`config.py` truncation residue
— since fixed in-place), one dead import (also fixed). 23 findings:
ROADMAP / README / three `validate-*.md` files reference
pre-implementation drafts; `cli.py` has crossed the 300-line
guardrail; wake-word integration is grep-tested rather than
behavior-tested.

**Key recommendation:** the doc-coherence drift is the biggest debt;
priority sequence in the doc's "Suggested resolution sequence"
section. Code health is green.

**Applicable next step:** Eric's morning checklist: confirm F1+F2,
then refresh ROADMAP / README / `validate-wake-word.md`.

### Plan files with research-attached recommendations

These are the `drafts/*-plan.md` documents that the research above
already cites or feeds into. They sit between research and shipped
code — the recommendations are concrete, but the implementation
session hasn't fired.

- **personality-plan.md** — full personality spec. Operator register,
  voice rules, anti-pattern list, three audience modes, system-prompt
  skeleton with token budgets. Decision 010 promoted out of drafts.
- **personality-lift-plan.md** — implementation plan to land the
  skeleton into `voice_loop._SYSTEM` + `chat._SYSTEM`. Awaits Eric's
  eyeball-review. Anti-pattern smokes proposed; the eval-framework
  doc above generalizes them.
- **avatar-plan.md** — Live2D + cue track. Implementation deep-dive
  is the 2026-04-26 avatar research file; multi-surface identity
  research adds the `Presence` actor to the picture.
- **tool-use-plan.md** — v1 of three tools. The toolspec-first-three
  research extends into v2.
- **budget-and-caching-plan.md** — prompt caching + per-tool counter.
  The eval framework's "tier 2 cost is ~$0.50/run" assumes the
  budget plumbing exists.
- **remaining-components-plan.md** — master menu of what's queued.
  Cleanup findings flag entries here as scaffolded-but-unvalidated.

---

## Recommended reading orders by goal

**Goal: ship something tomorrow.**
Read `CLEANUP_FINDINGS_2026-04-26.md` first (Eric's morning
checklist), then `personality-lift-plan.md` (the closest-to-ready
implementation plan). The personality lift is ~80 lines of new
code plus three smokes; cleanup findings is ~10 token-level edits.

**Goal: evaluate the memory architecture.**
Read in this order: (1) `2026-04-26-memory-architecture-evolution.md`
for the landscape, (2) decision 007 for what already shipped,
(3) compaction code in `sabrina-2/src/sabrina/memory/compaction.py`
to ground the L1 tier. Identity memory is the highest-leverage
next step; episodic comes after if dogfood demands it.

**Goal: understand the personality posture.**
Read in this order: (1) `personality-plan.md` (the spec — voice,
anti-patterns, audience modes), (2) `decisions/010-personality-spec.md`
(the locked summary), (3) `2026-04-26-personality-eval-framework.md`
(how we measure it). Skip `personality-lift-plan.md` unless the
question is "how does it land in code."

**Goal: plan the avatar arc.**
Read in this order: (1) `avatar-plan.md`, (2)
`2026-04-26-avatar-cue-track-implementation.md`,
(3) `2026-04-26-multi-surface-identity.md`. The third one earns its
place by reframing the avatar as one of three surfaces sharing a
`Presence` actor — non-obvious from the avatar plan alone.

**Goal: extend tool-use beyond v1.**
Read in this order: (1) `tool-use-plan.md`,
(2) `2026-04-26-toolspec-first-three.md`, (3) the side-effect
taxonomy table in §2 of the toolspec doc — that's the gating
artifact for the confirmation-UX work.

**Goal: catch up on backend / library landscape.**
Read `2026-04-25-stack-alternatives-survey.md` once, end-to-end.
Single source of truth for "what could we swap in 2026."

**Goal: see all the code-level drift.**
Read `CLEANUP_FINDINGS_2026-04-26.md` end-to-end. The ship-blocker
is fixed; the rest is doc coherence and one or two test-quality
items.

---

## What's still open across the whole research corpus

Decisions and questions that surfaced repeatedly while building
this index, not yet locked anywhere:

1. **Vision-turn personality integration.** Both the personality
   plan (Thin Spots) and the eval framework call out
   `DEFAULT_VISION_SYSTEM_PROMPT` as evading the persona block.
   No session has scheduled the fold-in. Cost: ~140 tok per vision
   turn; benefit: cross-channel voice consistency.
2. **Ollama parity, asserted vs. measured.** Personality spec
   says "Eric shouldn't be able to tell which backend is answering
   from tone alone"; eval framework names a path to measure it
   (third-party judge, lower threshold on known-weak axes).
   Neither has been run. First dogfood is still the only signal.
3. **`system_suffix=` plumbing.** Budget-and-caching plan and
   personality-plan both depend on it; personality-lift plan
   defers it. Until tool-use ships and pushes the cacheable head
   above the 1024-tok cache floor, the plumbing buys nothing
   observable. After tool-use, it's load-bearing.
4. **Identity memory ahead of episodic.** Memory-architecture
   research recommends identity-row first; nothing has scheduled
   it. Trivially scoped (~30 SQL lines) and high-leverage (every
   other memory improvement compounds with a clean profile).
5. **`Presence` actor scope before avatar lands.** Multi-surface
   research recommends building it alongside the avatar lift,
   not before. The avatar plan doesn't yet reference it. Risk:
   the avatar wires its own bus subscriber and the second-caller
   refactor never happens.
6. **Wake-word custom training schedule.** Wake-word plan +
   training-pipeline research are both ready; the bundled
   `hey_jarvis` model is shipping today. No date for the
   custom-train swap; gated on the integration validation
   running clean.
7. **Eval CI cost authorization.** Personality-eval framework
   proposes ~$0.50/run on tier 2, ~$5 on tier 3 backend bumps.
   No budget approval recorded; affordable, but worth a
   "yes, go ahead" before the CI workflow lands.
8. **Doc coherence sweep, scheduled or ad-hoc?** Cleanup findings
   list 8-9 ROADMAP / README / `validate-*.md` drift items.
   Ad-hoc is the current pattern; a quarterly "sweep all decision
   docs for stale references" ritual would catch this earlier.

The pattern across these eight: **measurement is consistently
deferred behind shipping**, and the deferred-measurement debt is
starting to compound. The personality spec is locked but unmeasured;
multi-surface identity is designed but unbuilt; Ollama parity is
asserted but unverified. The eval-framework research file is the
first explicit "let's catch up" move; the others (Ollama, vision,
multi-surface, identity-memory) are still pending.

If Eric reads only one item from this index: **the eval framework
doc, because it generalizes the gap that runs through everything
else.**
