"""A saturated or timed-out compute pool must not accumulate pending uploads."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi import HTTPException

from verity_api import limits
from verity_api import main


@pytest.fixture
def single_worker(monkeypatch):
    pool = ThreadPoolExecutor(max_workers=1)
    released = threading.Event()
    started = threading.Event()
    monkeypatch.setattr(main, "_COMPARE_EXECUTOR", pool)
    monkeypatch.setattr(main, "_COMPARE_CAPACITY", threading.BoundedSemaphore(1), raising=False)
    monkeypatch.setattr(limits, "LIMITS", replace(limits.LIMITS, compare_timeout_s=1))

    def blocking_work():
        started.set()
        assert released.wait(5), "test did not release its blocking worker"
        return "finished"

    yield pool, released, started, blocking_work
    released.set()
    pool.shutdown(wait=True)


async def _assert_busy():
    with pytest.raises(HTTPException, match="busy") as error:
        await asyncio.wait_for(main._offload(lambda: "must not be queued"), timeout=0.1)
    assert error.value.status_code == 503


def test_saturated_compute_pool_rejects_immediately_without_queue(single_worker):
    pool, released, started, worker = single_worker

    async def scenario():
        active = asyncio.create_task(main._offload(worker))
        try:
            assert await asyncio.to_thread(started.wait, 1)
            await _assert_busy()
        finally:
            released.set()
            assert await active == "finished"
        assert await main._offload(lambda: "next request") == "next request"

    asyncio.run(scenario())


def test_timeout_keeps_capacity_reserved_until_worker_finishes(single_worker, monkeypatch):
    pool, released, started, worker = single_worker
    monkeypatch.setattr(limits, "LIMITS", replace(limits.LIMITS, compare_timeout_s=0.02))

    async def scenario():
        with pytest.raises(HTTPException, match="timed out"):
            await main._offload(worker)
        assert started.is_set()
        await _assert_busy()
        released.set()
        # This direct test-only barrier finishes after the worker's done callback.
        await asyncio.wrap_future(pool.submit(lambda: None))
        assert await main._offload(lambda: "available") == "available"

    asyncio.run(scenario())


def test_canceled_request_keeps_running_worker_capacity(single_worker):
    pool, released, started, worker = single_worker

    async def scenario():
        active = asyncio.create_task(main._offload(worker))
        assert await asyncio.to_thread(started.wait, 1)
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        await _assert_busy()
        released.set()
        await asyncio.wrap_future(pool.submit(lambda: None))
        assert await main._offload(lambda: "available") == "available"

    asyncio.run(scenario())


def test_executor_submit_failure_does_not_leak_capacity(single_worker):
    pool, _, _, _ = single_worker
    pool.shutdown(wait=True)
    with pytest.raises(RuntimeError, match="shutdown"):
        asyncio.run(main._offload(lambda: None))
    assert main._COMPARE_CAPACITY.acquire(blocking=False)
    main._COMPARE_CAPACITY.release()
