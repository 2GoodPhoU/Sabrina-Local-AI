# Decision 010: Personality spec — who Sabrina is

**Date:** 2026-04-25

## Summary

Sabrina's voice is locked. Operator register, not customer-service.
Three open questions resolved with recommendations and override
knobs. A concrete system-prompt skeleton — actual block text, token
budgets, cacheable vs. dynamic markings — now lives in
`rebuild/drafts/personality-plan.md` under "System-prompt skeleton
(concrete)." That's what `voice_loop._SYSTEM` becomes once the
`system_suffix=` plumbing from `budget-and-caching-plan.md` ships.

The spec is upstream of every brain prompt and the avatar cue
track. Drift here costs more than drift anywhere else; the plan
calls that out and so does this doc.

## Resolutions

| Question | Recommendation |
|---|---|
| Profanity register | Mirror Eric. Never first turn of a session. |
| Pronouns           | she/her. No volunteered gender statement. |
| Opinions           | Hold technical opinions; push back when asked or load-bearing; non-committal on politics and contested values. |

Each carries a "why" line and an "override knobs" line in the plan.
An override changes one paragraph in the plan and one slogan in
this doc — nothing else cascades.

## What this commits us to

- The voice in `voice_loop._SYSTEM` (and any future Brain caller)
  shifts from "helpful, concise personal assistant" generic to the
  Sabrina-specific persona + voice rules from the skeleton.
- Anti-patterns are enumerated, not just felt. The system prompt
  can name them ("don't open with 'I'd be happy to'") instead of
  hoping the model infers them.
- Memory-continuity behavior is principled: retrieved turns are
  context, not dialogue; no "I remember everything we've talked
  about" pronouncements; references show up as behavior, not
  announcement.
- Audience register has three modes (A/B/C). A is default; B is
  ambient-detection-driven (future); C is `sabrina professional
  on` (CLI/GUI toggle).
- Cue-track vocabulary lives in the system prompt only when the
  avatar is on AND the backend is Claude. Ollama runs tag-free,
  state-driven animation picks up the slack.

## What stays open

- **"Dry humor as default."** Remains an inferred trait. The
  decision docs are dry-as-in-not-emotive; they don't actually
  contain jokes. The plan's updated "Where signals came from"
  section flags this honestly. If wrong, the fix is one line in
  voice rules + dialing back `amused`-leaning gestures.
- **Vision-turn system prompt.** `DEFAULT_VISION_SYSTEM_PROMPT` in
  `vision/see.py` doesn't yet pull in the persona block. Out of
  scope for the first ship of the skeleton; folded in on the next
  vision touch.
- **Block 5 (tool-use rules).** Reserved. `tool-use-plan.md`
  populates it when tool support lands.
- **Cache-floor non-issue.** Until either tools ship or the cue
  vocabulary lands alongside avatar, the cacheable head is below
  Anthropic's 1024-token cache floor; caching is inert by design.
  Documented in the skeleton's token-budget table.

## Ship criterion

> A fresh voice-loop session, mid-conversation, replies in 1–3
> short sentences without "I'd be happy to," "Great question," or
> a closing "Let me know if…"; refers back to a prior session via
> retrieval when retrieval has hits, and stays clean of "I
> remember…" pronouncements when it doesn't.

Validate manually on the first dogfood after commit. Fold any
drift back into the plan, not the prompt.

## Where to look in the plan

- Recommendations on open questions: `personality-plan.md` →
  "Recommendations on open questions."
- System-prompt skeleton with token budgets:
  `personality-plan.md` → "System-prompt skeleton (concrete)."
- Voice signals (explicit vs. assumed): `personality-plan.md` →
  "Where these signals came from — explicit vs. assumed."
- Anti-patterns to bake in: `personality-plan.md` →
  "Anti-patterns to actively avoid."

## Thin spots

- **Backend parity is asserted, not measured.** "Eric shouldn't be
  able to tell which backend is answering from tone alone" is the
  goal for blocks 1–3 across Claude and Ollama; first dogfood is
  the test. If qwen2.5:14b can't hold the persona without dropping
  to list-vomit, block 2 widens for Ollama and the parity claim
  weakens to "same persona, different floor."
- **`chat._SYSTEM` (text REPL) is a separate string today.** The
  REPL prompt is shorter and allows light markdown. Either it
  reuses block 1 only (persona) and keeps its own voice rules, or
  the skeleton grows a "REPL" mode. Pick at implementation time.
- **No automated test for the negative-anti-pattern list.** The
  enumerated openers and closers are easy to grep for in transcripts
  but not currently asserted anywhere. A tiny "did the last reply
  contain 'I'd be happy to'" smoke could land alongside the prompt
  if the dogfood surfaces drift.

## Alternatives worth researching

1. **Few-shot persona examples in-prompt.** Two or three
   before/after pairs (already enumerated in the plan) inlined as
   exemplars. Costs ~150 tok on the cacheable head; pays back on
   small-model parity. Defer until Ollama drift shows.
2. **Persona evals.** A handful of fixed prompts run against both
   backends, scored against the anti-pattern list. Lightweight; the
   real question is whether eval harness complexity is worth it for
   a single-user assistant.
3. **Mode switching as system-prompt swap, not block-level edit.**
   Cleaner than mutating block 3 in place; costs a cache miss per
   toggle but simplifies the implementation. Trade documented in
   the skeleton; revisit if toggle frequency rises.

## Where the changes live

```
rebuild/
├── drafts/
│   └── personality-plan.md       # OPEN-QUESTIONS reframed,
│                                  # signals section updated,
│                                  # +"System-prompt skeleton (concrete)"
└── decisions/
    └── 010-personality-spec.md   # this file
```

No source files were touched in this track.

## One thing to feel good about

Eric's working-style guardrails (anti-sprawl, ship-one-validate-
next, no-new-abstraction-without-second-caller) translated cleanly
into a conversational register without forcing a stance the docs
hadn't already taken. The plan's biggest risk — "voice inferred,
not stated" — is now flagged honestly in the plan and called out
as the first calibration step in `ACTION_ITEMS_personality.md`,
rather than papered over.

## Next

When Eric signs off:

1. In a separate session, lift the skeleton blocks into
   `voice_loop._SYSTEM` and `chat._SYSTEM`, and add the
   `system_suffix=` plumbing if `budget-and-caching-plan.md`
   hasn't shipped yet.
2. Smoke test + first dogfood; surface any drift back into the
   plan, not the prompt.
