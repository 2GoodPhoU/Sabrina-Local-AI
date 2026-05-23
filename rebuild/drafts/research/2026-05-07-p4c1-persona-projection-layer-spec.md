# P4.C1 — Router persona-projection layer for Ollama parity — spec

**Date:** 2026-05-07
**Author:** sabrina-spec-writer (06:50 scheduled run)
**Queue item:** QUEUE.md `Decomposed by phase` → Phase 4 → **P4.C1 Router — persona-projection layer for Ollama parity** (`[linux-runnable] [partial-dod-eligible] [P2] [M]`).
**Predecessors:**
- `rebuild/drafts/research/2026-04-26-ollama-parity.md` — twelve-axis divergence audit (Claude vs. qwen3:14b on the same persona block) plus the projection-layer recommendation. Treated as canon for *which* divergences cost what; this spec treats the audit's "five cheap in-prompt fixes / five projection-layer fixes / two accept-as-different-floor" partition as load-bearing.
- `rebuild/decisions/010-personality-spec.md` — operator-voice spec. Off-limits to edit per CLAUDE.md; this spec consumes it as input only.
- `rebuild/drafts/personality-plan.md` — names the "tighten block 2 on Ollama" follow-up. Not yet acted on.
- `rebuild/drafts/router-plan.md` — full router (P4.C2) design. P4.C1 is its prerequisite: without persona-projection, swapping to Ollama mid-day breaks the operator voice. This spec deliberately scopes *only* to the projection layer; routing logic is P4.C2.
- `sabrina-2/src/sabrina/brain/claude.py:248-378` — current persona blocks (`_PERSONA_BLOCK`, `_VOICE_RULES_BLOCK`, `_REFUSAL_AS_CHARACTER_BLOCK`, `_AUDIENCE_BLOCK_{A,B,C}`, `_MEMORY_CONTINUITY_BLOCK`, `build_system_prompt`, `SABRINA_SYSTEM_PROMPT`).
- `sabrina-2/src/sabrina/brain/ollama.py:33-100` — current Ollama backend; `chat()` accepts the `system` kwarg verbatim and forwards it to the Ollama REST client. No persona-aware logic today.

**Scope:** mixed-surface but the v1 (a)-half is fully Linux-runnable. Off-limits: `rebuild/decisions/`, legacy `core/`/`services/`/`utilities/`/`scripts/`/`models/`, `voice_loop.py` runtime path (the (b)-half wiring is router-side, P4.C2/C3, not this spec).

---

## What this item is

Today the persona blocks live inside `brain/claude.py` and the ClaudeBrain hardcodes them via `SABRINA_SYSTEM_PROMPT`. The voice loop, the chat REPL, and any future router all import the same string from `brain.claude` directly. When OllamaBrain receives that exact string, it emits a measurably different voice on the same turn — qwen3:14b drifts to closer-offer at ~1 in 8 turns, list-vomit at ~1 in 4, capability-language refusals on near-policy questions, and apology-stacking on retries (per `2026-04-26-ollama-parity.md` § 1.2/1.3/1.5/1.6). P4.C1 closes the gap with a model-agnostic projection layer: lift the persona blocks out of `brain/claude.py` into a new `brain/persona.py` module, give Ollama a tightened in-prompt overlay (the audit's five "cheap in-prompt fixes"), and add a post-process projection step that runs on Ollama's text deltas to strip the residual customer-service patterns the prompt can't suppress reliably (the audit's five "projection-layer fixes"). The two register-A audience blocks stay shared; only block 2 (voice rules) gets a divergent Ollama variant. ClaudeBrain calls remain byte-identical — the lift is structural, not semantic.

## Proposed approach

**(a)-half — `[linux-runnable] [partial-dod-eligible]`. Files touched:**

