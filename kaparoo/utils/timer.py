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
    type LabelPolicy = Literal["merge", "separate", "reject"]


_SCALES: dict[str, float] = {"s": 1e-9, "ms": 1e-6, "us": 1e-3, "ns": 1.0}

_LABEL_POLICIES: frozenset[str] = frozenset({"merge", "separate", "reject"})


class LapRecord(TypedDict):
    """A single timing record produced by `LapTimer`.

    Attributes:
        label: The lap's name. May carry a " (N)" suffix when produced under
            `on_same_label="separate"`.
        lap_time: Time elapsed since the previous lap (or the timer start),
            in the timer's `unit` and rounded by `ndigits` if given.
        total_time: Time elapsed since the timer started, in the timer's
            `unit` and rounded by `ndigits` if given.
    """

    label: str
    lap_time: float
    total_time: float


class BaseTimer(ContextDecorator, ABC):
    """Abstract base for `Timer` and `LapTimer`.

    Provides the shared timing machinery: unit/precision formatting,
    `pause`/`resume`/`suspend`, and a context-manager protocol that
    auto-resumes a paused timer on exit. Subclasses implement `_finalize`
    to record their final result, and may override the `_reset` hook to
    clear per-`with`-block state. Not part of the public API -- prefer
    `Timer` or `LapTimer`.
    """

    def __init__(self, unit: TimeUnit = "s", *, ndigits: int | None = None) -> None:
        """Initialize the timer with a reporting unit and optional precision.

        Args:
            unit: The time unit for reported values. One of "s", "ms", "us",
                "ns". Defaults to "s".
            ndigits: The number of decimal places to round reported values to.
                If None, no rounding is applied. Defaults to None.

        Raises:
            ValueError: If `unit` is not one of the supported values.
        """
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
        """Round `value` to `ndigits` decimal places, or return it unchanged."""
        return value if self.ndigits is None else round(value, self.ndigits)

    def _format_time(self, elapsed_ns: int) -> float:
        """Convert a nanosecond delta to the timer's reporting unit."""
        return self._apply_ndigits(elapsed_ns * self.scale)

    def _ensure_started(self) -> None:
        """Raise if the timer has not entered a `with` block (or has exited)."""
        if not self._started:
            msg = "Timer has not been started."
            raise RuntimeError(msg)

    def _reset(self) -> None:
        """Hook: clear per-`with`-block state. Called after `_start_time` is set."""

    @abstractmethod
    def _finalize(self) -> None:
        """Compute the final result. Called from `__exit__` after auto-resume."""

    def pause(self) -> None:
        """Pause the timer, excluding subsequent time from measurement.

        Subsequent time is excluded until `resume` is called (or until
        `__exit__` auto-resumes a still-paused timer).

        Raises:
            RuntimeError: If the timer has not been started, or is already
                paused.
        """
        self._ensure_started()
        if self._is_paused:
            msg = "Timer is already paused."
            raise RuntimeError(msg)

        self._pause_start = time.perf_counter_ns()
        self._is_paused = True

    def resume(self) -> int:
        """Resume the timer after a `pause` call.

        The just-elapsed pause interval is added to the internal start time
        so that subsequent measurements correctly exclude it.

        Returns:
            The duration of the just-finished pause, in nanoseconds.

        Raises:
            RuntimeError: If the timer has not been started, or is not paused.
        """
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
        """Pause the timer for the duration of the `with` block.

        Equivalent to calling `pause` on entry and `resume` on exit. The
        resume on exit is skipped if the user manually called `resume`
        inside the block, so paired pause/resume calls work safely.
        """
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
    """A single-shot timer measuring one elapsed duration.

    Usable as a context manager or as a decorator. The measured duration
    is stored in `elapsed` once the `with` block exits or the decorated
    function returns.

    Attributes:
        elapsed: The measured duration, in the timer's `unit`. Defaults to
            0.0 until the first exit.

    Example:
        with Timer("ms", ndigits=2) as t:
            do_work()
        # `t.elapsed` is now the elapsed time, e.g. 12.34.
    """

    def __init__(self, unit: TimeUnit = "s", *, ndigits: int | None = None) -> None:
        """Initialize the timer.

        Args:
            unit: The time unit for reported values. One of "s", "ms", "us",
                "ns". Defaults to "s".
            ndigits: The number of decimal places to round `elapsed` to.
                If None, no rounding is applied. Defaults to None.

        Raises:
            ValueError: If `unit` is not one of the supported values.
        """
        super().__init__(unit=unit, ndigits=ndigits)
        self.elapsed: float = 0.0

    def _finalize(self) -> None:
        """Store the elapsed time in `elapsed`."""
        elapsed_ns = time.perf_counter_ns() - self._start_time
        self.elapsed = self._format_time(elapsed_ns)


