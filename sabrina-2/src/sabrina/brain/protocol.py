"""The Brain protocol and its data types.

A `Brain` is anything that can take a conversation and produce a streamed reply.
Backends implement it: Claude, Ollama, a future router, a future fast-path.

Kept deliberately small. Tool use will arrive as additional event types in the
StreamEvent union; existing callers that only care about text won't break.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


Role = Literal["system", "user", "assistant"]


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
    ) -> AsyncIterator[StreamEvent]:
        """Stream a reply. Yields TextDelta events followed by a single Done."""
        ...
