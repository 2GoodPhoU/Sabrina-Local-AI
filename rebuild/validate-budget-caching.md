# Budget tracker + prompt caching — Windows validation procedure

**Purpose:** confirm token accounting, budget persistence, and Anthropic
prompt-caching plumbing work end-to-end on Eric's Windows box before we
call the budget/caching decision validated.
**Written:** 2026-04-23. One-shot procedure; run top-to-bottom from
`sabrina-2/`.
**Prerequisite:** PowerShell open in `Sabrina-Local-AI\sabrina-2`.
Budget/caching implementation has landed per `rebuild/drafts/budget-and-caching-plan.md`
(`budget.py`, `system_suffix` kwarg on `Brain.chat`, cache_control on
Claude head, `cache_read_tokens` on `Done`, `sabrina budget` verb,
`[budget]` block in `sabrina.toml`).

All commands copy-pasteable. One caveat up front: the 1024-token cache
floor means the caching half of this feature is **expected to be inert**
until the system prompt grows past that threshold. This doc treats
"cache_read_tokens=0 always" as a pass, not a fail — documented below.

---

## Step 0 — Sanity-check the Anthropic SDK exposes cache fields

The `Done` event pulls `cache_read_input_tokens` off the final message
`usage`. This attribute landed in anthropic SDK 0.40+. Confirm the
pinned version supports it.

```powershell
uv run python -c "import anthropic; print(anthropic.__version__); from anthropic.types import Usage; print('fields:', [f for f in Usage.model_fields if 'cache' in f])"
```

**Success:** prints `>=0.40.0` and a fields list including
`cache_read_input_tokens` and `cache_creation_input_tokens`.
**Failure signal:** empty `fields:` list or older version → SDK upgrade
needed. Bump the `anthropic` pin in `pyproject.toml` and re-run
`uv sync`.

---

## Step 1 — `uv sync` and `uv run pytest -q`

```powershell
uv sync
uv run pytest -q
```

**Success:** existing tests pass, plus the budget/caching block (~11
new tests):

- `test_price_usd_sonnet_matches_published_table`
- `test_price_usd_includes_cache_read_discount`
- `test_price_usd_unknown_model_returns_zero_and_logs_once`
- `test_budget_store_records_and_totals`
- `test_budget_store_persists_across_reopen`
- `test_budget_store_day_rollover`
- `test_brain_claude_sends_cacheable_system_block`
- `test_brain_claude_non_cached_suffix`
- `test_brain_ollama_concatenates_system_suffix`
- `test_done_event_carries_cache_read_tokens`
- `test_voice_loop_publishes_cost_and_records_to_budget`

Capture any red.

---

## Step 2 — Confirm `[budget]` block loaded

```powershell
uv run sabrina config-show | findstr /i budget
```

**Success:** prints the four budget keys (`daily_warn_usd`,
`monthly_warn_usd`, `monthly_ceiling_usd`, `path`) with the shipped
defaults.

---

## Step 3 — `sabrina budget` baseline

```powershell
uv run sabrina budget
```

**Success (cold DB):** output looks like:

```
Budget tracker at data/budget.json
  today (2026-04-23):   $0.00
  month-to-date:        $0.00
  by model (last 30d):  (none)
  daily warn:     $1.00   (ok)
  monthly warn:   $10.00  (ok)
  monthly ceiling:$100.00 (ok)
```

If `data/budget.json` doesn't exist, `sabrina budget` should create an
empty one and still print the above. **Failure signal:** crash on
missing file → `BudgetStore.__init__` isn't creating the parent
directory idempotently.

---

## Step 4 — One real voice turn, observe token accounting

