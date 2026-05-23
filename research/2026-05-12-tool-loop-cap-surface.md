# Tool-loop cap surface — what the operator hears when the brain bails after 5 rounds

**Date:** 2026-05-12 03:30
**Run:** sabrina-researcher
**Source:** NEEDS-INPUT.md `[from: researcher / 2026-04-30 03:30]` menu, option 4 verbatim: "Recursive tool loop hardening for the wire-up's recursion cap = 5 (research doc lands the cap but doesn't ground the observability/error-budget shape — bounded question: 'how should tool-use loops surface "cap exceeded" to the operator voice without leaking internals?')."
**Why this question now:** the (a)-half wire-up shipped in `acd6725` lands `_MAX_TOOL_RECURSION = 5` and yields `Done(stop_reason="tool_recursion_cap")` when it fires. The (b)-half voice-loop wire-up is `[windows-required]`, parked for Eric's next Windows session — so the cap-exceeded surface is one of the things that gets specced now, validated on Windows when (b)-half lands, and shipped before any real voice turn flips `[tools] enabled = true`. The 04-30 menu has been five-times-dedup-skipped + de-facto-resolved on three of its four candidate items (P2.1 wake-word, P2.4 autostart, P4.C1 persona-projection all picked up at QUEUE level); option 4 (recursion-cap surface) is the one un-investigated entry, and the question is bounded enough for one slot. Per researcher 2026-05-09 03:30's precedent ("when a P0/P1 NEEDS-INPUT carries a structural question with operational weight, the researcher answers it even if a formally-eligible queue item is absent"), pivoting from the dedup-skip path is the right call.

---

## Question

> How should `ClaudeBrain.chat`'s tool-use recursion loop surface "cap exceeded" (`Done(stop_reason="tool_recursion_cap")`) to the operator voice when the (b)-half wire-up lands `[tools] enabled = true` — what does the user actually hear, and which observability surfaces (bus events, structlog) carry the signal for avatar / log consumers — without leaking implementation internals (the cap value, the word "recursion", the model's mid-loop debris)?

---

## What I checked

- `sabrina-2/src/sabrina/brain/claude.py` (full read, post-acd6725 with the P4.B1 kill-switch + dry-run hooks landed) — confirmed cap fires at line 257 via `stop_reason = "tool_recursion_cap"` then `break`; the captured `in_tokens`/`out_tokens` from `final.usage` ride out on the Done.
- `sabrina-2/src/sabrina/brain/protocol.py` (full read) — confirmed `Done.stop_reason: str | None = None` is the carrier field; `StreamEvent = TextDelta | Done | ToolUseStart | ToolUseDone` (no `ToolLoopCapped` variant exists today).
- `sabrina-2/src/sabrina/voice_loop.py:520-590` — the one and only `Brain.chat` consumer. Lines 542-543: `elif isinstance(ev, Done): in_tok, out_tok = ev.input_tokens, ev.output_tokens` — `stop_reason` is read by literally zero production-code paths. When the cap fires today, the voice loop sees `Done`, captures tokens, exits the chat-stream loop, drains `speak_queue` to None, and returns to idle. The user hears whatever text the model emitted on the 5th round (which may be a useful sentence, a half-formed sentence, or nothing) and then silence.
- `sabrina-2/tests/test_smoke.py:2651-2689` — `test_claude_recursion_cap_yields_done_with_cap_reason` is the only place `tool_recursion_cap` is read at all. Asserts `final.stop_reason == "tool_recursion_cap"` and `len(calls) == _MAX_TOOL_RECURSION`. Test is unit-level — doesn't exercise the voice-loop surface.
- `sabrina-2/src/sabrina/brain/persona.py` (full read) — Block 1 ("Information before apology. If something's broken, say so. If you don't know, say so."), Block 2 voice rules (no "I'd be happy to", no "Let me know if...", no "Hope this helps!", no closing offers; "One 'my mistake' per turn maximum"; "she/her"), refusal-as-character ("Refuse as character — sound like you wouldn't, not like you can't"). The personality spec gives a concrete check-list for the bail-out line's exact wording.
- `rebuild/decisions/010-personality-spec.md` (full read) — operator-voice canonical posture; "Refusals are character, not capability" (Ollama variant block); "If something's broken, say so."
- `sabrina-2/src/sabrina/events.py` (header + class list) — bus events for `ThinkingStarted` / `ThinkingFinished` / `StateChanged` / `SpeakStarted` / `SpeakFinished` / `BargeInDetected`. **No** `ToolUseStarted` / `ToolUseFinished` / `ToolLoopCapped` yet — those land with the (b)-half wire-up per `research/2026-04-29-claudebrain-tool-wire-up-surface.md` §5.
- `research/2026-04-29-claudebrain-tool-wire-up-surface.md` §5 + §6 — the (b)-half spec hands voice_loop two new branches (ToolUseStart, ToolUseDone) and bus events (ToolUseStarted, ToolUseFinished). Does NOT yet address `stop_reason="tool_recursion_cap"` surfacing or its observability shape — that's the gap this doc closes.
- `rebuild/drafts/tool-use-plan.md` line 307 (referenced via the 04-29 doc) — origin of the 5-cap recommendation; doesn't speak to user-surface behavior when the cap fires.

