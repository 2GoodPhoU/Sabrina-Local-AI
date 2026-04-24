"""The Brain protocol and its data types.

A `Brain` is anything that can take a conversation and produce a streamed reply.
Backends implement it: Claude, Ollama, a future router, a future fast-path.

Kept deliberately small. Tool use will arrive as additional event types in the
StreamEvent union; existing callers that only care about text won't break.

`CancelToken` lives here rather than in its own module because Brain is the
primary cancellation surface. `Speaker` imports it too — anti-sprawl guardrail
#2 says a third caller earns the split into `sabrina/cancel.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class CancelToken:
    """Cooperative cancellation flag for long-running async operations.

    Callers (voice_loop) create a token per turn, pass it into Brain.chat and
    Speaker.speak, and call ``.cancel()`` from a different task (e.g. the VAD
    monitor running during ``speaking`` state) to request termination.
    Implementations check ``.cancelled`` at safe points — between stream
    deltas, between sentences, before starting the next subprocess — and
    return early (or raise ``asyncio.CancelledError``) to unwind.

    Why a plain flag instead of ``asyncio.Event``: the VAD detection callback
    runs on a threadpool (sounddevice InputStream); it shouldn't need the
    event loop to set the flag. ``bool`` assignment is atomic in CPython.
    """

    _cancelled: bool = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


@dataclass(frozen=True, slots=True)
class Image:
    """A single image attached to a user turn.

    `data` is raw bytes of the encoded image (PNG or JPEG). `media_type` is
    the MIME type the brain backend should advertise to the LLM. Kept dumb
    on purpose — no numpy dependency here so the protocol stays lean.
    """

    data: bytes
    media_type: Literal[
        "image/png", "image/jpeg", "image/webp", "image/gif"
    ] = "image/png"


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str
    # Images attached to this turn. Only honored on user turns by multimodal
    # backends (Claude). Text-only backends ignore them. Defaults to no
    # images so existing call sites don't need to change.
    images: tuple[Image, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class TextDelta:
    """Streamed text fragment."""

    text: str


@dataclass(frozen=True, slots=True)
class Done:
    """Stream finished. Optional usage + stop-reason info."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None


# Discriminated union of stream events. Add ToolCall, ToolResult, etc. later.
StreamEvent = TextDelta | Done


@runtime_checkable
class Brain(Protocol):
    """A reasoning backend."""

    name: str  # e.g. "claude:sonnet-4-6", "ollama:qwen2.5:14b"

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        cancel_token: CancelToken | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a reply. Yields TextDelta events followed by a single Done.

        If ``cancel_token`` is provided and ``cancel_token.cancelled`` becomes
        ``True`` during the stream, implementations should stop emitting
        TextDeltas promptly and yield a final ``Done(stop_reason="cancelled")``.
        Default ``None`` keeps existing callers working.
        """
        ...
