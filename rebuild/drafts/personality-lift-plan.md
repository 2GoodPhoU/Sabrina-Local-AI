# Personality lift — implementation plan

**Date:** 2026-04-25
**Status:** Draft, awaiting Eric's eyeball-review.
**Upstream:** [`personality-plan.md`](personality-plan.md) (the spec) +
[`010-personality-spec.md`](../decisions/010-personality-spec.md) (the
shipped decision).
**Owner of the lift session:** Claude. Eric's job is to glance the four
open questions below + flag anything off.

## The one-liner

Replace the two ~5-line generic system prompts (`voice_loop._SYSTEM`,
`chat._SYSTEM`) with the System-prompt skeleton from
`personality-plan.md`. Don't touch the Brain protocol. Don't touch
vision. Ship a tiny anti-pattern smoke test so future drift fails loud.

## Why this plan exists

`010-personality-spec.md` shipped the *spec*. The actual prompt strings
in code still read "You are Sabrina, a helpful, concise personal
assistant…" — generic-helpful-AI voice, no anti-pattern callouts, no
operator register. Every reply Sabrina has produced through 009/009a
validation has been against the wrong prompt. That's the gap this
session closes.

The personality plan calls out two places this lift could go wrong:

1. **Voice was inferred, not stated.** "Dry humor as default" is an
   extrapolation from the decision-doc voice. The lift bakes it in;
   first dogfood is the calibration.
2. **`system_suffix=` plumbing doesn't exist yet.** The skeleton
   assumes Block 7 (retrieval suffix) ships separately so it stays
   out of the cacheable head. Today everything goes through `system=`.
   See open question 2.

## What changes (file by file)

### `sabrina-2/src/sabrina/voice_loop.py`

Replace the existing `_SYSTEM` constant (lines 51-56) with an
assembled-at-import-time string built from blocks 1+2+3+6 of the
skeleton. Block 4 (cue track) is dropped until avatar ships. Block 5
(tool use) is empty until tool-use ships. Block 7 (retrieval suffix)
continues to be concatenated per-turn (`turn_system = _SYSTEM +
"\n\n" + retrieval_block`) as today — see open question 2.

Add a small helper:

```python
def _build_system_prompt(*, register: str = "A", with_cues: bool = False) -> str:
    """Assemble the cacheable head of the system prompt.

    register: "A" (Eric alone, default), "B" (someone else), "C" (professional).
    with_cues: include the avatar cue-track vocabulary block. Off by default;
               enabled when [avatar].enabled is true (avatar ships in a
               separate session).
    """
    parts = [_BLOCK_PERSONA, _BLOCK_VOICE_RULES, _BLOCK_REGISTER.format(register=register)]
    if with_cues:
        parts.append(_BLOCK_CUE_VOCAB)
    parts.append(_BLOCK_MEMORY_CONTINUITY)
    return "\n\n".join(parts)


_SYSTEM = _build_system_prompt()
```

Keeps the module-level constant for callers that don't care about
register; the helper is there for the future toggle.

### `sabrina-2/src/sabrina/chat.py`

Replace `_SYSTEM` (lines 26-30) with persona + voice-rules-text-edition
+ memory-continuity. Skip register (REPL is single-user-text by
definition) and cue track (text). Voice-rules-text-edition is a small
adaptation: drop "Output is spoken aloud" (REPL renders text), allow
light markdown for code blocks (the plan flags this in thin-spots
under `chat._SYSTEM` as "REPL prompt is shorter and allows light
markdown"), keep all the negative anti-patterns.

Two flavors of block 2 emerge: `_BLOCK_VOICE_RULES_SPEECH` (current,
used by voice_loop) and `_BLOCK_VOICE_RULES_TEXT` (new, used by chat).
Both share the same 15 anti-pattern bullets; they differ on the
markdown rule and the "spoken aloud" framing.

To avoid copy-paste drift between them, a single
`_block_voice_rules(channel: Literal["speech", "text"])` builder lives
in a new tiny module: `sabrina/personality.py` (~80 lines). See
**Anti-sprawl note** below.

### `sabrina-2/src/sabrina/personality.py` (NEW, ~80 lines)

Houses the 5 block constants + the `_build_system_prompt` and
`_block_voice_rules` builders. Both `voice_loop` and `chat` import
from here. The Ollama-tightening (open question 4) lives here too via
a `backend: Literal["claude", "ollama"]` parameter on
`_build_system_prompt`.

**Anti-sprawl check.** Two callers (voice_loop, chat) exist before
this module ships — that clears guardrail #2. Vision-turn (open
question 3) becomes the third caller if Eric picks "fold persona block
in." Without the new module, the same 5 block strings would live
duplicated across voice_loop and chat, with no clean way to share the
voice-rules variants — that's a worse outcome than the new file.