---

## What I found

### 1. The cap is implemented; the surface is not

`_MAX_TOOL_RECURSION = 5` is a module constant in `brain/claude.py:42`. The cap fires only at lines 250-258, after appending the tool_result turn to `api_messages`:

```python
recursion += 1
if recursion >= _MAX_TOOL_RECURSION:
    in_tokens = final.usage.input_tokens
    out_tokens = final.usage.output_tokens
    stop_reason = "tool_recursion_cap"
    break
```

The cap value is appropriate per the tool-use-plan (line 307) — generous for legitimate multi-step chains, tight enough to bail before burning Eric's token budget on a runaway loop. The value is NOT the question here; the surface is.

### 2. Today's silent failure mode

A `Done(stop_reason="tool_recursion_cap")` arrives at `voice_loop.py:542` and gets handled by a branch that reads only `input_tokens` and `output_tokens`. The branch is:

```python
elif isinstance(ev, Done):
    in_tok, out_tok = ev.input_tokens, ev.output_tokens
```

That's the entire consumption. After `Done`, the loop exits the `async for`, drains the speak queue, and returns to idle. The model's 5th-round text (whatever it was — a partial sentence, a "let me try one more tool", an apology, possibly nothing) gets streamed to TTS via `TextDelta` events before `Done` arrives, but the user gets **no signal that the loop bailed vs. that the model finished naturally**.

This is the canonical anti-pattern decision 010 names: silence in place of "if something's broken, say so." Worse, the model's 5th-round text is the LEAST reliable text in the turn (the model has been instructed to use tools and just exhausted its window without succeeding) — letting it stand as the final word is exactly the "trust the model's mid-loop debris" failure mode.

### 3. Three failure-shape variants the cap-bail covers

Reading the cap-trip path against the surface question separates three different "what just happened":

- **Shape A — model used tools productively but needed more rounds than the cap allows.** Legitimate multi-step task that the model genuinely needs >5 round-trips for. The 5th-round text will likely be a partial answer or "let me check one more thing" filler. User experience: a real task that just got cut short.
- **Shape B — model is in a feedback loop with itself.** The model keeps calling the same tool with slightly-different inputs because the result confused it (test `test_claude_recursion_cap_yields_done_with_cap_reason` constructs this shape — every round emits a `tool_use`, no text). The 5th-round text will be empty or a tool-call-only block. User experience: complete silence, no final sentence.
- **Shape C — model hits a handler error and keeps retrying.** A handler raises, the model sees `is_error=True` in `tool_result`, retries, sees the same error, retries, etc. The 5th-round text may be an apology or "let me try a different approach." User experience: the apology lands but the failed-task fact is lost.

All three want the SAME concrete surface — "I bailed on this; the work didn't finish" — but the optimal wording differs slightly. The recommendation below is shaped to cover all three.

### 4. Voice-rule constraints on the bail-out line

Decision 010 + persona.py Block 2 give a concrete check-list the line must pass:

- **No "I'd be happy to" / "Great question!" / "Let me..." / "Sure!" / "Of course!"** (Block 2 opener-list).
- **No "Let me know if..." / "Does that help?" / "Hope this helps!"** (Block 2 closer-list). Specifically: do NOT close the bail with "Want me to try again?" — that's the closing-offer pattern.
- **No identity disclaimer** ("As an AI...", "As a helpful assistant...", "I'm just a tool"). Operator voice; Sabrina is Sabrina.
- **One "my mistake" per turn maximum.** If the model's 5th-round text already includes an apology (Shape C), DO NOT prepend another apology — that double-apologizes. The simplest rule is the bail line never apologizes.
- **No expose of the cap value.** Saying "I hit my 5-round limit" leaks the implementation knob. Saying "I bailed out of a tool loop" leaks the word "tool" which the voice rules don't ban but is internal vocabulary the user doesn't need.
- **Refuse as character, not as capability.** "I won't keep grinding on this" reads as character; "I can't continue, max recursion exceeded" reads as machine-error.
- **1-3 short sentences, default 1.** Block 2 default reply length.

