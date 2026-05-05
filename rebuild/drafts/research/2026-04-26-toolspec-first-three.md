# Tool-use first ToolSpec set — beyond the planned three

**Date:** 2026-04-26 (overnight research, no code touched)
**Scope:** Concrete proposal for the first 3-5 ToolSpecs Sabrina ships,
expanding the existing `tool-use-plan.md` v1 set
(`get_time / read_clipboard / search_memory`). All proposals are
MCP-compatible by construction, per the audit baked into the plan
and the April 2026 stack survey's "MCP has won" finding.

**Anchor:** the plan's three open questions are now answered (ship all
three v1 tools, Claude-only first, always-threaded). This doc accepts
those as settled and asks the *next* question: what tools come after
those three, and which of them is morning-shippable.

**Audience:** Eric, Sunday morning, with no fresh research to do.

---

## How other personality-forward voice assistants pick first tools

Three patterns across mid-2026 projects:

1. **Time, weather, timer, calendar.** Vapi, Bland, Synthflow all
   ship these as their out-of-the-box "voice agent" tool set [1].
   Personal-AI projects (PAI, the "Build Your Personal AI Agent in
   60 Minutes" Maven course [2]) wire the same set first — calendar
   read, weather read, schedule a one-shot reminder — because they
   are the tools that pay for the latency of "should I have asked
   the assistant or just looked it up myself?"
2. **Read-only first, write-once second.** Every published "personal
   AI infrastructure" tutorial in 2026 (Daniel Miessler's PAI repo
   [3], the Anthropic Calendar 2025 artifact [4], the smart-calendar
   guide [5]) defers write-side tools — calendar create, email send,
   file write — to a later session, behind some form of
   confirmation. Sabrina's `tool-use-plan.md` already implies this
   ordering by holding `open_app` for the automation component.
3. **Local-system first, network-bound second.** Read-clipboard,
   read-screen, search-memory work without an API key, work offline,
   and never need rate-limit handling. Search-web, get-weather,
   send-email all need a key + a fallback story. The latency tax of
   "register an account, deal with the API key, encode the rate
   limit" is exactly the kind of cost the rebuild has consistently
   refused before the second-caller exists.

Sabrina's planned v1 set (`get_time`, `read_clipboard`,
`search_memory`) is squarely in the "read-only, local-system"
quadrant. The next set should expand along *both* axes — one
network-bound read, one write-side surface that proves the
confirmation UX, one local-system tool that exercises a different
side-effect class than the existing three.

---

## Side-effect taxonomy

Before naming candidates, the side-effect classes the tool framework
needs to support. The plan has been vague here; pinning it down now
makes per-tool risk obvious:

| Class | Examples | Approval needed? | MCP `isError` semantic |
|---|---|---|---|
| **read-only / pure** | `get_time`, `pi(n)` | No | Errors on bad input. |
| **read-from-clipboard** | `read_clipboard`, `screen_describe` | No (transient, user-initiated context) | Errors on absent data. |
| **read-from-fs** | `read_file(path)`, `list_directory(path)` | First-time-per-path consent | Errors on permission/missing. |
| **read-from-network** | `web_search`, `get_weather`, `read_url` | No (idempotent, public) | Errors on network/auth. |
| **write-to-clipboard** | `write_clipboard(text)` | No (low-cost, reversible) | Errors on Win32 contention. |
| **write-to-fs** | `append_note(text)`, `write_file(path)` | First-time-per-path consent | Errors on permission/disk. |
| **write-to-network** | `send_message`, `add_calendar_event` | Per-call confirmation | Errors on auth/quota. |
| **execute-OS** | `open_app`, `kill_process` | Per-call confirmation | Errors on missing app. |

The plan's three v1 tools occupy the first two classes. The proposal
below extends into the next three — `read-from-network`,
`write-to-clipboard`, `write-to-fs` — to exercise the framework's
breadth without crossing into the "execute-OS" trip-wire that should
land with the automation component.


## Proposal: the next three tools (after v1 ships)

### #4 — `write_clipboard(text)`

**Purpose:** Mirror of `read_clipboard`. Lets Sabrina put text on the
clipboard for the user to paste somewhere — the second half of every
"Sabrina, draft a message and put it on my clipboard" flow. The first
write-side tool, deliberately chosen for low risk.

**Side-effect class:** `write-to-clipboard`. Reversible (the user can
just copy something else); no auth; no network.

**Risk tier:** **low.** The clipboard already gets blasted by every
copy operation; one more write doesn't change the threat surface.

