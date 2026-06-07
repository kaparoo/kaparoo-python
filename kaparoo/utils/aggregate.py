"""Nested, pluggable aggregation of labelled metric streams.

WORK IN PROGRESS -- the public API of this module is experimental and may
change or be removed before the next release; it is not yet covered by the
project's SemVer guarantees. In particular, store-all reductions for
non-decomposable statistics (median, quantiles) are still under design.
"""

from __future__ import annotations

__all__ = (
    "Aggregator",
    "Fold",
    "Last",
    "Max",
    "Mean",
    "Min",
    "Reduction",
    "Std",
    "Sum",
    "UnweightedReduction",
    "Var",
)

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from typing import Any


class Reduction[S](ABC):
    """How to fold a stream of `(value, weight)` samples into one scalar.

    A reduction is a *weighted monoid*: `identity` is the unit, `merge`
    combines two partial states associatively, and `step` folds one
    sample in. Because partial states compose, the same reduction nests
    exactly across loop levels (batch -> epoch -> run) and stays online --
    constant memory per metric, no per-sample storage.

    Type Parameters:
        S: The reduction's internal accumulator state.

    Subclasses define the nesting behavior by implementing all four
    methods. Weight-agnostic reductions should subclass the simpler
    `UnweightedReduction` instead; `Fold` is a ready-made one built from a
    binary callable.
    """

    @abstractmethod
    def identity(self) -> S:
        """Return the empty accumulator state (the monoid unit)."""

    @abstractmethod
    def step(self, state: S, value: float, weight: float) -> S:
        """Fold one `(value, weight)` sample into `state`."""

    @abstractmethod
    def merge(self, a: S, b: S) -> S:
        """Combine two partial states; associative, with `identity` as unit."""

    @abstractmethod
    def result(self, state: S) -> float:
        """Project the accumulated `state` to its final scalar."""


class UnweightedReduction[S](Reduction[S]):
    """Base for reductions that ignore per-sample weight.

    Subclasses implement the weightless `accumulate` (plus `identity`,
    `merge`, `result`); `step` forwards to it and drops the weight. Use
    this for `Min`/`Max`/`Sum`-style folds where each sample counts once
    regardless of its weight.
    """

    def step(self, state: S, value: float, weight: float) -> S:  # noqa: ARG002
        # `weight` is part of the `Reduction.step` contract but irrelevant
        # to an unweighted fold; intentionally dropped here.
        return self.accumulate(state, value)

    @abstractmethod
    def accumulate(self, state: S, value: float) -> S:
        """Fold one `value` into `state`, ignoring weight."""