The header docstring justifies the module against the 300-line
guardrail and points at the personality plan as the source of truth
("if voice shifts, it shifts there first" — quoted from the plan).

### `sabrina-2/src/sabrina/vision/see.py`

**Default: untouched** (per open question 3 recommendation). If Eric
picks "fold persona block in," `DEFAULT_VISION_SYSTEM_PROMPT` becomes
`_BLOCK_PERSONA + "\n\n" + DEFAULT_VISION_SYSTEM_PROMPT_BODY`, where
`DEFAULT_VISION_SYSTEM_PROMPT_BODY` is the existing screenshot-handling
text. Adds ~140 tok per vision turn for the persona consistency.

### `sabrina-2/tests/test_smoke.py`

Three new tests, ~30 lines:

```python
def test_system_prompt_contains_no_anti_patterns():
    """Loud failure if the generic-helpful-AI prompt sneaks back in."""
    from sabrina.voice_loop import _SYSTEM
    forbidden = [
        "I'd be happy to",
        "Great question",
        "Let me know if",
        "As an AI",
        "As a helpful assistant",
        "It seems like",
        "I would be happy",
    ]
    for phrase in forbidden:
        assert phrase not in _SYSTEM, f"anti-pattern in _SYSTEM: {phrase!r}"


def test_system_prompt_contains_persona_anchor():
    """The persona block must land — not just generic prose."""
    from sabrina.voice_loop import _SYSTEM
    assert "Sabrina" in _SYSTEM
    assert "Eric" in _SYSTEM
    # Operator register marker:
    assert "Operator voice" in _SYSTEM or "operator" in _SYSTEM.lower()


def test_chat_system_prompt_drops_register_block():
    """REPL has no audience modes; the register block doesn't apply."""
    from sabrina.chat import _SYSTEM
    assert "Current register" not in _SYSTEM
    assert "Register A" not in _SYSTEM
```

Cheap. Catches the regression where someone re-introduces the old
generic prompt or an LLM-assisted refactor "simplifies" the persona
back to neutral.

### `sabrina-2/sabrina.toml`

No changes. Mode toggles (`professional on/off`, `[avatar].enabled`)
are read from existing config; the helper just routes on values.

### `sabrina-2/src/sabrina/config.py`

No changes. The new config knobs the plan eventually wants
(`personality.profanity = "mirror" | "never" | "always"`,
`personality.pronouns = "she" | "they" | "none"`, `personality.opinions
= "loose" | "default" | "strict"`) are deferred — the lift bakes the
recommended defaults into the prompt strings themselves. If Eric wants
runtime overrides later, the helper grows a `personality_overrides=`
kwarg and reads from a new `PersonalityConfig` block. ~30-line
follow-up; doesn't block the lift.

## Open questions

### Q1 — `chat._SYSTEM` scope: persona-only, full skeleton, or minimal?

**Recommendation: persona (block 1) + voice-rules-text-edition (block
2 adapted) + memory continuity (block 6). Skip block 3 (audience
register) and block 4 (cue vocabulary).** ~270 tok vs voice_loop's
~440. Reasoning: REPL is text + Eric-only by definition. Audience
modes don't apply (REPL never has someone-else-in-the-room mode), cue
vocabulary is meaningless for text output.

**Why this is the right cut:**

