"""In-process A2A task store with TTL (research D7)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoredTask:
    task_id: str
    context_id: str
    state: str = "TASK_STATE_SUBMITTED"
    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)


class TaskStore:
    """Bounded, thread-safe, TTL-scoped conversational state.

    Single replica by design: horizontal scaling requires externalizing this.
    """

    def __init__(self, ttl_seconds: int = 1800, max_tasks: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max = max_tasks
        self._tasks: dict[str, StoredTask] = {}
        self._contexts: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _expired(self, task: StoredTask, now: float) -> bool:
        return (now - task.updated_at) > self._ttl

    def _prune(self, now: float) -> None:
        for task_id in [t for t, task in self._tasks.items() if self._expired(task, now)]:
            self._tasks.pop(task_id, None)
        while len(self._tasks) > self._max:
            oldest = min(self._tasks.values(), key=lambda t: t.created_at)
            self._tasks.pop(oldest.task_id, None)

    def put(self, task: StoredTask) -> StoredTask:
        with self._lock:
            now = time.monotonic()
            self._tasks[task.task_id] = task
            self._prune(now)
        return task

    def get(self, task_id: str) -> StoredTask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if self._expired(task, time.monotonic()):
                self._tasks.pop(task_id, None)
                return None
            return task

    def update(self, task: StoredTask) -> None:
        with self._lock:
            task.updated_at = time.monotonic()
            self._tasks[task.task_id] = task

    def get_context(self, context_id: str) -> dict[str, Any]:
        with self._lock:
            return dict(self._contexts.get(context_id, {}))

    def set_context(self, context_id: str, **values: Any) -> None:
        with self._lock:
            current = self._contexts.setdefault(context_id, {})
            current.update(values)

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._contexts.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)


__all__ = ["StoredTask", "TaskStore"]
