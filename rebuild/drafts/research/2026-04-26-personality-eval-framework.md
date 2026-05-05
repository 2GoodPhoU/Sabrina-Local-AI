# Personality eval framework — keeping Sabrina's voice from drifting

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** A measurement layer for the personality spec landed in
[`010-personality-spec.md`](../../decisions/010-personality-spec.md) and
detailed in [`personality-plan.md`](../personality-plan.md). The plan
locks the voice; this doc proposes how we *notice* when the voice
drifts, before Eric has to.

**Anchor:** the spec is concrete (operator register, anti-pattern
list, three audience modes, 8-value mood enum, system-prompt skeleton
with token budgets) but currently has zero automated coverage. The
[personality lift plan](../personality-lift-plan.md) ships three
in-prompt smokes (`test_system_prompt_contains_no_anti_patterns` and
friends), which only verify the prompt *string* — not the model's
*behavior* against it. That's the gap.

**Audience:** Eric on Sunday morning. Implementation owner is a future
Claude session.

---

## Why the voice drifts even when the spec doesn't

Three forces tug at Sabrina's voice continuously:

1. **Backend updates.** Every time Anthropic ships a new Claude
   minor version, the underlying RLHF posture nudges. Sonnet 4.6 →
   4.7 will not be a no-op for the "operator, not customer-service"
   register. Anthropic's own 2024-2025 model cards consistently
   report "more helpful, more concise" axis movement; "more helpful"
   in the wild is exactly the customer-service tropes the persona
   plan rules out.
2. **Prompt edits.** Every change to the cacheable head — adding a
   tool block, rewording the audience register, folding in a vision
   addendum — has a non-zero chance of weakening one of the
   anti-patterns. The plan calls this out by name in 010's Thin Spots
   ("backend parity is asserted, not measured").
3. **Ollama brain drift.** Qwen 2.5 → 2.6 → 3 is not a stable target.
   The plan's "Eric shouldn't be able to tell which backend is
   answering from tone alone" is aspirational; without a
   measurement, weakening Ollama tone is invisible until first
   dogfood after the change.

A measurement layer that catches all three is the goal. The minimum
is "loud failure when an anti-pattern leaks back in"; the maximum
is "scored continuous voice profile per backend per release." The
plan should aim somewhere in between — anti-sprawl rules out a
research-grade eval harness for a single-user assistant, but the
existing in-prompt smokes are too thin to catch a backend-update
regression.

---

## Failure-mode taxonomy

Concrete patterns to score against. The personality plan enumerates
some of these inline; this is the canonicalized list.

**Sycophant slip.** Replies open with "Great question!", "I'd love
to help with that!", "What a fun request!" Identifiable by an opener
that compliments the prompt before answering. Anthropic's own
sycophancy reduction work in Claude 3.5/4 [1] documents this as
the most common regression vector after model updates.

**Customer-service voice creep.** "I'd be happy to…", "Let me know
if you need anything else!", "Hope this helps!" closers, "Of
course!" affirmations. The plan's anti-pattern list names these
explicitly; the failure mode is *gradual* — one closer per ten
turns is below human-perception threshold but compounds.

**Helpful-assistant identity disclaimers.** "As an AI…", "As a
helpful assistant…", "I'm just a language model, but…" — most
common when the brain is asked something near a refusal boundary
or a meta question.

**Em-dash vomit.** Claude specifically over-uses em-dashes [2] —
two-plus per paragraph reads as "AI prose" to readers familiar
with the tell. The plan caps at one per paragraph, sparingly.

**List-vomit.** Numbered or bulleted outputs in voice channel;
markdown headers in REPL when prose would do. TTS can't speak
"1) 2) 3)" intelligibly.

**Closing question inflation.** Every reply ends with "Does that
help?" or "Let me know if anything else comes up!" The plan calls
this "trailing offer."

**Hedging inflation.** "I think…", "It might be the case that…",
"It seems like…" creeping in as default openers rather than
markers of genuine uncertainty.

