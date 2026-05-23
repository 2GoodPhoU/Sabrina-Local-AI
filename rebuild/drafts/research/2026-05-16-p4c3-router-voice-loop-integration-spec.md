# P4.C3 — Router voice_loop integration + Windows e2e + decision doc — spec

**Date:** 2026-05-16
**Author:** sabrina-spec-writer (06:50 scheduled run; companion to today's P4.B4 spec at `2026-05-16-p4b4-automation-windows-validation-spec.md`)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Brain router → **P4.C3 Router — voice_loop integration + decision doc + Windows e2e** (`[windows-required] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-05-07-p4c1-persona-projection-layer-spec.md` (spec-writer 2026-05-07 06:50) — the (a)-half shipped by worker-10am 2026-05-08 is in the lock-blocked tree (`brain/persona.py` 415 LOC, `OllamaBrain` post-process projection, `BrainPersonaConfig`, `[brain.persona]` block, 14 unit tests). § "(b)-half — owned by P4.C2/P4.C3" of that spec defers the router dispatch + Windows validation here.
- `rebuild/drafts/research/2026-05-08-p4c2-router-routing-policy-spec.md` (spec-writer 2026-05-08 06:50) — the (a)-half shipped by worker-11am 2026-05-08 is in the lock-blocked tree (`brain/router.py`, `BrainRouterConfig`, `[brain.router]` block, 17 unit tests). § "(b)-half — owned by P4.C3" of that spec defers `voice_loop.py` + `chat.py` swap to `make_router_from_settings` + Windows session per-policy validation + decision doc here.
- Note: P4.C2 carries a queued P1 follow-up rework (`warn_threshold` field-removal per Eric's 2026-05-15 B answer at NEEDS-INPUT.md:140) — ~40 LOC code rework + ~15 LOC docstring updates. The rework lands BEFORE Eric's lock-clear sweep per planner 2026-05-15 07:00. P4.C3 here assumes the rework has landed; if not, Step 1 below picks it up first.
- `rebuild/drafts/research/2026-04-26-ollama-parity.md` — operator-voice parity audit. The persona-projection rules + the router's per-policy dispatch are the v1 surface that closes the parity gap.
- `rebuild/decisions/010-personality-spec.md` (in `main`) — canonical operator-voice spec. Cited by both predecessors and by the decision doc this spec lands.
- `ROADMAP.md` § "Gate 1 — Component completeness" item 4 (Brain router) — what P4.C3 closes.
- `sabrina-2/src/sabrina/voice_loop.py` — current voice loop. Constructs `ClaudeBrain` directly; P4.C3's edit replaces that construction with a router instantiation.
- Commit `acd6725` (Eric, 2026-05-05 08:43, in DONE.md) — the Phase 3 (a)-half tool wire-up that the router builds on (the router implements `Brain` protocol; `chat()` forwards `tools=`, `kill_switch=`, `dry_run=`, `settings=` per protocol).
- `roles/spec-writer.md` step 5 (partial-DoD framing) — names mixed-surface explicitly. P4.C3 is `[windows-required]`; no partial-DoD tier applies.

**Scope:** Windows-required voice-loop wiring + one real voice session per policy + decision doc. **The (a)-half implementations are already in the lock-blocked tree.** P4.C3's scope is purely Eric-side: clear `.git/index.lock` (composes with P4.B4's Step 1), apply the P4.C2 router rework first, swap `voice_loop.py`'s direct `ClaudeBrain` instantiation for `make_router_from_settings(settings)`, run one Windows voice session each for `force_local` and `claude_default` policies (and optionally `cost_aware`), confirm persona-projection survives the Ollama route, file the decision doc, flip the toml.

Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, no force-pushes, no remote rewrites. Off-scope: re-implementing what the two (a)-halves already shipped; persona-projection rule changes (canon per decision 010 + persona.py inline tests); cost_aware hysteresis tuning (Eric's "instant" pick per spec Q2 (a) is the v1 default); router policy beyond the three already shipped.

---

## What this item is

The QUEUE entry's Full DoD reads: "`voice_loop.py` instantiates the router instead of ClaudeBrain directly; both routes (`force_local`, `claude_default`) ship a real voice turn end-to-end; `pytest` passes; voice loop validated; decision doc filed." That is the gate, but it under-specifies four interlocking pieces:

1. **What is the precise construction-site swap?** Currently `voice_loop.py` reads `ClaudeBrain(model=..., system=...)` from settings (per `acd6725`). The router's `make_router_from_settings(settings)` returns a `Brain`-conforming object; the swap is one line. But the swap composes with P4.B4's `kill_switch=`/`dry_run=`/`settings=` kwarg threading at the same call site, and if P4.B4 lands first the construction surface is different than spec-writer 2026-05-08 saw. The spec needs to name the merge order.
2. **What counts as "both routes ship a real voice turn end-to-end"?** `force_local` routes to Ollama; `claude_default` routes to Claude. The persona-projection rules apply only to the Ollama route (per P4.C1 spec). A real voice turn through Ollama with operator voice surviving is the load-bearing test for Component 4; the Claude route is regression-only (it already works pre-router via `acd6725`). The spec calls out which is the high-leverage validation.
3. **What is the cost_aware policy's exit criterion when Eric isn't actively burning down budget on the test day?** Eric's box has ~$0 daily Claude spend on quiet days. Triggering the cost_aware → Ollama escalation requires either an artificially-low `[budget].warn_usd_monthly` (e.g. $0.001 — same pattern P2.8 uses) or running enough Claude turns to actually approach the warn threshold. The validation should be Reproducible-Cheap; the artificially-low knob is the right tool.
4. **What is the decision doc actually ratifying?** Two adjacent decisions: the persona-projection rules (P4.C1) and the routing-policy dispatch (P4.C2). Either one combined "Brain router + persona projection" decision doc, or two separate docs. The 010-personality-spec.md precedent (canonical voice doc) + the 008/009 decision-doc length argue for one combined doc; the per-(a)-half symmetry argues for two. This is the same Q2-shape as P4.B4's.

P4.C3 is the single closeout that answers all four. The (a)-halves did their jobs; the (b)-half is the empirical proof and the architecture ratification.

## Proposed approach

**Validation steps Eric runs on his i7-13700K/4080/Win11 box (the entire spec's deliverable):**

- **Step 0 — Pre-flight (~5 min).** Confirm in-tree state. Run `git status --short | findstr "brain/router\|brain/persona\|brain/ollama\|brain/claude\|config.py\|brain.persona\|brain.router"` — expect the C1 + C2 (a)-half file modifications listed. Run `git log --oneline -1 sabrina-2/src/sabrina/voice_loop.py` — confirm a recent commit on the file (post-`acd6725`). Confirm `Test-Path .git/index.lock`. **If pre-flight fails, abort to NEEDS-INPUT — the spec's framing is wrong.**

- **Step 1 — Lock-clear + P4.C2 rework + (a)-half pile land (~15 min).** Composes with P4.B4 Step 1; if P4.B4 ran first this session, lock is already clear and the pile is partially landed.
  1. If lock still present: `Remove-Item .git/index.lock`. Verify `git status` works.
  2. If P4.C2 router `warn_threshold` rework hasn't landed: pull from QUEUE (queued P1 today per PROPOSED #44). Diff is enumerated at `research/2026-05-15-dashboard-answer-batch-rework-surface.md` § "The one real code rework: P4.C2 router warn_threshold" — ~25 LOC code + ~15 LOC docstring + 1 test deleted + 1 simplified. Land as a separate commit on `automation/worker-2026-05-07-8am` before the (a)-half pile.
  3. If P4.B1 kill-switch hotkey docstring rework hasn't landed: similarly pull from QUEUE per PROPOSED #45.
  4. Land the remaining lock-blocked (a)-half pile per the per-entry Suggested-staging notes. C1 + C2 specifically are 2 of the 13 commits.
  5. **Net result:** `main` (or `automation/worker-2026-05-07-8am` ready for fast-forward) carries the C1 + C2 (a)-halves with current docstrings ratifying Eric's 5/15 answers; `voice_loop.py` still constructs `ClaudeBrain` directly.

- **Step 2 — `voice_loop.py` router-instantiation swap (~20 min).** The single load-bearing code change in P4.C3.
  1. **Replace direct `ClaudeBrain(...)` construction with `make_router_from_settings(settings)`.** At voice-loop startup (`voice_loop.py`'s setup region — search for the line that reads `from sabrina.brain.claude import ClaudeBrain` and instantiates it), replace with `from sabrina.brain.router import make_router_from_settings; brain = make_router_from_settings(settings)`. ~4 LOC delta net (drop direct construction; add router-factory call). The router instance implements `Brain` protocol — every existing `brain.chat(...)` call site downstream stays unchanged.
  2. **Carry `kill_switch=`/`dry_run=`/`settings=` through if P4.B4 has shipped first.** If P4.B4's Step 2 wire-up landed earlier in the session, the call sites pass those kwargs. The router's `chat()` delegates them to whichever backend (Claude or Ollama) it picks for the turn — `Brain` protocol expectation. If P4.B4 has NOT shipped, skip this composability — Step 2 here lands cleanly without those kwargs.
  3. **Confirm `chat.py` (the CLI entry point) also swaps.** Search for any other `ClaudeBrain(...)` direct constructions; the `chat` Typer command at `cli.py` may also instantiate the brain. Same swap. ~2 LOC delta.
  4. **Unit test for the wire-up.** Add `test_voice_loop_uses_router` to `sabrina-2/tests/test_smoke.py` (or a new test file if `test_voice_loop_*` doesn't exist — confirm via `Grep`). Mocks `make_router_from_settings` and asserts it's called with the settings object; mocks the brain + speaker + listener; asserts the constructed object's `chat()` method gets the expected kwargs. ~30 LOC. Runs under Linux/3.10 + Windows.
  5. **`python -m compileall sabrina-2/src` clean; `pytest sabrina-2/tests/test_router.py` + `test_persona_projection.py` + `test_smoke.py` PASS on Windows.** Linux-side regression: same gates GREEN per existing (a)-half worker shifts.

- **Step 3 — Real voice turn through Claude route (~5 min, regression).** Edit `sabrina-2/sabrina.toml`: `[brain.router] policy = "claude_default"`. Restart `sabrina voice`. Speak: "Sabrina, what's the weather like today?" (vision-disabled non-tool turn). Expected behavior:
  - Router picks `claude` for this turn (per `claude_default` policy).
  - `ClaudeBrain.chat()` fires; TTS confirms with a normal Claude operator-voice response.
  - `logs/sabrina.log` shows `brain.router.dispatched backend=claude policy=claude_default` (or equivalent structlog line from router (a)-half).
  - One captured timestamp + log line for the decision doc.
  
  **Regression intent:** confirms the router swap didn't break the pre-existing Claude path. No persona-projection applies here (Claude side); Eric's voice transcript should sound identical to a pre-router session.

- **Step 4 — Real voice turn through Ollama route + persona-projection survives (~10 min, load-bearing).** Edit `sabrina-2/sabrina.toml`: `[brain.router] policy = "force_local"`. Restart. Speak the same prompt: "Sabrina, what's the weather like today?" Expected:
  - Router picks `ollama` for the turn.
  - `OllamaBrain.chat()` fires; persona-projection rules apply (rules 1-4 active per `[brain.persona]` defaults; rule 5 mode-bleed is no-op per P4.C1 spec).
  - TTS confirms with an Ollama-produced operator-voice response — closing-offer-stripped, list-vomit-dehydrated, apology-deduped, sentence-count-truncated.
  - `logs/sabrina.log` shows `brain.router.dispatched backend=ollama policy=force_local` + `brain.persona.projected rules=[strip_closing_offer, dehydrate_lists, dedup_apologies, truncate_long_replies]` (or equivalent structlog from the (a)-halves).
  - **Eric reviews the spoken transcript for operator voice.** Specifically: no "Let me know if you'd like more" closing offers; no list-vomit ("There are three things: 1)... 2)... 3)..."); no double-apology stacking; sentence count ≤ the truncation cap. If any rule misfires, that's the spec-Q1 (b) per-rule disable surface from P4.C1 — flip the offending knob in `[brain.persona]` to `false` and re-run. If multiple misfires across a single utterance, document them all in the decision doc evidence.
  - Captured: TTS transcript (or Eric's verbatim recall) + at least 2 example sentences pre/post projection per rule that actually fired + timestamps + log lines.
  
  **This is the load-bearing test for Component 4 + Component 7 (Personality) combined.** Ollama-on-its-own without projection sounds like generic-helpful-AI per `2026-04-26-ollama-parity.md`; with projection, it sounds like Sabrina. The validation gate is "Eric, in a blind transcript, would not be able to tell whether the turn was Claude or Ollama without checking the log."

- **Step 5 — Cost-aware escalation (~5 min, optional but high-leverage).** Edit `sabrina-2/sabrina.toml`: `[brain.router] policy = "cost_aware"`, `[budget] warn_usd_monthly = 0.001` (artificially low — same pattern P2.8 uses). Restart. Speak: "Sabrina, what's the weather like today?" First turn picks `claude` (under warn threshold momentarily — but with `0.001` threshold the very first turn crosses it). Second turn picks `ollama` per the cost_aware escalation logic (Eric's 5/15 B answer at NEEDS-INPUT.md:140: "Read `[budget].warn_usd_monthly` directly; no `warn_threshold_usd` on `[brain.router]`. Single source of truth"). Expected:
  - First turn: `brain.router.dispatched backend=claude policy=cost_aware ratio=...` line.
  - Second turn: `brain.router.dispatched backend=ollama policy=cost_aware ratio=... reason=warn_threshold_crossed` line.
  - Voice TTS surface is identical in shape to Step 3/Step 4 (operator voice both); the listener shouldn't notice the swap because persona-projection ironed out the Ollama route.
  - Restore `[budget] warn_usd_monthly` to canonical default after validation.
  - Captured: 2 log lines + 2 transcript samples.

- **Step 6 — Voice-loop e2e + pytest on Windows (~10 min).** With the routing policy at Eric's preferred default (likely `claude_default` for v1 ship — see Q1 below), run one normal 5-turn conversation that exercises STT → router → brain (Claude) → TTS end-to-end. No tool use required. Then run `pytest sabrina-2/tests` on Windows — all PASS, including the 17 + 14 = 31 new router + persona tests from the (a)-halves. Capture pytest summary.

- **Step 7 — Combined decision doc (~45 min).** File `rebuild/decisions/0XX-brain-router-and-persona-projection.md` in decision-doc voice. Spec recommends covering: (1) the architecture — two coupled layers (router selects backend; persona-projection conditions Ollama output to operator voice); (2) the three policies — `claude_default` / `force_local` / `cost_aware` — with their selection criteria; (3) the persona-projection rules — strip closing offers / dehydrate lists / dedup apologies / truncate long replies — with their gating knobs; (4) the budget-gate hook — `cost_aware` reads `[budget].warn_usd_monthly` (Eric's 5/15 B answer, single source of truth); (5) what was deliberately NOT built — mode-bleed rule (deferred — corpus too small), more policies (`mixed`, `round_robin`, etc.); (6) the validation results from Steps 3-6 with timestamps + log lines + transcript samples as evidence; (7) the rollback posture — flip `[brain.router] policy = "claude_default"` to disable Ollama routing entirely without touching persona-projection or the router code; (8) reference to `rebuild/drafts/research/2026-05-07-p4c1-*.md` + `2026-05-08-p4c2-*.md` + `research/2026-05-15-dashboard-answer-batch-rework-surface.md` (for the `warn_threshold` rework history) + decision 010 (operator-voice canon). **The decision-doc number is open — see Q2 below.**

**What the partial-DoD framing says here:** P4.C3 is `[windows-required]`. Step 2's swap is technically Linux-runnable (the unit test mocks out the brain), BUT the load-bearing validation is Step 4 (Ollama operator voice surviving) which requires Eric's TTS-listening ears and the local Ollama instance on Eric's box. **No Linux-only diff lands as a partial-DoD ship for P4.C3.** Step 2's wire-up commit + Step 7's decision-doc commit ride together on `main` via Eric's normal client.

## What's deliberately NOT in scope

- **Persona-projection rule changes.** Canon per decision 010 + `2026-04-26-ollama-parity.md`; if Step 4's validation surfaces a rule-misfire that Eric wants tuned, that's a separate item.
- **Additional router policies** (`mixed`, `round_robin`, etc.). Three policies cover v1 use cases; future axes are post-v1.
- **`cost_aware` hysteresis tuning.** Eric's 5/15 answer at NEEDS-INPUT.md:140 picked the spec-Q2 (a) default (instant escalation, no debounce). If Step 5 surfaces escalation-jitter ("flip-flopping mid-conversation"), file as a P4.C3.1 follow-up; do not block P4.C3.
- **Streaming persona-projection.** Worker-10am 2026-05-08 shipped buffered-then-projected; rule 5 truncation needs full context anyway. Streaming-per-sentence shim is a post-v1 follow-up.
- **Setting up a Windows-runner CI.** Out of band; covered by Partial-DoD tier in CLAUDE.md.
- **Tool-use through the Ollama route.** Ollama doesn't support tool use per `acd6725`'s explicit `NotImplementedError`; `force_local` policy implies no automation actions. Documented in decision doc as a known limitation.
- **Re-implementing or re-designing the (a)-half code.** C1 + C2 match their respective specs; no change unless Steps 3-6 surface a specific defect.
- **Bake-in (P6.1) credit.** P4.C3 closes Component 4 (Router); daily-driver bake-in counts separately.

## Dependencies

- **`.git/index.lock` cleared.** Step 1 prerequisite per OPEN-DECISIONS S1(a). Composes with P4.B4 Step 1 if same session.
- **C1 + C2 (a)-halves landed on `main` (or on `automation/worker-2026-05-07-8am` and merged).** Both in the lock-blocked tree per worker-10am + worker-11am 2026-05-08 JOURNAL entries.
- **P4.C2 router `warn_threshold` rework landed** (queued P1 today per PROPOSED #44). The rework aligns the (a)-half with Eric's 5/15 B answer ("read `[budget].warn_usd_monthly` directly"). Step 5's cost_aware validation depends on this — without the rework, the router resolves the threshold via the deprecated `[brain.router].warn_threshold_usd` field which Eric is removing.
- **`logs/sabrina.log` writable + Ollama running locally on Eric's box.** Ollama install + the configured model (`[brain.ollama].model`) must be reachable. Confirm via `curl http://localhost:11434/api/tags` returns the model list, OR via `sabrina chat --backend ollama "test"` pre-flight pre-Step 4.
- **No new pip deps.** Router + persona-projection both use stdlib + existing `httpx` (Ollama) + `anthropic` (Claude).
- **Off-limits per CLAUDE.md unchanged.**
- **P4.B4 not a hard prerequisite, but composes.** Both edit `voice_loop.py` at adjacent call sites. If P4.B4 lands first, P4.C3 Step 2 lands on top of the new `kill_switch=`/`dry_run=`/`settings=` kwarg threading per the bailout-condition below. If P4.C3 lands first, P4.B4's Step 2 lands on top of the router-instantiation swap. Same-session bundling recommended.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable Windows checklist)

**Full DoD (this is `[windows-required]` — no partial-DoD tier applies; per CLAUDE.md):**

1. Step 0 pre-flight passed: C1 + C2 (a)-half modifications present in `git status` (or already-landed if lock-cleared earlier in session); `acd6725` (or later) on `voice_loop.py`; Ollama reachable.
2. Step 1 (lock-clear + P4.C2 rework + (a)-half pile land) executed: `.git/index.lock` gone; P4.C2 rework + P4.B1 docstring rework lands first; C1 + C2 (a)-halves land on `automation/worker-2026-05-07-8am` per Suggested-staging notes.
3. Step 2 (`voice_loop.py` router swap + unit test) executed: `voice_loop.py` (and `chat.py` / `cli.py` if applicable) constructs `make_router_from_settings(settings)` instead of `ClaudeBrain(...)`; new unit test `test_voice_loop_uses_router` PASS under Linux/3.10 + Windows; `compileall` clean; pytest passes.
4. Step 3 (Claude route regression) executed: `policy = "claude_default"`; one voice turn TTSed in operator voice; `logs/sabrina.log` shows `brain.router.dispatched backend=claude`. Timestamps captured.
5. Step 4 (Ollama route + persona-projection) executed: `policy = "force_local"`; one voice turn through Ollama TTSed in operator voice (closing-offer-stripped, list-vomit-dehydrated, apology-deduped, sentence-count-truncated); `logs/sabrina.log` shows `brain.router.dispatched backend=ollama` + `brain.persona.projected rules=[...]`. Eric's transcript review confirms operator voice survives. Captured: TTS transcript samples + pre/post-projection examples + log lines.
6. Step 5 (cost-aware escalation, optional) executed: `policy = "cost_aware"`, `[budget].warn_usd_monthly = 0.001`; first turn picks `claude`, second turn picks `ollama` after the threshold crosses; log lines confirm dispatch decisions; both turns surface operator voice through TTS. `warn_usd_monthly` restored to canonical default before commit.
7. Step 6 (voice-loop e2e + pytest) executed: 5-turn normal conversation works end-to-end through the router; `pytest sabrina-2/tests` passes on Windows including the 31 new C1 + C2 unit tests.
8. Step 7 — `rebuild/decisions/0XX-brain-router-and-persona-projection.md` exists in decision-doc voice; names Step 3-6 timestamps + log lines + transcript samples as evidence; cites the predecessors + decision 010; documents the rollback posture.
9. `sabrina-2/sabrina.toml` final state: `[brain.router] policy = "<eric's_v1_default>"` (likely `claude_default` per Q1 below); `[brain.persona]` knobs all `true` (or per Eric's rule-tuning); `[budget].warn_usd_monthly` at canonical default. Committed alongside the decision doc.
10. Gate 1 component 4 (Brain router) in `rebuild/ROADMAP.md` flips to `[x]` (Eric's edit).
11. QUEUE.md P4.C3 promotes from `[ ]` to `[done]`; P4.C1 + P4.C2 promote from `[in-progress] [linux-runnable] [partial-dod-eligible]` to `[done]`; DONE.md gets the entries.
12. Commit lands on `main` via Eric's normal client (the `voice_loop.py` delta + the decision doc + the toml updates); no `automation/` branch path for the decision-doc commit since this is a Windows-side human-led ship.

## Open questions for NEEDS-INPUT

**Q1 — Default `[brain.router].policy` for v1 ship?**

- **(a) `claude_default`** — every turn picks Claude unless explicitly overridden. Most operator-voice-coherent (Claude was canon for decision 010); Ollama route lives behind the `force_local` opt-in or the `cost_aware` automatic. Most Claude budget spend; least surprising for Eric's daily-driver pattern.
- **(b) `cost_aware`** — escalates to Ollama when monthly budget warn threshold is near. Mid-spend, mid-surprise — Eric won't notice the swap if persona-projection holds (per Step 4's validation gate), but will save real money on heavy days. Requires Step 5 to confirm the escalation works cleanly without flip-flopping.
- **(c) `force_local`** — every turn picks Ollama. Zero Claude spend; persona-projection load-bearing on every turn. High-trust posture on Step 4's load-bearing gate; risky if Step 4 surfaces any rule-misfire.
- **Spec recommendation: (a).** Lowest-risk v1 ship. Eric can flip to (b) once Step 5's cost_aware validation has multiple sessions of evidence (transcript-blindness ratio). (c) is post-v1 if at all — running Ollama 100% of the time is a different product than "operator-voice assistant with local fallback."

**Q2 — Decision-doc number and bundling: one combined "brain router + persona projection" doc, or two separate docs?**

- **(a) One combined doc at the next free integer** (per 005/008/009 precedent), excluding the 011 v1.0 reservation. Covers both C1 + C2 architectures under one number — the persona-projection rules + the router policy are one coupled architectural surface (router picks backend; projection conditions output) and read cleaner as one doc. ~180-220 lines (modeled on 008/009 + a router-section). Maintains flat-numbering precedent.
- **(b) Two separate decision docs** — one for persona-projection (C1) + one for router (C2). ~90-110 lines each. Maintains per-spec/per-doc symmetry; burns two decision numbers on adjacent surfaces.
- **(c) Bundle with P4.B4's decision doc** — one mega-doc covering Phase 4 (Automation + Router + Persona). ~400+ lines; harder to read; over-couples Component 4 and Component 10. Saves a decision number but conflates two distinct architectural gates.
- **Spec recommendation: (a).** Router + persona-projection are one coupled architecture; one decision doc reads cleaner. Same Q2-shape as P4.B4's; same answer recommended. Flat-numbering remains load-bearing through 010; this lands at the next free integer (likely 013 or 014 depending on P2.5 + P2.6 + P4.B4 sequencing).

Both questions written to `NEEDS-INPUT.md` per the spec-writer role doc. Neither is a Worker blocker — P4.C3 is `[windows-required]` and can't be pulled by a Linux-sandbox Worker; the questions only matter for Eric's session prep. The spec recommendations (a)+(a) are safe defaults.

## Bailout / not-yet conditions

- **If Step 0 pre-flight fails** (C1 + C2 (a)-halves not in tree, or `acd6725` not on `voice_loop.py`, or Ollama unreachable), the spec's "(a)-halves already in tree" framing is wrong OR the local Ollama setup is broken. Abort to NEEDS-INPUT; re-spec or fix Ollama install per researcher 2026-04-26 ollama-parity-research framing.
- **If Step 1 P4.C2 rework hasn't landed** before Step 2 starts, do NOT proceed — the router resolves `warn_threshold` via the deprecated field and Step 5 cost_aware will fail. Pull P4.C2 rework first; then resume Step 2.
- **If Step 2's `voice_loop.py` swap surfaces an init-order problem** (router needs settings; settings load order changed by a recent commit), confirm via `Grep` for any settings-load reordering in commits since `acd6725`. File as PROPOSED + P4.C3.0 init-order-fix item; do not ship P4.C3 until resolved.
- **If Step 4 persona-projection misfires** (Eric reviews the transcript and finds a closing offer that survived, or list-vomit, or apology-stack, or 5+ sentences), this is a rule-tuning question, not a P4.C3 blocker. Flip the offending `[brain.persona]` knob to `false`, re-run the same prompt, capture both transcripts in the decision-doc evidence section. File the misfire as a P4.C3.1 follow-up for rule-tuning; ship P4.C3 with the knob `false` for v1.
- **If Step 5 cost_aware "flip-flops"** mid-conversation (turn 3 escalates to Ollama, turn 5 reverts to Claude after budget recomputes), this is a P4.C2 cost_aware hysteresis question (Eric's 5/15 B-answer chose instant; debounce was spec-Q2 (b)). File as P4.C3.2 follow-up; ship P4.C3 with `claude_default` as v1 per Q1 (a) recommendation.
- **If Step 6 pytest fails on a previously-Linux-GREEN test**, suspect a backend-specific test path conditional. Likely candidates: `test_router_dispatches_claude_default`, `test_persona_projection_strips_closing_offer`. File the failing test list to PROPOSED; don't ship until resolved.
- **If P4.B4 ships in the same session and lands `voice_loop.py` Step 2 wire-up first**, P4.C3 Step 2's swap is a one-line change against the new construction line: replace `kill_switch = KillSwitch(...); brain = ClaudeBrain(...)` with `kill_switch = KillSwitch(...); brain = make_router_from_settings(settings)`. The router's `chat()` accepts the safety kwargs unchanged (`Brain` protocol). Composes cleanly.
- **If Ollama crashes mid-Step-4** or returns malformed output (timeout, JSON parse error), file the failure mode to PROPOSED with the stderr/structlog. The persona-projection layer is downstream of the model; an Ollama outage is not a P4.C3 gate failure but is decision-doc-worthy as a known risk class.

---

## Quick-reference: what changes if the spec's recommendations all hold

If Q1 = (a) (`claude_default` default) and Q2 = (a) (one combined doc at next free integer):

- **Files touched (across the session's commits):**
  - `sabrina-2/src/sabrina/voice_loop.py` — `ClaudeBrain(...)` → `make_router_from_settings(settings)` swap (~4 LOC).
  - `sabrina-2/src/sabrina/chat.py` (or `cli.py`'s `chat` command) — same swap at the CLI entry-point (~2 LOC).
  - `sabrina-2/tests/test_smoke.py` (or new `test_voice_loop_wireup.py`) — `test_voice_loop_uses_router` (~30 LOC).
  - `sabrina-2/sabrina.toml` — `[brain.router] policy = "claude_default"` (already the (a)-half default per C2 spec; confirm), plus restoration of any P2.5/B4-touched flags.
  - `rebuild/decisions/0XX-brain-router-and-persona-projection.md` — new file in decision-doc voice (~180-220 lines per 008/009 precedent).
  - `rebuild/ROADMAP.md` — Gate 1 component 4 (Router) flipped to `[x]` (Eric's edit).
  - `QUEUE.md` — P4.C3 promoted to `[done]`; P4.C1 + P4.C2 promoted from `[in-progress]` to `[done]`.
  - `DONE.md` — three new entries (P4.C1 + P4.C2 + P4.C3).

- **What Eric needs in front of him for the session:** PowerShell + working Ollama install + 80-100 minutes (Step 0-1 = ~20 min, Step 2 swap + tests = ~20 min, Step 3-6 validation = ~25 min, Step 7 decision doc = ~45 min). One restart of `sabrina voice` per policy-flag flip (3 restarts total: Step 3 → claude_default, Step 4 → force_local, optional Step 5 → cost_aware).

- **What does NOT need to happen on Saturday:** Persona-projection rule changes, additional policies, streaming projection shim, Ollama tool-use support, hysteresis tuning. Pure human-led Windows session against a 31-test gate that already runs GREEN under Linux.

- **Composability with P4.B4 (Automation Windows validation, separate spec):** both edit `voice_loop.py` at adjacent call sites. Recommended same-session bundling per STATE.md "Eric's Saturday-collapse." Either order is fine; the second edit is a 4-6 LOC delta against the first.

- **Composability with P2.5 + P2.6 (autostart + supervisor validation, separate specs):** independent — P4.C3's voice-loop swap doesn't change the supervisor's spawn surface or the autostart task XML. All four can ship in the same session; recommended order is P2.5 + P2.6 first (close daily-driver readiness items 2 + 3), then P4.B4 + P4.C3 (close Phase 4 components 10 + 4).
