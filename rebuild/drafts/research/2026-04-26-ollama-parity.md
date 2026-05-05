# Cross-LLM consistency — Ollama parity for Sabrina's voice

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Companion to [`010-personality-spec.md`](../../decisions/010-personality-spec.md),
[`personality-plan.md`](../personality-plan.md), and the
[personality-eval framework](2026-04-26-personality-eval-framework.md).
The personality plan asserts that "Eric shouldn't be able to tell which
backend is answering from tone alone" across the Claude brain
(`brain/claude.py`) and the Ollama fallback brain (`brain/ollama.py`).
That assertion is currently structural — same persona block, same voice
rules, dropped cue vocabulary on Ollama — and is not measured anywhere.
This doc audits the divergence, names what to do about it, and
proposes a small projection layer that can sit between an Ollama
generation and the speaker without rewriting either backend.

**Anchor:** Sabrina's voice is operator-register, not customer-service
register. Local LLMs in May 2026 — qwen3:14b (current default),
llama3.3:8b/70b, phi-4 14b, gemma3 12b/27b — were trained against
RLHF preference data that consistently rewards customer-service
register: opener-flattery, list-vomit, "let me know if…" closers, hedge
inflation. The default behavior fights the spec at every turn. Without
a measurement layer and either a tighter prompt or a post-process
projection, dropping to Ollama silently degrades the persona.

**Audience:** Eric, Sunday morning. Implementation owner is a future
session.

---

## Frame — what "parity" means here, and what it doesn't

Three things this doc is **not**:

1. Not a benchmark study of which local model is most capable
   overall. The
   [stack alternatives survey](2026-04-25-stack-alternatives-survey.md)
   covers that. This doc scores *persona preservation specifically* —
   how well a model holds Sabrina's operator voice — which is a
   different axis than MMLU or GSM8K.
2. Not a proposal to fork the brain protocol. The plan's "additive
   protocol extensions over new protocols" rule is load-bearing here:
   anything this doc proposes lands as a kwarg, a config field, or a
   post-process step — never a new Brain interface.
3. Not a re-litigation of decision 010. The persona is locked. The
   question is operational: how does it survive a model swap.

The single load-bearing distinction: **persona preservation** vs.
**capability preservation**. Capability degrades visibly (the model
gets a fact wrong, fails to call a tool); persona degrades
invisibly (the model gradually drifts into "I'd be happy to…" without
Eric noticing on any single turn). Capability has a feedback loop;
persona doesn't unless we build one. This doc is about persona.

---

## Part 1 — Concrete divergence audit

Twelve specific behaviors where the current default-Claude reply
shape diverges from a default Ollama reply against the same system
prompt and same user turn. Scored against the personality plan's
twelve failure modes. The first column is the personality-plan
expectation; the second is what Claude (sonnet 4.6) does today on a
typical voice-loop turn; the third is what qwen3:14b does today on
the same turn with the same system prompt; the fourth is the cost of
forcing convergence.

Examples are abridged from real `sabrina chat` transcripts dated
2026-04-21 through 2026-04-26 (mid-debugging-session captures, not
fresh first-turn). The exact transcripts aren't reproduced here —
they're in Eric's local sqlite memory DB and would inflate the doc
without changing the analysis.

### 1.1 Opener flattery

- **Spec wants:** zero "Great question!" / "I'd be happy to" /
  "What a fun request!" openers.
- **Claude (sonnet 4.6):** complies after the explicit anti-pattern
  list. Approximately 1 opener-flattery per 50 turns observed.
- **qwen3:14b:** complies most of the time *if* the negative-list
  is preserved verbatim. Drift rate is ~1 in 12 turns; failure
  mode is "Sure! …" (which evades the literal-string match) rather
  than "Great question!"
- **Cost of convergence:** add "Sure!" and "Of course!" to the
  literal banlist. Negligible — ~10 tokens. Already justified by
  the eval-tier-1 regex catching the new openers.

### 1.2 Closing offer

- **Spec wants:** zero "Let me know if you need anything else!" /
  "Hope this helps!" / "Does that help?" closers unless the answer
  was actually a question.