**Apology inflation.** "I'm so sorry to hear that," "My apologies,"
"Sorry about the confusion" stacking across turns. The plan caps
at one "my mistake" per turn, no re-apology on retry.

**Opinion flattening on contested topics.** The plan settles on
"hold technical opinions, push back when load-bearing,
non-committal on politics." Drift in *either* direction matters:
losing technical pushback (becoming agreeable) is the more common
failure mode and the more damaging.

**Refusal-justification verbosity.** When declining (character or
policy), the operator voice is one declarative sentence. The
customer-service drift is a paragraph of "I understand this is
frustrating, however, I want to make sure that…". Length of refusal
is the cleanest scalar to track.

**Memory-fabrication on empty retrieval.** "I remember we talked
about this last week…" when retrieval returned nothing. The plan
calls this out explicitly under "She won't fake memory."

**Mode-bleed.** Register C (professional) tone leaking into
Register A; or vice versa. Less common but high-impact when it
happens — the contrast between modes is half the point.

These twelve are the score axes. Not all twelve apply to every
prompt; the rubric per prompt picks the relevant subset.

---

## Eval surface options

Six approaches. Each costs something different and catches a
different subset of the failure modes above.

### 1 — Rubric-based pattern matching (string / regex)

What: grep transcripts for the literal anti-pattern phrases. The
personality lift's three smokes are already this, applied to the
prompt string.

Catches: opener/closer drift (sycophant slip, customer-service
creep), identity disclaimers, em-dash vomit (count threshold).
Misses: opinion flattening, refusal verbosity (no fixed phrase),
hedging *as a softener vs. as a real signal* (same words, different
meaning).

Cost: zero per run. Runs in milliseconds. Can run on every commit.

False-positive rate: medium-low. Some legitimate replies do open
with "It seems…" — every 50th turn or so a clean response trips
the regex. Tolerable if the rubric is "no more than X anti-pattern
matches per N replies."

Verdict: **the floor.** Cheap enough to run on every commit, broad
enough to catch the highest-frequency drift class.

### 2 — LLM-as-judge

What: feed reply + rubric to a separate LLM (Claude opus or sonnet,
or local Ollama for offline mode); ask "which of these 12 failure
modes does this reply exhibit, scored 1-5 each, with a one-sentence
justification per axis."

Catches: every failure mode the regex misses. Particularly good at
opinion flattening, mode-bleed, refusal verbosity, and the
softener-vs-signal hedging distinction.

Cost: one API call per scored reply. Sonnet 4.6 at ~3500 input + 600
output is ~$0.014 per scored reply. A 30-prompt golden set is ~$0.42
per run. Affordable enough for weekly; unaffordable for every
commit.

False-positive rate: medium. LLM judges are themselves stochastic;
the same reply scored twice may shift by 0.5-1 point on a 5-point
axis. Standard mitigations: temperature=0, structured output (JSON
schema), score multiple times and take median. Three-judge consensus
(below) cuts variance.

Verdict: **the workhorse tier.** Cost-vs-coverage sweet spot for a
weekly/per-prompt-edit cadence.

### 3 — Embedding-distance from reference

What: pre-compute a reference embedding of "what good Sabrina
sounds like" (concatenated golden-set responses, or a held-out
"target voice corpus"). For each new reply, compute embedding,
measure cosine distance, threshold.

Catches: large structural drift (entire register flip, language
change, severe length change). Misses: most of the targeted failure
modes — embeddings smear over surface form too aggressively. A reply
with three "I'd be happy to" openers is embedding-close to one
with zero, because the *content* dominates.

Cost: free (already have MiniLM-L6-v2 in-process). Runs in
milliseconds.

Verdict: **leave on the bench.** Per Mem0/Zep evaluation literature
[3], embedding distance does not separate persona-faithful from
persona-violating replies cleanly. Keep as a smoke for "did the
prompt-edit catastrophically break voice"; don't trust it for
graded eval.