A line that passes all of these:

> **"I'm stuck on this. Stopping here."**

Six words. States the failure. No apology, no opener, no closer, no implementation detail. The follow-up turn from Eric is the natural retry surface — Sabrina doesn't ask, Eric just gives the next prompt.

Variants for each shape:
- Shape A (productive but cut short) — "I'm stuck on this. Stopping here." carries.
- Shape B (self-loop) — "I'm stuck on this. Stopping here." carries.
- Shape C (handler error retries) — same line, but the model's 5th-round text may already carry the actual error context, which is useful for the user. Keep both: the model's text first, then this line.

### 5. Where the bail line gets injected

The cleanest insertion point in voice_loop.py is INSIDE the existing `elif isinstance(ev, Done):` branch, BEFORE the speak-queue None sentinel goes in. The sketch (~6 lines):

```python
elif isinstance(ev, Done):
    in_tok, out_tok = ev.input_tokens, ev.output_tokens
    if ev.stop_reason == "tool_recursion_cap":
        bail_line = "I'm stuck on this. Stopping here."
        await speak_queue.put(bail_line)
        reply_parts.append(bail_line)   # so it lands in history
        await bus.publish(ToolLoopCapped(rounds=_MAX_TOOL_RECURSION, ...))
        log.warning("tool.recursion_cap", rounds=_MAX_TOOL_RECURSION, ...)
```

Three sub-points worth pinning:

- **History append.** Adding `bail_line` to `reply_parts` (which gets joined into the assistant message that goes into history at line 586) means the NEXT turn's prompt context will include "I'm stuck on this. Stopping here." — so if Eric says "ok, try again" the model doesn't get a confusing memory of having succeeded. Without this, the assistant-side history would carry only the model's mid-loop text, leaving the model unaware it bailed.
- **Bus event.** The (b)-half plan in `research/2026-04-29` §5 adds `ToolUseStarted` / `ToolUseFinished`. A third event `ToolLoopCapped(rounds: int, last_tool: str | None)` rides the same channel; avatar can show a brief "bail" gesture; structlog catches it for debugging. The `last_tool` field is the name from the most recent `ToolUseStart` in this chat() invocation — voice_loop tracks it in a local during the chat-stream loop.
- **Structlog redaction.** The existing `redact_secrets` processor (CLAUDE.md "no logging secrets") handles tool_input redaction; the cap-trip log line carries `rounds` (int) and `last_tool` (str = tool name, not arguments) so there's no secret to leak. If we wanted to log the last tool's INPUTS for diagnostics, the redactor handles that — but `last_tool` alone is sufficient for the bail signal.

### 6. The interaction with the kill-switch (P4.B1) and the cancel-token cases

`brain/claude.py` already emits `Done(stop_reason=...)` for three other terminal reasons besides `tool_recursion_cap`:

- `"cancelled"` — barge-in or kill-switch tripped (the `cancelled = True` paths). Voice-loop branch at line 564 already handles this via `cancel_token.cancelled` + `BargeInDetected` event.
- `final.stop_reason` direct from Anthropic (e.g. `"end_turn"`, `"max_tokens"`, `"stop_sequence"`). These pass through unchanged.

The kill-switch path (P4.B1) emits `cancelled` via the same `cancelled = True` channel — voice_loop already covers that surface. So `tool_recursion_cap` is the ONE Done.stop_reason today that has no surface and no spoken signal. Adding the bail-line + bus event closes it.

A natural extension worth flagging (not in scope for this doc): when `final.stop_reason == "max_tokens"` (model hit its `max_tokens` budget mid-reply, NOT the same thing as tool-recursion-cap), voice_loop also says nothing. The audit pattern is the same — but max_tokens is the model's own budget, not Sabrina's, and the model's final text typically completes a thought before the cap fires. Lower priority. Flagging in §Open follow-ups.

### 7. Why not surface via the model rather than via voice_loop

