# ClaudeBrain tool-use wire-up — concrete diff surface

**Date:** 2026-04-29 03:30
**Run:** sabrina-researcher
**Source:** QUEUE.md P1 ("Wire ClaudeBrain.chat to pass tools= and handle ToolUseBlock events (~150 LOC)").
**Why this question:** the queue item ships with a definition-of-done that depends on `ToolSpec.to_anthropic_dict` round-trips and a working e2e voice turn, but doesn't enumerate the exact files / events / SDK calls. A Worker has one slot to deliver. Without a grounded diff, the first attempt is likely to bail with `[in-progress]` (per PROPOSED #4).

---

## Question

> In the current sabrina-2 codebase, what is the precise wire-up surface required to make `ClaudeBrain.chat` pass `tools=` to the Anthropic SDK, dispatch `ToolUseBlock` events end-to-end (recursive tool-result follow-up included), and surface those events to `voice_loop`? Specifically: which files change, which Anthropic SDK iteration API replaces the current `text_stream`-only loop, and what's the shape of the tool_result follow-up message?

---

## What I checked

- `sabrina-2/src/sabrina/brain/protocol.py` (full read).
- `sabrina-2/src/sabrina/brain/claude.py` (full read).
- `sabrina-2/src/sabrina/brain/ollama.py` (chat() signature + body).
- `sabrina-2/src/sabrina/tools/__init__.py` (ToolSpec definition + BUILTIN_TOOLS).
- `sabrina-2/src/sabrina/tools/clipboard.py` (handler signature/return shape).
- `sabrina-2/src/sabrina/voice_loop.py` (current Brain.chat call site + event handling).
- `sabrina-2/src/sabrina/config.py` lines 213-229 (`ToolsConfig`, `WriteClipboardToolConfig`).
- `sabrina-2/sabrina.toml` (`[tools]` and `[tools.write_clipboard]` blocks present).
- `sabrina-2/tests/test_smoke.py` lines 1869-1965 — ToolSpec round-trip tests.
- `sabrina-2/pyproject.toml` — `anthropic>=0.40` is the pinned floor.
- `rebuild/drafts/tool-use-plan.md` — the standing plan from 2026-04-23.
- `rebuild/drafts/research/2026-04-26-toolspec-first-three.md` (referenced; not re-read here, content already reflected in the plan).
- `git status` (via the night-auditor's report) — confirms `claude.py +134`, the ToolSpec/clipboard/test additions are uncommitted but present in the working tree.

---

## What I found

### 1. The state of the working tree vs. the plan

`ToolSpec` is already shipped (uncommitted) in `sabrina/tools/__init__.py` — *not* in `brain/protocol.py` where the plan put it. `BUILTIN_TOOLS` is populated with one entry: `write_clipboard`. The dataclass exposes `to_anthropic_dict()` and `to_mcp_dict()` with the field-naming difference the plan specifies (snake_case vs. camelCase).

**Round-trip tests already exist** at `tests/test_smoke.py:1872-1965`:
- `test_toolspec_to_anthropic_dict_uses_input_schema_key`
- `test_toolspec_to_mcp_dict_uses_camelcase_input_schema_key`
- `test_toolspec_round_trip_both_serializations_share_payload`
- `test_toolspec_mcp_shape_has_required_fields_per_spec`

**Implication:** PROPOSED.md #3 ("Add ToolSpec.to_anthropic_dict / to_mcp_dict round-trip tests") is already done in the working tree. The proposal was authored before the night-auditor's working-tree census surfaced. This is the canonical state-vs-reality gap PROPOSED #5 calls out — it's now concrete.

`config.tools.enabled` defaults to `False` in `config.py:226`. Even with the wire-up landed, the master switch must be flipped (in `sabrina.toml` or via env) for the brain to actually receive `tools=`. The toml file already has the `[tools]` block present.

### 2. What's actually missing from `protocol.py`

Current `StreamEvent` union (line 92):

```python
StreamEvent = TextDelta | Done
```

The `Brain` Protocol's `chat()` signature (lines 101-108) accepts `system`, `max_tokens`, and `cancel_token` — **not** `tools`.

Two additions are needed:

1. Two new event classes — `ToolUseStart(tool_id, name, input)` and `ToolUseDone(tool_id, name, result, error: str | None = None)` — both `frozen=True, slots=True` per the protocol's pattern. These extend `StreamEvent`.
2. A `tools: list[ToolSpec] | None = None` kwarg on the `Brain` Protocol's `chat()` method.

**Layering caveat:** `ToolSpec` lives in `sabrina/tools/__init__.py`. Importing it into `brain/protocol.py` creates a `brain → tools` import edge that the package layout has so far avoided (the brain package imports from `logging` only). The two clean options:

- **(A)** Move `ToolSpec` to `brain/protocol.py` per the original plan. ~30 lines moved; `tools/__init__.py` re-exports `ToolSpec` from there for backward compat with the already-shipped tests.
- **(B)** Use `from typing import TYPE_CHECKING` in `protocol.py` to import `ToolSpec` for type-checking only and accept `list[Any]` at runtime, OR keep `ToolSpec` where it is and use `from sabrina.tools import ToolSpec` in `protocol.py` — accept the import edge.

Option (B) preserves anti-sprawl posture (handler + spec colocated in `tools/`); option (A) honors the plan literally. **Recommendation: (B)**. The argument from `tools/__init__.py:4-9` ("ship needs *some* canonical home for `ToolSpec`. Keeping it in `tools/__init__.py` ... means handlers and their registrations live next to the spec class") still holds. Update the plan, not the code.

### 3. The streaming-loop change in `claude.py`

Current loop (lines 63-76):

```python
async with self._client.messages.stream(**kwargs) as stream:
    async for text in stream.text_stream:
        if cancel_token is not None and cancel_token.cancelled:
            cancelled = True
            break
        if text:
            yield TextDelta(text=text)
    if not cancelled:
        final = await stream.get_final_message()
        in_tokens = final.usage.input_tokens
        out_tokens = final.usage.output_tokens
        stop_reason = final.stop_reason
```

There are **two viable iteration strategies** for catching tool_use:

- **(I)** Switch to `async for event in stream` and dispatch on `event.type` — `content_block_start` (with `event.content_block.type == "tool_use"`), `content_block_delta` (with `delta.type` either `text_delta` or `input_json_delta` for argument accumulation), `content_block_stop`, `message_stop`. This is the strategy the tool-use-plan.md sketch uses (lines 270-285).
- **(II)** Keep the existing `text_stream` loop. After it completes, call `await stream.get_final_message()` and inspect `final.content` for `ToolUseBlock` instances. If `final.stop_reason == "tool_use"`, dispatch tools, build the follow-up message, recurse.

**Recommendation: (II).** Reasons:

- The voice loop's first-sentence-streaming UX (`_split_off_sentence` + `speak_queue` in `voice_loop.py:485-558`) depends on `TextDelta` events arriving as soon as the model emits text. `text_stream` is the SDK's optimized path for that; switching to raw event iteration adds per-chunk dispatch overhead inside the hot path of every voice turn — including turns that don't use tools. (II) keeps the fast path fast and only pays the tool-dispatch cost when `stop_reason == "tool_use"`.
- Anthropic's tool_use blocks **arrive intact in `final.content` after the stream completes** — same as Ollama's behavior (see `tool-use-plan.md:170-172`: "tool_calls tend to arrive whole, at the end of the stream"). There's no streaming-tool-arg observability gain from (I) for the voice use case (Sabrina's tools are all sync-fast; argument accumulation isn't useful intermediate state).
- Smaller diff: ~80 LOC inside `chat()` instead of ~150. Frees the rest of the slot for the `ollama.py` raise + the voice_loop surface.

The shape of (II):

```python
# Conceptual sketch for claude.py — not the literal patch.
api_tools = [t.to_anthropic_dict() for t in tools] if tools else None
recursion = 0
MAX_RECURSION = 5
while True:
    kwargs_local = dict(kwargs)
    if api_tools is not None:
        kwargs_local["tools"] = api_tools
    async with self._client.messages.stream(**kwargs_local) as stream:
        async for text in stream.text_stream:
            if cancel_token is not None and cancel_token.cancelled:
                cancelled = True
                break
            if text:
                yield TextDelta(text=text)
        if cancelled:
            break
        final = await stream.get_final_message()
    if final.stop_reason != "tool_use":
        in_tokens = final.usage.input_tokens
        out_tokens = final.usage.output_tokens
        stop_reason = final.stop_reason
        break
    # Recurse on tool_use.
    tool_uses = [b for b in final.content if b.type == "tool_use"]
    tool_results = []
    for tu in tool_uses:
        yield ToolUseStart(tool_id=tu.id, name=tu.name, input=tu.input)
        spec = next((t for t in tools if t.name == tu.name), None)
        if spec is None:
            err = f"unknown tool: {tu.name}"
            yield ToolUseDone(tool_id=tu.id, name=tu.name, result=None, error=err)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                 "content": err, "is_error": True})
            continue
        try:
            result = await spec.handler(**tu.input)
            yield ToolUseDone(tool_id=tu.id, name=tu.name, result=result)
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                 "content": json.dumps(result), "is_error": False})
        except Exception as exc:
            yield ToolUseDone(tool_id=tu.id, name=tu.name, result=None, error=str(exc))
            tool_results.append({"type": "tool_result", "tool_use_id": tu.id,
                                 "content": str(exc), "is_error": True})
        if cancel_token is not None and cancel_token.cancelled:
            cancelled = True
            break
    if cancelled:
        break
    # Append assistant turn (with full content) + user turn with tool_results.
    api_messages.append({"role": "assistant", "content": [b.model_dump() for b in final.content]})
    api_messages.append({"role": "user", "content": tool_results})
    kwargs["messages"] = api_messages
    recursion += 1
    if recursion >= MAX_RECURSION:
        stop_reason = "tool_recursion_cap"
        break
yield Done(input_tokens=in_tokens, output_tokens=out_tokens,
           stop_reason="cancelled" if cancelled else stop_reason)
```

Notable details:

- `final.content` is a list of `ContentBlock` instances; `b.type == "tool_use"` filters them. `ToolUseBlock` exposes `.id`, `.name`, `.input`. (Anthropic SDK ≥ 0.40 — pyproject.toml floor — has these.)
- The follow-up `tool_result` content block uses `tool_use_id` (not `id`), and `content` is either a string or a list of content blocks. JSON-stringifying the handler dict matches the plan's MCP-friendly wrapping (`tool-use-plan.md:577-580`).
- `is_error=True` on a `tool_result` lets the model see the error and either retry or apologize. Matches `ToolUseDone.error is not None`.
- The `b.model_dump()` round-trip on the assistant's prior content preserves `tool_use` blocks intact for the recursive call. Pydantic-backed in the Anthropic SDK.
- Recursion cap = 5 matches the plan's recommendation (`tool-use-plan.md:307`).

### 4. The Ollama side

`ollama.py:29-36` already accepts `system`, `max_tokens`, `cancel_token` — but **not `tools`**. Per Q2 of the plan (the recommendation Eric still has to confirm but is the working assumption), the cleanest patch is two lines added at the top of `chat()`:

```python
if tools:
    raise NotImplementedError(
        f"Backend {self.name!r} does not support tool use; "
        "pick Claude or set [tools] enabled = false."
    )
```

The `tools=` kwarg also has to be added to the signature (with a default of `None`) so callers passing it don't trip a TypeError on selection-time. Without that, even *configuring* tool use breaks Ollama as the active backend.

### 5. The voice_loop surface

`voice_loop.py:530-543` is the only call site of `Brain.chat()`. Current shape:

```python
async for ev in turn_brain.chat(
    history, system=turn_system, cancel_token=cancel_token
):
    if isinstance(ev, TextDelta):
        ...
    elif isinstance(ev, Done):
        ...
```

Three additions:

1. Pass `tools=BUILTIN_TOOLS` (filtered by `settings.tools.allowed` and gated on `settings.tools.enabled`) to `turn_brain.chat()`.
2. Two new `isinstance(ev, ToolUseStart)` / `isinstance(ev, ToolUseDone)` branches that print a dim console line ("(tool: write_clipboard ...)") and publish to the bus. Bus events would mirror the stream events; that's an `events.py` addition (`ToolUseStarted`, `ToolUseFinished`).
3. The `import` line at top of voice_loop.py needs `ToolUseStart, ToolUseDone` added to the `from sabrina.brain.protocol import ...` row.

The vision-mode brain swap (lines 386-419) instantiates a fresh `ClaudeBrain` for the turn — the tools list would need to flow through there too if vision turns are supposed to use tools. **Recommendation: pass `tools=None` for vision turns explicitly.** Vision is already an end-of-turn answer; there's no value in giving the vision pass tool access on day one.

### 6. CancelToken interaction during tool execution

The current `cancel_token.cancelled` polling sites in `claude.py:65-68` cover the text-stream loop only. With tool use:

- Poll `cancel_token.cancelled` between tool dispatches (within the for-loop over `tool_uses`).
- Poll `cancel_token.cancelled` before incrementing `recursion` and entering the next `messages.stream()` call.

The three initial tools (`write_clipboard` only ships today; `get_time` and `search_memory` are still in the plan) are all `<10ms` synchronous wrapped in `asyncio.to_thread`. No cooperative cancellation inside handlers; turn-level polling is sufficient (matches `tool-use-plan.md:181-195`).

### 7. Tests to add (worker-sized)

- `test_claude_executes_one_tool_and_continues` — stub Anthropic client; first stream emits tool_use, second stream emits text + final; assert event sequence (`TextDelta?`, `ToolUseStart`, `ToolUseDone`, `TextDelta+`, `Done`).
- `test_claude_recursion_cap_yields_done_with_cap_reason` — stub that always emits tool_use; assert `Done(stop_reason="tool_recursion_cap")` after 5 iterations.
- `test_claude_tool_handler_error_surfaces_in_tool_result` — handler raises; assert `ToolUseDone.error` is set and the follow-up `tool_result` carries `is_error=True`.
- `test_claude_unknown_tool_name_returns_error_result` — model invents a name not in `tools`; recurse with an error tool_result instead of crashing.
- `test_ollama_raises_cleanly_when_tools_provided` — pass `tools=[some_spec]` to OllamaBrain.chat(); assert `NotImplementedError` with the exact message.
- `test_brain_chat_tools_none_is_backward_compatible` — default-path regression; existing call sites that don't pass `tools=` keep working byte-for-byte.

The four ToolSpec-shape tests (already in the working tree) close out the round-trip side of the DoD.

---

## Recommendation

**Actionable change.** The wire-up surface is now precise enough to ship in two Worker-sized slots, matching PROPOSED #4's split. The two halves:

- **(a)** `protocol.py` adds `ToolUseStart`/`ToolUseDone` + extends `StreamEvent` and the `Brain.chat` Protocol signature with `tools=`. `claude.py` keeps the `text_stream` loop, adds the recursive tool-dispatch loop using strategy (II) above, with `_MAX_TOOL_RECURSION = 5` constant. `ollama.py` adds the `tools` kwarg + clean-raise. New unit tests cover dispatch, recursion cap, error surfacing, unknown-tool, ollama-raise, backward-compat.

- **(b)** `events.py` adds `ToolUseStarted`/`ToolUseFinished` bus events. `voice_loop.py` imports the new protocol events, wires `tools=BUILTIN_TOOLS` (gated on `settings.tools.enabled`), prints/buses the events, leaves vision turns at `tools=None`. `sabrina.toml` flips `[tools] enabled = true`. Windows e2e validation: a turn that says "copy 'hello world' to my clipboard" should fire `write_clipboard` and the clipboard should reflect it on the user's machine (per `validate-automation.md` ship criterion).

The slot boundary keeps (a) under one hour for a Worker (~80 LOC + 6 tests, no e2e gate) and (b) honest about needing the Windows-side validation step (~70 LOC + Windows access).

---

## Open follow-ups

1. **Plan-vs-code divergence on `ToolSpec` location.** Plan says `brain/protocol.py`; code shipped to `tools/__init__.py`. Recommendation above is to update the plan, not the code — but Eric should confirm before the next plan-doc sweep, because the layering rationale (anti-sprawl colocation) is a real argument and probably belongs in a DECISIONS.md entry rather than a plan-doc footnote.
2. **`system_suffix` kwarg.** `tool-use-plan.md:236-238` proposes a separate `system_suffix` kwarg on `Brain.chat`. The current voice_loop concatenates the retrieved-memory block into `turn_system` inline (`voice_loop.py:466`). No second caller exists today. Hold on adding it (anti-sprawl #2). Note here so the next planner doesn't re-derive the question.
3. **PROPOSED #3 is already done.** Round-trip tests exist at `tests/test_smoke.py:1869-1965`. The next planner can mark PROPOSED #3 as "done in-tree, awaiting commit per PROPOSED #1+#5 triage" rather than graduating it to QUEUE.
4. **Master switch defaults to off.** `config.py:226` keeps `tools.enabled = False`. Worker (b) needs to flip it explicitly in `sabrina.toml` as part of the e2e validation step. Don't expect a tool to fire just because the wire-up shipped.
5. **Tool-use observability in logs.** Not in scope for the queue item, but `log.info("tool.start", ...)` / `log.info("tool.done", ...)` calls in claude.py would let the structlog-redacting processor catch any tool inputs that leak secrets. Worth a follow-up proposal once the wire-up has bedded in.
