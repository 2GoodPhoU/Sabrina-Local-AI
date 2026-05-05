"""Claude backend.

Thin adapter over the Anthropic SDK. Streaming only. Returns TextDelta events
followed by a single Done with token usage.
"""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic

from sabrina.brain.protocol import (
    CancelToken,
    Done,
    Message,
    StreamEvent,
    TextDelta,
    ToolUseDone,
    ToolUseStart,
)
from sabrina.logging import get_logger

if TYPE_CHECKING:
    from sabrina.tools import ToolSpec

log = get_logger(__name__)


# Hard cap on tool-use recursion depth per chat() invocation. After this
# many model->tool round-trips the loop yields ``Done`` with stop_reason
# ``"tool_recursion_cap"`` rather than recursing further. Five matches the
# tool-use plan's recommended ceiling — generous enough for legitimate
# multi-step tool chains, tight enough that a runaway loop bails before
# burning the user's token budget.
_MAX_TOOL_RECURSION = 5


class ClaudeBrain:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
    ) -> None:
        if not api_key:
            raise ValueError("Claude backend requires an Anthropic API key.")
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._default_max_tokens = max_tokens
        self.name = f"claude:{model}"

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        cancel_token: CancelToken | None = None,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        api_messages = [_render_message(m) for m in messages if m.role != "system"]
        # Pull first system message out of the history if the caller didn't pass one.
        if system is None:
            sys_msgs = [m.content for m in messages if m.role == "system"]
            system = sys_msgs[0] if sys_msgs else None

        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if system:
            kwargs["system"] = system

        # Pre-serialize the tool advertisement once; the same payload rides
        # every recursion. Empty / None tools list -> classic text-only path.
        api_tools = [t.to_anthropic_dict() for t in tools] if tools else None
        tool_lookup: dict[str, ToolSpec] = (
            {t.name: t for t in tools} if tools else {}
        )

        in_tokens: int | None = None
        out_tokens: int | None = None
        stop_reason: str | None = None
        cancelled = False
        recursion = 0

        while True:
            kwargs_local = dict(kwargs, messages=api_messages)
            if api_tools is not None:
                kwargs_local["tools"] = api_tools

            async with self._client.messages.stream(**kwargs_local) as stream:
                async for text in stream.text_stream:
                    if cancel_token is not None and cancel_token.cancelled:
                        # Don't wait for final_message — it requires draining
                        # the stream, which delays the cancel. Bail and emit
                        # Done.
                        cancelled = True
                        break
                    if text:
                        yield TextDelta(text=text)
                if cancelled:
                    break
                final = await stream.get_final_message()

            # Non-tool stop: capture usage and exit. Same shape as before.
            if final.stop_reason != "tool_use":
                in_tokens = final.usage.input_tokens
                out_tokens = final.usage.output_tokens
                stop_reason = final.stop_reason
                break

            # Tool dispatch. The model may invoke multiple tools in one turn
            # — handle each, build a single user-turn carrying all results,
            # then recurse so the model can continue with the answers.
            tool_uses = [
                b for b in final.content
                if getattr(b, "type", None) == "tool_use"
            ]
            tool_results: list[dict[str, Any]] = []
            for tu in tool_uses:
                tool_input = tu.input if isinstance(tu.input, dict) else {}
                yield ToolUseStart(
                    tool_id=tu.id, name=tu.name, input=tool_input
                )
                spec = tool_lookup.get(tu.name)
                if spec is None:
                    err = f"unknown tool: {tu.name}"
                    yield ToolUseDone(
                        tool_id=tu.id, name=tu.name, result=None, error=err,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": err,
                        "is_error": True,
                    })
                    continue
                try:
                    result = await spec.handler(**tool_input)
                except Exception as exc:  # noqa: BLE001 — surface to model
                    err_msg = str(exc) or exc.__class__.__name__
                    yield ToolUseDone(
                        tool_id=tu.id,
                        name=tu.name,
                        result=None,
                        error=err_msg,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": err_msg,
                        "is_error": True,
                    })
                else:
                    yield ToolUseDone(
                        tool_id=tu.id, name=tu.name, result=result,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result),
                        "is_error": False,
                    })
                if cancel_token is not None and cancel_token.cancelled:
                    cancelled = True
                    break
            if cancelled:
                break

            # Append the assistant's tool_use turn (preserving its full
            # content blocks via model_dump so tool_use blocks survive the
            # round-trip) plus our user turn carrying tool_results.
            assistant_content = [b.model_dump() for b in final.content]
            api_messages = api_messages + [
                {"role": "assistant", "content": assistant_content},
                {"role": "user", "content": tool_results},
            ]

            recursion += 1
            if recursion >= _MAX_TOOL_RECURSION:
                # Cap fired: report usage from the last call and stop. The
                # caller (voice loop, REPL) sees a Done with the cap reason
                # and can surface that to the operator voice.
                in_tokens = final.usage.input_tokens
                out_tokens = final.usage.output_tokens
                stop_reason = "tool_recursion_cap"
                break

            if cancel_token is not None and cancel_token.cancelled:
                cancelled = True
                break

        yield Done(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            stop_reason="cancelled" if cancelled else stop_reason,
        )


def _render_message(m: Message) -> dict[str, Any]:
    """Convert a Sabrina Message into Anthropic's native message shape.

    Text-only turns stay as {"role", "content": str} so we don't pay for
    the content-block list conversion on the 99% path. Turns with images
    get the list-of-blocks form, with each image base64-encoded inline.
    """
    if not m.images:
        return {"role": m.role, "content": m.content}
    blocks: list[dict[str, Any]] = []
    for img in m.images:
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.media_type,
                    "data": base64.standard_b64encode(img.data).decode("ascii"),
                },
            }
        )
    # Text block goes *after* the images — Claude's vision docs recommend
    # placing the image first so the question can reference it naturally
    # ("describe the image above").
    if m.content:
        blocks.append({"type": "text", "text": m.content})
    return {"role": m.role, "content": blocks}


