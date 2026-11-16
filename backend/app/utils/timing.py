import time
from contextlib import contextmanager


class StageTimer:
    """Collects how long each pipeline stage takes, in milliseconds.

        timer = StageTimer()
        with timer.stage("translate"):
            ...
        timer.as_dict()  -> {"translate": 412, "total": 1290}
    """

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.stages: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = self.stages.get(name, 0) + int((time.perf_counter() - start) * 1000)

    def total_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)

    def as_dict(self) -> dict[str, int]:
        return {**self.stages, "total": self.total_ms()}