Make sure `.env` has `ANTHROPIC_API_KEY` set (needed for the Claude
backend — Ollama-only runs don't exercise the caching path).

```powershell
uv run sabrina voice
```

Hold PTT, ask a clearly non-trivial question like *"in three sentences,
what is the capital of France and why does that matter historically?"*
Release. Let Sabrina finish.

**Success — three things to find in the structlog output:**

1. **Per-turn `brain.claude.done` line with token fields:**

   ```
   brain.claude.done model=claude-sonnet-4-6 in=120 out=85
   cache_read=0 cache_creation=0 cost_usd=0.00164 stop_reason=end_turn
   ```

   Tokens should be sensibly in the low hundreds for the input
   (`_SYSTEM` + history), under 200 for the output.
   `cost_usd` ≈ input_tokens × $3/M + output × $15/M for Sonnet.
   Manually cross-check: `(120 × 3 + 85 × 15) / 1_000_000 = $0.00164`.
   Within one or two cents is fine; exact match is the pass criterion.

2. **`AssistantReply` event on the bus carries `cost_usd`:**
   Look for `event.publish assistant_reply ... cost_usd=0.00164`.

3. **`cache_read=0 cache_creation=0` on the first turn.** First-turn
   zero is expected — there's no prior cache entry.

**Failure signals:**
- `cache_read=None` (not zero) → the `getattr` fallback fired on the
  SDK's `usage` object. Means the SDK version doesn't surface the
  field despite step 0 claiming it does. Run step 0 again from a fresh
  shell; check for a venv mismatch.
- `cost_usd` off by 2× or more → model-string mismatch with the
  `COSTS` table. The tier string passed to `price_usd` must exactly
  match a key in `COSTS` (e.g. `claude:claude-sonnet-4-6`, not
  `claude-sonnet-4-6`). Capture the `brain.name` value and compare.

---

## Step 5 — Second turn within 5 min — the cache test

In the same voice session (don't Ctrl+C out), within 5 minutes of turn
1, ask a second question. Let it finish.

**Watch for:**

```
brain.claude.done model=claude-sonnet-4-6 in=180 out=90
cache_read=<X> cache_creation=<Y> cost_usd=...
```

Two possibilities — **both are passes** per the plan's 1024-token
floor caveat:

**Case A — `cache_read=0, cache_creation=0` on the second turn too.**

This is the **documented expected behavior** of the current default
system prompt. `_SYSTEM` is ~80 tokens; Anthropic won't honor a
`cache_control` block under 1024 tokens. The caching machinery is
wired and correct; it just doesn't have enough material to cache.

**Pass criterion for this case:** the structlog field is *present and
zero*, not missing. Absence of the field would indicate the cache
plumbing regressed. Zero in the presence of the field is fine.

**Case B — `cache_read>0` on the second turn.**

This means someone grew the system prompt past 1024 tokens (tool-use
descriptions landing, compaction summaries loaded in, whatever). In
this case:

- `cache_creation` should be 0 (the first turn created the cache
  entry — which costs regular-input + 25%).
- `cache_read` should be approximately the same number of tokens as
  the first turn's non-suffix `in` count.
- `cost_usd` should be noticeably less than turn 1's cost — the cached
  tokens bill at 10% of regular input.

**Pass criterion:** `cache_read > 0`, `cost_usd` lower than turn 1 for
a similar-length output. Numbers match rough math.

**Failure signal that covers both cases:** cache fields *missing
entirely* from the structlog line → the `Done` event isn't carrying
them from claude.py, OR the voice-loop structlog binder dropped them.
Capture the raw event trace.

---

## Step 6 — Confirm `sabrina budget` reflects the turn

Ctrl+C out of the voice loop. Then:

```powershell
uv run sabrina budget
```

**Success:** `today` is the exact sum of turn 1's `cost_usd` + turn 2's
`cost_usd` from steps 4 and 5, down to the cent. `month-to-date` ≥
`today`. `by model (last 30d)` shows `claude:claude-sonnet-4-6: $X.XX`.

**Failure signal:** numbers don't match → `BudgetStore.record` either
isn't being called in the voice-loop cost-attach block, or the JSON
persistence isn't flushing. Check:

```powershell
type data\budget.json
```

— today's date key should be populated.

---

## Step 7 — Day-rollover correctness spot-check

Skip this step unless you've crossed midnight UTC between turns. The
underlying behavior is covered by `test_budget_store_day_rollover`;
manual validation is opportunistic. If you did cross midnight:

```powershell
type data\budget.json
```

**Success:** two `per_day` keys, one for yesterday's UTC date and one
for today's, with costs distributed correctly by when you spoke.

---

## Step 8 — Ceiling enforcement is *not* active (confirm)

The plan is explicit: `monthly_ceiling_usd` currently only affects
logging + GUI color. Enforcement ships with the brain router. Confirm
by editing `sabrina.toml`:

```toml
[budget]
monthly_ceiling_usd = 0.001
```

Run `sabrina budget`. **Success:** prints the monthly ceiling in red
/ bold / warning format, with a line like `exceeded: $X.XX over
$0.001 ceiling`. **Does NOT block any future spending.** Run another
voice turn — it should succeed and add to the budget normally.

**Failure signal:** the voice turn errors out with a "budget exceeded,
request blocked" message → enforcement got enabled prematurely. The
validation catches the regression; file a follow-up decision.

Revert `monthly_ceiling_usd` to 100.00 after the check.

---

## Step 9 — First-audio latency — no regression

This is the soft check that the extra request-shape (system as a
list of blocks instead of a string) didn't add round-trips.

```powershell
uv run sabrina voice
```

Ask a short question: *"hello"*. Measure first-audio latency via
structlog timings (`voice_loop.first_audio_ms`). Warm target per
decision 007: ≤ ~2.0 s.

**Success:** first-audio within ~50 ms of the pre-budget baseline
(semantic-memory validation's measurement).

**Failure signal:** first-audio up by 200+ ms → the system-block
construction is happening per-turn where it could be cached in the
voice_loop, or the anthropic SDK is doing something odd with the
block-list shape. Unlikely; capture the timing breakdown if it fires.

---

## If step N fails — quick triage

| Step | Symptom | Likely cause | What to capture |
|---|---|---|---|
| 0 | No `cache_*_input_tokens` fields | anthropic SDK < 0.40 | `uv pip show anthropic` |
| 1 | `test_brain_claude_sends_cacheable_system_block` fails | System-param construction regressed in claude.py | Full traceback |
| 3 | `sabrina budget` crash on first run | Missing `data/` directory not auto-created | Full traceback + `Test-Path data` |
| 4 | `cache_read=None` | SDK version mismatch or shadowed venv | `uv run python -c "import sys, anthropic; print(sys.executable, anthropic.__version__)"` |
| 4 | cost_usd off by 2x+ | Brain.name doesn't match COSTS key | `brain.claude.done` line with `model=` substring |
| 5 | Cache fields missing entirely | Done event not carrying them | Raw event structlog for the turn |
| 6 | budget.json not updating | record() not called or JSON not flushing | `type data\budget.json` |
| 8 | Ceiling actually blocks request | Enforcement wired prematurely | Error traceback from the blocked turn |
| 9 | First-audio regressed | System block built per-turn needlessly | `voice_loop.timings` structlog |

---

## Known risks from the pre-validation code audit

1. **Cache inert by design today.** Plan's call (option a): ship the
   cache wiring, accept zero `cache_read_tokens` until the system
   prompt grows. If step 5's case A fires, that's **not a bug** — it's
   the plan's accepted-and-documented state. Do not file a decision
   doc about it. Do **log** the state in the ROADMAP bump so future-
   Eric understands why caching is wired but not visibly active.
2. **`AnthropicClient` strips `cache_control` from blocks under 1024
   tokens silently — no warning.** If you were expecting to see a
   warning and there isn't one, that's the SDK being quiet, not our
   code failing.
3. **`COSTS` table pricing is hard-coded.** Prices in the code must
   match Anthropic's current published prices. If the `price_usd`
   cross-check in step 4 is off by a flat multiple, the table is
   stale. Fix: update `COSTS` in `budget.py`; not a validation
   failure, a maintenance nudge.
4. **Ollama turns don't exercise the caching path at all.** If your
   default brain is Ollama (`brain.default = "ollama"`), skip this
   validation and run with `brain.default = "claude"` — Ollama's
   `OllamaBrain.chat` just concatenates the suffix.
5. **`budget.json` uses UTC dates.** If you care about your local
   midnight, that's a different calendar — displayed totals in
   "today" may include or exclude turns near local midnight depending
   on timezone offset. Not a bug; a UX choice from the plan.
6. **Atomic write on Windows can fail if the JSON file is open in
   another tool.** If you have `budget.json` open in VS Code or
   tailing in another shell, `os.replace` may transiently fail —
   `BudgetStore.record` should retry once, but if not, close that
   tool and retry the voice turn.

---

## If all green — the ROADMAP bump

Edit `rebuild/ROADMAP.md`:

1. Update the "Last updated" line.
2. Append one line:

```
Budget tracker + caching wiring validated on Windows (i7-13700K/4080,
Python 3.12) <YYYY-MM-DD>: costs match published table to the cent,
<C> cents logged over <N> turns, cache_read=<R> (expected <R>
pending system-prompt growth).
```

`<C>`, `<N>` from step 6; `<R>` will be `0` in the common case.

Commit with message:
```
validate: budget tracker + cache wiring on Windows
```

---

## If any step failed

1. Capture per the triage table.
2. For cost-math or missing-field bugs, file a focused follow-up
   decision under `rebuild/decisions/` — the fix is usually one file.
3. For the SDK-version mismatch (step 0 / step 4 case), bumping the
   pin is a single-commit change with a footnote on the shipped
   decision doc; no new numbered decision needed.
