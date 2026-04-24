# Budget tracker + prompt caching plan (working doc — ready-to-ship)

**Date:** 2026-04-23
**Status:** Draft. Implementable in one session. No open questions for Eric.
**Closes:** daily-driver gap #5 from decision 006 (budget observability);
delivers the immediate-cost-reduction win flagged in every recent
decision doc.

## The one-liner

Every Anthropic turn already emits token usage in the `Done` event — we
just aren't totaling it. This plan persists a running per-day / per-month
total in `data/budget.json`, adds a `sabrina budget` CLI verb and a GUI
tab, and — in the same session — wires Anthropic prompt caching so the
stable system head costs ~10% of its current price on every repeat turn.

## Protocol decision (committed)

`Brain.chat` gets an explicit `system_suffix: str | None = None` kwarg.
`system` is the stable head (cacheable on Claude); `system_suffix` is the
per-turn appendix (retrieved memory block, never cached). Claude splits
them into two system blocks with `cache_control={"type": "ephemeral"}`
on the head. Ollama concatenates `system + "\n\n" + system_suffix` since
it has no cache mechanism.

Why this over a magic-string split inside `brain/claude.py`:
- Keeps the contract honest. Each brain can choose how to use the suffix.
- `voice_loop.py` already has both halves separately (the base `_SYSTEM`
  constant and the `retrieved_block`); plumbing them through as two
  fields is cleaner than stringing them together and re-splitting inside
  the backend.
- Additive and backward-compatible. Existing callers that pass only
  `system=` keep working.
- Matches the pattern Eric blessed in decision 005 (`Message.images`
  additive extension).

Ollama honors the kwarg by concatenation. Future backends that have
their own caching primitives (Gemini, GPT-5) can map it to theirs.

## Scope

In:
- `Brain.chat` protocol signature: `system_suffix: str | None = None`.
  Implemented in `ClaudeBrain` (cacheable head + suffix as separate
  blocks) and `OllamaBrain` (concatenation).
- Anthropic prompt caching on the system block (5-minute ephemeral
  tier — the right choice for conversational voice use).
- `voice_loop.py`: stop string-concatenating `retrieved_block` onto
  `turn_system`; pass it as `system_suffix=` instead.
- `sabrina/budget.py` (~120 lines): rolling per-day / per-month cost
  counters, persisted to `data/budget.json`. Cost table for Sonnet 4.6
  and Haiku 4.5 as constants.
- `events.py`: extend `AssistantReply` and `ThinkingFinished` with
  optional `cost_usd: float | None` and `cache_read_tokens: int | None`
  fields.
- `brain/claude.py`: parse `usage.cache_read_input_tokens` (new
  Anthropic field), feed it through `Done` so the voice-loop can
  publish it.
- `brain/protocol.py`: extend `Done` with
  `cache_read_tokens: int | None`, `cache_creation_tokens: int | None`.
- `sabrina budget` CLI verb: prints today / month-to-date / by-model
  breakdowns.
- `[budget]` config block (mirrors the decision-001 posture: target $0,
  warn $10/mo, ceiling $100/mo).
- GUI: new "Budget" tab — current-day spend, month-to-date, rolling
  7-day list.
- Tests: cost computation, persistence, day rollover, Claude cache
  shape, Ollama concat shape.