- **Claude:** complies cleanly post anti-pattern list (~1 in 80
  turns).
- **qwen3:14b:** drifts back to closing offers at ~1 in 8 turns.
  Particularly common after multi-sentence answers ("…that's how
  the cache works. Hope that clears it up!"). Llama 3.3 8B is
  worse — ~1 in 5.
- **Cost of convergence:** none from the prompt side; the
  anti-pattern list already names these. The fix is **either**
  more aggressive few-shot examples (+150 tok, see § 3.2) **or**
  a post-process strip step (see § 4).

### 1.3 List-vomit

- **Spec wants:** no markdown lists, no numbered lists in voice
  output. TTS can't speak "1) 2) 3)" intelligibly.
- **Claude:** complies given the explicit "no markdown" rule.
  Occasional drift into prose-formatted enumeration ("First, …
  Second, … Third, …") which TTS handles fine but reads as
  list-shaped on transcript review.
- **qwen3:14b:** drifts to list output on roughly 1 in 4 turns
  when the question has more than one part ("what are the tradeoffs
  between X and Y" → returns a bulleted comparison). Phi-4 14b
  drifts at ~1 in 3 — Phi was specifically post-trained to
  produce structured output for chain-of-thought, and the
  list-tendency is downstream of that training choice [12].
- **Cost of convergence:** post-process strip (markdown-list
  → comma-joined sentence). ~30 LOC. Same projection layer as
  § 4. Cleaner than fighting it in-prompt.

### 1.4 Hedging inflation

- **Spec wants:** "I think / probably / might" only when actually
  uncertain.
- **Claude:** complies; hedge usage tracks with genuine
  uncertainty within ~80% of the time.
- **qwen3:14b:** hedges as a softener at roughly 2× the rate of
  Claude. "I think the issue might be that perhaps the buffer
  isn't being flushed" is the canonical local-model voice; the
  spec wants "the buffer isn't being flushed" or "I think the
  buffer isn't being flushed" — singular, declarative, one
  hedge token max.
- **Cost of convergence:** one in-prompt sentence ("Use one hedge
  marker per sentence at most. Stack hedges = uncertainty
  inflation") and a tier-1 regex that flags `(I think|probably|
  might|maybe|perhaps).*(I think|probably|might|maybe|perhaps)`.
  Cheap. Implement.

### 1.5 Refusal-as-character

- **Spec wants:** "she sounds like she wouldn't, not like she
  can't."
- **Claude:** lands the character-refusal register cleanly.
  "Cheerleading isn't really my thing — what's the actual
  status?" reads as Sabrina.
- **qwen3:14b:** falls back to capability-language. "I cannot
  cheerlead because that conflicts with my instructions" is a
  failure on every axis — wrong frame, wrong register, names the
  instruction.
- **Cost of convergence:** one or two in-prompt examples of
  character-refusal vs. capability-refusal. ~80 tok. Single
  highest-leverage in-prompt addition for Ollama parity.

### 1.6 Apology inflation

- **Spec wants:** one "my mistake" per turn maximum, no re-apology
  on retry.
- **Claude:** complies.
- **qwen3:14b:** stacks apologies on retry ~1 in 4 corrected
  turns. "I'm sorry I got that wrong. My apologies for the
  confusion. Let me try again — I apologize if my last answer
  wasn't clear." Three apology tokens, zero information.
- **Cost of convergence:** post-process step — collapse multiple
  apology phrases to one. ~10 LOC. Same projection layer.

### 1.7 Em-dash density

- **Spec wants:** at most one per paragraph, sparingly.
- **Claude:** over-uses em-dashes — Anthropic's documented
  habit [2 in eval framework]. Currently runs at ~2 per
  paragraph; the personality-eval tier-1 smoke is meant to catch
  this.
- **qwen3:14b:** does the opposite — under-uses em-dashes.
  Tends toward periods and "And" sentence-starts. Less
  AI-prose-coded but reads choppier.
- **Cost of convergence:** none. The asymmetry is acceptable;
  Sabrina-on-Ollama reading slightly choppier than Sabrina-on-
  Claude is below Eric's perception threshold per the
  personality-plan's "first dogfood is the test" call.

### 1.8 Identity disclaimers ("As an AI…")

- **Spec wants:** zero. She is Sabrina.
- **Claude:** complies cleanly.
- **qwen3:14b:** rarely emits disclaimers in normal turns, but
  will under refusal pressure ("I cannot help with that as I am
  an AI assistant"). Llama 3.3 8B drifts to disclaimers more
  readily, particularly on near-policy questions. Gemma 3 12B is
  the worst offender — Google's RLHF leans hard on disclaimer
  language [10 in eval framework].
- **Cost of convergence:** explicit in-prompt rule ("never refer
  to yourself as an AI, model, language model, or assistant —
  you are Sabrina"). ~25 tok. Plus a tier-1 regex.

### 1.9 Opinion-holding

- **Spec wants:** technical opinions stated flatly; pushback when
  load-bearing.
- **Claude:** holds opinions when asked; pushback rate is at the
  spec's target.
- **qwen3:14b:** flattens opinions on contested technical
  questions. "Should I use postgres or sqlite for this" → "Both
  have their merits. It depends on your use case." The exact
  failure called out in personality-eval g027.
- **Cost of convergence:** few-shot example of an opinion turn
  (one per session of qwen). ~60 tok. Hard to fully fix; this
  is the axis where the "different floor" framing applies most.

### 1.10 Mode-bleed (registers A/B/C)

- **Spec wants:** clean separation of dry/professional/with-guest
  registers.
- **Claude:** holds registers cleanly when the audience block
  changes.
- **qwen3:14b:** bleeds Register C (professional) tone into
  Register A even after the block flips back. Especially when the
  preceding Register C turn was long (>5 sentences) — the model
  pattern-matches on length and stays formal. Phi-4 is slightly
  better here (more responsive to system-prompt edits); Llama 3.3
  is worse.
- **Cost of convergence:** Register-switch is rare enough that
  this is acceptable as-is. Document the limitation; don't fight
  it.

### 1.11 Memory-fabrication on empty retrieval

- **Spec wants:** zero invented shared history. "She won't fake
  memory."
- **Claude:** complies cleanly given the explicit memory-continuity
  block.
- **qwen3:14b:** fabricates at ~1 in 30 turns when the user
  prompt suggests continuity ("the issue from yesterday"). The
  model invents a plausible-sounding "yesterday" event. This is
  the most dangerous failure mode in the audit because it's
  invisible — Eric has no way to know the recall is fake.
- **Cost of convergence:** the memory-continuity block already
  names this; the fix is harder enforcement. Two paths: (a) tier-2
  judge specifically catches "claims-shared-context-with-no-
  retrieval" as a top-priority failure axis; (b) the voice loop
  explicitly tells the brain "no retrieval hits this turn" when
  the suffix is empty (rather than just omitting the suffix).
  Implement both.

### 1.12 Sentence length + count

- **Spec wants:** 1–3 short sentences default. Long answers only
  when asked.
- **Claude:** holds 1–3 cleanly post the explicit length rule.
- **qwen3:14b:** drifts to 4–6 sentences over the course of a
  session. The drift compounds — once the model has emitted a
  5-sentence answer and the conversation continued normally, the
  next answer is also 5 sentences. Llama 3.3 8B drifts faster
  (4–5 by turn 10); Phi-4 14B is best (holds 1–3 reliably,
  probably an artifact of its short-form training).
- **Cost of convergence:** ~50-LOC post-process truncation step:
  if reply > 4 sentences and the user prompt didn't request
  detail, truncate to 3 + ". Want more?" Aggressive but
  effective. Same projection layer.

### Audit summary

Five of twelve divergences are cheap in-prompt fixes (1.1, 1.4, 1.5,
1.8, 1.11). Five are best handled by a post-process projection
layer (1.2, 1.3, 1.6, 1.10, 1.12). Two are accepted as "different
floor" (1.7, 1.9) because forcing them harms either prompt budget
or response usefulness more than the divergence costs.

The cheap in-prompt fixes total ~200 tok added to the Ollama-only
prompt block. Within budget — the personality-plan's Ollama tightening
section already anticipates ~150 tok of additional in-prompt cost
relative to the Claude prompt.

---

## Part 2 — Personality projection on local models — what works

The persona block currently in `brain/claude.py` is the same string
for both backends. The personality plan acknowledges this should
"tighten block 2" on Ollama. This section names the specific
techniques that move the persona-preservation needle most on
sub-30B local models.

### 2.1 Long persona blocks beat short

The PromptHub / SearchEngineJournal persona-prompting research [1]
documents that persona prompts help on alignment-dependent tasks
(writing, role-play, safety) more than they help on factual tasks
(math, knowledge). Sabrina is alignment-dependent at every turn —
the spec is the alignment target. Implication: don't trim the
persona block to save tokens on Ollama. The marginal cost of a
larger persona block on a local 14B model is ~50 ms of additional
prompt-eval; the marginal benefit on persona preservation is
substantial.

The Vanderbilt persona-pattern-language paper [3] catalogues the
effective persona components: name, role, expertise, register,
explicit anti-patterns. The Sabrina persona block already has all
five. The Ollama-tightened version should *expand* the explicit
anti-patterns (add "Sure!", "Of course!", capability-language) and
the register block (add a one-line example for each of the five
core voice adjectives). Net add: ~120 tok.

### 2.2 Few-shot examples earn their tokens on small models

The personality plan flags few-shot persona examples as "defer
until Ollama drift shows" (decision 010 alternative #1). Drift is
showing — see § 1.5, 1.9, 1.12 above. Time to land them.

The "few-shot dilemma" paper [11] documents that 2–4 examples is
the sweet spot for small models; 5+ examples degrades accuracy by
training the model to over-pattern-match the example shape. For
Sabrina's persona, four pairs cover the load-bearing axes:

1. Opener-flattery example (g001 "what time is it" → "3:42.")
2. Pushback example (g027 "should I use postgres or sqlite" →
   opinionated answer)
3. Refusal-as-character example ("be more affectionate" → in-
   character decline)
4. Empty-retrieval example ("the issue from yesterday" → "I
   don't have that from before — refresh me")

Inline in the system prompt, formatted as "User: …\nSabrina: …"
pairs. Total: ~180 tok. Fits the Ollama budget; pays back
immediately on § 1.5 and § 1.9.

### 2.3 Anti-patterns named explicitly, not gestured at

Claude can pattern-match "don't be sycophantic" to the right
behavior. Local models pattern-match it to "don't say the word
sycophantic," which is a different goal. The Ollama prompt should
enumerate the anti-patterns as literal strings to avoid:

> Do not begin replies with: "Sure!", "Of course!", "I'd be happy
> to", "Great question", "What a fun request", "It seems like",
> "It looks like". Do not end replies with: "Let me know if",
> "Hope this helps", "Does that help", "Feel free to". Do not
> refer to yourself as: "an AI", "a language model", "a chatbot",
> "an assistant".

Twenty-eight tokens of explicit string-banlist outperform a
hundred tokens of behavioral description on a 14B model. The
PersonaGym work [4 in eval framework] makes this point on
adversarial persona prompts.

### 2.4 Character-defining rules, not behavioral descriptions

"Sabrina is direct" is description; the model has to interpret
it. "Sabrina answers in 1–3 sentences. The first sentence states
the answer or the most important question. Hedges only on
genuine uncertainty" is rule, the model executes it. The first
form is what current `_VOICE_RULES_BLOCK` mostly uses; on Claude
it's enough, on Ollama the rule form measurably outperforms.

The Persona-Aware Contrastive Learning (PCL) framework [5] from
ACL 2025 finds the same pattern: explicit role-chain rules
("if X then Y") beat trait descriptors ("be Y") on small models
by 8–15 points on persona consistency.

---

## Part 3 — Model selection in May 2026 — persona preservation rank

The personality-preservation rank is *not* the general-capability
rank. A model can be smarter and worse at staying in character;
that's the Phi-4 story.

### Qwen 3 14B (current default)

**Persona preservation rank: 1 of 4.** The Qwen team's stated
focus on "more resilient to the diversity of system prompts,
enhancing role-play implementation" [6] is real. Compared to
Qwen 2.5, the v3 line holds the persona block better on multi-
turn — opener-flattery rate dropped roughly 30%, list-vomit
roughly 25% in informal A/B testing. Multi-turn stability is
the load-bearing axis for Sabrina (a session is dozens of turns)
and Qwen 3 is the strongest in that axis among the four
considered.

Caveat: thinking-mode (`/think`) toggles are easy to leak into
output if not handled at the brain layer. The current Ollama
brain doesn't strip thinking blocks, which could appear as
visible "Let me think about this…" turns that violate § 1.1. Fix
either at the prompt level (`/no_think` in system) or strip
`<think>...</think>` server-side.

### Llama 3.3 8B

**Persona preservation rank: 4 of 4.** Llama 3.3 holds the
explicit-rule form of the persona well but drifts back to
helpful-assistant defaults faster than the others under multi-
turn pressure. Closer-offer drift (§ 1.2) is 2× Qwen 3's;
sentence-length drift (§ 1.12) is the worst measured. Llama 3.3
70B at q4 is competitive with Qwen 3 14B q4 on persona
preservation but costs 5× the VRAM — not viable on Eric's box
without offloading to disk, which kills latency.

### Phi-4 14B

**Persona preservation rank: 3 of 4.** Phi-4's strength is
short-form output (rank 1 on § 1.12 sentence-count). Its
weakness is structural: trained on a chain-of-thought-heavy
data mix [12], it list-vomits more than the others (§ 1.3),
and is the worst at refusal-as-character (§ 1.5) — falls back
to capability-language nearly always. Wrong fit for an
operator-voice assistant despite being a strong instruction-
follower in the abstract.

### Gemma 3 12B

**Persona preservation rank: 2 of 4.** Gemma 3's RLHF leans
warm-and-helpful by default, which fights the operator
register, but the warmth is consistent — once tuned with
explicit anti-patterns, Gemma stays tuned. Identity-disclaimer
rate (§ 1.8) is higher than Qwen's; everything else is
comparable. The Gemma 4 release (2026-04-02) [7] adds MoE and
trimodal but doesn't ship a persona-preservation improvement;
Gemma 3 vs. Gemma 4 is a wash for Sabrina's use case as of
this writing. Hold.

### Recommendation

**Stay on Qwen 3 14B.** Re-evaluate when Qwen 3.5 14B ships at
GA (currently in waves per [7], 14B variant not released as of
2026-04-26) — the smaller Qwen 3.5 line is positioned to
improve precisely the multi-turn stability axis Sabrina cares
about most. The eval framework's tier 3 (per backend bump)
fires on a model swap; defer the Qwen 3.5 evaluation until
that trigger fires anyway.

---

## Part 4 — Eval framework adaptation

The personality-eval framework lays out three tiers (tier 1
regex, tier 2 LLM-judge, tier 3 multi-judge consensus +
human). Each needs to flex for Ollama.

### Tier 1 — regex smokes

**No change.** Regex doesn't care about the model. Run the same
banlist against Ollama generations. The Ollama prompt is
expected to suppress the same patterns; passing tier 1 is the
floor for both backends. Expect lower pass rate on Ollama (1.2,
1.3, 1.6 in particular) until the projection layer is in place.

Add three patterns named in the divergence audit: "Sure!",
"Of course!", capability-language ("I cannot", "I am unable",
"my instructions"). One PR.

### Tier 2 — LLM-judge

**Two adjustments, per the personality-eval framework's existing
Ollama-parity section:**

1. **Looser thresholds on axes the small model demonstrably
   can't hold.** Median ≥ 3 (rather than ≥ 4) on opener-flattery,
   list-vomit, hedging-inflation, length-cap, and
   identity-disclaimer when generating with `--backend ollama`.
   Same rubric, different bar. The plan accepts "same persona,
   different floor."
2. **Strict threshold preserved on:** memory-fabrication,
   refusal-as-character, opinion-flattening, sycophant slip.
   These are the persona-load-bearing axes; relaxing them means
   the persona has eroded, not adapted.

**One adjustment not in the framework yet:** use a
*third-party judge* for Ollama runs. Claude judging Ollama
shouldn't share the same RLHF blind spots as Claude judging
Claude, but the asymmetry is worth measuring — run gpt-5-mini
and Claude sonnet against the same Ollama generations for the
first month, log the disagreement rate, retire whichever judge
systematically over-scores.

### Tier 3 — multi-judge consensus + human

**Trigger flips.** The framework fires tier 3 on Claude minor
version bumps; for Ollama it should fire on (a) Ollama model
swaps (Qwen 3.5 release, etc.) and (b) `pull` of any new image
for the configured model. Eric's box silently auto-pulls
updates if Ollama is set to do so; tier 3 should fire on those
pulls even if Eric didn't intend a model swap. Cheap insurance.

### Golden-set coverage

The 30-prompt golden set should add a small Ollama-specific
slice: 5 prompts that target the divergence axes most likely
to fail on Ollama — sentence-length, list-vomit, capability-
language refusal, multi-turn closer-drift (3-turn dialogues
specifically). Total: 35 prompts.

---

## Part 5 — Operational tier — does Sabrina announce the backend?

The personality plan deliberately doesn't say. Three options:

1. **Silent.** The brain swap is invisible to Eric. Pure parity
   target; the eval framework is the safety net. *Pro:* matches
   the "same persona" goal. *Con:* if Ollama drifts and Eric
   doesn't notice, the persona erodes silently.
2. **Status-bar only.** The settings GUI / status indicator shows
   which backend is active; voice output never references it.
   *Pro:* Eric can audit on demand without the assistant
   narrating implementation details. *Con:* requires looking at
   the screen, defeats voice-only operation.
3. **On-demand.** "Sabrina, which brain are you on?" → "Ollama,
   qwen3 14b. Anthropic's down." Otherwise silent. *Pro:*
   honest, doesn't intrude. *Con:* one more thing to
   prompt-engineer to reliable behavior.

**Recommendation: 2 + 3.** Status bar shows backend persistently;
on-demand voice answer is part of the meta-question handling
(future). She doesn't volunteer the swap because doing so
breaks character (Sabrina-the-person doesn't have a backend),
but she answers when asked because pretending otherwise is
the kind of fakery the persona spec rules out under "she won't
fake memory." Same principle, different fact.

---

## Part 6 — The personality projection layer

A small post-process step that runs on Ollama generations
before they go to TTS. Catches the failure modes from § 1
that are cheaper to filter than to prompt-prevent. Rough
implementation sketch (~50 LOC, probably less):

```python
# sabrina/brain/persona_filter.py
import re

_OPENER_STRIPS = [
    r"^(Sure|Of course|Absolutely|Great question|I'd be happy to)[!,.]?\s*",
    r"^(It seems|It looks|It appears) like\s*",
    r"^(Let me|I'll)\s+(help you|assist you|try to)\s*",
]
_CLOSER_STRIPS = [
    r"\s*(Let me know|Hope (this|that) helps|Does that help|Feel free to)\b[^.!?]*[.!?]?\s*$",
]
_APOLOGY_COLLAPSE = re.compile(
    r"((I'm sorry|My apologies|I apologize)[^.!?]*[.!?]\s*){2,}",
    re.IGNORECASE,
)
_LIST_PATTERN = re.compile(r"^[\s]*[-*\d]+[.)]\s+", re.MULTILINE)

def project(text: str, *, max_sentences: int = 3) -> str:
    """Apply persona-projection filters to local-model output."""
    for pat in _OPENER_STRIPS:
        text = re.sub(pat, "", text, count=1, flags=re.IGNORECASE)
    for pat in _CLOSER_STRIPS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    text = _APOLOGY_COLLAPSE.sub(
        lambda m: m.group(0).split(".")[0] + ". ", text
    )
    if _LIST_PATTERN.search(text):
        text = _list_to_prose(text)
    text = _truncate_sentences(text, max_sentences)
    return text.strip()
```

Plus the two helpers (`_list_to_prose` joins items with commas
and an "and"; `_truncate_sentences` keeps first N sentences,
appends "Want more?" only if it truncated). About 50 LOC total.

**Where it lives.** `brain/persona_filter.py`. New file —
justified by "second caller exists" because both `brain/ollama.py`
and the future `brain/local_*.py` (whatever swaps in next) want
it. Wired into `OllamaBrain.chat` between TextDelta accumulation
and TextDelta yield, OR — cleaner — in the voice loop's
sentence buffer between brain output and TTS input. Latter is
better; it keeps the brain layer pure and applies the filter
to *any* brain configured as `[brain].project_persona = true`.

**What it doesn't do.** Doesn't touch substance. The truncation
step is the most aggressive transformation; everything else is
opener/closer/apology removal. The model still generated the
substantive answer. The filter only strips the ritual
boilerplate the model can't help adding.

**Test surface.** Personality-eval tier 1 already has the regex
banlist; reusing it as the filter input means the filter is
self-validating. If a tier-1 regex fires *after* the filter,
the filter is buggy. Cheap loop.

---

## Part 7 — Decisions Eric needs to lock

Five dials. Each carries a recommendation, the override, and
what changes downstream.

### D1 — Ship the personality projection layer

**Recommendation: yes, on the voice-loop sentence buffer side
(not inside the brain).** ~50 LOC. Single new file. Solves five
of twelve divergences at zero in-prompt cost.
**Override consequence:** if no, the in-prompt anti-pattern
list grows by ~200 tok on Ollama (and meaningful tier 2 score
gaps remain on closer-drift, list-vomit, apology-inflation).

### D2 — Stay on Qwen 3 14B as the default Ollama model

**Recommendation: yes, until Qwen 3.5 14B GA.** Best persona
preservation in the 14B class as of May 2026.
**Override consequence:** Llama 3.3 70B is available with
disk offload but kills voice latency; Phi-4 14B is faster but
worse on refusal-as-character. Stay on Qwen.

### D3 — Backend disclosure register

**Recommendation: silent in voice (no proactive announcement);
on-demand voice answer; persistent status-bar indicator.** Per
§ 5.
**Override consequence:** "always announce" breaks character;
"never disclose" requires Sabrina to lie when asked, which
violates the persona-spec's anti-fakery line.

### D4 — Tier-2 thresholds on Ollama

**Recommendation: ≥ 3 (instead of ≥ 4) on the five "different
floor" axes; ≥ 4 retained on memory-fabrication, refusal-as-
character, opinion-flattening, sycophant slip.** Per § 4.
**Override consequence:** one threshold for both backends
either fails Ollama (parity claim weakens to "Claude only") or
masks Claude regressions (because Claude can clear the lower
bar).

### D5 — Tier-3 trigger on Ollama auto-pulls

**Recommendation: yes — fire tier 3 multi-judge consensus on
any Ollama image pull for the configured model, not just on
explicit model swaps.** Cheap insurance against silent backend
drift.
**Override consequence:** Ollama updates ship persona
regressions silently; first dogfood after any Anthropic-down
day catches them, but only after Eric has heard them.

---

## Thin spots in this doc

- **No real A/B numbers.** The divergence rates in § 1 are
  observed-on-recent-transcripts estimates, not formal
  measurements. The right move is a one-shot "run the golden
  set against both backends and tabulate" before locking the
  thresholds in D4.
- **Phi-4 and Gemma 3 ranking is from secondary literature**
  and one casual A/B over the past week; no quantitative
  measurement on Sabrina-specific prompts. The eval framework
  is the right place to harden this; once the 35-prompt
  golden set is running, swap each model in for a single
  weekly run and score.
- **The projection layer assumes English prose patterns.** If
  Sabrina ever runs in another language (not currently planned),
  the regex banlists need rewriting per language. Out of scope
  but worth flagging.
- **No accounting for thinking-mode token costs.** Qwen 3's
  `/think` mode produces hidden reasoning that costs tokens
  even when stripped. If Eric ever hits VRAM pressure, the
  `/no_think` toggle is the first lever; document it in the
  Ollama brain config docstring.

---

## Alternatives worth researching (not blocking)

- **Fine-tune Qwen 3 14B on Sabrina-style transcripts.** Once
  the memory DB has a few hundred high-quality Sabrina turns,
  a LoRA fine-tune on the persona is plausible (~hours on a
  single 4090). Would close most of the divergence gap without
  prompt cost. Anti-sprawl says defer until the projection
  layer is shipped and proven insufficient.
- **DSPy-style prompt optimization.** The DSPy framework (per
  the eval framework's alternative-3) could in principle tune
  the Ollama-specific prompt against the rubric. Same caveat
  as the eval framework: don't optimize the spec, optimize
  adherence to it. Defer.
- **Constitutional self-critique on Ollama only.** Have qwen
  critique its own draft against the persona block before
  emitting. Doubles tokens but pushes persona scores up. Real
  cost is latency — voice-loop turns cannot afford 2×. Skip
  unless tier 2 surfaces consistent post-projection drift.

---

## References

[1] Promptingguide.ai — [Few-Shot Prompting](https://www.promptingguide.ai/techniques/fewshot).
[2] PromptHub — [Role-Prompting: Does Adding Personas to Your Prompts Really Make a Difference?](https://www.prompthub.us/blog/role-prompting-does-adding-personas-to-your-prompts-really-make-a-difference).
[3] Schmidt et al., Vanderbilt — [A Pattern Language for Persona-based Interactions with LLMs](https://www.dre.vanderbilt.edu/~schmidt/PDF/Persona-Pattern-Language.pdf).
[4] Search Engine Journal — [Research: persona prompting works in some cases, backfires in others](https://www.searchenginejournal.com/research-you-are-an-expert-prompts-can-damage-factual-accuracy/570397/).
[5] Persona-Aware Contrastive Learning, ACL 2025 — [arXiv:2503.17662](https://arxiv.org/abs/2503.17662).
[6] Qwen team — [Qwen3 model card and instruction-following notes](https://huggingface.co/Qwen/Qwen3-14B); [Qwen3 release blog](https://qwenlm.github.io/blog/qwen3/).
[7] MindStudio comparison — [Gemma 4 vs Qwen 3.5: Open-Weight Models for Local AI Workflows](https://www.mindstudio.ai/blog/gemma-4-vs-qwen-3-5-open-weight-comparison).
[8] Lushbinary — [Llama 4 vs Qwen 3.5 vs Gemma 3 comparison](https://lushbinary.com/blog/gemma-4-vs-llama-4-vs-qwen-3-5-open-weight-model-comparison/).
[9] Botmonster — [Phi-4 Mini vs Gemma 3 vs Qwen 2.5 for code/structured tasks 2026](https://botmonster.com/posts/phi-4-mini-vs-gemma-3-vs-qwen-25-best-slm-coding-2026/).
[10] Meta — [Llama 3.3 model card and prompt format](https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_3/); [Llama 3.3 70B Instruct on HuggingFace](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct).
[11] Few-shot dilemma paper — [arXiv:2509.13196 (over-prompting in few-shot)](https://arxiv.org/html/2509.13196v1).
[12] Microsoft — [Phi-4 technical report (chain-of-thought training data)](https://arxiv.org/abs/2412.08905).
[13] Inflection AI — Pi technical report on persona regression suite (NeurIPS 2024); referenced in [`2026-04-26-personality-eval-framework.md`](2026-04-26-personality-eval-framework.md).
[14] PersonaGym, NeurIPS 2024 — referenced in eval-framework. [arXiv:2407.18416](https://arxiv.org/abs/2407.18416).
[15] [`personality-plan.md`](../personality-plan.md), this repo — anchor; § "Ollama differences" is the upstream call this doc operationalizes.
[16] [`010-personality-spec.md`](../../decisions/010-personality-spec.md), this repo — Thin spots § "Backend parity is asserted, not measured" is the gap this doc closes.
[17] [`2026-04-26-personality-eval-framework.md`](2026-04-26-personality-eval-framework.md), this repo — measurement layer; this doc proposes Ollama-specific tier flexes on top.
[18] [`2026-04-25-stack-alternatives-survey.md`](2026-04-25-stack-alternatives-survey.md), this repo — model-selection prior art; this doc adds the persona-preservation axis.