- `sabrina-2/src/sabrina/brain/persona.py` (new, ~180 lines) — single home for the persona blocks. Three top-level surfaces:
  - `build_system_prompt(*, register: str, backend: Literal["claude", "ollama"], tool_use_block: str = "") -> str` — replaces `brain/claude.py`'s `build_system_prompt`. The new `backend` kwarg picks block 2: `"claude"` returns the existing `_VOICE_RULES_BLOCK`; `"ollama"` returns a tightened variant with the four cheap in-prompt fixes named in `2026-04-26-ollama-parity.md` § 1.1, 1.4, 1.5, 1.8 (extra opener-banlist entries: "Sure!", "Of course!"; a sentence on hedge-stacking; one or two character-refusal vs. capability-refusal example pairs; the explicit "never refer to yourself as an AI/model/assistant" rule). Net Ollama-only delta is ~120 tokens per the audit's budget.
  - `project_ollama_text(text: str) -> str` — pure-text post-process. Five fixes from the audit's projection list:
    1. Closing-offer strip (1.2): drop sentences matching `(let me know|hope (this|that) helps|does that help)` if they're the final sentence.
    2. List-vomit dehydration (1.3): collapse markdown / numbered / "First, … Second, …" enumerations to a single comma-joined sentence. Token count delta is logged; no operation if the result would be >2× the original length.
    3. Apology dedup (1.6): if more than one of `{my mistake, sorry, my apologies, apologies for}` appears in a turn, keep only the first.
    4. Mode-bleed nothing (1.10): accepted as-is per the audit; document the choice in module docstring.
    5. Sentence-count truncation (1.12): if reply >4 sentences and the prior user message length is <60 chars (proxy for "didn't ask for detail"), truncate to 3 sentences plus `" Want more?"`.
  - `SABRINA_SYSTEM_PROMPT_CLAUDE: str` and `SABRINA_SYSTEM_PROMPT_OLLAMA: str` module-level constants for callers that don't need register/tool-use customization (mirrors the existing `SABRINA_SYSTEM_PROMPT` shape; the existing constant becomes a thin re-export of the Claude variant for back-compat).
- `sabrina-2/src/sabrina/brain/claude.py` — replace lines 248-378 (the persona-block private constants + `build_system_prompt` + `SABRINA_SYSTEM_PROMPT` definition) with a single re-export: `from sabrina.brain.persona import SABRINA_SYSTEM_PROMPT_CLAUDE as SABRINA_SYSTEM_PROMPT`. ClaudeBrain's call sites (none modified) keep importing `SABRINA_SYSTEM_PROMPT`. Net delta is `-128` lines from `claude.py` and the file shrinks below the 600-line "consider splitting" threshold the existing comments flag. **Edit hazard caveat per CLAUDE.md:** this is a multi-block private-constant lift that hit the edit-truncation hazard hard during `worker-8am 2026-05-06`'s `protocol.py`/`claude.py` recovery; budget bash-heredoc + `os.fsync()` rewrite + AST-parse spot-check after each Edit call.
- `sabrina-2/src/sabrina/brain/ollama.py` — extend `OllamaBrain.chat()` with an in-process projection wrapper. Two changes:
  - Around line 67-100, wrap the streaming `async for chunk in stream:` loop in a sentence-buffering shim (sentences end at `.!?` followed by whitespace or end-of-stream). On each completed sentence, run `project_ollama_text(buffered)` and yield the result as a `TextDelta`. The shim is bypassable via `OllamaBrain(project=False)` for tests that need raw output.
  - Add a private `_project: bool = True` constructor flag, default True. When False, behavior matches today's pass-through.