class LapTimer(BaseTimer):
    """A multi-lap timer recording named intermediate timings.

    Usable as a context manager or as a decorator. Inside the block, call
    `lap(label)` to record a lap.

    Attributes:
        on_same_label: The same-label handling policy (see `__init__`).
        records: The list of user-supplied laps.
        total_elapsed: The total measured duration, from start to exit.
            Defaults to 0.0 until the first exit.

    Example:
        with LapTimer("ms", ndigits=1) as lt:
            step_a()
            lt.lap("A")
            step_b()
            lt.lap("B")
        # `lt.summary` is e.g. {"A": 12.3, "B": 8.7};
        # `lt.total_elapsed` is e.g. 21.0.
    """

    def __init__(
        self,
        unit: TimeUnit = "s",
        *,
        ndigits: int | None = None,
        on_same_label: LabelPolicy = "merge",
    ) -> None:
        """Initialize the lap timer.

        Args:
            unit: The time unit for reported values. One of "s", "ms", "us",
                "ns". Defaults to "s".
            ndigits: The number of decimal places to round reported values
                to. If None, no rounding is applied. Defaults to None.
            on_same_label: Behavior when a label passed to `lap` has been
                used before in the same `with` block. "merge" records the
                label verbatim so duplicates aggregate in `summary`,
                "separate" appends a " (N)" suffix so repeats stay distinct,
                "reject" raises `ValueError`. Defaults to "merge".

        Raises:
            ValueError: If `unit` or `on_same_label` is not one of the
                supported values.
        """
        super().__init__(unit=unit, ndigits=ndigits)

        if on_same_label not in _LABEL_POLICIES:
            msg = f"on_same_label must be one of {sorted(_LABEL_POLICIES)}"
            msg += f" (got {on_same_label!r})."
            raise ValueError(msg)

        self.on_same_label = on_same_label
        self.records: list[LapRecord] = []
        self.total_elapsed: float = 0.0

        self._last_time: int = 0
        self._label_counts: dict[str, int] = {}

    @property
    def summary(self) -> dict[str, float]:
        """Per-label sum of `lap_time` across `records` (excludes `final`).

        Each record's `lap_time` is already rounded by `ndigits` (when
        set); this property sums those rounded values and rounds the sum
        once more.

        Returns:
            A mapping from label to total `lap_time` for that label, in the
            timer's `unit`.
        """
        grouped: dict[str, float] = defaultdict(float)
        for record in self.records:
            grouped[record["label"]] += record["lap_time"]

        return {label: self._apply_ndigits(total) for label, total in grouped.items()}

    def resume(self) -> int:
        """Resume the timer and advance the lap baseline.

        Extends `BaseTimer.resume` by also adding the pause duration to
        `_last_time` so that the next lap's `lap_time` excludes the pause
        interval.

        Returns:
            The duration of the just-finished pause, in nanoseconds.

        Raises:
            RuntimeError: If the timer has not been started, or is not paused.
        """
        pause_duration = super().resume()
        self._last_time += pause_duration

        return pause_duration

    def _reset(self) -> None:
        """Clear per-`with`-block state so the timer can be reused safely."""
        self._last_time = self._start_time
        self.records.clear()
        self.total_elapsed = 0.0
        self._label_counts.clear()

    def _resolve_label(self, label: str) -> str:
        """Apply `on_same_label` and return the actual label to record.

        Increments the per-label counter only if the lap is accepted, so a
        failed "reject" lap does not leave the counter inflated.
        """
        next_count = self._label_counts.get(label, 0) + 1
        if next_count > 1 and self.on_same_label == "reject":
            msg = f"Label {label!r} is already used."
            raise ValueError(msg)

        self._label_counts[label] = next_count

        return (
            f"{label} ({next_count})"
            if next_count > 1 and self.on_same_label == "separate"
            else label
        )

    def _make_record(self, label: str) -> LapRecord:
        """Build a record stamped with the current time and advance `_last_time`."""
        current_time = time.perf_counter_ns()

        record: LapRecord = {
            "label": label,
            "lap_time": self._format_time(current_time - self._last_time),
            "total_time": self._format_time(current_time - self._start_time),
        }
        self._last_time = current_time

        return record

    def lap(self, label: str = "Lap") -> None:
        """Record a lap with the given label.

        The lap's `lap_time` is the time since the previous `lap` call (or
        the start of the `with` block), excluding any pause intervals. The
        lap's `total_time` is the time since the start, also excluding
        pauses.

        Args:
            label: The lap's name. Defaults to "Lap".

        Raises:
            RuntimeError: If the timer has not been started, or is paused.
            ValueError: If `on_same_label` is "reject" and `label` has
                already been used in this `with` block.
        """
        self._ensure_started()
        if self._is_paused:
            msg = "Cannot record a lap while paused."
            raise RuntimeError(msg)

        self.records.append(self._make_record(self._resolve_label(label)))

    def _finalize(self) -> None:
        """Set `total_elapsed` from start to current time."""
        elapsed_ns = time.perf_counter_ns() - self._start_time
        self.total_elapsed = self._format_time(elapsed_ns)
