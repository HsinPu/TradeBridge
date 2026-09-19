"""Cooperative interruption shared by the worker and provider waits."""
from contextvars import ContextVar
from collections.abc import Callable
import time

execution_check: ContextVar[Callable[[], None] | None] = ContextVar("execution_check", default=None)


def check_execution() -> None:
    check = execution_check.get()
    if check is not None:
        check()


def interruptible_wait(seconds: float) -> None:
    deadline = time.monotonic() + max(0, seconds)
    while True:
        check_execution()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.2))