**Input schema (MCP shape):**

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "Plain text to place on the system clipboard. Truncated to 100 KB.",
      "maxLength": 100000
    }
  },
  "required": ["text"]
}
```

**Output schema:**

```json
{
  "type": "object",
  "properties": {
    "bytes_written": {"type": "integer"},
    "truncated": {"type": "boolean"}
  },
  "required": ["bytes_written", "truncated"]
}
```

**MCP-compatible JSON shape (for `tools/list`):**

```json
{
  "name": "write_clipboard",
  "description": "Place plain text on the user's clipboard. Returns bytes written.",
  "inputSchema": { ...as above... }
}
```

`tool_result` content block (per the audit's `[{"type": "text",
"text": "..."}]` wrapping):

```json
{
  "content": [{"type": "text", "text": "{\"bytes_written\":142,\"truncated\":false}"}],
  "isError": false
}
```

### #5 — `append_note(text, *, section=None)`

**Purpose:** Append text to a single Markdown notes file under a
known path (default `~/SabrinaNotes.md`). The first write-to-fs tool,
chosen because the path is fixed (no path-traversal vector), the
operation is monotonic (append, never overwrite), and the value is
high (Sabrina becomes an accumulator of "save this for later"
moments).

**Side-effect class:** `write-to-fs` against a single allowlisted
path. The path itself lives in `[tools.append_note].file_path` in
`sabrina.toml`; the tool refuses any input that tries to override it.
No path argument is accepted from the brain.

**Risk tier:** **low-medium.** The risk is "fills the disk" or
"clobbers a note"; both are bounded — append-only with a 1 MB cap on
the file size before rotation to `SabrinaNotes.YYYY-MM-DD.md`.

**Input schema:**

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string",
      "description": "Markdown text to append. A blank line is inserted before the new content.",
      "maxLength": 10000
    },
    "section": {
      "type": "string",
      "description": "Optional H2 section title. If provided and not present, the section is created at end-of-file. If present, the text is appended under it.",
      "maxLength": 200
    }
  },
  "required": ["text"]
}
```

**Output schema:**

```json
{
  "type": "object",
  "properties": {
    "file_path": {"type": "string"},
    "bytes_written": {"type": "integer"},
    "section_used": {"type": "string"},
    "rotated": {"type": "boolean"}
  },
  "required": ["file_path", "bytes_written"]
}
```

### #6 — `web_search(query, *, max_results=5)`

**Purpose:** First read-from-network tool. Lets Sabrina answer
questions whose factual content post-dates Claude's training cutoff
without a vision capture. Highest-leverage tool in the list because
it converts "I don't know, my training stopped at <month>" into
"here's what I just looked up."

**Side-effect class:** `read-from-network`. Idempotent (search is
side-effect-free server-side), needs an API key.

**Risk tier:** **medium.** Not the call itself — the *result* might
be content the brain then summarizes incorrectly or links to. This is
upstream of every "Sabrina hallucinated" complaint becoming "Sabrina
hallucinated *from a real search result*" — slightly worse for trust.
Mitigation in the tool: return the structured hits (title, url,
snippet) but never auto-fetch the URL. The brain then either decides
the snippet is enough, or follows up with a `read_url` tool (held
back to v3).

**Backend choice — Brave Search API.** Brave has an independent
index, a free tier of 2,000 queries / month, no third-party
dependencies, simple JSON in / JSON out. Anthropic's own
prompting docs cite Brave as the canonical example for tool-use
search [6]. SerpAPI is the runner-up but its free tier is
disappearing in 2026.