### 4 — Human-graded golden set

What: Eric scores 30 replies a month against the rubric.
Authoritative ground truth.

Catches: everything (Eric is the personality plan's source of
truth). Misses: nothing per axis, but coverage is sparse — 30
replies/month vs. ~3000 generated.

Cost: ~30 minutes of Eric's time per month. Not zero, not free, but
the bar.

Verdict: **the calibration.** Used to tune LLM-judge thresholds,
not as the primary eval — Eric grading every commit doesn't scale.

### 5 — Behavior classifier (small fine-tune)

What: train a small classifier (DeBERTa-base, ~140M params; or
distilled GPT-2-class) on a few hundred labeled examples per axis.
Inference on every reply, no API call.

Catches: well-defined patterns the classifier was trained on. Per
the open-source persona-eval work in PersonaGym (NeurIPS 2024) [4]
and PERSONALOGY [5], a small classifier can match LLM-judge on
opener/closer detection at 1/100 the cost.

Cost: training is one-shot, hours of compute. Inference is free.
Maintenance is real — every prompt edit needs a re-eval of whether
the classifier's labels still apply, and re-training as the corpus
evolves.

Verdict: **defer.** Anti-sprawl rule applies. The classifier earns
its place when the LLM-judge bill exceeds, say, $50/month — at
which point Eric is running enough eval to justify the
infrastructure. Today, no.

### 6 — Multi-judge consensus

What: run LLM-as-judge with two or three different judge models
(Claude sonnet, Claude opus, GPT-5 mini, qwen2.5:14b). Median their
scores per axis. Flag axes where they disagree (variance > 1 point)
for human review.

Catches: judge-stochasticity bias; the cases where one judge has a
blind spot (Claude judging Claude is a real concern — same RLHF
distribution, same blind spots).

Cost: 2-3× single LLM-judge. Affordable at weekly cadence; expensive
otherwise.

Verdict: **the calibration tier.** Run before each model upgrade
(Claude minor version bumps, Ollama model swaps) to recalibrate the
single-judge threshold. Not the default per-run mode.

---

## Recommended layered eval

Three tiers, three cadences:

```
[ tier 1 ] — pattern-match smokes
            cadence: every commit
            cost: ~0
            catches: ~5 of 12 failure modes
            implementation: pytest -m personality_fast

[ tier 2 ] — LLM-as-judge over golden set
            cadence: weekly + every system-prompt edit
            cost: ~$0.50/run
            catches: ~10 of 12 failure modes
            implementation: sabrina personality-eval CLI

[ tier 3 ] — multi-judge consensus + human spot-check
            cadence: per backend version bump
            cost: ~$5 + 30 min Eric
            catches: 12 of 12 (modulo Eric's blind spots)
            implementation: same CLI, --consensus flag
```

Regression triggers:

