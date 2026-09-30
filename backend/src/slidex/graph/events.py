"""Per-deck event fan-out from the worker thread to SSE subscribers."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DeckEvent(BaseModel):
    event: str
    deck_id: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run: dict[str, Any] | None = None
    slide_number: int | None = None
    source_id: str | None = None
    document_id: str | None = None
    message: str | None = None


class Broadcaster:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[DeckEvent]]]] = (
            defaultdict(list)
        )

    def subscribe(self, deck_id: str) -> asyncio.Queue[DeckEvent]:
        queue: asyncio.Queue[DeckEvent] = asyncio.Queue(maxsize=1000)
        with self._lock:
            self._subs[deck_id].append((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, deck_id: str, queue: asyncio.Queue[DeckEvent]) -> None:
        with self._lock:
            self._subs[deck_id] = [(lp, q) for lp, q in self._subs[deck_id] if q is not queue]

    def publish(self, event: DeckEvent) -> None:
        """Safe to call from any thread."""
        with self._lock:
            targets = list(self._subs.get(event.deck_id, ()))
        for loop, queue in targets:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(_offer, queue, event)


def _offer(queue: asyncio.Queue[DeckEvent], event: DeckEvent) -> None:
    if queue.full():  # drop the oldest rather than block the worker
        queue.get_nowait()
    queue.put_nowait(event)