Out:
- Hard kill-switch at the monthly ceiling. Today the ceiling just logs
  + shows in the GUI; enforcement ships with the brain router (master
  plan item #5), where "all cloud calls route to local" has somewhere
  to route to.
- Per-session cost breakdown. Per-day is enough.
- Live GUI updates. Static-on-open with a refresh button. Proper live
  bus-driven updates ride on the `ConfigReloaded`-style work from
  voice-loop polish (master plan item #10).
- Caching on the conversation history messages themselves. Cache the
  system block only; the prefix-cache on messages is a second-order win
  that's worth its own session (the messages list reshapes every turn
  — to cache it, we need a more careful block structure).

## Files to touch

```
sabrina-2/src/sabrina/
├── budget.py                    # NEW, ~120 lines
├── brain/
│   ├── protocol.py              # +system_suffix kwarg, +Done extensions
│   ├── claude.py                # cache_control + cost/usage fields
│   └── ollama.py                # accept + concatenate system_suffix
├── voice_loop.py                # pass retrieved_block as system_suffix,
│                                # publish cost_usd on AssistantReply
├── events.py                    # +cost_usd, +cache_read_tokens fields
├── cli.py                       # +sabrina budget verb
├── gui/settings.py              # +Budget tab
└── config.py                    # +BudgetConfig
sabrina-2/
├── sabrina.toml                 # +[budget]
└── tests/test_smoke.py          # +budget tests
```

`budget.py` is the only new file. Keep it ≤200 lines; if it grows,
split `budget/store.py` (persistence) + `budget/costs.py` (model table).

## Protocol / API changes

### `brain/protocol.py`

```python
@dataclass(frozen=True, slots=True)
class Done:
    input_tokens: int | None = None
    output_tokens: int | None = None
    # NEW — optional, Claude-only today.
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    stop_reason: str | None = None


class Brain(Protocol):
    name: str

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        system_suffix: str | None = None,     # NEW
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]: ...
```

### `brain/claude.py`

```python
async def chat(self, messages, *, system=None, system_suffix=None,
               max_tokens=None, model=None):
    api_messages = [_render_message(m) for m in messages if m.role != "system"]
    if system is None:
        sys_msgs = [m.content for m in messages if m.role == "system"]
        system = sys_msgs[0] if sys_msgs else None

    # Build system as a list of blocks so we can cache the head.
    system_param: list[dict] | None = None
    if system:
        head = {"type": "text", "text": system,
                "cache_control": {"type": "ephemeral"}}
        system_param = [head]
        if system_suffix:
            system_param.append({"type": "text", "text": system_suffix})
    elif system_suffix:
        # Odd case: suffix with no head. No cache benefit. Still send it.
        system_param = [{"type": "text", "text": system_suffix}]

    kwargs = {"model": model or self._model,
              "max_tokens": max_tokens or self._default_max_tokens,
              "messages": api_messages}
    if system_param:
        kwargs["system"] = system_param

    # ... stream.text_stream loop unchanged ...
    final = await stream.get_final_message()
    usage = final.usage
    yield Done(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", None),
        stop_reason=final.stop_reason,
    )
```

The `getattr` guards tolerate older SDK versions that haven't surfaced
the cache fields yet. Anthropic ships them as named attrs on `usage`
on recent SDK releases; we already pin `anthropic>=0.40`.

### `brain/ollama.py`

```python
async def chat(self, messages, *, system=None, system_suffix=None,
               max_tokens=None):
    combined_system = system
    if system_suffix:
        combined_system = (system + "\n\n" + system_suffix) if system else system_suffix
    # ... rest unchanged, using combined_system ...
```

No cache semantics; pass the combined text through as before.

### `voice_loop.py`

Two edits:

1. Stop string-concatenating `retrieved_block` onto `turn_system`.
   Pass as `system_suffix` instead:

```python
# before:
if retrieved_block:
    turn_system = f"{turn_system}\n\n{retrieved_block}"
# after:
turn_system_suffix = retrieved_block if retrieved_block else None
# ... later:
async for ev in turn_brain.chat(
    history, system=turn_system, system_suffix=turn_system_suffix
):
    ...
```

2. Compute cost on `Done` and attach to `AssistantReply`:

```python
elif isinstance(ev, Done):
    in_tok, out_tok = ev.input_tokens, ev.output_tokens
    cache_read = ev.cache_read_tokens
    cost_usd = budget.price_usd(
        model=turn_brain.name,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_read,
        cache_creation_tokens=ev.cache_creation_tokens,
    )
    budget.record(model=turn_brain.name, cost_usd=cost_usd)
# publish with cost_usd
await bus.publish(AssistantReply(text=reply, tier=turn_brain.name, cost_usd=cost_usd))
```

### `events.py`

```python
class AssistantReply(_EventBase):
    kind: Literal["assistant_reply"] = "assistant_reply"
    text: str
    tier: str
    cost_usd: float | None = None              # NEW, defaults None

class ThinkingFinished(_EventBase):
    kind: Literal["thinking_finished"] = "thinking_finished"
    tier: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None       # NEW
    cost_usd: float | None = None              # NEW
```

Defaults preserve the existing schema guard pattern (decision 003).

## `budget.py` shape

```python
# Prices in USD per 1M tokens. Keyed by the tier string Claude reports
# via Brain.name (e.g. "claude:claude-sonnet-4-6").
# Sources: Anthropic pricing page, cross-checked against their billing
# export. Update when Anthropic updates — a stale entry is a visible bug.
#
# Cache math: cache_read tokens are billed at 10% of the regular input
# price. cache_creation tokens are billed at 125% (first-write premium).
COSTS: dict[str, ModelCost] = {
    "claude:claude-sonnet-4-6":        ModelCost(input=3.00, output=15.00),
    "claude:claude-haiku-4-5-20251001":ModelCost(input=1.00, output=5.00),
}

def price_usd(model, input_tokens, output_tokens,
              cache_read_tokens=0, cache_creation_tokens=0) -> float:
    cost = COSTS.get(model)
    if cost is None:
        return 0.0    # unknown model or ollama — record as zero, log once
    regular_in = (input_tokens or 0) - (cache_read_tokens or 0) - (cache_creation_tokens or 0)
    total_per_m = (
        regular_in * cost.input
        + (cache_read_tokens or 0) * cost.input * 0.1
        + (cache_creation_tokens or 0) * cost.input * 1.25
        + (output_tokens or 0) * cost.output
    )
    return total_per_m / 1_000_000

class BudgetStore:
    """Per-day + per-month USD totals, persisted to data/budget.json.
    Atomic writes: tempfile + os.replace."""

    def __init__(self, path: Path): ...
    def record(self, model: str, cost_usd: float) -> None: ...
    def today(self) -> float: ...
    def month_to_date(self) -> float: ...
    def last_n_days(self, n: int) -> list[tuple[date, float]]: ...
    def by_model(self, days: int = 30) -> dict[str, float]: ...
```

Persistence format (JSON by design — small, transparent, easy to grep):

```json
{
  "version": 1,
  "per_day": {
    "2026-04-23": {"total": 0.0823, "by_model": {"claude:sonnet": 0.07, ...}},
    "2026-04-22": {"total": 0.1201, "by_model": {...}}
  }
}
```

Rotation: if the file exceeds 1 MB (hundreds of days in), we prune
entries older than 400 days on the next write. Unlikely to matter.

## Config additions

```toml
[budget]
# Soft targets, from decision 001. These only affect logging + GUI color;
# enforcement lives with the router (ships later).
daily_warn_usd = 1.00
monthly_warn_usd = 10.00
monthly_ceiling_usd = 100.00

# Relative paths resolve to project root.
path = "data/budget.json"
```

No behavior change tied to the ceilings today — purely observability.
The monthly-ceiling enforcement becomes real when the router lands
(decision 001's "all cloud calls route to local or fast-path").

## Cache-control subtleties (correctness worth flagging)

- The cache key is the full content of cached blocks, left-to-right.
  Any whitespace change in `_SYSTEM` invalidates. `_SYSTEM` is a module-
  level constant, stable by construction. Good.
- Cache TTL is 5 minutes (ephemeral tier). On the rare voice session
  with > 5-min gaps, the cache expires and the next turn pays full
  price. Acceptable for MVP. The 1-hour tier is more expensive to
  create; ephemeral is right for conversational use.
- The retrieved-memory block MUST NOT be inside the cached head — it
  changes every turn. Keeping it as `system_suffix` (a separate,
  non-cached block) is the whole point of this protocol change.
- Minimum cacheable size: Anthropic's cache has a ~1024-token floor
  (smaller cached blocks are no-ops). Our `_SYSTEM` is ~80 tokens. The
  cache block won't be honored on `_SYSTEM` alone. **This is the one
  risk in the plan.**

### Handling the 1024-token cache floor

Two options:

**(a) Accept it.** Caching does nothing for our current system prompt
because it's too small. The budget-tracker half of this plan still
ships value. The cache path is wired but inert until system prompts
grow (e.g., when we add tool-use descriptions — each tool's schema is
hundreds of tokens).

**(b) Pre-pack a stable preamble** into the system prompt specifically
to push it past 1024 tokens — a "you are Sabrina, here is what you
know about Eric, here are your defaults" block. Raises the per-call
token floor, which costs a tiny amount on Ollama and everything that
doesn't cache-hit — but pays back on every cache-hit. Over 100 turns
at a 5-min session pattern, plausible savings are still under $0.05.

**Plan's call: (a).** Ship the caching machinery; let it become useful
when tool use or richer system prompts arrive. The alternative trades
clarity (a synthetic preamble the brain didn't really need) for
pennies. Flag this in the shipped decision doc's "what works well vs.
what's inert" section so future-Eric knows why caching is wired but
not observable in usage.

## Test strategy

Fast unit tests (< 100 ms each):

- `test_price_usd_sonnet_matches_published_table` — pin a known
  input/output pair, assert expected USD.
- `test_price_usd_includes_cache_read_discount` — assert that
  `cache_read_tokens` contributes at 0.1×.
- `test_price_usd_unknown_model_returns_zero_and_logs_once` — unknown
  tier returns 0.0, structlog captured once per process lifetime.
- `test_budget_store_records_and_totals` — write N events, assert
  `today()` and `month_to_date()`.
- `test_budget_store_persists_across_reopen` — write, close, reopen,
  assert totals.
- `test_budget_store_day_rollover` — write at 23:59 UTC, write at
  00:01 UTC (next day), assert they land on different `per_day` keys.
- `test_brain_claude_sends_cacheable_system_block` — monkeypatch the
  Anthropic client, capture the kwargs; assert the system param is
  a list of blocks with `cache_control` on the first.
- `test_brain_claude_non_cached_suffix` — same pattern; assert the
  suffix block has no `cache_control`.
- `test_brain_ollama_concatenates_system_suffix` — monkeypatch the
  Ollama client; confirm the `system` message is `head + "\n\n" + suffix`.
- `test_done_event_carries_cache_read_tokens` — fake stream final with
  `usage.cache_read_input_tokens=500`; assert it arrives on `Done`.

Integration test:

- `test_voice_loop_publishes_cost_and_records_to_budget` — stub brain
  that returns a synthetic `Done`, run one turn, assert
  `AssistantReply.cost_usd` is non-None and `BudgetStore.today()` went
  up by that amount.

Manual smoke (`validate-budget-windows.md` when we ship):
- `sabrina voice` one real turn; verify structlog line
  `brain.claude.done cache_read=... cache_creation=... in=... out=... cost_usd=...`.
  First turn has zero cache_read (cold). Repeated within 5 min: non-zero
  cache_read, lower cost. (Note: at 80-token `_SYSTEM`, actual cache_read
  may be zero until we cross the 1024 floor — see plan-call (a) above.)
- `sabrina budget` prints today's amount matching the publisher.

## Step-ordered implementation outline

1. `BudgetConfig` in `config.py` + `[budget]` block in `sabrina.toml`.
   One commit.
2. `budget.py`: `ModelCost`, `COSTS`, `price_usd`, `BudgetStore`.
   Unit tests. One commit.
3. `brain/protocol.py`: extend `Done` + add `system_suffix` to the
   `chat` protocol. One commit.
4. `brain/ollama.py`: accept and concatenate `system_suffix`. Test.
   One commit.
5. `brain/claude.py`: system-block rework + cache_control +
   `cache_read_tokens` / `cache_creation_tokens` on `Done`. Tests.
   One commit.
6. `events.py`: add optional `cost_usd` and `cache_read_tokens` fields.
   Schema guard test. One commit.
7. `voice_loop.py`: pass `retrieved_block` as `system_suffix`, compute
   cost, publish. One commit.
8. `cli.py`: `sabrina budget` verb. One commit.
9. `gui/settings.py`: "Budget" tab. One commit.
10. `validate-budget-windows.md` manual smoke. One commit.

Commit 5 is the largest — if it bumps claude.py above ~150 lines, fine;
well under the 300 guardrail.

## Dependencies to add

None. `anthropic>=0.40` already surfaces cache fields on recent SDK
minor versions.

## Windows-specific concerns

- `data/budget.json` uses the same path-resolution logic as
  `data/sabrina.db`: relative-to-project-root if the config path isn't
  absolute.
- Atomic write on Windows: `os.replace(tmp, target)` is atomic for
  this pattern. Don't use `os.rename` (fails if target exists on
  older Windows).
- If `data/` doesn't exist yet on first run, `BudgetStore.__init__`
  creates it. Memory already does this; mirror that.
- JSON encoding: ASCII only (`ensure_ascii=True`) for maximum
  cross-tool grep compatibility — the file is meant to be readable with
  `type data\budget.json` in PowerShell.

## Open questions (none blocking)

All four Eric-level questions were resolved:
- Protocol: explicit `system_suffix` kwarg. (Committed above.)
- Cost source: hard-coded `COSTS` table; revisit when we support more
  providers.
- Persistence cadence: every turn. File stays small; atomic replace
  is cheap.
- Caching: ephemeral tier on system head; suffix non-cached; prefix-
  cache on messages is a follow-up session.

The only runtime surprise is the 1024-token cache floor (flagged above).
Plan's call is to ship caching wiring and accept that it's inert until
system prompts grow. If Eric wants caching observably-active on day
one, we add a synthetic preamble; that's a one-line change, easy to
revisit.

## Ship criterion

- All new unit tests pass. Existing tests unchanged.
- `sabrina voice` one turn: `sabrina budget` shows a non-zero cost in
  "today" exactly equal to that turn's cost.
- `Brain.chat` signature changes don't break any existing test; the new
  kwarg defaults to `None`.
- Structured log line at end of each Claude turn carries
  `cache_read_tokens` (likely zero until we cross the cache floor,
  but the field is present).
- No latency regression on the voice loop's first-audio time
  (the cache block structure is a tiny request-shape change, not a
  new round-trip).

## Not in this plan (later)

- Hard monthly-ceiling enforcement (ships with the brain router).
- Messages-prefix caching (separate session; requires careful block
  structuring).
- Per-session cost breakdown in the GUI.
- Automatic refresh of the GUI Budget tab via the event bus.
- Cost reporting for future providers (Gemini, GPT-5). Adds a row to
  `COSTS`; that's it.
- 1-hour cache tier. Different billing shape; worth a look only if
  voice sessions regularly span hours.

---

**Ready for implementation.** No pending Eric-decisions; the one
known correctness risk (1024-token cache floor) is documented and the
plan commits to accept-and-ship rather than work around.
