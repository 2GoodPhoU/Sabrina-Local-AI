# Brain router plan

**Date:** 2026-04-23
**Status:** Research + draft. Implementation blocked on three open
questions at the top of this doc. Everything below the open-questions
block is settled research.
**Closes:** ROADMAP open question "Build brain router or skip?" +
decision 001's "local tier is first-class" posture.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Default tier on a normal voice turn: local or cloud?** Today it's
   cloud (Claude Sonnet 4.6 via `brain.default = "claude"`). A router
   can flip this so the default is `qwen2.5:14b` locally with cloud
   escalation for hard cases. Decision 001 says "local is first-class,
   not a fallback" which implies local-default, but nothing in the
   rebuild reflects that yet. Picking local-default changes the
   routing-rule shape (escalate-to-cloud is easier to reason about than
   demote-to-local).

   **Recommendation: `default_tier = "local"`.** This is the posture
   decision 001 actually committed to — "local tier is first-class, not
   a fallback" with an explicit list of cloud-exception cases (complex
   planning, vision, tool-use escalation). It also makes the rule shape
   simpler: `cloud_keywords` enumerates the escalation set and
   everything else stays local, which is a shorter word-list to tune
   than the inverse. Bonus: `$0/month target` from decision 001 is only
   real if the default path is free. Override: if Eric wants
   cloud-default, flip `default_tier = "cloud"` in config and the
   keyword classifier does the work the other direction — no code
   change, just tune `local_keywords` for the "things you specifically
   want local."