- Persona is upstream of everything; it has to land in both channels
  or backend tone diverges in a way Eric will notice and dislike.
- Voice rules carry the anti-patterns that matter just as much in text
  as in speech. The "Output is spoken aloud" line is the only one that
  doesn't translate; the markdown line gets relaxed for code blocks.
- Memory continuity stays because the REPL also pulls semantic
  retrieval (`chat.py:run_repl` calls `memory.load_recent` and the
  brain sees retrieved hits via the same path).

**Override knobs:**

- "Lift everything" — include blocks 3, 4, 6 anyway. Cost: ~120 extra
  tok per turn, no behavior change in text channel.
- "Minimal" — block 1 only. Cost: regressions on anti-patterns leak
  into REPL replies; first dogfood would surface them.

### Q2 — `system_suffix=` plumbing: ship now, defer, or additive-kwarg-only?

**Recommendation: defer.** Concatenate the retrieval block into
per-turn `system=` as today. The personality plan's own token-budget
analysis says caching is inert below the 1024-tok floor, and the
cacheable head sits at ~440-870 tok depending on flags. Until tool-use
ships and pushes the head above the floor, `system_suffix=` plumbing
delivers zero observable benefit.

**Why defer:**

- Anti-sprawl rule #2: no new abstraction without a second caller.
  `system_suffix=` has zero callers today and one speculative caller
  (post-tool-use). One isn't enough.
- Touching the Brain protocol in the personality lift session pulls
  in the CancelToken thread (decisions 009/009a) and the Ollama-vs-
  Claude divergence — risk per line of touched code is high.
- The plan itself documents the cache-floor non-issue under "Cache-
  floor non-issue" in 010-personality-spec — this is the call.

**Override knobs:**

- "Ship as additive Brain kwarg now" — add `system_suffix: str | None
  = None` to the protocol and both backends; ClaudeBrain concatenates
  to `system=`, OllamaBrain prepends to the system message. ~30 lines
  + tests. Future-proofs but pays no current cost.
- "Bundle with budget-and-caching plan" — the natural home for it. The
  budget plan already accounts for `system_suffix=` in its design.
  Cleaner to ship there alongside the cache-friendliness work that
  actually motivates it.

### Q3 — Vision-turn integration: defer, fold persona in, or full lift?

**Recommendation: defer.** Per the personality plan: "Out of scope for
the first ship of the skeleton; folded in on the next vision touch."
Vision turns use a separate fresh ClaudeBrain (per decision 005), so
they don't share `_SYSTEM` automatically — folding the persona in
requires either (a) refactoring vision's brain construction to accept
a base prompt or (b) hardcoding `_BLOCK_PERSONA` into
`DEFAULT_VISION_SYSTEM_PROMPT`. Both work; neither is the lift session's
business.

**Why defer:**

- Vision turns are rare (Eric triggers them explicitly via voice phrase
  or hotkey). Personality drift on vision turns matters less than on
  the conversational path.
- The existing `DEFAULT_VISION_SYSTEM_PROMPT` already enforces the
  one anti-pattern that matters most for vision ("Keep the reply to
  1-3 sentences"). The persona/anti-pattern gap is real but not
  blocking.
- Vision-polish-plan.md is a separate plan awaiting sign-off. Folding
  this in *there* lets it benefit from the window-capture / OCR work
  that plan ships.

**Override knobs:**

- "Fold persona block in" — `DEFAULT_VISION_SYSTEM_PROMPT = _BLOCK_PERSONA
  + "\n\n" + DEFAULT_VISION_SYSTEM_PROMPT_BODY`. ~5-line change. No
  refactor. Cost: ~140 tok per vision turn for tone consistency.
- "Full lift" — refactor vision to use the same skeleton helper. ~50
  lines. Couples vision to personality module; loses standalone-ness.

### Q4 — Ollama tightening + anti-pattern smoke test scope

**Recommendation: ship both. Ollama tightening is one helper kwarg;
smoke test is 30 lines.**

**Ollama tightening.** Per the personality plan: "Tighten block 2 —
smaller models default harder to list-vomit and 'Let me know if…'
closers, so keep the negative examples and shorten the positive
ones." Implementation is one kwarg on `_build_system_prompt`:

```python
def _build_system_prompt(*, backend: str = "claude", register: str = "A", with_cues: bool = False) -> str:
    voice_rules = _BLOCK_VOICE_RULES if backend == "claude" else _BLOCK_VOICE_RULES_OLLAMA_TIGHT
    ...
```

`_BLOCK_VOICE_RULES_OLLAMA_TIGHT` keeps all the negative bullets,
collapses the positive ones into a single "Default reply: 1-3 short
sentences. One idea per sentence. No markdown, lists, or apologies."
~50 tok shorter; all the load-bearing anti-pattern guidance survives.

The voice loop knows which backend it's calling on (passes `brain`
in) so the per-turn prompt assembly picks the right variant.