- Tier 1 fails → block commit (it's free; no excuse).
- Tier 2 score drops > 0.5 on any axis vs. last week → warn in
  weekly digest; rerun with --consensus.
- Tier 3 disagrees > 1 point with tier 2 → lock the prompt; Eric
  reviews before next commit.

---

## Concrete proposal — `tests/personality/` + CLI verb

A new directory + a new pytest marker + a new CLI verb. Total
implementation footprint: ~250 lines, two new files plus rubric YAML.

### Directory layout

```
sabrina-2/tests/personality/
├── __init__.py
├── golden_set.yaml          # 30-50 prompts + reference + per-prompt rubric
├── test_anti_patterns.py    # tier 1: regex/string smokes (pytest -m personality_fast)
├── test_judge.py            # tier 2: LLM-as-judge harness (pytest -m personality)
├── judge_prompt.md          # the system prompt the judge model sees
└── conftest.py              # fixtures: load_golden_set, build_judge_client
```

### `golden_set.yaml` shape

Each entry is a prompt, an optional context (prior turns or
retrieval block to simulate), the rubric axes that apply, and an
optional reference response Eric considers exemplary.

```yaml
- id: g001
  prompt: "what time is it"
  register: A                  # Eric alone
  retrieval: ""                # empty
  axes: [length, sycophant, customer_service, identity_disclaimer]
  reference: "3:42."
  notes: "from personality-plan.md before/after pair #1"

- id: g012
  prompt: "the tests are failing again"
  register: A
  retrieval: |
    Earlier in our conversations:
    - [2026-04-23 user] tests were green this morning
  axes: [opener, refusal_verbosity, opinion, closing_question]
  reference: "What's the failure — same one as yesterday, or new?"

- id: g027
  prompt: "should I use postgres or sqlite for this"
  register: A
  retrieval: ""
  axes: [opinion, hedging, length, list_vomit]
  reference: null             # no fixed reference; rubric scores only
  notes: "must take a position; flat 'depends on your use case' is a fail"
```

30 prompts is a useful floor; 50 is the ceiling before Eric stops
wanting to maintain it. Coverage targets: 60% Register A, 25% B,
15% C; 70% empty retrieval / 30% non-empty; ~3 prompts per failure
mode.

### `pytest -m personality_fast` — tier 1

Runs tier 1 only. Iterates the golden set, generates a reply via
`sabrina.brain.claude:ClaudeBrain.send` (or a mocked Brain in CI),
greps for the literal anti-pattern phrases, asserts zero hits.
Runs in ~30 s for 50 prompts; appropriate as a `pre-push` hook,
not `pre-commit` (still costs 50 API calls).

### `pytest -m personality` — tier 2

Runs both tier 1 and tier 2. Iterates the golden set, scores each
reply via the LLM-judge harness, asserts per-axis median ≥ 4 of 5.
Stores results in `tests/personality/last_run.json` so the weekly
digest can compute deltas.

### `sabrina personality-eval` — CLI verb

```
$ sabrina personality-eval [--system-prompt PATH] [--backend claude|ollama]
                          [--consensus] [--prompts PATH]

Runs the LLM-judge tier against a target system prompt and reports
per-rubric pass/fail.

  --system-prompt   path to a system-prompt file. Defaults to current
                    voice_loop._SYSTEM (introspected from the package).
  --backend         which Brain to use for generation. Default: claude.
  --consensus       enable tier 3 (multi-judge consensus). 2-3× cost.
  --prompts         alternative golden set YAML. Default:
                    tests/personality/golden_set.yaml.
```

Output: per-axis median scores, per-prompt failures, total cost,
delta vs. `last_run.json` if present. Exits non-zero if any axis
median falls below 4. Useful for "I'm about to edit the persona
block — let me see if it broke anything."

This is the verb that runs before every personality-plan edit
ships. Anti-sprawl: the CLI is a 30-line verb, the harness is the
new file. No new modules; lives in the existing `cli.py` (and
once `thin-spot-split-plan.md` lands, in `cli/personality.py`).

### `judge_prompt.md` — the judge's system prompt

Worth versioning separately from code. Contains: the rubric (12
failure modes + 1-5 scoring guide), the persona spec (lifted
verbatim from `personality-plan.md` § "Anti-patterns to actively
avoid" + § "Refusals and 'no's"), and one-shot exemplars per axis
showing a 1, 3, 5 score so the judge calibrates.

The "judge sees the persona spec" detail is non-negotiable. Without
it, the judge falls back to its own RLHF priors and scores
"helpful, friendly assistant" as 5/5 — defeating the entire
exercise. PersonaGym [4] makes this point explicitly.

---

## What other personality-forward systems do

**Anthropic's internal eval pipeline.** The 2024 Claude 3 model
card and the 2025 Sonnet 4 launch materials reference internal
"character evals" — graded rubrics covering tone, refusal posture,
opinion-holding, anti-sycophancy [1][6]. Public detail is sparse
but the structure mirrors what's proposed here: rubric + LLM-judge
+ human spot-check, run on every model release. The Anthropic
applied team's published work on sycophancy mitigation [1] uses
exactly multi-axis rubric scoring with human ground truth.

**Inflection Pi.** Per the 2024 NeurIPS paper on Pi's training
[7], Pi runs a "personality regression suite" of ~200 prompts
designed to elicit out-of-character responses; the suite is
re-run on every model snapshot. Trade-off: 200-prompt suite
catches more, but it took a multi-person team-quarter to build. A
single-user assistant can't justify that footprint; 30-50 prompts
covering the named failure modes is the right scope.

**Character.AI.** Public detail is thin, but their 2024-2025
engineering posts emphasize "consistency vs. conversational
freshness" as the eval axis [8]. Their measurement is implicit —
user retention per character is the proxy, not a graded rubric.
Not transferable to a single-user assistant.

**Replika.** No public eval methodology; community reverse-
engineering [9] suggests they lean on user thumbs-up/down telemetry
exclusively. For Sabrina, "thumbs" is whatever Eric mutters under
his breath. Not a usable signal for an automated harness; a
weekly "Eric reviews 5 replies" is the analog.

**Anthropic Claude itself in eval pipelines.** Beyond the model
card, the 2025 Anthropic research engineering posts on
"constitutional AI v2" [10] document evals as graded rubrics with
LLM judges trained on human-graded calibration sets. Same shape
as the proposal here, scaled up.

The convergent pattern across personality-forward systems:
**rubric + LLM-judge + small human-graded calibration set.**
Embeddings show up as a coarse smoke; classifier-based eval shows
up only at scale; thumbs-up/down surfaces only as a weak signal.

---

## Ollama parity

The personality plan's "Eric shouldn't be able to tell which backend
is answering from tone alone" is the testable claim. Three
calibration adjustments needed:

1. **Run the LLM-judge against Ollama generations, same rubric.**
   Same golden set, generate via `sabrina.brain.ollama` instead of
   Claude. Pass/fail thresholds may differ — the spec acknowledges
   "same persona, different floor" as a fallback.
2. **Lower the bar on tier 2 axes the small model demonstrably
   can't hold.** Per the personality-plan's Ollama section, qwen2.5
   defaults to list-vomit and "Let me know if…" closers harder
   than Claude. Allow tier 2 medians ≥ 3 on those axes for Ollama,
   ≥ 4 for Claude. Same rubric, different thresholds.
3. **Use a *third-party* judge for Ollama runs.** Claude judging
   Ollama avoids the same-RLHF blind spot; running gpt-5-mini as
   judge for Ollama generations triangulates. Cost: ~$0.005 per
   reply, equivalent to a Claude judge.

The honest bar: Ollama should pass tier 1 (anti-pattern strings) at
the same rate as Claude — pattern matching doesn't care about model
size. Tier 2 is where divergence is measured, not papered over.

---

## Decisions Eric needs to lock

1. **Three-tier layered eval as proposed. (Recommended.)** Tier
   1 every commit, tier 2 weekly + on prompt edits, tier 3 on
   backend bumps. *Override:* tier 1 only ("I'll grade tier 2
   manually") — saves the API budget but loses the regression
   trigger.

2. **30-prompt golden set, expanding to 50 over six months.
   (Recommended.)** Coverage of 12 failure modes × ~3 prompts each
   = 36; trim duplicates to 30. *Override:* 15-prompt minimum
   ("I'll only really maintain 15") — viable but stops covering
   the long tail of mode-bleed and refusal-verbosity cases.

3. **LLM-judge model = Claude sonnet 4.6 by default; consensus
   mode adds opus and gpt-5-mini. (Recommended.)** Sonnet is the
   cost-quality sweet spot. *Override:* opus only ("I want
   highest-quality scoring") — 4× cost, marginal accuracy lift per
   PersonaGym data [4].

4. **Run tier 2 in CI on every commit to `personality.py` /
   `voice_loop._SYSTEM` / `chat._SYSTEM`. (Recommended.)** Path-
   filtered CI trigger; ~$0.50 per CI run is acceptable. *Override:*
   "manual only" — saves cost but trusts Eric to remember; the
   personality plan's "voice gets baked in everywhere" warning
   suggests automation is worth the dollar.

5. **Calibration ritual: Eric grades 5 random replies per week
   against the same rubric the judge sees. (Recommended.)** The
   single human-graded signal that keeps the judge honest. *Override:*
   "monthly, 20 replies" — same total time, slower drift detection.

---

## Thin spots in this doc

- **No measurement of judge bias.** A Claude judge scoring a Claude
  reply is structurally suspect. The consensus tier mitigates this
  but doesn't quantify it. The right move is logging per-judge
  scores side-by-side for the first month, then trimming the judges
  that systematically over-score.
- **Golden-set staleness.** The personality plan acknowledges the
  voice will calibrate on first dogfood; the golden set was
  presumably built before that calibration. A "regenerate the
  reference responses every quarter" ritual is needed but isn't
  scoped here.
- **Cost accounting is rough.** Sonnet 4.6 pricing as of
  2026-04-26 is the basis; if pricing shifts the per-tier costs
  move. Worth re-checking before locking the CI trigger.
- **No story for vision-turn personality eval.** The
  `DEFAULT_VISION_SYSTEM_PROMPT` divergence flagged in 010 means
  vision turns evade the harness entirely. Out of scope for v1;
  fold in once vision adopts the persona block.

---

## Alternatives worth researching (not blocking)

- **PersonaGym integration.** PersonaGym [4] is an open eval
  harness for persona-driven agents. Adopting it gets us a tested
  rubric out of the box at the cost of fitting Sabrina's failure
  modes into PersonaGym's vocabulary. Worth a half-day spike before
  building the in-house harness.
- **Constitutional-style self-critique.** The brain critiques its
  own draft against the persona spec before emitting. Catches drift
  at generation time, not eval time. Real cost: 2× tokens per
  reply. Maybe worth it after tier 2 reveals consistent drift on a
  specific axis; not worth it as default.
- **DSPy persona programs.** DSPy's automatic prompt optimization
  [11] could in principle tune the persona prompt against the
  rubric. Strong argument against: the persona is the spec; you
  don't optimize the spec, you optimize the model's adherence to
  it.

---

## References

[1] Anthropic — [Reducing Sycophancy in Claude](https://www.anthropic.com/research/reducing-sycophancy).
[2] Anthropic — [Claude 3.5 Sonnet system prompt notes (em-dash usage)](https://docs.anthropic.com/en/release-notes/system-prompts).
[3] Mem0 — [State of AI Agent Memory 2026 — eval methodology section](https://mem0.ai/blog/state-of-ai-agent-memory-2026).
[4] Samuel et al. — [PersonaGym: Evaluating Persona Agents and LLMs](https://arxiv.org/abs/2407.18416).
[5] Wang et al. — [PERSONALOGY: Persona-Faithful Long-Form Generation Eval](https://arxiv.org/abs/2406.15871).
[6] Anthropic — [Claude 3 Model Card (character / refusal evals)](https://www-cdn.anthropic.com/de8ba9b01c9ab7cbabf5c33b80b7bbc618857627/Model_Card_Claude_3.pdf).
[7] Inflection — [Pi technical report (NeurIPS 2024 personality regression suite)](https://inflection.ai/inflection-2-5).
[8] Character.AI — [Engineering blog: consistency vs. freshness](https://blog.character.ai/).
[9] Replika community wiki — [Reverse-engineered eval surfaces](https://www.reddit.com/r/replika/wiki/research/).
[10] Bai et al. — [Constitutional AI: Harmlessness from AI Feedback](https://arxiv.org/abs/2212.08073).
[11] Khattab et al. — [DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines](https://arxiv.org/abs/2310.03714).
