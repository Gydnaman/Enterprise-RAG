from __future__ import annotations

import asyncio

from rag_workbench.adapters.database import SessionFactory
from rag_workbench.adapters.models import RunRecord
from rag_workbench.application.workflows import run_answer, run_demo_trace


class InProcessRunDispatcher:
    """One bounded, single-worker dispatcher for local mock runs."""

    def __init__(self, session_factory=SessionFactory, capacity: int = 32) -> None:
        self.session_factory = session_factory
        self.capacity = capacity
        self._reserved = 0
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._active_run: str | None = None

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._serve(), name="rag-workbench-run-dispatcher")

    async def reserve(self) -> bool:
        if self._reserved >= self.capacity or self._worker is None:
            return False
        self._reserved += 1
        return True

    def release_reservation(self) -> None:
        self._reserved = max(0, self._reserved - 1)

    def enqueue_reserved(self, run_id: str) -> None:
        if self._worker is None:
            self.release_reservation()
            raise RuntimeError("dispatcher_not_started")
        self._queue.put_nowait(run_id)

    async def _serve(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                if run_id is None:
                    return
                self._active_run = run_id
                with self.session_factory() as session:
                    run = session.get(RunRecord, run_id)
                    kind = run.kind if run is not None else ""
                if kind == "answer":
                    await run_answer(self.session_factory, run_id)
                elif kind == "demo_trace":
                    await run_demo_trace(self.session_factory, run_id)
            finally:
                if run_id is not None:
                    self._active_run = None
                    self.release_reservation()
                self._queue.task_done()

    async def shutdown(self) -> None:
        if self._worker is None:
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout=5)
        except TimeoutError:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        else:
            self._queue.put_nowait(None)
            await self._worker
        self._worker = None
