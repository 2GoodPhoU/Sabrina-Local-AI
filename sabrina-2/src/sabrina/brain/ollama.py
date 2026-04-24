"""Ollama backend.

Talks to a local Ollama server (`ollama serve`) over its REST API via the
official Python client. Streaming; returns TextDelta events followed by Done.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ollama import AsyncClient

from sabrina.brain.protocol import CancelToken, Done, Message, StreamEvent, TextDelta
from sabrina.logging import get_logger

log = get_logger(__name__)


class OllamaBrain:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:14b",
    ) -> None:
        self._client = AsyncClient(host=host)
        self._model = model
        self.name = f"ollama:{model}"

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        cancel_token: CancelToken | None = None,
    ) -> AsyncIterator[StreamEvent]:
        api_messages: list[dict[str, str]] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        for m in messages:
            api_messages.append({"role": m.role, "content": m.content})

        options: dict[str, int] = {}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        in_tokens: int | None = None
        out_tokens: int | None = None
        stop_reason: str | None = None
        cancelled = False

        stream = await self._client.chat(
            model=self._model,
            messages=api_messages,
            stream=True,
            options=options or None,
        )
        async for chunk in stream:
            if cancel_token is not None and cancel_token.cancelled:
                cancelled = True
                break
            piece = (
                chunk.get("message", {}).get("content")
                if isinstance(chunk, dict)
                else chunk.message.content
            )
            if piece:
                yield TextDelta(text=piece)
            done = chunk.get("done") if isinstance(chunk, dict) else chunk.done
            if done:
                # ollama returns prompt_eval_count / eval_count as token usage.
                if isinstance(chunk, dict):
                    in_tokens = chunk.get("prompt_eval_count")
                    out_tokens = chunk.get("eval_count")
                    stop_reason = chunk.get("done_reason")
                else:
                    in_tokens = getattr(chunk, "prompt_eval_count", None)
                    out_tokens = getattr(chunk, "eval_count", None)
                    stop_reason = getattr(chunk, "done_reason", None)

        yield Done(
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            stop_reason="cancelled" if cancelled else stop_reason,
        )
