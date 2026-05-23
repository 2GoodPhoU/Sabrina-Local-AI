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

from sabrina.automation.allow_list import (
    DestructiveActionBlocked,
    check_allowed,
)
from sabrina.automation.dry_run import dry_run_wrap
from sabrina.automation.kill_switch import KillSwitch, KillSwitchTripped
from sabrina.brain.protocol import (
    CancelToken,
    Done,
    Message,
    StreamEvent,
    TextDelta,
    ToolUseDone,
    ToolUseStart,
)
from sabrina.budget import compute_cost
from sabrina.logging import get_logger

if TYPE_CHECKING:
    from sabrina.config import Settings
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
        kill_switch: KillSwitch | None = None,
        dry_run: bool = False,
        settings: Settings | None = None,
    ) -> AsyncIterator[StreamEvent]:
        api_messages = [_render_message(m) for m in messages if m.role != "system"]
        # Pull first system message out of the history if the caller didn't pass one.
        if system is None:
            sys_msgs = [m.content for m in messages if m.role == "system"]
            system = sys_msgs[0] if sys_msgs else None

        resolved_model = model or self._model
        kwargs: dict[str, Any] = {
            "model": resolved_model,
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
                # Allow-list poll (pre-dispatch, P4.B3). If the tool is
                # destructive AND its name isn't allow-listed in
                # ``[automation] destructive_actions``, refuse before
                # the kill-switch + dry-run path even fires. Spec rec:
                # block precedes dry-run (model learns the action is
                # forbidden, not that a dry-run-would-have-fired) and
                # precedes the kill-switch poll (defense-in-depth
                # ordering — even a tripped kill-switch shouldn't
                # silently "succeed" by allowing a blocked tool to
                # never invoke the handler under the wrong reason
                # label).
                try:
                    check_allowed(spec, settings)
                except DestructiveActionBlocked as exc:
                    err_msg = "destructive_action_blocked"
                    yield ToolUseDone(
                        tool_id=tu.id,
                        name=tu.name,
                        result=None,
                        error=err_msg,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": str(exc),
                        "is_error": True,
                    })
                    continue
                # Kill-switch poll (pre-dispatch). If the global hotkey
                # has fired since the last poll point, refuse to invoke
                # the handler — the existing error branch below catches
                # the raise and surfaces ``ToolUseDone(error=...)``.
                # Dry-run does NOT bypass this poll: spec § Q3 / test
                # ``test_claude_dispatch_dry_run_still_honors_kill_switch``.
                if kill_switch is not None:
                    try:
                        kill_switch.check()
                    except KillSwitchTripped as exc:
                        err_msg = "kill_switch_tripped"
                        yield ToolUseDone(
                            tool_id=tu.id,
                            name=tu.name,
                            result=None,
                            error=err_msg,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": str(exc),
                            "is_error": True,
                        })
                        continue
                # Dry-run wrap. When the per-call ``dry_run`` kwarg is
                # True (the (b)-half voice loop reads
                # ``is_dry_run(settings)`` and passes the boolean
                # through), swap the real handler for the wrapper that
                # logs + returns a synthetic shape.
                handler = (
                    dry_run_wrap(spec.handler, name=spec.name)
                    if dry_run
                    else spec.handler
                )
                try:
                    result = await handler(**tool_input)
                except KillSwitchTripped:
                    err_msg = "kill_switch_tripped"
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
                    # Kill-switch poll (post-dispatch). If a hotkey fire
                    # raced the handler completing, surface the abort
                    # before the next tool round trip starts so the
                    # model isn't asked to think with a now-stale
                    # success result. The handler's result still rode
                    # back to the model on this turn — recovery
                    # (re-prompting) belongs to the voice loop, not
                    # here.
                    if kill_switch is not None and kill_switch.tripped:
                        cancelled = True
                        break
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

        # Cost is only computed when we have a real usage block. A
        # mid-stream cancel that fires before ``final.usage`` is extracted
        # leaves ``in_tokens`` / ``out_tokens`` at None — pass ``cost_usd=None``
        # in that case rather than reporting a false $0.0 turn.
        cost_usd: float | None
        if in_tokens is None and out_tokens is None:
            cost_usd = None
        else:
            cost_usd = compute_cost(in_tokens, out_tokens, resolved_model)
        yield Done(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            stop_reason="cancelled" if cancelled else stop_reason,
            cost_usd=cost_usd,
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
#
# As of P4.C1 (2026-05-08) the blocks live in `brain/persona.py`. This
# module re-exports the public surface for back-compat with callers that
# import `SABRINA_SYSTEM_PROMPT` / `build_system_prompt` from
# `sabrina.brain.claude` (chat.py, voice_loop.py, cli.py, test_smoke.py).
# ---------------------------------------------------------------------------


# ruff: noqa: E402  (intentional late re-import for back-compat re-exports)
from sabrina.brain.persona import (
    SABRINA_SYSTEM_PROMPT_CLAUDE as SABRINA_SYSTEM_PROMPT,
    build_system_prompt,
)

__all__ = [
    "ClaudeBrain",
    "SABRINA_SYSTEM_PROMPT",
    "build_system_prompt",
    "compute_cost",
]
