"""Async pub/sub event bus.

Design goals:
  * Tiny. No external deps beyond asyncio.
  * Typed. Publishers send Event instances; subscribers get filtered streams.
  * Lossy per-subscriber on backpressure: if a subscriber's queue is full, old
    events are dropped rather than blocking the publisher. We favor keeping
    real-time loops responsive over guaranteeing delivery.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any

from sabrina.events import Event
from sabrina.logging import get_logger

log = get_logger(__name__)


class _Subscriber:
    def __init__(self, filter_fn: Callable[[Event], bool], maxsize: int) -> None:
        self.filter = filter_fn
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0


class EventBus:
    """In-process async pub/sub. One instance per Sabrina process."""

    def __init__(self) -> None:
        self._subs: list[_Subscriber] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
        # Copy subs under lock so we don't race with subscribe/unsubscribe.
        async with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if not sub.filter(event):
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                sub.dropped += 1
                log.warning("bus.dropped_event", kind=event.kind, dropped=sub.dropped)

    async def subscribe(
        self,
        *kinds: str,
        maxsize: int = 1024,
    ) -> AsyncIterator[Event]:
        """Async-iterate over events. If kinds given, filter to those event kinds.

        Usage:
            async for ev in bus.subscribe("user_message", "assistant_reply"):
                ...
        """
        if kinds:
            kind_set = set(kinds)

            def _filter(ev: Event) -> bool:
                return ev.kind in kind_set

        else:

            def _filter(ev: Event) -> bool:
                return True

        sub = _Subscriber(_filter, maxsize=maxsize)
        async with self._lock:
            self._subs.append(sub)
        try:
            while True:
                ev = await sub.queue.get()
                yield ev
        finally:
            async with self._lock:
                with contextlib.suppress(ValueError):
                    self._subs.remove(sub)

    def stats(self) -> dict[str, Any]:
        return {
            "subscribers": len(self._subs),
            "queued": [s.queue.qsize() for s in self._subs],
            "dropped": [s.dropped for s in self._subs],
        }