**Anti-pattern smoke test.** Already specified above. Three test
functions, ~30 lines. The single most important regression guard —
catches the "someone re-simplified the prompt" case the plan calls
out as a thin spot.

**Override knobs:**

- "Smoke only" — ship the test, defer Ollama tightening. Risk: first
  qwen2.5 dogfood shows list-vomit and the fix is one session away.
  Reasonable if you'd rather measure first.
- "Tightening only" — skip the smoke test. Loses the regression
  guard. Not recommended.
- "Neither" — Claude-only ship, no test. Fastest. Highest drift risk.

## Implementation order

1. **Add `personality.py`** with the 6 block constants + the
   `_build_system_prompt(backend, register, with_cues)` helper +
   `_block_voice_rules(channel)`. ~80 lines.
2. **Refactor `voice_loop._SYSTEM`** to import from personality. The
   voice loop also needs to pass `backend=brain.name` per turn so the
   per-backend assembly works. The existing per-turn `turn_system =
   _SYSTEM` line at voice_loop.py:377 becomes `turn_system =
   _build_system_prompt(backend=turn_brain.name, ...)`. Keep
   `_SYSTEM` as a module-level constant for the backward-compat case
   (Claude default).
3. **Refactor `chat._SYSTEM`** similarly — `_build_system_prompt(channel="text",
   backend=brain.name)` (channel kwarg routes to the text-edition voice
   rules + skips register/cue blocks).
4. **Add the 3 smoke tests** to `tests/test_smoke.py`.
5. **Run `uv run pytest -q`.** Expect +3 tests passing.
6. **Manual smoke**: `sabrina chat`, ask "what's 2+2?". Expect a
   ≤3-sentence reply with no "I'd be happy to" / "Great question" /
   trailing offer.
7. **Decision doc**: write `rebuild/decisions/011-personality-lift-shipped.md`
   in the voice of 002-009. Reference 010-personality-spec.md as the spec.
8. **Update ROADMAP.md**: bump the open question
   "Next infra vs. character step?" — the character side has its first
   ship.

Estimated session length: 1.5-2 hours assuming Eric signs off on the
recommendations as-is.

## Validation

This is a refactor, not a feature, so the gating procedure is the
test suite + a one-shot manual smoke. No `validate-*.md` doc needed
(matches the B1 logging-vocabulary precedent — the test suite gates
it).

**Manual smoke after the lift commits:**

1. `cd sabrina-2 && uv run pytest -q` — expect ~99 passing (+3 from
   smoke tests).
2. `sabrina chat` (Claude backend, default):
   - "what's 2+2?" → expect ≤3 sentences, no "I'd be happy to / Great
     question / Let me know if".
   - "any thoughts on the rebuild?" → expect a real opinion, not a
     hedge-and-list-options.
   - "what was the last thing we talked about?" → expect either a
     specific reference if memory has hits, or a short "nothing recent
     in memory" without a "let me check" wind-up.