# ---------------------------------------------------------------------------
# Personality system-prompt blocks (decision 010, plan: personality-plan.md
# section "System-prompt skeleton (concrete)").
#
# Blocks 1, 2, 3, 5, 6 form the cacheable head — stable within a session
# unless the audience register toggles. Block 7 (retrieval suffix) is the
# dynamic part; callers append it themselves so prompt caching works when
# `cache_control` wires up later (see budget-and-caching-plan.md). Block 4
# (cue vocabulary) is omitted here — it ships with the avatar component.
# ---------------------------------------------------------------------------


# Block 1 — Persona (~140 tok, always cached)
_PERSONA_BLOCK = """\
You are Sabrina. You work with Eric on his projects through a voice
interface on his Windows PC. You are not a chatbot, a butler, or a brand
voice. Think of yourself as the senior engineer who sits at the next
desk — knows the code, remembers last week's debugging session, and
tells him when his plan has a smell.

Operator voice, not customer-service voice. Information before apology.
If something's broken, say so. If you don't know, say so. If the answer
is yes, the answer is yes."""


# Block 2 — Voice rules (~180 tok, always cached)
_VOICE_RULES_BLOCK = """\
Reply rules:
- Default reply: 1-3 short sentences. Long answers only when asked.
- One idea per sentence. Verb-first where it reads naturally.
- No markdown, bullet lists, code blocks, or emoji. Output is spoken
  aloud.
- Hedge only when actually uncertain. "Probably / I think / might" are
  signals, not softeners.
- "I don't know" is a complete answer. Optionally follow with "want me
  to check?" — never with "here's what I'd guess" unless asked to guess.
- Do not open with: "I'd be happy to...", "Great question!", "It seems
  like...", "Let me...", or any identity disclaimer ("As an AI...", "As
  a helpful assistant...").
- Do not close with: "Let me know if...", "Does that help?", "Hope this
  helps!" — unless the answer was actually a question.
- One "my mistake" per turn maximum. No re-apology on retry.
- Pronouns for self: she/her. Do not volunteer a gender statement.
- Profanity: mirror the user. Never first turn of a session."""


# Refusal-as-character framing (folded under voice, not a separate block)
_REFUSAL_AS_CHARACTER_BLOCK = """\
Some things you won't do because they're not who you are: cheerlead
("you've got this!"), be extra (emoji rain, exclamation-point rain,
"absolutely!"), explain a joke, role-play as a different assistant
(ChatGPT, Siri), or fake memory. Refuse as character — sound like
you wouldn't, not like you can't."""


# Block 3 — Audience register (~70 tok, cached; invalidates on toggle)
_AUDIENCE_BLOCK_A = """\
Current register: A.
- A — Eric alone. Default. Dry, direct. Profanity mirror active.
  Shared-history references natural."""

_AUDIENCE_BLOCK_B = """\
Current register: B.
- B — someone else in the room. Same spine; no shared-history
  references unless Eric introduces them first; profanity off; humor
  dialed down."""

_AUDIENCE_BLOCK_C = """\
Current register: C.
- C — professional mode. Full sentences, no humor, no shared history,
  length budget +1 sentence."""


# Block 5 — Tool-use rules. Reserved; contributes zero tokens until
# tool-use ships per `rebuild/drafts/tool-use-plan.md`.
_TOOL_USE_BLOCK_DEFAULT = ""


# Block 6 — Memory-continuity preamble (~50 tok, always cached)
_MEMORY_CONTINUITY_BLOCK = """\
You have access to a semantic-memory retrieval system. When relevant
earlier turns are appended below, read them as prior context, not
current dialogue. Reference them only when they clarify something.
Never list them back. If nothing is appended, do not invent shared
history. She won't fake memory."""


_AUDIENCE_BLOCKS: dict[str, str] = {
    "A": _AUDIENCE_BLOCK_A,
    "B": _AUDIENCE_BLOCK_B,
    "C": _AUDIENCE_BLOCK_C,
}


def build_system_prompt(
    *,
    register: str = "A",
    tool_use_block: str = _TOOL_USE_BLOCK_DEFAULT,
) -> str:
    """Assemble the cacheable head of Sabrina's system prompt.

    Returns the joined persona + voice + register + tool-use + memory
    continuity blocks (no trailing newline). Callers concatenate the
    dynamic retrieval suffix themselves so the cacheable head stays
    byte-stable across turns within a session.

    Args:
        register: "A" (Eric alone, default), "B" (someone else in the
                  room), or "C" (professional mode).
        tool_use_block: optional block 5 contents. Default empty until
                        tool-use ships.
    """
    if register not in _AUDIENCE_BLOCKS:
        raise ValueError(
            f"Unknown register {register!r}. Expected one of "
            f"{sorted(_AUDIENCE_BLOCKS)}."
        )
    parts = [
        _PERSONA_BLOCK,
        _VOICE_RULES_BLOCK,
        _REFUSAL_AS_CHARACTER_BLOCK,
        _AUDIENCE_BLOCKS[register],
    ]
    if tool_use_block.strip():
        parts.append(tool_use_block.strip())
    parts.append(_MEMORY_CONTINUITY_BLOCK)
    return "\n\n".join(parts)


# Convenience: the most common shape (Register A, no tools, no avatar
# cue track). Voice loop and chat REPL both use this today.
SABRINA_SYSTEM_PROMPT: str = build_system_prompt(register="A")
