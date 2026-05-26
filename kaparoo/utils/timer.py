from __future__ import annotations

__all__ = ("LapRecord", "LapTimer", "Timer")

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import ContextDecorator, contextmanager
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType
    from typing import Literal, Self

    type TimeUnit = Literal["s", "ms", "us", "ns"]
    type DupMode = Literal["allow", "number", "strict"]


_SCALES: dict[str, float] = {"s": 1e-9, "ms": 1e-6, "us": 1e-3, "ns": 1.0}


class LapRecord(TypedDict):
    label: str
    lap_time: float
    total_time: float


class BaseTimer(ContextDecorator, ABC):
    def __init__(self, unit: TimeUnit = "s", *, ndigits: int | None = None) -> None:
        if unit not in _SCALES:
            msg = f"unit must be one of {sorted(_SCALES)} (got {unit!r})."
            raise ValueError(msg)
        self.unit = unit
        self.scale = _SCALES[unit]
        self.ndigits = ndigits
        self._start_time: int = 0
        self._started: bool = False
        self._is_paused: bool = False
        self._pause_start: int = 0

    def _apply_ndigits(self, value: float) -> float:
        return value if self.ndigits is None else round(value, self.ndigits)

    def _format_time(self, elapsed_ns: int) -> float:
        return self._apply_ndigits(elapsed_ns * self.scale)

    def _ensure_started(self) -> None:
        if not self._started:
            msg = "Timer has not been started."
            raise RuntimeError(msg)

    def _reset(self) -> None:
        """Hook: clear per-`with`-block state. Called after `_start_time` is set."""

    @abstractmethod
    def _finalize(self) -> None:
        """Compute the final result. Called from `__exit__` after auto-resume."""

    def pause(self) -> None:
        self._ensure_started()
        if self._is_paused:
            msg = "Timer is already paused."
            raise RuntimeError(msg)
        self._pause_start = time.perf_counter_ns()
        self._is_paused = True

    def resume(self) -> int:
        self._ensure_started()
        if not self._is_paused:
            msg = "Timer is not paused."
            raise RuntimeError(msg)
        pause_duration = time.perf_counter_ns() - self._pause_start
        self._start_time += pause_duration
        self._is_paused = False
        return pause_duration

    @contextmanager
    def suspend(self) -> Iterator[None]:
        self.pause()
        try:
            yield
        finally:
            if self._is_paused:
                self.resume()

    def __enter__(self) -> Self:
        self._start_time = time.perf_counter_ns()
        self._started = True
        self._is_paused = False
        self._reset()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._is_paused:
            self.resume()
        self._finalize()
        self._started = False


class Timer(BaseTimer):
    def __init__(self, unit: TimeUnit = "s", *, ndigits: int | None = None) -> None:
        super().__init__(unit=unit, ndigits=ndigits)
        self.elapsed: float = 0.0

    def _finalize(self) -> None:
        elapsed_ns = time.perf_counter_ns() - self._start_time
        self.elapsed = self._format_time(elapsed_ns)


class LapTimer(BaseTimer):
    _END_LABEL = "End"

    def __init__(
        self,
        unit: TimeUnit = "s",
        *,
        ndigits: int | None = None,
        dup_mode: DupMode = "allow",
    ) -> None:
        super().__init__(unit=unit, ndigits=ndigits)
        self.dup_mode = dup_mode
        self.records: list[LapRecord] = []
        self.final: LapRecord | None = None
        self.total_elapsed: float = 0.0
        self._last_time: int = 0
        self._label_counts: dict[str, int] = {}

    @property
    def summary(self) -> dict[str, float]:
        """Sum `lap_time` per label across `records` (excludes `final`)."""
        grouped: dict[str, float] = defaultdict(float)
        for record in self.records:
            grouped[record["label"]] += record["lap_time"]
        return {label: self._apply_ndigits(total) for label, total in grouped.items()}

    def resume(self) -> int:
        pause_duration = super().resume()
        self._last_time += pause_duration
        return pause_duration

    def _reset(self) -> None:
        self._last_time = self._start_time
        self.records.clear()
        self.final = None
        self.total_elapsed = 0.0
        self._label_counts.clear()

    def _resolve_label(self, label: str) -> str:
        next_count = self._label_counts.get(label, 0) + 1
        if next_count > 1 and self.dup_mode == "strict":
            msg = f"Label {label!r} is already used."
            raise ValueError(msg)
        self._label_counts[label] = next_count
        return (
            f"{label} ({next_count})"
            if next_count > 1 and self.dup_mode == "number"
            else label
        )

    def _make_record(self, label: str) -> LapRecord:
        """Build a record stamped with the current time."""
        current_time = time.perf_counter_ns()
        record: LapRecord = {
            "label": label,
            "lap_time": self._format_time(current_time - self._last_time),
            "total_time": self._format_time(current_time - self._start_time),
        }
        self._last_time = current_time
        return record

    def lap(self, label: str = "Lap") -> None:
        self._ensure_started()
        if self._is_paused:
            msg = "Cannot record a lap while paused."
            raise RuntimeError(msg)
        self.records.append(self._make_record(self._resolve_label(label)))

    def _finalize(self) -> None:
        self.final = self._make_record(self._END_LABEL)
        self.total_elapsed = self.final["total_time"]