@dataclass(frozen=True)
class Mean(Reduction[tuple[float, float]]):
    """Weighted arithmetic mean; state is `(weighted_sum, total_weight)`.

    With the default `weight=1` this is the plain mean; pass per-sample
    weights (e.g. batch sizes) for a correctly pooled mean. Empty -> `nan`.
    """

    def identity(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def step(
        self, state: tuple[float, float], value: float, weight: float
    ) -> tuple[float, float]:
        return (state[0] + weight * value, state[1] + weight)

    def merge(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> tuple[float, float]:
        return (a[0] + b[0], a[1] + b[1])

    def result(self, state: tuple[float, float]) -> float:
        return state[0] / state[1] if state[1] else float("nan")


@dataclass(frozen=True)
class Var(Reduction[tuple[float, float, float]]):
    """Weighted population variance; state is `(weight, mean, M2)`.

    Accumulated online (Welford) and merged exactly (Chan's parallel
    algorithm), so it nests across loop levels like the other reductions.
    Uses the population convention -- M2 over the total weight, as in
    numpy's default `ddof=0` -- which stays well-defined under weighting.
    Empty -> `nan`.
    """

    def identity(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def step(
        self, state: tuple[float, float, float], value: float, weight: float
    ) -> tuple[float, float, float]:
        total, mean, m2 = state
        total += weight
        delta = value - mean
        mean += (weight / total) * delta
        m2 += weight * delta * (value - mean)
        return (total, mean, m2)

    def merge(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        total_a, mean_a, m2_a = a
        total_b, mean_b, m2_b = b
        total = total_a + total_b
        if total == 0:
            return (0.0, 0.0, 0.0)
        delta = mean_b - mean_a
        mean = mean_a + delta * total_b / total
        m2 = m2_a + m2_b + delta * delta * total_a * total_b / total
        return (total, mean, m2)

    def result(self, state: tuple[float, float, float]) -> float:
        total, _mean, m2 = state
        return m2 / total if total else float("nan")


@dataclass(frozen=True)
class Std(Var):
    """Weighted population standard deviation: the square root of `Var`.

    Shares `Var`'s online, mergeable moments; only the final projection
    differs. Empty -> `nan`.
    """

    def result(self, state: tuple[float, float, float]) -> float:
        variance = super().result(state)
        if math.isnan(variance):  # empty state
            return variance
        return max(variance, 0.0) ** 0.5


@dataclass(frozen=True)
class Sum(UnweightedReduction[float]):
    """Running sum of values (weight ignored). Empty -> `0.0`."""

    def identity(self) -> float:
        return 0.0

    def accumulate(self, state: float, value: float) -> float:
        return state + value

    def merge(self, a: float, b: float) -> float:
        return a + b

    def result(self, state: float) -> float:
        return state


@dataclass(frozen=True)
class Min(UnweightedReduction[float | None]):
    """Running minimum; `None` until the first sample. Empty -> `nan`."""

    def identity(self) -> float | None:
        return None

    def accumulate(self, state: float | None, value: float) -> float | None:
        return value if state is None else min(state, value)

    def merge(self, a: float | None, b: float | None) -> float | None:
        if a is None:
            return b
        if b is None:
            return a
        return min(a, b)

    def result(self, state: float | None) -> float:
        return float("nan") if state is None else state


@dataclass(frozen=True)
class Max(UnweightedReduction[float | None]):
    """Running maximum; `None` until the first sample. Empty -> `nan`."""

    def identity(self) -> float | None:
        return None

    def accumulate(self, state: float | None, value: float) -> float | None:
        return value if state is None else max(state, value)

    def merge(self, a: float | None, b: float | None) -> float | None:
        if a is None:
            return b
        if b is None:
            return a
        return max(a, b)

    def result(self, state: float | None) -> float:
        return float("nan") if state is None else state


@dataclass(frozen=True)
class Last(UnweightedReduction[float | None]):
    """Most recently seen value; empty -> `nan`.

    Under `merge`, the right operand wins (it is the later sub-stream).
    """

    def identity(self) -> float | None:
        return None

    def accumulate(self, state: float | None, value: float) -> float | None:  # noqa: ARG002
        # "last" discards the prior `state` by definition.
        return value

    def merge(self, a: float | None, b: float | None) -> float | None:
        return a if b is None else b

    def result(self, state: float | None) -> float:
        return float("nan") if state is None else state


@dataclass(frozen=True)
class Fold(UnweightedReduction[float]):
    """A scalar-monoid reduction built from a binary `combine` callable.

    `combine` must be associative and commutative with `initial` as its
    unit -- e.g. `(min, inf)`, `(max, -inf)`, `(operator.add, 0.0)`,
    `(operator.mul, 1.0)`. Per-sample weight is ignored; for weighted
    reductions use `Mean` or subclass `Reduction` directly.

    `finalize`, if given, transforms the accumulated scalar on `result`
    (e.g. a square root for an RMS-style fold).
    """

    combine: Callable[[float, float], float]
    initial: float
    finalize: Callable[[float], float] | None = None

    def identity(self) -> float:
        return self.initial

    def accumulate(self, state: float, value: float) -> float:
        return self.combine(state, value)

    def merge(self, a: float, b: float) -> float:
        return self.combine(a, b)

    def result(self, state: float) -> float:
        return state if self.finalize is None else self.finalize(state)


class Aggregator:
    """A named collection of online reductions over labelled value streams.

    Each metric name maps to its own `Reduction`; `update` folds a batch
    of named values in, `compute` projects every metric to its scalar.
    Levels of a nested loop compose two ways:

        - `merge` combines another `Aggregator`'s raw states into this one
          (same reduction per metric, sample-weighted) -- e.g. an exact
          pooled mean over every batch of every epoch.
        - `update(child.compute(), weight=...)` feeds a child's *results*
          back as samples, which is how an outer level may use a different
          reduction than its children (e.g. `Min` over epoch means to find
          the best epoch).

    Metrics are created on first sight using the default `reduction`,
    unless named in `overrides`. Reductions are online, so memory stays
    constant in the number of samples.
    """

    def __init__(
        self,
        reduction: Reduction[Any] | None = None,
        *,
        overrides: Mapping[str, Reduction[Any]] | None = None,
    ) -> None:
        """Configure the per-metric reductions.

        Args:
            reduction: Default reduction applied to any metric not named in
                `overrides`. Defaults to `Mean()`.
            overrides: Per-metric reduction overrides keyed by metric name.
        """
        self._default: Reduction[Any] = Mean() if reduction is None else reduction
        self._overrides: dict[str, Reduction[Any]] = dict(overrides or {})
        self._metrics: dict[str, tuple[Reduction[Any], Any]] = {}
        self._weight: float = 0.0

    def update(self, values: Mapping[str, float], *, weight: float = 1.0) -> None:
        """Fold one sample of named `values` in, each carrying `weight`.

        Args:
            values: Metric name -> value for this sample (e.g. one batch).
            weight: Shared weight for every value (e.g. the batch size).
                Defaults to 1.0.

        Raises:
            ValueError: If `weight` is not positive.
        """
        if weight <= 0:
            msg = f"weight must be positive (got {weight})"
            raise ValueError(msg)

        metrics = self._metrics
        for key, value in values.items():
            entry = metrics.get(key)
            if entry is None:
                reduction = self._overrides.get(key, self._default)
                state = reduction.identity()
            else:
                reduction, state = entry
            metrics[key] = (reduction, reduction.step(state, value, weight))

        self._weight += weight

    def compute(self) -> dict[str, float]:
        """Project every accumulated metric to its final scalar."""
        return {
            key: reduction.result(state)
            for key, (reduction, state) in self._metrics.items()
        }

    def reset(self) -> None:
        """Clear all accumulated state, keeping the reduction configuration."""
        self._metrics.clear()
        self._weight = 0.0

    def state(self) -> dict[str, tuple[Reduction[Any], Any]]:
        """Snapshot each metric's `(reduction, accumulator state)`.

        States are immutable, so the snapshot is safe to keep or restore --
        useful for `merge` and for checkpointing a long run.
        """
        return dict(self._metrics)

    def merge(self, other: Aggregator) -> None:
        """Fold another `Aggregator`'s state into this one, in place.

        Shared metrics are combined via their reduction's `merge` (so the
        result is exactly as if both streams had fed one tracker); metrics
        only in `other` are adopted. The total `weight` is added.

        Args:
            other: The tracker to absorb. Metrics present in both must use
                an equal reduction.

        Raises:
            ValueError: If a shared metric's reductions differ.
        """
        for key, (reduction, other_state) in other._metrics.items():
            entry = self._metrics.get(key)
            if entry is None:
                self._metrics[key] = (reduction, other_state)
                continue
            own_reduction, own_state = entry
            if own_reduction != reduction:
                msg = (
                    f"cannot merge metric {key!r}: reductions differ "
                    f"({own_reduction} vs {reduction})"
                )
                raise ValueError(msg)
            self._metrics[key] = (own_reduction, own_reduction.merge(own_state, other_state))

        self._weight += other.weight

    def fresh(self) -> Aggregator:
        """Return a new empty `Aggregator` with the same reduction config."""
        return Aggregator(self._default, overrides=self._overrides)

    @property
    def weight(self) -> float:
        """Total weight folded in across all `update` calls (and absorbed via
        `merge`).

        A grand total over every call, independent of which metric keys each
        call carried -- so when updates have heterogeneous key sets it need
        not equal any single metric's effective weight. A weighted reduction
        already tracks its own per-metric weight inside its state (`Mean`'s
        `total_weight`, `Var` / `Std`'s `weight`); unweighted reductions
        (`Sum`, `Min`, `Max`, `Last`) discard weight entirely.
        """
        return self._weight
