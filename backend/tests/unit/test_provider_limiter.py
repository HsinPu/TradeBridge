from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.infrastructure.external.provider_limiter import ProviderLimiter
from app.application.services.execution_control import execution_check
from app.application.ports.job_execution_store import ExecutionInterrupted


def test_shared_weight_and_config_change_preserve_consumption():
    clock = [0.0]
    waits = []
    def wait(seconds):
        waits.append(seconds)
        clock[0] += seconds
    limiter = ProviderLimiter(4, 0, clock=lambda: clock[0], wait=wait)
    limiter.acquire(2)
    limiter.acquire(2)
    limiter.configure(4, 0)
    limiter.acquire(2)
    assert waits == [60]
    limiter.defer(30)
    limiter.acquire(1)
    assert waits == [60, 30]


def test_rate_limit_wait_can_be_interrupted():
    limiter = ProviderLimiter()
    limiter.defer(60)
    def stop():
        raise ExecutionInterrupted("cancelled")
    token = execution_check.set(stop)
    try:
        with pytest.raises(ExecutionInterrupted):
            limiter.acquire(1)
    finally:
        execution_check.reset(token)


def test_oversized_weight_fails_instead_of_waiting_forever():
    with pytest.raises(ValueError):
        ProviderLimiter(1).acquire(2)