- `sabrina-2/src/sabrina/voice_loop.py` and `sabrina-2/src/sabrina/chat.py` — **not modified** in the (a)-half. Both currently import `SABRINA_SYSTEM_PROMPT` from `brain.claude`; the back-compat re-export keeps them functional. Switching either to the Ollama variant is router-side work (P4.C2/C3) and lives behind that item's `[brain.router]` config dispatch.
- `sabrina-2/src/sabrina/cli.py:1048-1051` — there's a `target_prompt = SABRINA_SYSTEM_PROMPT` reference (the personality-snapshot sub-command). Confirm this still resolves via the back-compat re-export; spot-check by running `python -c "from sabrina.brain.claude import SABRINA_SYSTEM_PROMPT; print(len(SABRINA_SYSTEM_PROMPT))"`.
- `sabrina-2/tests/test_persona_projection.py` (new, ~220 lines) — twelve unit tests:
  - `test_build_system_prompt_claude_matches_pre_lift_string` — golden test against the byte-stable Claude prompt (uses an inline literal of the current `SABRINA_SYSTEM_PROMPT` value to guard against accidental Claude-side drift).
  - `test_build_system_prompt_ollama_includes_extra_anti_patterns` — assert `"Sure!"`, `"Of course!"`, `"never refer to yourself as an AI"`, hedge-stacking sentence appear only in the Ollama variant.
  - `test_build_system_prompt_register_b_and_c_swap_audience_blocks` — both backends emit the new register block when toggled.
  - `test_project_ollama_text_strips_trailing_let_me_know` — `"That's how the cache works. Let me know if you need anything else."` → `"That's how the cache works."`.
  - `test_project_ollama_text_strips_hope_this_helps` — analogous.
  - `test_project_ollama_text_dehydrates_markdown_list` — `"- alpha\n- beta\n- gamma"` → `"alpha, beta, gamma."`.
  - `test_project_ollama_text_dehydrates_numbered_list` — `"1) alpha\n2) beta"` → `"alpha, beta."`.
  - `test_project_ollama_text_dedups_apology_stack` — `"I'm sorry. My apologies. Sorry again, here goes."` → `"I'm sorry. Here goes."` (first apology kept, rest dropped, non-apology sentences preserved).
  - `test_project_ollama_text_sentence_count_truncation_kicks_in_on_short_user_prompt` — 6-sentence reply + 30-char user prompt → 3 sentences + `" Want more?"`.
  - `test_project_ollama_text_sentence_count_truncation_skipped_on_long_user_prompt` — 6-sentence reply + 200-char user prompt → reply unchanged.
  - `test_ollama_brain_streams_projected_text_when_default` — fake Ollama client emits two list-vomit chunks; assert the brain's TextDelta stream emits the dehydrated form.
  - `test_ollama_brain_passes_through_when_project_false` — `OllamaBrain(project=False)`, same fake client; assert raw text reaches the caller.
- `sabrina-2/tests/personality/golden_set.yaml` — **read-only consumer**. The existing 256-line golden test set authored 2026-05-05 covers Claude register-A turns. P4.C1 does NOT extend the golden set; that's tied to a real-Ollama eval run (P4.C1 follow-up, listed under "what's deliberately NOT in scope" below).

**(b)-half — folded into P4.C2 / P4.C3, NOT deliverable here:**

