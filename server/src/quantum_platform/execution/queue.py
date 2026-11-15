"""Job queue abstraction and its in-process implementation."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod


class JobQueue(ABC):
    @abstractmethod
    async def enqueue(self, job_id: str) -> None:
        """Add a job to the back of the queue."""

    @abstractmethod
    async def dequeue(self) -> str:
        """Wait for and remove the job at the front of the queue."""

    @abstractmethod
    def depth(self) -> int:
        """Number of jobs waiting."""


class InMemoryJobQueue(JobQueue):
    """FIFO queue living in the API process. Its contents are lost on restart."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def dequeue(self) -> str:
        return await self._queue.get()

    def depth(self) -> int:
        return self._queue.qsize()
