"""Single background worker: runs pipeline jobs on its own event loop and thread.

Jobs are coroutine factories keyed by run id. Cancellation cancels the asyncio task.
Resuming is delegated to per-run-kind resumers registered by the pipeline modules.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

log = logging.getLogger(__name__)

JobFactory = Callable[[], Awaitable[None]]
Resumer = Callable[[str], JobFactory]


class Worker:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._resumers: dict[str, Resumer] = {}

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="slidex-worker", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()
        self._loop.close()

    def stop(self) -> None:
        loop = self._loop
        if loop is None:
            return
        for run_id in list(self._tasks):
            self.cancel(run_id)
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._thread = None
        self._loop = None
        self._ready.clear()

    def submit(self, run_id: str, factory: JobFactory) -> concurrent.futures.Future[None]:
        if self._loop is None:
            raise RuntimeError("worker not started")

        async def _start() -> None:
            task = asyncio.current_task()
            assert task is not None
            self._tasks[run_id] = task
            try:
                await factory()
            except asyncio.CancelledError:
                log.info("run %s cancelled", run_id)
                raise
            except Exception:
                log.exception("run %s failed", run_id)
                raise
            finally:
                self._tasks.pop(run_id, None)

        return asyncio.run_coroutine_threadsafe(_start(), self._loop)

    def run_sync(
        self, factory: Callable[[], Coroutine[Any, Any, Any]], timeout: float = 600
    ) -> Any:
        """Run a coroutine on the worker loop and wait for its result (used for small jobs)."""
        if self._loop is None:
            raise RuntimeError("worker not started")
        return asyncio.run_coroutine_threadsafe(factory(), self._loop).result(timeout=timeout)

    def cancel(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        if task is None or self._loop is None:
            return False
        self._loop.call_soon_threadsafe(task.cancel)
        return True

    def is_active(self, run_id: str) -> bool:
        return run_id in self._tasks

    def register_resumer(self, kind: str, resumer: Resumer) -> None:
        self._resumers[kind] = resumer

    def resumer_for(self, kind: str) -> Resumer | None:
        return self._resumers.get(kind)