2. **Offline behavior: auto-fallback on network failure, or manual
   toggle?** Auto means "Claude call times out → try Ollama once →
   speak the Ollama reply." Manual means "user sets
   `[brain.router].mode = offline` and that's that." Auto is friendlier
   but makes bugs and rate-limiting indistinguishable at runtime.
   Manual is honest but requires explicit "offline on" before the
   plane loses wifi. Pick one; affects failure-path code.

   **Recommendation: manual toggle only for v1.** The loud-failure
   guardrail from the rebuild ("illegal transitions raise loudly
   instead of silently half-working" — decision 003) points this way.
   Auto-fallback hides rate-limiting, expired keys, and network glitches
   behind a stealth quality drop; Eric would never know why Sabrina got
   dumber this afternoon. The `mode = "offline"` switch is a 1-line
   TOML edit and maps to the Settings GUI cleanly. Override: if Eric
   wants auto, add a `mode = "auto_offline"` value that attempts Claude
   once, catches `APIConnectionError` / `RateLimitError` only (not all
   exceptions), and retries locally with a structlog warning. Additive,
   ship later.

3. **Ceiling enforcement: router does this or budget tracker does?**
   The budget-and-caching plan promised that monthly ceiling
   enforcement ships "with the router." The honest question is: when
   `budget.month_to_date() > monthly_ceiling_usd`, does the router
   silently rewrite `claude` → `ollama` for every turn, or does the
   router just refuse and surface an error? Silent rewrite matches
   decision 001's language. Explicit refusal is safer (no surprise
   quality drop). Affects UX wording in `sabrina budget`.

   **Recommendation: silent rewrite to local with a loud log line + a
   one-time spoken heads-up.** Decision 001 literally says "all cloud
   calls route to local or fast-path until reset" — the rebuild already
   committed to this behavior in text. Since local is first-class (not
   a degraded fallback), the "surprise quality drop" framing doesn't
   apply the same way it would in a cloud-only assistant. What matters
   is transparency: structlog a `router.decision rule=ceiling` line
   every turn and once per ceiling-hit publish an `AssistantReply` with
   a preamble sentence ("I'm at the monthly cap so I'll answer locally
   for the rest of the month"). Override: if Eric wants explicit
   refusal, change rule 1 in `_decide` to raise a
   `BudgetCeilingExceeded` that the voice loop catches and speaks as
   an error — same plumbing, different user-facing posture.

Everything below reflects the above recommendations. Implementation
starts immediately when Eric either signs off or overrides. Config
defaults and pseudocode below assume Eric accepts the recommendations.

---

## The one-liner

Add a `RouterBrain` that implements the `Brain` protocol and dispatches
each turn to Claude or Ollama based on a handful of cheap, explainable
rules: user-message prefix override, context size, and a small
keyword classifier. No learned router, no confidence-from-local,
no server-side routing services. Two hundred lines total; every decision
is loggable. Budget ceiling + offline-mode behavior fold in cleanly.

## Research — routing strategies surveyed

Ranked rough-fit-to-Sabrina. Citations pulled from memory; Eric can
verify if a specific strategy matters for his call.

### A. Explicit user prefix

User types or speaks a marker ("quick:", "think hard", "/local") to
pin the tier. Zero false positives. Zero ML. Adds a user-language
burden but that burden is voluntary.

### B. Context-size heuristic

Count tokens (or words as a proxy). Below ~200 tokens total prompt →
local is fine. Above → cloud is better. Cheap. Works well as a tie-
breaker inside a hybrid.

### C. Keyword classifier

Hand-curated word lists: `{code, explain, design, plan, write, essay,
philosophical, translate, summarize, edit}` → cloud. `{time, date,
weather, hello, thanks, yes, no}` → local. A single-digit-line
classifier. Misses a lot individually but good as one of several
signals.

### D. Confidence-from-local

Ask the local model first, take first-token logprobs, escalate to cloud
if below a threshold. Conceptually elegant, implementationally hard
(Ollama's `logprobs` surface is unstable; faster-whisper-style
first-token latency would double for every turn). Rejected for v1.

### E. Learned router (LM Systems RouteLLM, Martian, OpenRouter)

A BERT-class classifier or an external routing API. Decision 001
explicitly pitched its own local-preferring router; the deferment was
"until complexity is justified." None of these external services were
justified even once in the decision log. Rejected for v1 — add only
if A+B+C prove insufficient.

### F. Cost-aware routing (budget month-to-date as input)

"If we're past daily warn, prefer local; if past monthly warn, force
local; if past ceiling, refuse cloud entirely." Important but
composable with A+B+C — it's a final filter, not a routing rule.
Ships in this plan.

## The plan's routing model

Hybrid A + B + C + F, evaluated in this exact order for every turn:

1. **Budget gate.** `budget.month_to_date() > monthly_ceiling_usd`
   → force local (silent rewrite, per Q3 recommendation). Decided
   first because it's a hard rule, not a preference.

2. **Offline gate.** `router.mode == "offline"` → force local. Same
   reasoning; no outbound HTTP.

3. **Explicit prefix.** Scan the user's message for markers:
   - `think hard`, `think about it`, `take your time` → cloud (Sonnet
     if cloud tier set).
   - `quick`, `fast`, `just`, leading `tl;dr` → local.
   - `/local`, `/cloud` → explicit pin (stripped from the user text
     before it reaches the brain).
   If matched, done. Skip 4-5.

4. **Context-size heuristic.** Sum `len(m.content)` over `messages`
   and the `system`. Convert to an approximate token count (÷4).
   Threshold: 500 tokens total → cloud; below → local.

5. **Keyword classifier.** Score the user message against two word
   lists (~30 words each, tuned on actual Sabrina conversation log).
   Score tie → `default_tier` (recommended "local").

Final chosen tier threaded through the rest of the turn unchanged.

Every decision gets a structlog entry:

```
router.decision chosen=claude:sonnet-4-6 rule=prefix reason=think_hard
router.decision chosen=ollama:qwen2.5:14b rule=size tokens_est=184
router.decision chosen=claude:sonnet-4-6 rule=keyword score_cloud=3 score_local=0
```

Traceable, debuggable, no black box.

## Scope

In:
- `sabrina/brain/router.py` (~180 lines): `RouterBrain` implements
  `Brain`; composes ClaudeBrain + OllamaBrain; runs the decision rules
  above per turn.
- `brain/router.py::RouterDecision` dataclass (`tier`, `rule`, `reason`,
  `tokens_est`).
- New event `RouterChose(decision: RouterDecision)` on the bus.
  Optional subscriber (GUI eventually).
- `[brain.router]` config block: mode, thresholds, keyword lists.
- `voice_loop.py`: when `brain.default == "router"`, instantiate
  `RouterBrain` instead of one of the backends directly.
- Vision exception: vision turns still pin Claude (Haiku) regardless of
  the router — see "Vision turns bypass routing" below.
- Tests: each rule in isolation, gate precedence, logging.

Out:
- Confidence-from-local (option D).
- Learned router (option E).
- Per-user prefix customization. The prefix list is a config block
  (so editable), but there's no UI for it.
- Streaming-transition fallback ("started local, saw a bad token,
  switched to cloud mid-stream"). Overcomplicated; not worth it.

## Vision turns bypass routing

Today `voice_loop` instantiates a per-turn `ClaudeBrain` for vision
turns (decision 005). That pattern stays: routing applies only to
the text-only default path. Vision-trigger turns always use Claude's
fast model, or a local VLM if local-vlm-plan.md lands (which adds
its own selection rule).

## Files to touch

```
sabrina-2/src/sabrina/
├── brain/
│   ├── router.py                 # NEW, ~180 lines
│   └── __init__.py               # export RouterBrain
├── events.py                     # +RouterChose
├── voice_loop.py                 # +build RouterBrain if configured
├── cli.py / cli/brain.py         # +`sabrina route-test "..."` verb for
│                                 #  dry-running the classifier
└── config.py                     # +RouterConfig under BrainConfig
sabrina-2/
├── sabrina.toml                  # +[brain.router]
└── tests/test_smoke.py           # +router tests
```

## Protocol / API changes

None at the `Brain` protocol level — `RouterBrain` implements it.
Internally it delegates to the two backends and yields their streaming
events verbatim. `Done.stop_reason` surfaces the sub-brain's reason;
`RouterBrain.name` is `router:<chosen_tier>` per turn (mutable on the
instance across calls) or a stable `router:qwen2.5:14b+claude:sonnet-4-6`
for logging.

Decision worth calling out: we do NOT change `Brain.name` per call (it's
supposed to be stable). Instead:
- `RouterBrain.name` is a stable string: `router`.
- The publisher of `AssistantReply` reads from the `RouterChose` event
  (or from `Done.stop_reason` which the router annotates) to surface
  the real chosen tier.

## Config additions

```toml
[brain]
# Set default to "router" to enable the router. "claude" or "ollama"
# still work as before and bypass the router.
default = "router"

[brain.router]
# Mode:
#   "auto"     = follow the A+B+C+F rules above (recommended).
#   "offline"  = force local (Ollama). Cloud calls blocked.
#   "online"   = force cloud (Claude). Local never invoked.
mode = "auto"

# Tier pinned when every rule falls through. Recommended "local" per
# decision 001's "local is first-class" posture + $0/month target.
# "local" = ollama / "cloud" = claude.
default_tier = "local"

# Rule 3 — explicit prefix match. Case-insensitive substring match on
# the LAST user message's text.
cloud_prefixes = ["think hard", "think about it", "take your time", "/cloud"]
local_prefixes = ["quick:", "fast:", "tl;dr", "/local"]

# Rule 4 — context-size threshold in approximate tokens (chars/4).
# Above this, cloud. Counting is cheap (no tokenizer dep).
size_threshold_tokens = 500

# Rule 5 — keyword classifier. Each list scores +1 for any match on
# the user message. Higher total wins; ties go to default_tier.
cloud_keywords = [
    "code", "explain", "design", "plan", "write", "essay", "translate",
    "summarize", "edit", "debug", "philosophical", "analyze", "compare",
    "review", "draft", "proofread", "brainstorm",
]
local_keywords = [
    "time", "date", "weather", "hello", "hi", "thanks", "yes", "no",
    "what time", "what day", "how are you", "open", "close", "play",
    "stop", "pause",
]
```

## Pseudocode — `RouterBrain.chat`

```python
class RouterBrain:
    name = "router"

    def __init__(self, claude: ClaudeBrain, ollama: OllamaBrain,
                 cfg: RouterConfig, budget: BudgetStore | None = None,
                 bus: EventBus | None = None) -> None:
        self._claude = claude
        self._ollama = ollama
        self._cfg = cfg
        self._budget = budget
        self._bus = bus

    async def chat(self, messages, *, system=None, system_suffix=None,
                   max_tokens=None):
        decision = self._decide(messages, system, system_suffix)
        brain = self._claude if decision.tier == "cloud" else self._ollama
        if self._bus is not None:
            await self._bus.publish(RouterChose(decision=decision))
        log.info("router.decision",
                 chosen=brain.name, rule=decision.rule,
                 reason=decision.reason)
        async for ev in brain.chat(messages, system=system,
                                    system_suffix=system_suffix,
                                    max_tokens=max_tokens):
            yield ev

    def _decide(self, messages, system, system_suffix) -> RouterDecision:
        # 1. Budget gate
        if self._ceiling_hit():
            return RouterDecision(tier="local", rule="ceiling",
                                   reason=f"mtd_over_{self._cfg.monthly_ceiling}")
        # 2. Offline / online mode
        if self._cfg.mode == "offline":
            return RouterDecision(tier="local", rule="mode", reason="offline")
        if self._cfg.mode == "online":
            return RouterDecision(tier="cloud", rule="mode", reason="online")
        # 3. Explicit prefix on the last user message
        last_user = _last_user(messages)
        if last_user:
            prefix_hit = _match_prefix(last_user, self._cfg)
            if prefix_hit is not None:
                return prefix_hit
        # 4. Context-size
        total = _size_tokens_est(messages, system, system_suffix)
        if total > self._cfg.size_threshold_tokens:
            return RouterDecision(tier="cloud", rule="size",
                                   reason=f"est_{total}_tok")
        # 5. Keyword classifier
        if last_user:
            kw = _keyword_score(last_user, self._cfg)
            if kw.score_cloud > kw.score_local:
                return RouterDecision(tier="cloud", rule="keyword",
                                       reason=f"c{kw.score_cloud}_l{kw.score_local}")
            if kw.score_local > kw.score_cloud:
                return RouterDecision(tier="local", rule="keyword",
                                       reason=f"c{kw.score_cloud}_l{kw.score_local}")
        return RouterDecision(tier=self._cfg.default_tier, rule="default",
                               reason="no_rule_matched")
```

`_size_tokens_est` is `sum(len(m.content) for m in messages)/4` plus
the system halves. No tokenizer; the ÷4 rule is famously accurate to
±15% on English.

## Test strategy

- `test_router_budget_gate_forces_local` — mock budget over ceiling;
  run one decision; assert tier=local, rule="ceiling".
- `test_router_mode_offline_forces_local` — mode="offline"; assert
  rule="mode", reason="offline".
- `test_router_prefix_think_hard_selects_cloud` — last user message
  starts with "think hard about"; assert cloud.
- `test_router_prefix_local_slash_selects_local` — "/local: what
  time is it"; assert local. Also assert the prefix is NOT stripped
  here — routing doesn't mutate history; that's the caller's job if
  they want.
- `test_router_size_threshold_selects_cloud` — messages sum to 3000
  chars; assert cloud.
- `test_router_keyword_debug_selects_cloud` — "debug this"; assert
  cloud.
- `test_router_default_tier_used_when_no_rules_match` — trivial "hi"
  with short context, no matching keyword; assert default_tier.
- `test_router_chose_event_published` — spy on bus; assert one
  `RouterChose` event per `chat` call.
- `test_router_streams_child_events_verbatim` — stub child brain
  yields 3 TextDeltas + Done; assert the same sequence reaches the
  caller.

Manual smoke:
- `sabrina route-test "write an essay about..."` prints
  `cloud (rule=keyword)`.
- `sabrina route-test "quick: time please"` prints
  `local (rule=prefix)`.

## Dependencies to add

None. Pure composition over existing backends.

## Windows-specific concerns

None substantive. The router adds ~1 ms per turn (the rules are string
ops and dict lookups).

## Performance

A decision takes <1 ms on any hardware. The streaming passthrough is
zero overhead. The router doesn't "look at" the brain's output — it
just forwards events.

One thing the router does NOT do: streaming mid-decision. It picks one
backend and commits. If the local backend returns garbage, that's this
turn's reply; the user can retry. Picking mid-stream would require
generating twice, which defeats the cost savings.

## Ship criterion

- All new unit tests pass.
- `sabrina voice` with `brain.default = "router"` works end-to-end:
  trivial query ("what time is it?") goes local; complex query
  ("debug this error") goes cloud. Verify via the structlog line.
- `sabrina route-test` dry-runs a handful of phrases and prints
  readable decisions.
- No regression on first-audio latency (~1 ms router overhead is
  invisible).
- `brain.default = "claude"` and `brain.default = "ollama"` still work
  unchanged — router is opt-in.

## Not in this plan (later)

- Confidence-from-local routing (option D).
- Learned router (option E).
- Streaming-transition fallback.
- Per-user prefix learning.
- Router-aware prompt-caching (currently caching only works for Claude;
  a cloud→local fallback mid-session re-prepares the cache when cloud
  is picked again — no code, just reality).
