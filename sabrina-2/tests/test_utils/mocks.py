"""Protocol-typed fake factories for the Sabrina rebuild test scaffolding.

This module is NOT a port. The legacy `tests/test_utils/helpers.py` mocked
`VoiceService`, `HearingService`, `AutomationService`, `EventBus`, and a
state machine — abstractions the rebuild deliberately rejected. Instead
the rebuild ships a protocol-based surface (`Brain`, `Listener`, `Speaker`,
typed event bus, state machine) and these factories produce minimal stubs
shaped to those protocols.

What you get:
  * `make_fake_brain(reply, ...)` — yields scripted text deltas + a Done.
  * `make_fake_speaker(...)`      — records every speak() call; no audio.
  * `make_fake_listener(text, ...)` — returns a canned Transcript.
  * `make_fake_bus()`             — in-memory pub/sub double.
  * `make_cancel_token()`         — convenience wrapper around CancelToken.

The fakes are deliberately small: they cover the surface that voice-loop
unit tests need, not the deep behavior of each backend. Tests that want
richer behavior should compose the fakes (e.g., a Brain that yields
deltas slowly enough to exercise barge-in cancellation) rather than
expanding the factories.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sabrina.brain.protocol import (
    Brain,
    CancelToken,
    Done,
    Message,
    StreamEvent,
    TextDelta,
)
from sabrina.events import Event
from sabrina.listener.protocol import Listener, Segment, Transcript
from sabrina.speaker.protocol import Speaker, SpeakResult


# --- Brain -----------------------------------------------------------------


@dataclass
class FakeBrain:
    """Minimal `Brain` stub. Yields scripted deltas + a single `Done`.

    `name` and `reply` are settable; `calls` records every chat() invocation
    so tests can assert what was sent. Cancel-aware: if `cancel_token` is
    provided and fires mid-stream, stops yielding deltas and emits
    `Done(stop_reason="cancelled")`.
    """

    name: str = "fake-brain"
    reply: str = "ok"
    deltas: tuple[str, ...] | None = None  # if set, overrides `reply`
    input_tokens: int | None = 1
    output_tokens: int | None = 1
    stop_reason: str = "end_turn"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def chat(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        cancel_token: CancelToken | None = None,
        tools: Any = None,  # ToolSpec list; unused in the fake
    ) -> AsyncIterator[StreamEvent]:
        self.calls.append(
            {
                "messages": list(messages),
                "system": system,
                "max_tokens": max_tokens,
                "tools": tools,
            }
        )
        chunks = self.deltas if self.deltas is not None else (self.reply,)

        async def _stream() -> AsyncIterator[StreamEvent]:
            for chunk in chunks:
                if cancel_token is not None and cancel_token.cancelled:
                    yield Done(stop_reason="cancelled")
                    return
                yield TextDelta(text=chunk)
            yield Done(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                stop_reason=self.stop_reason,
            )

        return _stream()


def make_fake_brain(
    reply: str = "ok",
    *,
    deltas: Iterable[str] | None = None,
    name: str = "fake-brain",
    stop_reason: str = "end_turn",
) -> FakeBrain:
    """Return a `Brain`-protocol fake. See `FakeBrain` for fields."""
    return FakeBrain(
        name=name,
        reply=reply,
        deltas=tuple(deltas) if deltas is not None else None,
        stop_reason=stop_reason,
    )


# --- Speaker ---------------------------------------------------------------


@dataclass
class FakeSpeaker:
    """Minimal `Speaker` stub. Records every speak() call; never produces audio.

    `calls` is a list of (text, voice) tuples. `engine` is exposed via the
    returned `SpeakResult.engine`. Cancel-aware: if `cancel_token` fires
    before speak() returns, the call records a partial duration and exits.
    """

    name: str = "fake-speaker"
    engine: str = "fake-engine"
    duration_s: float = 0.0
    calls: list[tuple[str, str | None]] = field(default_factory=list)
    stopped: int = 0

    async def speak(
        self,
        text: str,
        *,
        voice: str | None = None,
        cancel_token: CancelToken | None = None,
    ) -> SpeakResult:
        self.calls.append((text, voice))
        # Yield once so cancellation has a chance to fire under asyncio.
        await asyncio.sleep(0)
        if cancel_token is not None and cancel_token.cancelled:
            return SpeakResult(engine=self.engine, duration_s=0.0)
        return SpeakResult(engine=self.engine, duration_s=self.duration_s)

    async def stop(self) -> None:
        self.stopped += 1


def make_fake_speaker(
    *,
    name: str = "fake-speaker",
    engine: str = "fake-engine",
    duration_s: float = 0.0,
) -> FakeSpeaker:
    """Return a `Speaker`-protocol fake. See `FakeSpeaker` for fields."""
    return FakeSpeaker(name=name, engine=engine, duration_s=duration_s)


# --- Listener --------------------------------------------------------------


@dataclass
class FakeListener:
    """Minimal `Listener` stub. Returns a canned `Transcript` from transcribe().

    `calls` records the audio argument from each transcribe() invocation so
    tests can assert what was passed without reading actual audio.
    """

    name: str = "fake-listener"
    text: str = "hello"
    language: str = "en"
    language_prob: float = 0.99
    audio_duration_s: float = 1.0
    transcribe_duration_s: float = 0.1
    calls: list[Any] = field(default_factory=list)

    async def transcribe(
        self,
        audio: Path | object,
        *,
        language: str | None = None,
    ) -> Transcript:
        self.calls.append(audio)
        seg = Segment(start_s=0.0, end_s=self.audio_duration_s, text=self.text)
        return Transcript(
            text=self.text,
            language=language or self.language,
            language_prob=self.language_prob,
            audio_duration_s=self.audio_duration_s,
            transcribe_duration_s=self.transcribe_duration_s,
            segments=(seg,),
        )


def make_fake_listener(
    text: str = "hello",
    *,
    name: str = "fake-listener",
    language: str = "en",
    audio_duration_s: float = 1.0,
) -> FakeListener:
    """Return a `Listener`-protocol fake. See `FakeListener` for fields."""
    return FakeListener(
        name=name,
        text=text,
        language=language,
        audio_duration_s=audio_duration_s,
    )


# --- Event bus -------------------------------------------------------------


@dataclass
class FakeBus:
    """Minimal in-memory pub/sub double for the rebuild's `EventBus`.

    Records every published event in `events` so tests can assert ordering
    and content. `subscribe()` returns a synchronous list-iterator over
    matching events captured up to the point of subscription — enough for
    test assertions; the production `EventBus.subscribe()` is async-iterator
    based and tests that need that semantics should use the real `EventBus`.

    A `subscribers_called` counter increments each time `subscribe()` is
    invoked, useful for asserting that a component subscribed at all.
    """

    events: list[Event] = field(default_factory=list)
    subscribers_called: int = 0

    async def publish(self, event: Event) -> None:
        self.events.append(event)

    def subscribe(
        self,
        *kinds: str,
        filter_fn: Callable[[Event], bool] | None = None,
    ) -> list[Event]:
        self.subscribers_called += 1
        if filter_fn is not None:
            return [e for e in self.events if filter_fn(e)]
        if kinds:
            kind_set = set(kinds)
            return [e for e in self.events if getattr(e, "kind", None) in kind_set]
        return list(self.events)

    def stats(self) -> dict[str, Any]:
        return {
            "events": len(self.events),
            "subscribers_called": self.subscribers_called,
        }

    def clear(self) -> None:
        self.events.clear()


def make_fake_bus() -> FakeBus:
    """Return an in-memory event-bus double. See `FakeBus` for fields."""
    return FakeBus()


# --- Cancel token ----------------------------------------------------------


def make_cancel_token(*, cancelled: bool = False) -> CancelToken:
    """Return a fresh `CancelToken`. If `cancelled=True`, pre-tripped."""
    token = CancelToken()
    if cancelled:
        token.cancel()
    return token


# --- Re-exports for convenience -------------------------------------------

__all__ = [
    "FakeBrain",
    "FakeBus",
    "FakeListener",
    "FakeSpeaker",
    "make_cancel_token",
    "make_fake_brain",
    "make_fake_bus",
    "make_fake_listener",
    "make_fake_speaker",
]


# Sanity: the `Brain`/`Listener`/`Speaker` protocols are runtime_checkable, so
# a quick `isinstance(make_fake_brain(), Brain)` works in tests as a
# structural check. The protocols are imported at module top so a failure
# here surfaces at collection time, not deep in a test.
_ = (Brain, Listener, Speaker, time)  # silence unused-import lint