Alternative the question's "without leaking internals" clause invites: feed the cap-bail BACK to the model as a system message ("you've used 5 tool rounds, please summarize what you've got"), let the model write its own bail line. Rejected for three reasons:

- **The cap exists because the model wasn't converging.** Asking it to summarize in a 6th turn is the same loop one round deeper; it may use more tokens, may try another tool, may produce another partial answer.
- **It costs another round of tokens AND another API call.** The whole point of the cap is to bound spending; a recovery turn defeats it.
- **The bail line is structural, not conversational.** "I bailed" is a fact about the runtime, not the conversation. Hard-coding it keeps Sabrina's operator voice in Sabrina's hands, not in whatever the model emits when prompted to summarize a failed loop.

### 8. Why not surface via the avatar/console only, leaving the voice silent

Alternative: log + publish bus event + show a dim "(tool loop capped)" line on the console, but DO NOT speak. The case for this is "audio is the user-active channel; an audible bail risks talking over the user."

Rejected because the bail fires DURING a turn — the user is in `thinking` state, waiting for Sabrina to reply. Silence at that moment reads as "she gave up and isn't telling me." Audible bail matches the operator-voice posture from decision 010 ("If something's broken, say so"). The 6-word line costs ~1.5 seconds of TTS; not a barge-in problem.

---

## Recommendation

**Actionable change.** Fold the cap-surface change into the (b)-half voice-loop wire-up that's parked Windows-pending. Three additions to the (b)-half diff:

1. **`events.py`** — add `ToolLoopCapped(rounds: int, last_tool: str | None)` event (Pydantic model, same `_EventBase` parent as the other bus events; `kind: Literal["tool_loop_capped"]` discriminator). ~5 lines.

2. **`voice_loop.py`** — track `last_tool: str | None = None` in the chat-stream local scope, set on every `ToolUseStart`. In the existing `elif isinstance(ev, Done):` branch (line 542), add an `if ev.stop_reason == "tool_recursion_cap":` sub-branch that (a) speak-queues the literal string `"I'm stuck on this. Stopping here."`, (b) appends the same to `reply_parts` so it lands in `history`, (c) `await bus.publish(ToolLoopCapped(rounds=_MAX_TOOL_RECURSION, last_tool=last_tool))`, (d) `log.warning("tool.recursion_cap", rounds=_MAX_TOOL_RECURSION, last_tool=last_tool)`. ~8 lines including the local-state plumbing.

3. **`tests/test_smoke.py`** — extend `test_claude_recursion_cap_yields_done_with_cap_reason` (already exists at line 2651) with a sibling voice-loop test that asserts (a) the bail line appears in the speak queue exactly once, (b) the bail line is the assistant-message content stored in history, (c) a `ToolLoopCapped` bus event is published, (d) the structlog warning fires with `rounds=5`. ~30 lines via the existing `FakeBus` + `FakeSpeaker` fixtures from `tests/test_utils/mocks.py`.

