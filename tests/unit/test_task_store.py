from __future__ import annotations

import asyncio

import pytest

from cto_order_agent.a2a.tasks import StoredTask, TaskStore


@pytest.mark.unit
def test_ttl_expiry() -> None:
    store = TaskStore(ttl_seconds=-1)
    store.put(StoredTask(task_id="t1", context_id="c1"))
    assert store.get("t1") is None


@pytest.mark.unit
def test_capacity_evicts_oldest() -> None:
    store = TaskStore(max_tasks=2)
    for index in range(3):
        store.put(StoredTask(task_id=f"t{index}", context_id="c1", created_at=float(index)))
    assert len(store) == 2


@pytest.mark.unit
async def test_concurrent_access() -> None:
    store = TaskStore()

    async def write(index: int) -> None:
        store.put(StoredTask(task_id=f"t{index}", context_id=f"c{index}"))
        store.set_context(f"c{index}", order="0000012345")

    await asyncio.gather(*(write(i) for i in range(20)))
    assert len(store) == 20
    assert store.get_context("c7")["order"] == "0000012345"


@pytest.mark.unit
def test_missing_task_returns_none() -> None:
    assert TaskStore().get("nope") is None
