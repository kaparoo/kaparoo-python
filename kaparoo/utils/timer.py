from __future__ import annotations

__all__ = ("SpanRecord", "SpanTimer", "Timer")

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


class SpanRecord(TypedDict):
    """A single timing record produced by `SpanTimer`.

    A span is produced either by `lap` (the span since the previous
    lap) or by `measure` (the span of a wrapped block).

    Attributes:
        label: The span's name. May carry a " (N)" suffix when produced
            under `on_same_label="separate"`.
        duration: Length of this span, in the timer's `unit` and rounded
            by `ndigits` if given. For `lap`, the time since the previous
            lap (or the timer start); for `measure`, the wrapped block's
            duration.
        total_time: Time elapsed from the timer start to this span's end,
            in the timer's `unit` and rounded by `ndigits` if given.
    """

    label: str
    duration: float
    total_time: float


class BaseTimer(ContextDecorator, ABC):
    """Abstract base for `Timer` and `SpanTimer`.

    Provides the shared timing machinery: unit/precision formatting,
    `pause`/`resume`/`suspend`, and a context-manager protocol that
    auto-resumes a paused timer on exit. Subclasses implement `_finalize`
    to record their final result, and may override the `_reset` hook to
    clear per-`with`-block state. Not part of the public API -- prefer
    `Timer` or `SpanTimer`.

    An instance is reusable but **not reentrant**: a single instance must
    not be nested within itself -- including as a decorator on a recursive
    function -- because it holds one set of per-run state. Re-entering a
    still-running timer raises `RuntimeError`; use a separate instance per
    concurrent measurement.
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
        self.ndigits = ndigits

        self._start_time: int = 0
        self._started: bool = False
        self._is_paused: bool = False
        self._pause_start: int = 0

    @property
    def scale(self) -> float:
        """Nanosecond-to-`unit` multiplier, derived from `unit`.

        Kept as a derived value so it can never drift out of sync with
        `unit`.
        """
        return _SCALES[self.unit]

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

    def _resume(self) -> int:
        """Resume the timer and return the just-finished pause, in nanoseconds.

        The shared worker behind `resume`; subclasses override this hook
        (not the public `resume`) to react to the pause interval. The
        just-elapsed pause is added to the internal start time so that
        subsequent measurements correctly exclude it.

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

    def resume(self) -> None:
        """Resume the timer after a `pause` call.

        The just-elapsed pause interval is excluded from subsequent
        measurements.

        Raises:
            RuntimeError: If the timer has not been started, or is not paused.
        """
        self._resume()

    @contextmanager
    def suspend(self) -> Iterator[None]:
        """Pause the timer for the duration of the `with` block.

        Equivalent to calling `pause` on entry and `resume` on exit. The
        resume on exit is skipped if the user manually called `resume`
        inside the block, so paired pause/resume calls work safely.

        Single-level only: pausing is a flag, not a depth counter, so
        nesting `suspend` blocks (or calling `pause` inside one) raises
        `RuntimeError` from the inner `pause`.
        """
        self.pause()
        try:
            yield
        finally:
            if self._is_paused:
                self.resume()

    def __enter__(self) -> Self:
        if self._started:
            msg = "Timer is not reentrant; use a separate instance."
            raise RuntimeError(msg)

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

        try:
            self._finalize()
        finally:
            self._started = False


class Timer(BaseTimer):
    """A single-shot timer measuring one elapsed duration.

    Usable as a context manager or as a decorator. The measured duration
    is stored in `elapsed` once the `with` block exits or the decorated
    function returns.

    Args:
        unit: The time unit for reported values. One of "s", "ms", "us",
            "ns". Defaults to "s".
        ndigits: The number of decimal places to round `elapsed` to. If
            None, no rounding is applied. Defaults to None.

    Attributes:
        elapsed: The measured duration, in the timer's `unit`. Defaults to
            0.0 until the first exit.

    Raises:
        ValueError: If `unit` is not one of the supported values.

    Example:
        with Timer("ms", ndigits=2) as t:
            do_work()
        # `t.elapsed` is now the elapsed time, e.g. 12.34.
    """

    elapsed: float = 0.0

    def _finalize(self) -> None:
        """Store the elapsed time in `elapsed`."""
        elapsed_ns = time.perf_counter_ns() - self._start_time
        self.elapsed = self._format_time(elapsed_ns)


