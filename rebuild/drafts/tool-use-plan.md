# Tool use plan — extending the Brain protocol

**Date:** 2026-04-23
**Status:** Research + draft. Implementation blocked on three open
questions at the top of this doc. Everything below is settled research.
**Prerequisites:** barge-in's `CancelToken` must land first (tool
execution runs inside the same turn; cancellation must stop both the
brain stream and an in-progress tool call).
**Closes:** decision 006 thin-spot "tool use; not wired up." Unblocks
the automation component.

## OPEN QUESTIONS (block implementation — Eric's call)

1. **Which tools ship in v1?** Research below recommends three zero-risk
   tools that cost nothing to add: `get_time`, `read_clipboard`,
   `search_memory`. Any of them could be cut; other candidates
   (`get_weather` requires an API key choice; `open_app` is
   automation-adjacent and risky) are explicitly held back. Confirm
   the starting set.

   **Recommendation: ship all three (`get_time`, `read_clipboard`,
   `search_memory`) as the v1 set.** Each clears the rebuild's
   bar — zero external deps, read-only, one caller now and obvious
   second callers later (every future tool reuses this plumbing).
   Trimming any of them weakens the "first real test of the protocol"
   goal: three tools exercise the dispatch loop, the Anthropic
   tool-result round-trip, and the recursion cap. Two wouldn't. Plus
   `search_memory` is the one that earns the whole plan its keep by
   turning the decision-007 retrieval path into something the brain
   can steer. Override: cutting `read_clipboard` is the cleanest trim
   if Eric wants a tighter session — it's the one with a potential
   privacy footprint (even read-only), though still strictly less
   than what vision already sees.

2. **Ollama tool use: ship day-one or Claude-only first?** Claude's
   tool-use API is mature and documented. Ollama supports tools via
   `qwen2.5` / `llama3.1` with OpenAI-compatible shapes, but behavior
   across Ollama versions has been inconsistent. Options:
   (a) Implement both — Claude works reliably, Ollama works "mostly."
   (b) Implement Claude only; raise a clean "tool use not supported
   on this backend" if the router picks Ollama for a tool-requesting
   turn. Ship Ollama in a follow-up once behavior stabilizes.
   (a) is more honest to decision 001's "local-first." (b) is faster
   and safer.

   **Recommendation: (b) — Claude only for v1; Ollama raises cleanly.**
   Tool use is upstream of automation, which is the highest-risk
   component in the whole roadmap. The critical property for
   automation's safety is that when the brain says "call `launch_app`,"
   the tool call arguments are reliable and the schema is honored.
   Qwen2.5's Ollama tool-call path has known edge cases (whole-call at
   end-of-stream, version drift). Shipping Claude-only first locks in
   the reliable half and gives the automation plan a solid upstream;
   Ollama tool use slots in later as an additive backend upgrade
   without touching the protocol. "Local-first" is a routing posture,
   not a tool-use posture — the router plan still defaults to local
   for non-tool turns regardless. Override: if Eric wants (a), the
   `ollama.py` `raise` becomes a `_translate_tool_calls` function and
   the test suite grows by ~4 tests covering the OpenAI-compatible
   shape. Additive either way.