**Input schema:**

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "minLength": 1,
      "maxLength": 400,
      "description": "Search query in natural English."
    },
    "max_results": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "default": 5
    }
  },
  "required": ["query"]
}
```

**Output schema:**

```json
{
  "type": "object",
  "properties": {
    "hits": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "url": {"type": "string"},
          "snippet": {"type": "string"}
        },
        "required": ["title", "url", "snippet"]
      }
    },
    "queried_at": {"type": "string"}
  },
  "required": ["hits", "queried_at"]
}
```


## Held back

- **`read_url(url)`.** Naturally pairs with `web_search` but has its
  own scraping headaches (paywalls, JS-rendered pages, robots.txt).
  Worth its own session once `web_search` proves the network-bound
  pattern.
- **`add_calendar_event`.** High-value, highest-friction. Needs OAuth
  to Google Calendar / Outlook + a per-call confirmation UX. Belongs
  with the automation component, not v2.
- **`open_app(name)` / `kill_process`.** Already held back by the
  plan for the automation component.
- **`get_weather(location)`.** Replaceable by `web_search("weather in
  <city>")` for v2. Adding a dedicated weather tool requires picking
  an API; not worth the bikeshed in the morning's session.
- **`set_timer(seconds)`.** Useful but introduces an in-process
  scheduler that's a separate piece of infrastructure. Defer to
  whichever component first needs scheduled callbacks (probably
  scheduled tasks / supervisor).

---

## Implementation outline — `write_clipboard` (Eric's morning ship)

This is the cheapest of the three to ship. Scaffolding already exists
from `read_clipboard`; add a sibling module, register, write tests,
done.

### File map

```
sabrina-2/src/sabrina/tools/
├── __init__.py            # extend BUILTIN_TOOLS list
├── clipboard.py           # add write_clipboard alongside read_clipboard
sabrina-2/sabrina.toml     # +[tools.write_clipboard]
sabrina-2/tests/test_smoke.py   # +write_clipboard tests
```

### `clipboard.py` — sketch (additive)

```python
# tools/clipboard.py
from __future__ import annotations
import asyncio
import win32clipboard
import win32con

MAX_BYTES = 100_000

# existing read_clipboard handler stays as-is

def _win_clipboard_set(text: str) -> int:
    """Replace clipboard contents with `text`. Returns bytes written."""
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(
            win32con.CF_UNICODETEXT, text
        )
    finally:
        win32clipboard.CloseClipboard()
    return len(text.encode("utf-8"))

async def write_clipboard(text: str) -> dict:
    """Place plain text on the system clipboard.

    The brain calls this with up to 100 KB of text; longer is truncated.
    """
    truncated = len(text.encode("utf-8")) > MAX_BYTES
    if truncated:
        # Truncate by characters, not bytes — avoids splitting a UTF-8
        # multibyte sequence. Conservative cap.
        text = text[:MAX_BYTES // 4]
    bytes_written = await asyncio.to_thread(_win_clipboard_set, text)
    return {"bytes_written": bytes_written, "truncated": truncated}
```

### Registration

```python
# tools/__init__.py
from sabrina.brain.protocol import ToolSpec
from .clipboard import read_clipboard, write_clipboard
from .memory import search_memory
from .time_tool import get_time

BUILTIN_TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_time",
        description="Get the current local time as ISO 8601 + a friendly string.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=get_time,
    ),
    ToolSpec(
        name="read_clipboard",
        description="Read the current contents of the user's clipboard. Returns up to 10,000 characters.",
        input_schema={"type": "object", "properties": {}, "required": []},
        handler=read_clipboard,
    ),
    ToolSpec(
        name="write_clipboard",
        description="Place plain text on the user's clipboard. Returns bytes written.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": 100000,
                         "description": "Plain text to place on the clipboard."}
            },
            "required": ["text"],
        },
        handler=write_clipboard,
    ),
    ToolSpec(
        name="search_memory",
        description="Search Sabrina's long-term memory for turns matching a query.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text query."},
                "k":     {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
        },
        handler=search_memory,
    ),
]
```

### Config

```toml
[tools.write_clipboard]
enabled = true
max_chars = 100000   # safety cap; the tool also clamps internally
```

### Tests (in `test_smoke.py`)

```python
def test_write_clipboard_returns_bytes_written(monkeypatch):
    set_calls = []
    def fake_set(text):
        set_calls.append(text)
        return len(text.encode("utf-8"))
    monkeypatch.setattr(
        "sabrina.tools.clipboard._win_clipboard_set", fake_set,
    )
    result = asyncio.run(write_clipboard("hello"))
    assert result == {"bytes_written": 5, "truncated": False}
    assert set_calls == ["hello"]

def test_write_clipboard_truncates_long(monkeypatch):
    monkeypatch.setattr(
        "sabrina.tools.clipboard._win_clipboard_set",
        lambda t: len(t.encode("utf-8")),
    )
    long_text = "x" * 200_000
    result = asyncio.run(write_clipboard(long_text))
    assert result["truncated"] is True
    assert result["bytes_written"] <= MAX_BYTES + 4   # allowing UTF-8 slack
```

### Manual smoke

```powershell
sabrina tool-test write_clipboard --text "hello from sabrina"
# clipboard now contains "hello from sabrina"; verify by Ctrl+V somewhere
```

Then end-to-end: `sabrina voice` → "Sabrina, put 'foo bar baz' on my
clipboard." Expect a `ToolUseStart(write_clipboard)` console line and
the text to land on the clipboard.

### Total effort

Adding `write_clipboard` on top of an already-shipped v1 set is one
sitting: ~30 minutes for the handler, ~15 for registration + config,
~30 for tests, ~15 for manual smoke. ~90 minutes of focused work.
This is the morning ship.

`append_note` is the next session — it's about 3 hours because of
the H2-section parsing logic, the rotation policy, and the tests
around them. `web_search` is its own session because of the
API-key + retry + offline-fallback story.

---

## Risk tiering, summarized

| Tool | Side-effect class | Approval | Risk | Earliest ship |
|---|---|---|---|---|
| `get_time` | read-only | none | zero | v1 |
| `read_clipboard` | read-from-clipboard | none | zero | v1 |
| `search_memory` | read-only (own data) | none | zero | v1 |
| `write_clipboard` | write-to-clipboard | none | low | v2 (morning) |
| `append_note` | write-to-fs (allowlisted path) | first-run consent | low-medium | v2 |
| `web_search` | read-from-network | none | medium | v3 |
| `read_url` | read-from-network | none | medium | v4 |
| `add_calendar_event` | write-to-network | per-call | high | with automation |
| `open_app` / `kill_process` | execute-OS | per-call | highest | with automation |

The "approval" column is what the framework needs to learn to
support before shipping the row. v1+v2 require *no* new framework
machinery — `BUILTIN_TOOLS` registration is enough. v3+ adds
network-key handling. Automation-tier tools require the full
confirmation harness from `automation-plan.md`.

---

## Two cross-cuts worth flagging

1. **Tool budget visibility.** Each tool call doubles the per-turn
   API cost (one model turn → tool dispatch → one more model turn).
   `web_search` adds the search API cost on top. The
   `budget-and-caching-plan.md` should grow a per-tool line item the
   first time `web_search` lands; until then, the existing turn-cost
   tracking is enough.

2. **MCP migration is unaffected.** Every schema in this doc is
   already MCP-shaped (`inputSchema` field, `content[]` result wrap,
   `isError` boolean). The plan's "design once, swap transport
   later" promise holds: when Sabrina migrates the tool surface to
   an MCP server, the handlers in this doc move file-as-is; only the
   transport (in-process call → stdio JSON-RPC) changes.

---

## Thin spots in this doc

- **No measurement of how often Claude actually picks each tool.**
  The "useful first three" set is justified by analogy to other
  voice assistants and by side-effect-class coverage; whether
  Claude *uses* `write_clipboard` once a week or five times a day
  for Eric is unknown until a few weeks of telemetry. The
  budget-and-caching plan's per-tool counter is the natural place
  to surface that.
- **No design for tool-call observability in the GUI.** The plan
  defers this to "polish" and this doc agrees, but as the tool list
  grows past 5-6 the lack of a visible "Sabrina is searching the
  web…" indicator will start mattering. Add to the GUI tabs
  reorganization plan.
- **Assumes the Claude-only path from the plan's Q2.** If Eric ever
  flips to "(a) — implement Ollama too," the schemas above still
  hold but `web_search`'s reliability story complicates: Qwen 2.5
  on Ollama emits search-tool calls with mangled query strings ~5%
  of the time per the survey. Mitigation: the tool's `query`
  validator rejects empty/whitespace-only queries with a clean error
  the brain can recover from on the next turn.

---

## References

[1] Lindy — voice agent comparison Q1 2026 —
    https://www.lindy.ai/blog/best-ai-voice-assistants
[2] Maven — "Build Your Personal AI Agent With Claude Code in 60
    Minutes" — https://maven.com/p/936bdf/build-your-personal-ai-agent-with-claude-code-in-60-minutes
[3] danielmiessler/Personal_AI_Infrastructure —
    https://github.com/danielmiessler/Personal_AI_Infrastructure
[4] Anthropic — "Use Calendar 2025 for Smarter Time Management" public
    artifact — https://claude.ai/public/artifacts/aca6b887-cd83-466d-89f5-e01db4f37cbd
[5] claude-ai.chat — "Build a Smart Calendar Assistant Using Claude" —
    https://claude-ai.chat/guides/build-a-smart-calendar-assistant-using-claude/
[6] Anthropic prompting docs — tool-use cookbook (Brave Search) —
    https://docs.anthropic.com/en/docs/build-with-claude/tool-use
[7] Merge.dev — MCP tool schema deep-dive —
    https://www.merge.dev/blog/mcp-tool-schema
[8] OpenAI Agents SDK — Model Context Protocol docs —
    https://openai.github.io/openai-agents-python/mcp/