class SpanTimer(BaseTimer):
    """A timer recording named time spans within one `with` block.

    Usable as a context manager or as a decorator. Spans are recorded
    in two complementary ways:

        - `lap(label)` splits the timeline: each lap's `duration` is the
          time since the previous lap (or the start), so every instant is
          attributed to exactly one span.
        - `measure(label)` brackets a region (as a `with` block or a
          decorator): only the wrapped span is recorded, and time spent
          outside any `measure` block is attributed to no span.

    Both feed the same `records` / `summary`, honour `on_same_label`, and
    exclude paused intervals.

    Attributes:
        on_same_label: The same-label handling policy (see `__init__`).
        records: The recorded spans, in call order.
        elapsed: The total measured duration, from start to exit.
            Defaults to 0.0 until the first exit.

    Example:
        with SpanTimer("ms", ndigits=1) as st:
            step_a()
            st.lap("A")              # split: time since start
            with st.measure("B"):    # block: only this region
                step_b()
        # `st.summary` is e.g. {"A": 12.3, "B": 8.7};
        # `st.elapsed` is the full block's wall time.
    """

    def __init__(
        self,
        unit: TimeUnit = "s",
        *,
        ndigits: int | None = None,
        on_same_label: LabelPolicy = "merge",
    ) -> None:
        """Initialize the span timer.

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
        self.records: list[SpanRecord] = []
        self.elapsed: float = 0.0

        self._last_time: int = 0
        self._label_counts: dict[str, int] = {}

    @property
    def summary(self) -> dict[str, float]:
        """Per-label sum of `duration` across `records`.

        Only recorded spans count: time outside every `lap` / `measure`
        span (e.g. after the last `lap`, or between `measure` blocks) is
        not included. Each record's `duration` is already rounded by
        `ndigits` (when set); this property sums those rounded values and
        rounds the sum once more.

        Returns:
            A mapping from label to total `duration` for that label, in the
            timer's `unit`.
        """
        grouped: dict[str, float] = defaultdict(float)
        for record in self.records:
            grouped[record["label"]] += record["duration"]

        return {label: self._apply_ndigits(total) for label, total in grouped.items()}

    def _resume(self) -> int:
        """Resume the timer and advance the lap baseline.

        Extends `BaseTimer._resume` by also adding the pause duration to
        `_last_time` so that the next lap's `duration` excludes the pause
        interval.
        """
        pause_duration = super()._resume()
        self._last_time += pause_duration

        return pause_duration

    def _reset(self) -> None:
        """Clear per-`with`-block state so the timer can be reused safely."""
        self._last_time = self._start_time
        self.records.clear()
        self.elapsed = 0.0
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

    def _make_record(self, label: str) -> SpanRecord:
        """Build a record stamped with the current time and advance `_last_time`."""
        current_time = time.perf_counter_ns()

        record: SpanRecord = {
            "label": label,
            "duration": self._format_time(current_time - self._last_time),
            "total_time": self._format_time(current_time - self._start_time),
        }
        self._last_time = current_time

        return record

    def lap(self, label: str = "Lap") -> None:
        """Record a lap with the given label.

        The lap's `duration` is the time since the previous `lap` call (or
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

    @contextmanager
    def measure(self, label: str = "Block") -> Iterator[None]:
        """Record a span covering only the wrapped block (stopwatch style).

        Unlike `lap`, which splits the timeline into contiguous spans,
        `measure` times only the wrapped region; time spent outside any
        `measure` block is attributed to no span. Pauses inside the
        block are excluded. A span is recorded only on clean exit -- if
        the block raises, nothing is recorded and the exception propagates.
        Repeated labels follow `on_same_label`, exactly as `lap`. Do not
        nest `measure` blocks: each resets the shared baseline, so an outer
        block would record only the span after its inner block ends.

        Because `contextmanager` results are also `ContextDecorator`s, the
        returned object doubles as a decorator (every decorated call
        records one span, provided the timer is running when called):

            st = SpanTimer("ms")

            @st.measure("load")
            def load() -> None: ...

            with st:
                load()                    # records a "load" span
                with st.measure("parse"):
                    parse()               # records a "parse" span

        Args:
            label: The span's name. Defaults to "Block".

        Yields:
            None. The wrapped block runs while the span is timed.

        Raises:
            RuntimeError: If the timer has not been started, or is paused on
                entry.
            ValueError: If `on_same_label` is "reject" and `label` has
                already been used in this `with` block.
        """
        self._ensure_started()
        if self._is_paused:
            msg = "Cannot start a measurement while paused."
            raise RuntimeError(msg)

        self._last_time = time.perf_counter_ns()
        yield
        self.lap(label)

    def _finalize(self) -> None:
        """Set `elapsed` from start to current time."""
        elapsed_ns = time.perf_counter_ns() - self._start_time
        self.elapsed = self._format_time(elapsed_ns)