3. **Tool-execution threading: always-threaded or per-tool?** Every
   tool must run under `asyncio.to_thread` if it blocks on I/O
   (`read_clipboard` is effectively instant; `search_memory` hits
   SQLite and should absolutely go off-thread). Options:
   (a) All tools use `asyncio.to_thread` uniformly.
   (b) Declare each tool's preferred thread mode in its `ToolSpec`.
   (a) is less code, matches decision 007's `asyncio.to_thread`
   convention. (b) is more explicit. I'd pick (a), but Eric should
   sign off.

   **Recommendation: (a) always-threaded.** Matches the decision-007
   convention that every blocking call goes through `asyncio.to_thread`
   — a precedent the rebuild has stuck to without regret. The "less
   code" argument compounds with guardrail #2: a per-tool thread-mode
   field is a new abstraction without a second caller demanding it
   (today's three tools all want threading). `asyncio.to_thread` over
   a trivially-fast callable costs ~10 μs; that's below the noise
   floor on a voice turn. Override: if a future pure-CPU-bound tool
   shows up that's hot enough to regret the thread hop, add the
   `thread_mode: Literal["thread", "inline"]` field to `ToolSpec`
   then — at which point the abstraction has its second caller.

Everything below reflects these recommendations. Implementation starts
when Eric signs off or overrides. The Ollama path assumes (b); if Eric
picks (a), the "raise cleanly" path becomes a full translation layer.

---

## The one-liner

Add an additive `tools` kwarg to `Brain.chat` and a new
`ToolCall / ToolResult / ToolUseStart / ToolUseDone` set of events on
the `StreamEvent` union. Register three initial tools
(`get_time`, `read_clipboard`, `search_memory`) in a new `sabrina/tools/`
folder, each as a small module. Claude's tool-use API is the reference
implementation; Ollama raises cleanly when `tools` is non-empty
(per Q2 recommendation — add the translation layer later when Qwen2.5's
Ollama tool-call shape stabilizes).

## Research — the three APIs that matter

### Anthropic's tool-use shape

Tools are declared as a list of objects:

```python
tools = [
    {
        "name": "get_time",
        "description": "Get the current local time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    ...
]
```

On the model's side, when it decides to call a tool, the stream includes
a `tool_use` content block:

```
{
  "type": "tool_use",
  "id": "toolu_01abc...",
  "name": "get_time",
  "input": {},
}
```

Claude's streaming API interleaves `text_stream` fragments with
`input_json_delta` events for tool-call argument accumulation, then a
`message_stop`. The stream finishes *before* we run the tool. We run
the tool, build a response message with a `tool_result` content block
pointing at the same `id`, then call `messages.stream` again with the
history including both the assistant's tool_use turn and our
tool_result turn.

Anthropic's SDK exposes this via `AsyncMessageStream.on(...)` callbacks
or iterating final content blocks. We already use `stream.text_stream`;
we'll need to switch to iterating all content-block events so we can
detect and process tool_use blocks.

### Ollama's tool-use shape

Qwen2.5 and Llama 3.1 emit OpenAI-compatible tool calls via Ollama's
chat API:

```json
{
  "message": {
    "role": "assistant",
    "content": "",
    "tool_calls": [
      {
        "function": {"name": "get_time", "arguments": {}}
      }
    ]
  }
}
```

We send the tool result as a new message with `role="tool"` and
`content` as the JSON-encoded result. The specifics have been in flux
across Ollama 0.3 → 0.4 → 0.5; current stable interface is `tool_calls`
on the streamed chunk's message object. Known sharp edges:
- Streaming delta tool-call arguments are not delivered granularly —
  tool_calls tend to arrive whole, at the end of the stream. We treat
  them as "end-of-stream reveals tool calls" and dispatch then.
- Not every model Eric pulls into Ollama will support tools. `qwen2.5`
  does. We check the model's declared capabilities at init time;
  missing capability → raise cleanly when a caller passes `tools`.

### CancelToken interaction

Tool execution is inside the turn loop. If barge-in fires while a tool
is running:
1. The `CancelToken` gets set (by the `AudioMonitor` dispatch).
2. The main loop sees `cancel_token.cancelled` after the tool returns
   (or polls during a long-running tool).
3. Don't send the tool_result back; break the turn.
4. Publish `BargeInDetected`; state machine goes back to listening.

For tools themselves:
- `search_memory` returns in ~50 ms. Skip cooperative cancellation.
- `read_clipboard` returns in ~5 ms. Skip.
- Future longer-running tools (`search_web`, `read_file_big`) should
  accept the `CancelToken` in their signature and poll it.

The plan doesn't add cancel-polling to the three initial tools; they're
all fast enough that the turn-level token check after execution is
sufficient.

## The protocol change

```python
# brain/protocol.py (additive)

@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Declaration of a tool the brain may call."""
    name: str
    description: str
    input_schema: dict[str, Any]        # JSON schema
    handler: Callable[..., Awaitable[Any]]   # async invocation target

@dataclass(frozen=True, slots=True)
class ToolUseStart:
    """Brain chose to call a tool. Stream event."""
    tool_id: str
    name: str
    input: dict[str, Any]

@dataclass(frozen=True, slots=True)
class ToolUseDone:
    """Tool execution completed. Stream event."""
    tool_id: str
    name: str
    result: Any
    error: str | None = None

# Discriminated union
StreamEvent = TextDelta | Done | ToolUseStart | ToolUseDone


class Brain(Protocol):
    name: str

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        system_suffix: str | None = None,
        max_tokens: int | None = None,
        tools: list[ToolSpec] | None = None,       # NEW
        cancel_token: CancelToken | None = None,   # NEW (from barge-in)
    ) -> AsyncIterator[StreamEvent]: ...
```

`tools=None` (default) means "no tools available" — existing callers
are unaffected. Backends that don't support tools either raise cleanly
when `tools is not None` (Ollama path before stabilization) or no-op
(text-only future backends).

**Why `handler` is on `ToolSpec` and not a separate registry:** the
voice-loop builds the list of tools per turn; it already knows which
handlers go with which names. Carrying the callable alongside the
schema keeps the call site honest (you can't register a tool name
without a handler). This is the same pattern as
`Message.images` — additive, self-contained.

## Claude tool-execution loop

```python
# brain/claude.py (sketch)
async def chat(self, messages, *, tools=None, **kwargs):
    # Convert our tools to Anthropic's format
    api_tools = [_to_anthropic_tool(t) for t in tools] if tools else None
    # ... existing system/messages prep ...

    while True:
        kwargs_local = dict(kwargs_base)
        if api_tools:
            kwargs_local["tools"] = api_tools

        async with self._client.messages.stream(**kwargs_local) as stream:
            tool_calls_this_turn = []
            async for chunk in stream:
                if chunk.type == "content_block_delta" and chunk.delta.type == "text_delta":
                    yield TextDelta(text=chunk.delta.text)
                elif chunk.type == "content_block_start" and chunk.content_block.type == "tool_use":
                    tool_calls_this_turn.append(chunk.content_block)

            final = await stream.get_final_message()

        if final.stop_reason != "tool_use":
            yield Done(input_tokens=final.usage.input_tokens,
                       output_tokens=final.usage.output_tokens,
                       stop_reason=final.stop_reason)
            return

        # Execute the tools, build the follow-up user message
        tool_results = []
        for call in tool_calls_this_turn:
            yield ToolUseStart(tool_id=call.id, name=call.name, input=call.input)
            try:
                spec = _find_spec(tools, call.name)
                result = await spec.handler(**call.input)
                yield ToolUseDone(tool_id=call.id, name=call.name, result=result)
                tool_results.append((call.id, result, None))
            except Exception as exc:
                yield ToolUseDone(tool_id=call.id, name=call.name,
                                   result=None, error=str(exc))
                tool_results.append((call.id, None, str(exc)))

        # Append assistant tool_use turn + user tool_result turn to history
        messages = messages + [_assistant_turn(tool_calls_this_turn),
                                _tool_result_turn(tool_results)]
```

The outer `while True` lets tool use recurse: if the model sees the
tool_result and decides it needs another tool call, we loop again. We
should cap recursion depth (say, 5) to avoid pathological loops.

## Initial tool set — justified

### `get_time`

```python
async def get_time() -> dict:
    """Return the current local time."""
    return {"iso": datetime.now().isoformat(timespec="seconds"),
            "local": datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")}
```

- **Risk:** zero. No I/O, no state.
- **Value:** low but concrete. "What time is it" is a classic voice-
  assistant baseline; Sabrina answering without the tool means she
  hallucinates (training cutoff → wrong date). With the tool, she's
  correct.
- **Second-caller justification:** every tool after this reuses the
  same plumbing. `get_time` is the second caller to the protocol
  (per guardrail #2).

### `read_clipboard`

```python
async def read_clipboard() -> dict:
    """Return the current Windows clipboard contents."""
    text = await asyncio.to_thread(_win_clipboard_text)
    return {"text": text[:10_000] if text else ""}  # safety cap
```

- **Risk:** low. Read-only, no side effects. Clipboard might contain
  sensitive data — but Sabrina already has access to the user's
  screen via vision; clipboard is strictly less than that.
- **Value:** high. "Sabrina, summarize what I just copied" is a
  killer daily-driver pattern and doesn't require any GUI.
- **Implementation:** `pywin32`'s `win32clipboard` module. Already in
  our deps (SAPI pulls it).

### `search_memory`

```python
async def search_memory(query: str, k: int = 5) -> dict:
    """Search Sabrina's long-term memory for turns matching `query`."""
    hits = await asyncio.to_thread(
        _memory_store.search, _embedder.embed(query), k=k
    )
    return {
        "hits": [
            {"date": h.message.ts.isoformat(),
             "role": h.message.role,
             "content": h.message.content[:500],
             "distance": round(h.distance, 3)}
            for h in hits
        ]
    }
```

- **Risk:** zero. Reuses existing memory-store + embedder.
- **Value:** high. Today the voice loop pre-retrieves top-k on every
  turn. With this tool, Sabrina can *decide* to retrieve more, or
  retrieve by a different query than the user's turn (e.g., user says
  "what did I say about hardware last month" → Sabrina issues
  `search_memory("hardware")` herself).
- **Synergy with the 007 retrieval path:** voice loop still pre-
  retrieves a "quick hits" block into `system_suffix`. The tool is for
  deeper follow-ups.

### Held back (for now)

- `get_weather(location)`. Requires picking an API (OpenWeather, NWS,
  etc.) and an API key. One day of work; not this session.
- `open_app(name)`. Automation-adjacent; should land with the
  automation component behind the full safety harness.
- `search_web(query)`. Requires a search API; lots of options; worth
  its own session.
- `read_file(path)`. Meta-risk: broad file-system access. The voice
  loop should probably require explicit consent per access, which is
  a UX design question, not a tool-implementation one.
- `play_music(...)`. Automation. Same gating as `open_app`.

## Scope

In:
- `brain/protocol.py`: `ToolSpec`, `ToolUseStart`, `ToolUseDone`, extend
  `StreamEvent`. Extend `Brain.chat` with `tools` and `cancel_token`.
- `brain/claude.py`: tool-use loop (above).
- `brain/ollama.py`: accept `tools`; raise clean error ("Backend
  `ollama:qwen2.5:14b` does not support tool use; pick Claude or
  disable [tools]") per Q2 recommendation.
- `sabrina/tools/` package:
  - `__init__.py` — `BUILTIN_TOOLS` list (the three above).
  - `time.py`, `clipboard.py`, `memory.py` — one tool per module.
- `voice_loop.py`: pass `tools=BUILTIN_TOOLS` on brain.chat; publish
  `ToolUseStart`/`ToolUseDone` events to the bus as they arrive;
  surface tool calls to the console as dim lines ("(looking up time...)").
- `events.py`: mirror the stream events as bus events.
- `[tools]` config block: per-tool enable toggles.
- Tests: tool dispatch (stubbed brain), Claude tool-call parsing,
  each tool unit test, recursion cap, cancel-token propagation.

Out:
- Tool approval UX ("Sabrina wants to read your clipboard — OK?").
  Not needed for read-only tools; needed the first time a tool can
  mutate state. Revisit with `open_app`.
- Multi-tool parallel execution. Claude's API lets the model return
  multiple tool_use blocks in one turn; we execute them serially. In
  practice, tools so far don't parallelize meaningfully.
- Tool-use observability in the GUI. Log lines + `ToolUseStart` bus
  events are enough; GUI wiring is polish.

## Files to touch

```
sabrina-2/src/sabrina/
├── brain/
│   ├── protocol.py               # +ToolSpec, +ToolUseStart/Done
│   ├── claude.py                 # tool-use loop
│   └── ollama.py                 # tools param accepted (raise if (b))
├── tools/                        # NEW package
│   ├── __init__.py               # BUILTIN_TOOLS
│   ├── time.py
│   ├── clipboard.py
│   └── memory.py
├── voice_loop.py                 # pass tools, surface events
├── events.py                     # +ToolUseStart, +ToolUseDone
├── cli.py / cli/brain.py         # +`sabrina tool-test <name>` verb
└── config.py                     # +ToolsConfig
sabrina-2/
├── sabrina.toml                  # +[tools]
└── tests/test_smoke.py           # +tool tests
```

## Config additions

```toml
[tools]
# Master switch. When false, Brain.chat is called without tools and
# Sabrina behaves like today.
enabled = true

# Per-tool toggles. Disabling a tool removes it from the list passed to
# the brain, so the model can't call it.
[tools.get_time]
enabled = true

[tools.read_clipboard]
enabled = true
# Cap the returned text. Prevents 4 MB clipboards from eating context.
max_chars = 10000

[tools.search_memory]
enabled = true
default_k = 5
```

## Test strategy

- `test_tool_spec_from_handler` — declare a tool, validate the
  Anthropic-schema rendering is correct.
- `test_claude_executes_one_tool_and_continues` — stub Anthropic client;
  first stream emits tool_use, second stream emits text + final;
  assert one handler call, correct sequence of stream events
  (TextDelta → ToolUseStart → ToolUseDone → TextDelta → Done).
- `test_claude_recursion_cap` — stub that always emits tool_use; assert
  the loop stops after 5 iterations and yields a `Done` with a
  stop_reason indicating the cap.
- `test_tool_handler_error_surfaces_in_tool_result` — handler raises;
  assert `ToolUseDone` has `error` set and the model sees the error
  string in its tool_result message.
- `test_tool_get_time_returns_iso` — direct.
- `test_tool_read_clipboard_returns_text_and_truncates_long` —
  monkeypatch `win32clipboard`; assert capping.
- `test_tool_search_memory_uses_embedder_and_returns_hits` — stub
  embedder + memory; verify the result shape.
- `test_ollama_raises_cleanly_when_tools_provided_and_unsupported`
  — clean-error path from Q2 recommendation.

Manual smoke:
- `sabrina tool-test get_time` — prints current time.
- `sabrina tool-test read_clipboard` — echoes clipboard.
- `sabrina tool-test search_memory "hardware"` — runs the same query
  `sabrina memory-search` would.
- `sabrina voice`: ask "what time is it?" — expect a `ToolUseStart`
  console line followed by the correct time in the reply.

## Dependencies to add

None. `pywin32` already in deps. Memory/embedder already present.

## Windows-specific concerns

- Clipboard: open-and-close the clipboard quickly
  (`win32clipboard.OpenClipboard()` without a handle, then
  `CloseClipboard()` in a `finally`). Leaking the clipboard is a known
  footgun; don't.
- If `win32clipboard.GetClipboardData(CF_UNICODETEXT)` isn't present
  (clipboard has only an image or file-drop), return `{"text": ""}` —
  don't crash.
- `read_clipboard` should run on a worker thread (`asyncio.to_thread`)
  to avoid holding the clipboard open on the event loop.

## Ship criterion

- All new unit tests pass.
- Claude: manual smoke with real API — "what time is it" fires
  `get_time` and returns a current time string.
- Claude: "summarize what's in my clipboard" (with text pre-copied)
  fires `read_clipboard` and produces a relevant summary.
- Claude: "what did we say about hardware last week" fires
  `search_memory` (visible via `ToolUseStart` console line) and
  produces an answer grounded in retrieved content.
- `Brain.chat(tools=None)` still works identically (backward compat
  test).
- Ollama as the configured brain raises a clear error when `tools`
  is non-empty: "Backend `ollama:qwen2.5:14b` does not support tool
  use; pick Claude or disable [tools]." (Per Q2 recommendation.)

## Not in this plan (later)

- Tool-approval UX.
- Parallel tool execution.
- Tool-use budget tracking (separate line item in `sabrina budget`
  for tool-call round-trips — each tool call doubles the per-turn API
  cost).
- A `web_search` tool.
- Tool streaming (some tools might stream partial results; not needed
  for the initial three).
- GUI surface for tool invocations.

## MCP compatibility (added 2026-04-25 per overnight research)

The April 2026 stack survey found MCP has won as the cross-vendor
standard for tool surfaces (Anthropic, OpenAI, Google DeepMind, Microsoft
Copilot all consume MCP-defined tools natively; 97 M installs by March
2026 per Anthropic's own blog; see
`rebuild/drafts/research/2026-04-25-stack-alternatives-survey.md`
section 9). This plan ships Anthropic native first (Q2 above) — that
hasn't changed. What this section adds: a deliberate "design once, swap
transport later" check so v1's tool surface translates to MCP without a
schema rewrite when we move tools out-of-process.

### What's already MCP-compatible

- **JSON Schema for `input_schema`.** MCP's `inputSchema` field uses the
  same JSON Schema draft. No change.
- **Sequential dispatch.** MCP is request/response per tool call;
  parallel-execution is out of scope (matches "Out:" above). No change.
- **`BUILTIN_TOOLS` registry.** MCP servers expose `list_tools`; our
  `BUILTIN_TOOLS` list is the local equivalent. The data structures
  line up.
- **`CancelToken` semantics.** MCP defines cancellation via the
  `notifications/cancelled` JSON-RPC method. Our token sets a flag the
  loop polls; an MCP transport adapter would translate that into the
  notification. No protocol-shape change required.

### What diverges (and the trivial change to fix)

1. **Field naming: `input_schema` (snake_case) vs `inputSchema` (camelCase).**
   MCP's wire format is camelCase. Internally we keep snake_case
   (Pythonic). Add `ToolSpec.to_mcp_dict()` and `ToolSpec.to_anthropic_dict()`
   helpers so serialization is per-transport without changing the Python
   surface. Cost: ~10 lines.

2. **Tool result shape: free-form `Any` vs typed `content[]` blocks.**
   Today's plan has handlers return `Any` and Claude's `tool_result`
   takes whatever (auto-serialized). MCP requires:
   ```json
   {"content": [{"type": "text", "text": "..."}], "isError": false}
   ```
   Trivial fix: wrap any non-list handler return as
   `[{"type": "text", "text": json.dumps(result)}]` at the transport
   boundary. Don't change handler signatures; the wrapping lives in the
   adapter. Cost: ~15 lines (one helper, used in both Anthropic + future
   MCP paths).

3. **Error shape: `error: str | None` vs `isError: bool` + error text in
   content.** `ToolUseDone.error` already carries the string. Add an
   `is_error` property = `error is not None`. The MCP adapter sets
   `isError = is_error` and puts the error string into a text content
   block. The Anthropic adapter does the same with `is_error=True` on
   the tool_result content block (it already accepts that). Cost: ~5
   lines.

### Concrete protocol delta vs the spec above

```python
# brain/protocol.py (additive, MCP-friendly)

@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]

    def to_mcp_dict(self) -> dict:
        """Serialize for MCP's `tools/list` response (camelCase wire format)."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def to_anthropic_dict(self) -> dict:
        """Serialize for Anthropic native tool-use API (snake_case)."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True, slots=True)
class ToolUseDone:
    tool_id: str
    name: str
    result: Any
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None
```

These are the only schema-level changes needed for MCP-readiness. The
transport (HTTP+JSON-RPC vs in-process) is purely an adapter swap when
the time comes. No internal call sites change.

### What this rules out vs. what it doesn't

**Rules out:** silently picking a non-MCP tool surface for v1 and then
having to rename fields/restructure result shapes when MCP migration
lands. The diff would be larger and would touch every handler.

**Does not rule out:** Anthropic native as v1's transport. The
recommendation in Q2 above stands. MCP-shaped *schemas* + Anthropic
native *transport* is the lowest-friction path to "ship soon, migrate
cheaply later." Migration cost is then ~50 lines of MCP-server boilerplate
(stdio JSON-RPC server) plus moving `BUILTIN_TOOLS` into the server's
`list_tools` handler. The handlers themselves don't change.

### What remains an open question for the MCP migration session

(Listed here so the implementation session that ships MCP doesn't have
to re-derive these.)

- **In-process MCP server vs separate process.** Anthropic's reference
  MCP servers are subprocesses spawned on demand. For Sabrina the
  voice-loop and the tools live in the same process today; an
  in-process MCP-shaped registry is fine and avoids subprocess
  ceremony. The decision becomes interesting if Sabrina starts hosting
  *external* MCP servers (e.g. filesystem, Slack) — that's a separate
  decision (likely decision 0XX-mcp-host).
- **MCP's resources/prompts surfaces.** MCP defines three primitives:
  `tools`, `resources`, `prompts`. We only need `tools` for v1.
  `resources` would be a clean fit later for Sabrina's memory store
  ("the assistant can browse past sessions"), but that's a different
  scope.
- **Tool-result streaming.** MCP added incremental tool-result content
  in early 2026; the spec is settled but not all clients consume it.
  Skip in v1; revisit if a streaming tool (web search, large file read)
  lands.
