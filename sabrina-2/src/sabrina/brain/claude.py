"""Claude backend.

Thin adapter over the Anthropic SDK. Streaming only. Returns TextDelta events
followed by a single Done with token usage.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from sabrina.brain.protocol import Done, Message, StreamEvent, TextDelta
from sabrina.logging import get_logger

log = get_logger(__name__)


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
    ) -> AsyncIterator[StreamEvent]:
        api_messages = [_render_message(m) for m in messages if m.role != "system"]
        # Pull first system message out of the history if the caller didn't pass one.
        if system is None:
            sys_msgs = [m.content for m in messages if m.role == "system"]
            system = sys_msgs[0] if sys_msgs else None

        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
            "messages": api_messages,
        }
        if system:
            kwargs["system"] = system

        in_tokens: int | None = None
        out_tokens: int | None = None
        stop_reason: str | None = None

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                if text:
                    yield TextDelta(text=text)
            final = await stream.get_final_message()
            in_tokens = final.usage.input_tokens
            out_tokens = final.usage.output_tokens
            stop_reason = final.stop_reason

        yield Done(
            input_tokens=in_tokens, output_tokens=out_tokens, stop_reason=stop_reason
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
