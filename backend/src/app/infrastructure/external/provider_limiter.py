from collections import deque
from threading import Lock
from time import monotonic

from app.application.services.execution_control import interruptible_wait, check_execution


class ProviderLimiter:
    """Shared sliding-minute request budget; config changes preserve consumption."""
    def __init__(self, budget=1200, cooldown_ms=200, *, clock=monotonic, wait=interruptible_wait):
        self._lock = Lock()
        self._requests = deque()
        self._next_request = 0.0
        self._blocked_until = 0.0
        self._clock = clock
        self._wait = wait
        self.configure(budget, cooldown_ms)

    def configure(self, budget, cooldown_ms):
        with self._lock:
            self.budget = max(1, budget)
            self.cooldown = max(0, cooldown_ms) / 1000

    def defer(self, seconds):
        with self._lock:
            self._blocked_until = max(self._blocked_until, self._clock() + max(0, seconds))

    def acquire(self, weight):
        while True:
            check_execution()
            with self._lock:
                if weight > self.budget:
                    raise ValueError("Provider request weight exceeds configured minute budget")
                now = self._clock()
                while self._requests and self._requests[0][0] <= now - 60:
                    self._requests.popleft()
                delay = max(0, self._next_request-now, self._blocked_until-now)
                if sum(item[1] for item in self._requests) + weight > self.budget:
                    delay = max(delay, self._requests[0][0] + 60 - now)
                if delay <= 0:
                    self._requests.append((now, weight))
                    self._next_request = now + self.cooldown
                    return
            self._wait(delay)