The bail line `"I'm stuck on this. Stopping here."` is the spec. The wording was vetted against decision 010 Block 1 ("information before apology"), Block 2 (opener + closer + apology + length rules), and the refusal-as-character framing. Override knob for Eric if the wording proves wrong on dogfood: make it a module constant `_TOOL_LOOP_CAP_BAIL_LINE` in `brain/claude.py` or `voice_loop.py` so a one-line edit retunes it; no config-knob churn (per decision 010's "voice in code is fine, override is one edit").

The change does NOT modify the (a)-half landed code (`brain/claude.py` still emits the same `Done(stop_reason="tool_recursion_cap")` shape); it only adds the surface on the consumer side. Composable with the existing (b)-half wire-up diff (`events.py` + `voice_loop.py` + `sabrina.toml` flip per `research/2026-04-29` §5/§6) — same files, additive shape, lands in the same Worker slot Eric runs on Windows.

Net Worker effort once the FUSE lock clears: ~45 LOC across 3 files + extension of one existing test. The Windows e2e validation step is one synthetic turn — prompt that forces tools into a loop (or use the existing test's `FakeAnthropicClient.MessageStreamFactory(always_tool_use=True)` shape) and confirm the bail line speaks.

---

## Open follow-ups

1. **`max_tokens` stop reason has the same silent-failure surface.** When `final.stop_reason == "max_tokens"`, voice_loop also says nothing — the model's reply cuts off mid-thought, user gets silence after the cut. Different shape from `tool_recursion_cap` (model's budget, not Sabrina's; doesn't reflect a logic failure), but identical "silence as bail" anti-pattern. Worth a separate bounded research slot once tools ship and Eric has dogfood signal. Recommended bail line if surfaced: `"Hit my reply length. Want the rest?"` (DOES use the closing-offer pattern — but `max_tokens` is the one case where "want more" is the literal correct question, since the user can re-ask with `--max-tokens` lifted).

2. **`last_tool` enrichment for diagnostics.** The (b)-half plan tracks `last_tool` in voice_loop scope. A natural follow-up is to also log the LAST tool's input dict (redacted via `redact_secrets`) on the cap-trip warning, so debugging a Shape-B self-loop has the inputs visible. Anti-sprawl says don't add it until the FIRST cap-trip-debug session needs it; flagging here so the future debugger doesn't re-derive.

3. **Avatar cue when the bail fires.** Decision 010 reserves block 4 (cue vocabulary) for avatar; when the avatar lands (P4.A1+), a `bailed` or `stuck` cue tag in the bail line would drive avatar animation. Not in scope today (avatar is P4 / unshipped), but the wording `"I'm stuck on this. Stopping here."` was chosen for cue-friendliness — "stuck" maps to a furrowed-brow tier-1 affect; "stopping here" is firm-resolution body language; no contradiction between the audio and the avatar register.

4. **Recursion-cap value as a config knob.** Today it's a module constant. If the cap-bail fires too often on real Eric workloads (which the dogfood will show), the natural fix is to widen the constant; if it fires too rarely (runaway loops Eric wants to bail sooner), narrow it. Either way the rate is what informs the value, not pre-fitting. Anti-sprawl: leave it constant until a second caller (or a real cap-rate-debug shift) earns the knob.

5. **Bus-event consumption symmetry with `BargeInDetected`.** `BargeInDetected` is currently produced and consumed only by `voice_loop` itself. `ToolLoopCapped` would be the same shape — produced by voice_loop, consumed by future avatar / external observers. Not a follow-up per se, just a sanity-check on the precedent: the bus-event addition is the right shape because it matches the existing `BargeInDetected` lifecycle, not because there's a current second consumer.

6. **Override-knob via `[brain] tool_loop_cap_bail_line` in TOML.** Spec-recommend NOT doing this. Per decision 010, "An override changes one paragraph in the plan and one slogan in this doc — nothing else cascades" — the bail line is one slogan; making it config-tunable invites Eric to tune it once, forget, and then a year later wonder why the bail reads weirdly. Module-constant override (re-edit `_TOOL_LOOP_CAP_BAIL_LINE` and re-commit) is the right ceremony level. Flagging so the future "should this be configurable" question has a recorded position.

---

## Composability with current state (today's pickup)

This research doc lands in `research/` only — no code changes. The recommended change folds into the (b)-half wire-up that's parked for Eric's next Windows session; nothing here unblocks the 10 lock-blocked diffs in working tree or touches the FUSE lock surface (worker-8am 2026-05-07 NEEDS-INPUT still the canonical record). Composes with PROPOSED #37/#38 (researcher 2026-05-09's read/write-side disciplines) — the recommended `voice_loop.py` edit uses Edit-tool-with-anchor per #38's codification, and the `brain/claude.py` post-edit AST-parse verification per #37 catches the typical truncation hazard. Composes with P4.B1's KillSwitch / dry_run hooks (already in the (a)-half landed code at `claude.py:67-69, 156-173`) — the kill-switch path emits `cancelled`, not `tool_recursion_cap`, so the bail-line surface for the cap doesn't interfere with the kill-switch's `BargeInDetected` surface.

---

## What I did NOT investigate

- Did NOT spec the exact `events.py` Pydantic shape for `ToolLoopCapped` — left to the (b)-half spec writer when the Windows-session pickup happens.
- Did NOT propose changing `_MAX_TOOL_RECURSION = 5` value — out of scope for the surface question.
- Did NOT touch the cap-bail surface for OllamaBrain — Ollama raises `NotImplementedError` on `tools=` per `research/2026-04-29` §4, so the cap-bail path doesn't reach it.
- Did NOT investigate cap-bail interaction with the P4.C2 router (which can swap Claude → Ollama mid-conversation). The cap-bail fires inside `ClaudeBrain.chat`, before the router would see another opportunity to swap; the next user turn re-enters the router fresh. Worth a sanity-check on the router (a)-half landed code if/when it commits, but not gating.
