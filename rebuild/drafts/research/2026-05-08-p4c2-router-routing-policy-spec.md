# P4.C2 — Brain router routing policy + budget-gate hook — spec

**Date:** 2026-05-08
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → Brain router → **P4.C2 Router — Claude/Ollama routing policy + budget-gate hook** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-05-07-p4c1-persona-projection-layer-spec.md` — the persona-projection spec. P4.C2 is its consumer: the router calls `SABRINA_SYSTEM_PROMPT_CLAUDE` or `SABRINA_SYSTEM_PROMPT_OLLAMA` from `brain/persona.py` per route and lets each backend's `chat()` post-process accordingly. Treated as canon for the per-backend system-prompt selection.
- `rebuild/drafts/research/2026-05-05-p27-budget-tracker-spec.md` — the budget-tracker spec. P4.C2's budget-gate hook calls into `BudgetLog.sum_month()` from `sabrina.budget`. Treated as canon for the rolling-MTD + threshold-state shape.
- `rebuild/decisions/001-hardware-and-budget.md` — sets the $0/$10/$100 thresholds + the "ceiling is observed-not-enforced" posture today. The router's budget gate is what flips the ceiling from observed to enforced.
- `rebuild/drafts/router-plan.md` — the original router plan. P4.C2 is the routing-logic implementation; voice_loop integration + Windows e2e is P4.C3.
- `sabrina-2/src/sabrina/brain/protocol.py:137-168` — current `Brain` protocol. The router implements this protocol; consumers don't need to know they're talking to a router vs. a leaf backend.
- `sabrina-2/src/sabrina/brain/claude.py:43-237` — `ClaudeBrain` reference implementation. Router delegates to one of these per turn.
- `sabrina-2/src/sabrina/brain/ollama.py:23-130` — `OllamaBrain` reference implementation. Router delegates to one of these per turn.
- `sabrina-2/src/sabrina/budget.py:62-180` — `compute_cost`, `_COST_TABLE`, `BudgetLog.sum_month`, `check_thresholds`. The budget-gate hook reads `sum_month()` and consults `check_thresholds()` to pick a route.
- `sabrina-2/sabrina.toml:11-23` — current `[brain]`, `[brain.claude]`, `[brain.ollama]` blocks. P4.C2 adds `[brain.router]` and the dispatch table; the existing per-backend blocks stay untouched.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, `voice_loop.py` runtime path (the voice-loop swap is router-side wiring; P4.C3, not this spec).

---

## What this item is

`voice_loop.py` today instantiates `ClaudeBrain` directly (per the (a)-half wire-up at `acd6725`); the router will swap that for a `Router` instance that implements the `Brain` protocol but delegates to either `ClaudeBrain` or `OllamaBrain` per a TOML-configured policy. Three policies in v1: `force_local` (always Ollama — for offline / privacy modes), `claude_default` (always Claude — today's behavior), and `cost_aware` (Claude until rolling MTD crosses the warn threshold from `[budget]`, then Ollama for the rest of the month — the active enforcement of the $10/$100 ceiling decision 001 calls out as observed-not-enforced today). The router is a Linux-runnable structural surface; the Windows voice-loop swap + decision doc are P4.C3.

P4.C2's only hard dependency is P4.C1's `brain/persona.py` (so per-backend system prompts exist). It does NOT depend on P2.7's (b)-half — the (a)-half is enough: `BudgetLog.sum_month()` is a pure-fn read of the JSONL log, doesn't need `voice_loop.py` wiring to work. If `[budget]` is misconfigured (log_dir empty, no rows yet), the budget gate degrades open: `cost_aware` reads zero MTD, picks Claude, behaves identically to `claude_default`.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/brain/router.py` (new, ~220 lines):
  - `class Router` — implements `Brain` protocol. Constructor takes `claude: ClaudeBrain | None`, `ollama: OllamaBrain | None`, `policy: Literal["force_local", "claude_default", "cost_aware"]`, `budget_log: BudgetLog | None = None`, `warn_threshold_usd: float | None = None`. Either `claude` or `ollama` may be None; the router fails loudly if a route resolves to a None backend.
  - `name: str` — `f"router:{policy}"`. Logged on `ThinkingStarted` for observability.
  - `def select_backend(self) -> Brain` — single-source-of-truth resolver:
    - `force_local` → returns `self.ollama` (raises `RouterMisconfigured` if None).
    - `claude_default` → returns `self.claude` (raises `RouterMisconfigured` if None).
    - `cost_aware` → consults `self.budget_log.sum_month()` if non-None; if MTD ≥ `self.warn_threshold_usd`, returns `self.ollama` (or `self.claude` if Ollama is None — log a warning + degrade-open); otherwise returns `self.claude` (or `self.ollama` if Claude is None). If both are None, raise.
  - `async def chat(self, messages, *, system=None, max_tokens=None, cancel_token=None, tools=None) -> AsyncIterator[StreamEvent]` — picks a backend via `select_backend()`, swaps `system` to the per-backend persona prompt if `system` was None on entry (uses `SABRINA_SYSTEM_PROMPT_CLAUDE` / `SABRINA_SYSTEM_PROMPT_OLLAMA` from `brain/persona.py`), forwards everything else through. If the picked backend doesn't support `tools` (Ollama today), drops `tools` to None and logs a one-line `router.tools_dropped` at INFO — this is the lever that lets `cost_aware` swap to Ollama mid-day without crashing on a tool-enabled prompt; the brain just won't call tools that turn.
  - `class RouterMisconfigured(Exception)` — raised when the policy resolves to a None backend.
  - `def make_router_from_settings(settings, budget_log=None) -> Router` — factory: instantiates `ClaudeBrain` and `OllamaBrain` per the existing config blocks (only the configured backends; if `[brain.router] enable_ollama = false`, `ollama=None`), reads `policy` and `warn_threshold_usd` from `[brain.router]`, returns a wired `Router`. Mirrors the existing `ClaudeBrain.from_settings` factory pattern in `brain/claude.py`.