- `voice_loop.py` and `chat.py` switching to the router (which then picks per-turn `system`) — P4.C3.
- `[brain.router]` config block — P4.C2.
- Real Windows voice-turn validation that an Ollama-routed turn reads as Sabrina to Eric — P4.C3 (the only seat where the projection layer's effect is observable end-to-end).
- Decision doc — P4.C3 promotes the entire router triplet (C1 + C2 + C3) under one decision number, per existing precedent (one decision doc per phase milestone, not per item).

## What's deliberately NOT in scope

- **Few-shot persona examples** — `2026-04-26-ollama-parity.md` § 2.2 recommends adding 4 few-shot pairs (~250 tok). The audit's recommendation is "land them when drift shows" (decision 010 alternative #1); the spec scope here is the projection layer, not the few-shot expansion. If post-projection drift is still measurable on the (b)-half, the follow-up is a P4.C1.1 spec adding the few-shot block to `_VOICE_RULES_BLOCK_OLLAMA`.
- **Tier-1 regex extension for Ollama-specific failure modes** — the `tests/personality/test_regex_smokes.py` file authored 2026-05-05 covers Claude-flavored failures. The Ollama-flavored regexes (per audit § 1.1, 1.4, 1.8) should land alongside a real-Ollama eval run. P4.C1 follow-up.
- **Memory-fabrication enforcement (audit § 1.11)** — the audit recommends both a tier-2 judge axis and an explicit voice-loop preamble. The voice-loop change is voice-loop runtime, off the (a)-half partial-DoD scope. P4.C2 absorbs it.
- **Ollama parity benchmarking** — running a real qwen3:14b eval against the post-projection turn shape. Requires an Ollama install in the test runner (Cowork sandbox doesn't have one); this is a Windows-side eval Eric runs as part of P4.C2's decision-doc work.
- **Per-tool persona overlays** — automation tools (`launch_app`, `list_files`) may want different voice rules ("don't speak the file count, just say it's done"). That's automation-plan territory (P4.B*), not P4.C1.

## Dependencies

- **`rebuild/drafts/research/2026-04-26-ollama-parity.md`** — canon for the partition. The (a)-half's `_VOICE_RULES_BLOCK_OLLAMA` content + the five projection rules are direct ports of the audit's recommendations. If Eric overrides any of the audit's "cheap in-prompt fix" vs. "projection layer" assignments, the spec routes around it: the projection rules are config-driven via a `[brain.persona]` config block (see open question below).
- **`rebuild/decisions/010-personality-spec.md`** — read-only canonical voice. The lift must not change any user-visible Claude behavior; the golden test guards this.
- **`sabrina-2/src/sabrina/brain/claude.py:55` `SABRINA_SYSTEM_PROMPT` import** — used by `voice_loop.py`, `chat.py`, `cli.py`. Back-compat re-export covers all three.
- **`sabrina-2/src/sabrina/brain/protocol.py`** — no changes. The lift is implementation-side; the `Brain` protocol is unchanged.
- **No new pip deps.** Pure stdlib + existing project surface.
- **Phase 3 (a)-half landed (`acd6725`)** — confirmed in DONE.md 2026-05-05. Phase 3 (b)-half is NOT a dependency: P4.C1's projection layer applies whether or not tools are enabled (Ollama doesn't support tools today; the projection runs on the text path only).
- **CLAUDE.md "Partial-DoD tiers"** — the (a)-half does NOT touch `voice_loop.py`, audio I/O, clipboard, mss/pynput/pyperclip paths, or pywin32-only modules. Eligible for partial-DoD ship.

## Concrete DoD (replaces the queue entry's prose DoD with a verifiable checklist)

**(a)-half DoD (Partial DoD, Linux-runnable, this spec's deliverable):**

1. `sabrina-2/src/sabrina/brain/persona.py` exists with the three surfaces named above (`build_system_prompt`, `project_ollama_text`, the two module-level constants).
2. `sabrina-2/src/sabrina/brain/claude.py` no longer defines persona-block private constants or `build_system_prompt`; `SABRINA_SYSTEM_PROMPT` is a back-compat re-export from `persona.py`.
3. `sabrina-2/src/sabrina/brain/ollama.py` `OllamaBrain` accepts `project: bool = True` constructor flag; default chat path runs `project_ollama_text` per sentence; `project=False` matches today's pass-through behavior.
4. `python3 -m compileall -q sabrina-2/src sabrina-2/tests` exits 0.
5. AST-parse spot-check on the three modified files (`persona.py`, `claude.py`, `ollama.py`) confirms intact tails (per CLAUDE.md edit-tool truncation hazard guidance).
6. `python3 -m pytest sabrina-2/tests/test_persona_projection.py -v` → 12/12 PASS.
7. Combined regression run on `test_persona_projection.py` + `tests/personality/test_regex_smokes.py` + `test_smoke.py::test_claude_*` (the 6 (a)-half wire-up tests + the 4 ToolSpec round-trip tests) → all PASS, no new failures vs. the worker-8am 2026-05-06 baseline (122 PASS / 10 SKIPPED / 4 pre-existing failures unchanged).
8. `python -c "from sabrina.brain.claude import SABRINA_SYSTEM_PROMPT; print(len(SABRINA_SYSTEM_PROMPT))"` returns the same length as before the lift (golden test's job, but spot-check verifies callers don't break).
9. `ruff check sabrina-2/src/sabrina/brain/persona.py sabrina-2/src/sabrina/brain/claude.py sabrina-2/src/sabrina/brain/ollama.py` reports no new errors above the worker-8am 2026-05-06 baseline.
10. Commit lands on `automation/<role>-2026-05-DD-<slot>` with `Windows-pending: e2e` in the body and a Windows DoD checklist in JOURNAL.md naming the (b)-half work (one Ollama-routed Windows voice-turn that reads as Sabrina, captured in the next P4.C2/C3 worker run).
11. JOURNAL.md run summary names the diff partition (5 files: persona.py new, claude.py shrunk, ollama.py extended, test_persona_projection.py new, golden test added) and the partition's independence from any other in-progress queue item.

**(b)-half DoD — owned by P4.C2 / P4.C3, not this spec:**

12. `[brain.router]` config dispatches `system=` to either `SABRINA_SYSTEM_PROMPT_CLAUDE` or `SABRINA_SYSTEM_PROMPT_OLLAMA` per chosen tier.
13. One Windows voice session ≥3 turns picks Ollama via the router and emits projected output; Eric reviews the resulting transcript and confirms the operator voice survives.
14. Decision doc filed (next number in `rebuild/decisions/`, decision-doc voice) covering the C1 + C2 + C3 triplet under a single "Brain router shipped" entry.

## Open questions for NEEDS-INPUT

**Q1 — `[brain.persona]` config block: ship now or defer?**

- **(a) Ship now.** Add a `[brain.persona]` block to `sabrina.toml` with `ollama_strip_closing_offer = true`, `ollama_dehydrate_lists = true`, `ollama_dedup_apologies = true`, `ollama_truncate_long_replies = true` (one bool per projection rule). Cost: ~30 tokens of TOML and four config-load test cases. Benefit: Eric can disable any single rule without a code edit if it misfires in a real conversation.
- **(b) Hard-coded constants for v1.** All five projection rules always-on, no config knob. Cost: a misfire in production needs a code edit + commit to disable. Benefit: smaller initial surface, one less ratcheted config decision to backfill if a rule turns out to be load-bearing.
- **(c) Compromise — single `ollama_projection_enabled = true` master switch only.** Ships with all-or-nothing behavior; per-rule knobs added later if a single rule misfires.
- **Spec recommendation: (a).** Decision 008's posture ("schema-versioned config" + the existing `[memory.semantic.embedder]` precedent of per-feature config knobs) reads in favor of the granular shape, and the four rules are independent enough that one of them (truncation in 1.12) is the most likely to misfire on Eric's actual usage pattern. Worker can ship the (a)-half against (a) without waiting; if Eric overrides to (b) or (c) before pull, Worker reroutes.

**Q2 — Apology-dedup heuristic: keep first or keep last?**

- **(a) Keep first.** `"I'm sorry. My apologies. Sorry again, here goes."` → `"I'm sorry. Here goes."`. Matches the audit § 1.6 example.
- **(b) Keep last.** Same input → `"Sorry again, here goes."`. Reads more "current" but loses turn-opening apology context.
- **(c) Keep neither — drop all apologies if there are >1.** Aggressive; the user's prompt may have actually warranted one.
- **Spec recommendation: (a).** The audit's example uses first-apology preservation; first-position is also more common in TTS-spoken context (the user has already heard the first sentence by the time the second renders). Worker can ship the (a)-half against (a) without waiting; if Eric overrides, the heuristic is one branch in `project_ollama_text`.

Both questions written to `NEEDS-INPUT.md` per the spec-writer role doc.

## Bailout / not-yet conditions

- The lift requires re-running the 2026-05-05 personality-snapshot test against the post-lift Claude string. If the snapshot test asserts on a specific block ordering and the lift accidentally re-orders blocks, the test will fail. Spec mitigation: the golden test in `test_persona_projection.py` pins the post-lift Claude string byte-for-byte against the pre-lift value; if they diverge, the lift has a bug and the spec bails before commit.
- If `worker-8am 2026-05-06` PROPOSED items around personality-snapshot test ownership are not yet resolved, the lift may interact with a separately-edited `claude.py` working tree. Spec mitigation: **read `git status sabrina-2/src/sabrina/brain/claude.py` first** and only proceed if the working tree on `claude.py` is clean against `acd6725`. If dirty, mark `[in-progress]` and write to NEEDS-INPUT before any production-code change.
- If `[brain.router]` config block lands in working tree before this spec is pulled (out-of-order Worker pickup of P4.C2), the projection layer is still independently shippable — the lift is purely structural and the new `OllamaBrain(project=True)` default keeps existing direct-Ollama callers working.