3. `sabrina chat --brain ollama` (qwen2.5:14b):
   - Same 3 prompts. The Ollama variant should hold the persona — Eric
     shouldn't be able to tell which backend is answering from tone.
     (Plan's parity claim. First dogfood is the test.)
4. `sabrina voice` (PTT mode):
   - One short interaction. Listen for tone — "Operator, not customer-
     service." If the reply opens with "I'd be happy to," the smoke
     test should have caught it; if it didn't, add the missing
     anti-pattern phrase to the test.

Drift-handling per spec ("fold any drift back into the plan, not the
prompt"): if the first dogfood surfaces an anti-pattern not in the
list, add it to `_BLOCK_VOICE_RULES`'s negative bullets *and* to the
smoke test.

## Thin spots

- **"Dry humor as default" remains assumption.** This lift can't
  validate it — only first dogfood can. The plan flags this honestly
  in "What stays open." If wrong, fix is one line in `_BLOCK_VOICE_RULES`
  + dialing back the Ollama tightening.
- **Prompt token cost grows from ~50 → ~440 for voice_loop, ~30 → ~270
  for chat.** Real cost: ~$0.001 extra per Claude turn (Sonnet pricing,
  spec'd cacheable but caching inert below floor). Negligible against
  the $0/month target. Adds ~50 ms to first-token on Ollama turns
  (qwen2.5 prompt-eval is ~10K tok/s on a 4080).
- **No runtime override for the personality knobs.** Profanity,
  pronouns, opinions are baked into the prompt strings. Eric can edit
  the constants, but there's no `sabrina settings personality
  profanity = never` path. Follow-up if wanted.
- **Register toggle isn't wired.** `_build_system_prompt` accepts
  `register=` but nothing calls it with B or C — the voice loop
  always passes A. Wiring B (someone-else-in-room ambient detection)
  is in `personality-plan.md` as "future"; wiring C (`sabrina
  professional on` CLI/GUI toggle) is a 5-line follow-up.

## Alternatives worth researching

1. **Per-message persona injection vs. system-prompt-only.** Today
   the persona lives in the `system=` kwarg. Some reports suggest
   smaller models (qwen2.5:7b in particular) follow persona better
   when it's also reinforced in a "prefix" injected into the user
   message. Cheap experiment if Ollama parity falls short on first
   dogfood; ~30 lines + a config knob.
2. **Persona evals.** A handful of fixed prompts run against both
   backends, scored against the anti-pattern list. The plan flags
   this as alternative #2; revisit if dogfood-driven calibration
   feels too slow.
3. **Cache-friendly assembly.** When tool-use ships and pushes the
   cacheable head above 1024 tok, the assembly currently rebuilds
   the prompt string every turn. Switch to caching the assembled
   string per `(backend, register, with_cues)` tuple — trivial
   `@functools.lru_cache(maxsize=8)` on the helper.

## Where the changes live

```
sabrina-2/src/sabrina/
├── personality.py            # NEW (~80 lines): 6 block constants
│                              # + _build_system_prompt + _block_voice_rules
├── voice_loop.py             # _SYSTEM lift to call _build_system_prompt
├── chat.py                   # _SYSTEM lift to call _build_system_prompt(channel="text")
├── vision/see.py             # UNTOUCHED (per Q3 recommendation)
└── tests/test_smoke.py       # +3 anti-pattern smoke tests

rebuild/
├── drafts/personality-lift-plan.md      # this file
└── decisions/011-personality-lift-shipped.md  # written after the lift session
```

## One thing to feel good about

The `personality.py` module does what every previous decision doc has
asked for: justify a new file with two callers (voice_loop, chat)
*before* it ships, and document the third caller (vision) as a
deferred-but-natural extension. Anti-sprawl rule #2 holding cleanly,
not by hand-waving but by counting callers.

## Next

When Eric signs off on the four open-question recommendations:

1. Implement steps 1-6 from "Implementation order" above.
2. Write `decisions/011-personality-lift-shipped.md`.
3. Move this draft to `rebuild/drafts/done/` (or just leave it; the
   decision doc supersedes).
4. First dogfood: 24 hours of normal Sabrina use; surface drift back
   into `_BLOCK_VOICE_RULES` + the smoke test.