- `sabrina-2/src/sabrina/config.py` — additive `BrainRouterConfig` Pydantic model:
  - `class BrainRouterConfig(BaseModel): policy: Literal["force_local", "claude_default", "cost_aware"] = "claude_default"; warn_threshold_usd: float = 10.0; enable_claude: bool = True; enable_ollama: bool = True` — `policy` defaults to `claude_default` so a no-op config edit (just adding `[brain.router]`) doesn't change today's behavior. The two `enable_*` flags let Eric kill one backend without uninstalling it (e.g. Ollama not running on a fresh box).
  - Add `router: BrainRouterConfig = BrainRouterConfig()` to the existing `BrainConfig` model in `config.py`.
- `sabrina-2/sabrina.toml` — additive `[brain.router]` block mirroring the new defaults. Lives below `[brain.ollama]`; no schema-version bump needed (additive-with-defaults is back-compat per decision 008's posture).
- `sabrina-2/src/sabrina/brain/__init__.py` — re-export `from sabrina.brain.router import Router, make_router_from_settings, RouterMisconfigured` so callers (voice_loop in P4.C3, chat REPL, future tests) can `from sabrina.brain import Router` without an extra import path.
- `sabrina-2/src/sabrina/voice_loop.py` and `sabrina-2/src/sabrina/chat.py` — **not modified** in the (a)-half. Both currently instantiate `ClaudeBrain` directly. Switching to the router is voice-loop runtime work (P4.C3); doing it in this spec would push the (a)-half off the Linux-runnable partial-DoD posture.
- `sabrina-2/tests/test_router.py` (new, ~340 lines) — fifteen unit tests:
  - `test_router_name_includes_policy` — `Router(policy="force_local", ...).name == "router:force_local"`.
  - `test_force_local_picks_ollama` — `select_backend()` returns the ollama instance.
  - `test_force_local_with_no_ollama_raises_router_misconfigured` — passing `ollama=None, policy="force_local"` raises on `select_backend()`.
  - `test_claude_default_picks_claude` — `select_backend()` returns the claude instance.
  - `test_claude_default_with_no_claude_raises_router_misconfigured` — analogous.
  - `test_cost_aware_picks_claude_when_mtd_below_threshold` — fake BudgetLog returns `sum_month() == 5.0`, threshold 10.0; picks claude.
  - `test_cost_aware_picks_ollama_when_mtd_at_threshold` — fake returns 10.0, threshold 10.0; picks ollama (>= comparison).
  - `test_cost_aware_picks_ollama_when_mtd_above_threshold` — fake returns 15.0, threshold 10.0; picks ollama.
  - `test_cost_aware_with_no_budget_log_picks_claude` — `budget_log=None` → degrades to claude_default.
  - `test_cost_aware_with_ollama_disabled_logs_warning_and_picks_claude` — fake MTD 15.0 + `ollama=None` → caplog captures `router.degraded_open` warning, returns claude.
  - `test_chat_routes_to_selected_backend_text_only` — fake claude + ollama; in `claude_default` mode, claude's stream is consumed; ollama's mock stream is untouched.
  - `test_chat_swaps_system_prompt_per_backend` — `system=None` on entry; assert claude route receives `SABRINA_SYSTEM_PROMPT_CLAUDE`; ollama route receives `SABRINA_SYSTEM_PROMPT_OLLAMA`.
  - `test_chat_passes_through_explicit_system_prompt` — `system="custom"` on entry; both routes receive `"custom"`, not the per-backend persona constant.
  - `test_chat_drops_tools_when_route_does_not_support` — `tools=[NOOP_ACTION_SPEC]` + `force_local` → ollama receives `tools=None` and a `router.tools_dropped` log line fires.
  - `test_make_router_from_settings_wires_both_backends` — pass a `Settings` fixture with `policy="cost_aware"`; assert the returned Router has both backends + the configured threshold.

**Edit-hazard caveat per CLAUDE.md:** spec doesn't expect to hit the truncation hazard hard since `router.py` is a new file (no large multi-block lift); `config.py` extension follows the known-good `BudgetConfig` pattern from worker-8am 2026-05-06. Standard AST-parse + compileall + tail integrity check after each Edit per CLAUDE.md.

**(b)-half — folded into P4.C3, NOT deliverable here:**

- `voice_loop.py` and `chat.py` swap `ClaudeBrain(...)` for `make_router_from_settings(...)` — runtime change; P4.C3.
- `events.py` `ThinkingStarted` and `ThinkingFinished` already carry `tier: str`; the router's per-turn tier (`"claude:claude-sonnet-4-6"` vs. `"ollama:qwen2.5:14b"`) reaches them via the existing wire-up. Minor: log a `router.route_picked` line on each turn for observability, behind P4.C3's voice-loop integration step.
- One real Windows voice session per policy (`force_local` → audible Sabrina-with-Ollama-voice; `claude_default` → today's voice; `cost_aware` → cross-threshold transition with `[budget].warn_usd_monthly` artificially set low for the test) — P4.C3.
- Decision doc — P4.C3 promotes the C1 + C2 + C3 triplet under one decision number.

## What's deliberately NOT in scope

- **Per-turn override** — a voice-loop "speak via Ollama for this turn only" override (e.g. user says "stay local") is router-plan territory but introduces a turn-level config surface that's distinct from the policy-level surface. P4.C2.1 if/when the use case materializes.
- **Hot-reload of policy** — toml policy switch without a Sabrina restart. The existing `Settings` model is not hot-reloadable; this is decision-008 territory.
- **Fast-path / micro-tier routing** — `claude:fast_model` vs. `claude:default` per-turn dispatch (e.g. trivial questions go to Haiku 4.5, complex to Sonnet 4.6). Would need a turn-classifier; out of scope. The existing `model=` kwarg on `ClaudeBrain.chat()` already covers programmatic per-turn override; the router doesn't need to change that.
- **Memory-fabrication preamble for Ollama turns** — flagged in P4.C1 spec § "what's deliberately NOT in scope" as P4.C2's territory. Implementing here would mean wedging a `system=` augmentation that the C1 spec doesn't define. Defer to P4.C2.1 if the post-projection drift survives.
- **Decision doc** — P4.C3 owns it (one decision per phase milestone, not per item).

## Dependencies

- **`rebuild/drafts/research/2026-05-07-p4c1-persona-projection-layer-spec.md`** — the (a)-half reads `SABRINA_SYSTEM_PROMPT_CLAUDE` / `SABRINA_SYSTEM_PROMPT_OLLAMA` from `brain/persona.py`. P4.C1's (a)-half ships those constants; if P4.C1 isn't in `main` when this spec is pulled, the Worker either (a) waits for C1, or (b) uses today's `from sabrina.brain.claude import SABRINA_SYSTEM_PROMPT` for both routes (the latter is a graceful-degrade path the open question Q3 below treats explicitly).
- **`rebuild/drafts/research/2026-05-05-p27-budget-tracker-spec.md`** — the (a)-half reads `BudgetLog.sum_month()` from `sabrina.budget`. P2.7's (a)-half is currently `[in-progress]` (committable post-P0); the router's `cost_aware` policy works against it directly. If P2.7 isn't in `main`, the router still ships — `cost_aware` degrades to `claude_default` when `budget_log=None`.
- **`rebuild/decisions/001-hardware-and-budget.md`** — sets the threshold the router enforces. The default `warn_threshold_usd: float = 10.0` mirrors `[budget].warn_usd_monthly`. If Eric edits `[budget]`, he edits `[brain.router]` too — they're the same threshold, two sources of truth. The open question Q1 below addresses this.
- **`sabrina-2/src/sabrina/brain/protocol.py`** — `Brain` protocol unchanged. The router implements the protocol; no protocol additions needed.
- **No new pip deps.** Pure stdlib + existing project surface.
- **Phase 3 (a)-half landed (`acd6725`)** — confirmed in DONE.md 2026-05-05. The router delegates through `Brain.chat()`, which post-`acd6725` accepts `tools=`; without that, the router would have to drop tools unconditionally.
- **Phase 3 (b)-half NOT a dependency for the (a)-half** — the router accepts `tools=` and forwards it; whether the toml flag flips is a P4.C3 concern.
- **CLAUDE.md "Partial-DoD tiers"** — the (a)-half does NOT touch `voice_loop.py`, audio I/O, clipboard, mss/pynput/pyperclip paths, or pywin32-only modules. Eligible for partial-DoD ship.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. `sabrina-2/src/sabrina/brain/router.py` exists with `Router`, `RouterMisconfigured`, `make_router_from_settings`, plus the `Brain`-protocol surface.
2. `sabrina-2/src/sabrina/config.py` has `BrainRouterConfig` model with the four named fields and defaults; `BrainConfig.router` defaults to `BrainRouterConfig()`.
3. `sabrina-2/sabrina.toml` has a `[brain.router]` block with the four fields and matching defaults; `policy` default value is `"claude_default"` so existing setups keep today's behavior on schema upgrade.
4. `sabrina-2/src/sabrina/brain/__init__.py` re-exports `Router`, `make_router_from_settings`, `RouterMisconfigured`.
5. `python3 -m compileall -q sabrina-2/src sabrina-2/tests` exits 0.
6. AST-parse spot-check on the three modified files (`router.py`, `config.py`, `brain/__init__.py`) confirms intact tails per CLAUDE.md edit-tool truncation hazard guidance.
7. `python3 -m pytest sabrina-2/tests/test_router.py -v` → 15/15 PASS.
8. Combined regression run on `test_router.py` + `test_smoke.py::test_claude_*` (the 6 (a)-half wire-up tests + the 4 ToolSpec round-trip tests) + `test_budget.py` + `test_persona_projection.py` (if P4.C1 (a)-half landed) → all PASS, no new failures vs. the worker-8am 2026-05-07 baseline (122 PASS / 10 SKIPPED / 4 pre-existing failures unchanged).
9. `ruff check sabrina-2/src/sabrina/brain/router.py sabrina-2/src/sabrina/config.py sabrina-2/src/sabrina/brain/__init__.py` reports no new errors above the post-P0 baseline.
10. Commit lands on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` in the body and a Windows DoD checklist in JOURNAL.md naming the (b)-half work (one Windows session per policy, ≥3 turns each, captures the route picked + the threshold transition for `cost_aware`).
11. JOURNAL.md run summary names the diff partition (1 new file + 3 extended files = 4) and the partition's independence from the in-flight P4.C1 (a)-half (zero file overlap; persona.py is read-only consumer here) and the P2.7 (a)-half (same: budget.py is read-only consumer).

**(b)-half DoD — owned by P4.C3, not this spec:**

12. `voice_loop.py` and `chat.py` instantiate the router via `make_router_from_settings`; existing direct-`ClaudeBrain` lines retired.
13. One Windows voice session per policy (`force_local`, `claude_default`, `cost_aware` with artificially-low `warn_usd_monthly`) ≥3 turns each; transcripts saved to JOURNAL; `cost_aware` transition observed (Claude turn 1, Ollama turn 3 after threshold crossed).
14. `events.py` `ThinkingStarted.tier` reflects the router-picked backend per turn; structlog log line `router.route_picked` fires once per turn at INFO.
15. Decision doc filed (next free integer in `rebuild/decisions/`, decision-doc voice) covering the C1 + C2 + C3 triplet under a single "Brain router shipped" entry.

## Open questions for NEEDS-INPUT

**Q1 — Budget threshold source: read `[brain.router].warn_threshold_usd`, read `[budget].warn_usd_monthly`, or read both and require equal?**

- **(a) `[brain.router].warn_threshold_usd` only.** The router has its own threshold field, defaulting to 10.0 to match decision 001. Cost: Eric editing `[budget].warn_usd_monthly` doesn't move the router gate — two sources of truth, easy to drift.
- **(b) Read `[budget].warn_usd_monthly` directly; no `warn_threshold_usd` field on `[brain.router]`.** Single source of truth. Cost: the router gate is forever pinned to the same threshold as the structlog warn line; if Eric wants the warn line to fire sooner than the route swap (typical: warn at $5, swap to local at $10), he can't.
- **(c) `[brain.router].warn_threshold_usd` defaults to `null`; if null, fall back to `[budget].warn_usd_monthly`.** Best of both — single source of truth by default, override available when needed.
- **Spec recommendation: (c).** The fallback shape lets Eric ship today's setup with one config knob (just `[budget].warn_usd_monthly`), and add the override later only if the warn-vs-swap divergence becomes load-bearing. Worker can ship the (a)-half against (c) without waiting; if Eric overrides to (a) or (b), the change is a 5-line resolver edit.

**Q2 — `cost_aware` policy hysteresis: instant transition, daily-only transition, or once-per-month?**

- **(a) Instant.** First turn after MTD crosses threshold → swap to Ollama; if the user does a memory-clearing operation that drops MTD below threshold mid-month, swap back to Claude. Cost: a noisy MTD (e.g. one expensive turn briefly pushes MTD over, but a refund-side correction adjusts it back) thrashes the route. Spec: low risk in practice — MTD is monotonic in the BudgetLog (no refund mechanism).
- **(b) Daily-only.** Recompute the route at most once per UTC day. Cost: a turn at 23:59 stays on Claude even if the threshold crosses; the next day's first turn picks up. Smoother, but loses the "stop spending the moment we hit $10" guarantee.
- **(c) Once-per-month.** Once swapped to Ollama, stay there until the next UTC month rollover. Cost: a one-time spike (Eric set up a long ad-hoc research session) locks the route to Ollama for the rest of the month even if MTD then drops below threshold via... actually MTD is monotonic, so this is identical to (a) except with a ratchet. The argument is "the threshold is a defense-in-depth gate, not a precise budget cap; once crossed, stay defensive."
- **Spec recommendation: (a).** The "MTD is monotonic" property of the BudgetLog (the (a)-half spec doesn't ship a refund/correction surface) means (a) and (c) collapse to the same observable behavior — the swap to Ollama persists for the rest of the month either way. (a) is the simpler implementation. If Eric's usage pattern reveals thrash (it shouldn't), the move to (b) or (c) is a one-line resolver change. Worker can ship the (a)-half against (a) without waiting.

**Q3 — Persona-projection prompt source if P4.C1 hasn't landed yet: wait for C1, or fall back to the existing `SABRINA_SYSTEM_PROMPT`?**

- **(a) Wait for C1.** Block the (a)-half ship until P4.C1 lands. Cost: serial dependency; if C1 stalls on its open NEEDS-INPUT, C2 stalls too.
- **(b) Fall back to `from sabrina.brain.claude import SABRINA_SYSTEM_PROMPT` for both routes.** Ships against today's `claude.py` directly; both routes get the Claude-flavored prompt. Cost: Ollama drift (the four cheap in-prompt fixes from `2026-04-26-ollama-parity.md` § 1.1, 1.4, 1.5, 1.8) is unaddressed; the `cost_aware` swap voice-fork has the exact problem P4.C1 was specced to solve. Spec: (b) is a temporary degraded-quality path that Eric should know about explicitly.
- **(c) Read both `SABRINA_SYSTEM_PROMPT_CLAUDE` and `SABRINA_SYSTEM_PROMPT_OLLAMA` if `brain/persona.py` exists; else fall back to (b).** Lazy import inside `make_router_from_settings`; the router degrades open without crashing if C1 hasn't landed. Cost: hides the C1 dependency under a try/except, which can mask C1's absence in production until a `cost_aware` swap actually happens.
- **Spec recommendation: (a).** The serial dependency is the right cost — C1's (a)-half is small (~120 lines, one new module + back-compat re-export) and the spec is detailed; a Worker can ship it in one slot. C2 against today's `SABRINA_SYSTEM_PROMPT` would ship a router that misroutes Ollama's voice on every `force_local` or `cost_aware` turn — the entire reason the router exists. Worker waits for C1 (or pulls C1 themselves first if both happen to be top-of-queue). If Eric explicitly approves (b) or (c) before pull (e.g. "ship the router today, fix the prompt later"), the change is a one-line import swap.

All three questions written to `NEEDS-INPUT.md` per the spec-writer role doc.

## Bailout / not-yet conditions

- The router's `tools=` forwarding behavior (drop on Ollama, pass on Claude) interacts with `[tools] enabled = true` once Phase 3 (b)-half ships. Spec mitigation: the `router.tools_dropped` log line is a debug-friendly signal that a `cost_aware` transition silently dropped tool support; that's expected behavior, not a bug, but the log line is what tells Eric mid-conversation. If the (b)-half wire-up adds `tools=BUILTIN_TOOLS` unconditionally before the router lands, the router still does the right thing — it drops on the route that doesn't support them.
- The `cost_aware` policy interacts with the `[budget].ceiling_usd_monthly = 100.0` ceiling. Decision 001 names the ceiling as observed-not-enforced today. The router's `warn_threshold` is below the ceiling by default (10 vs 100). Spec mitigation: the router only uses `warn_threshold_usd`; the ceiling stays observed-not-enforced unless Eric files a follow-up explicitly making `cost_aware` enforce it. (Possible future shape: `cost_aware_with_ceiling` policy that hard-stops ALL turns above ceiling — out of scope for v1.)
- If P2.7 (a)-half doesn't land before P4.C2 is pulled, the `cost_aware` policy degrades to `claude_default` at runtime (per the spec's `budget_log=None` branch). Worker JOURNAL entry should call this out so Eric knows the policy is structurally available but degraded until P2.7 lands.
- Edit-tool truncation hazard on `config.py`: this file has been hit twice in the last two weeks (worker-8am 2026-05-06 + worker-8am 2026-05-07's recovery). Spec mitigation: use bash-heredoc + `os.fsync()` rewrite if Edit truncates; `compileall` + AST + line-count check after every Edit.
- If the `Brain` protocol is amended in a parallel in-flight diff (e.g. P4.C1 adds a method), the router-as-Brain implementation needs to grow that method. Spec mitigation: `from typing import runtime_checkable` lets `isinstance(router, Brain)` catch protocol drift in tests; add a `test_router_implements_brain_protocol` assertion to `test_router.py`.
