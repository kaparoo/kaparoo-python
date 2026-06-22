"""Nested, pluggable aggregation of labelled metric streams."""

from __future__ import annotations

__all__ = (
    "Aggregator",
    "Fold",
    "Last",
    "Max",
    "Mean",
    "Median",
    "Min",
    "OptionalFold",
    "Quantile",
    "Reduction",
    "Std",
    "Stored",
    "Sum",
    "UnweightedReduction",
    "Var",
)

import math
from abc import ABC, abstractmethod
from bisect import bisect_left
from dataclasses import dataclass
from itertools import accumulate
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from typing import Any


# ========================== #
#         Reductions         #
# ========================== #


class Reduction[S](ABC):
    """A weighted, mergeable fold of a `(value, weight)` stream into one scalar.

    A reduction is a *weighted monoid*: `identity` is the unit, `merge`
    combines two partial states associatively, and `step` folds one
    sample in. Because partial states compose, the same reduction nests
    exactly across loop levels (batch -> epoch -> run) and stays online --
    constant memory per metric, no per-sample storage.

    Weights are assumed **positive** -- `Aggregator` enforces `weight > 0`,
    and `step` / `merge` are undefined for zero or negative weight (a
    variance, for instance, divides by the running total weight).

    Type Parameters:
        S: The reduction's internal accumulator state.

    Subclasses define the nesting behaviour by implementing all four
    methods. Weight-agnostic reductions should subclass the simpler
    `UnweightedReduction`; `Fold` is a ready-made one built from a binary
    callable.
    """

    @abstractmethod
    def identity(self) -> S:
        """Return the empty accumulator state -- the unit `merge` leaves alone."""

    @abstractmethod
    def step(self, state: S, value: float, weight: float) -> S:
        """Fold one `(value, weight)` sample into `state`."""

    @abstractmethod
    def merge(self, a: S, b: S) -> S:
        """Combine two partial states into one.

        Associative with `identity` as the unit, so states from different
        loop levels compose into the same result as a single pass.
        """

    @abstractmethod
    def result(self, state: S) -> float:
        """Project the accumulated `state` to its final scalar."""


class UnweightedReduction[S](Reduction[S]):
    """A `Reduction` whose samples each count once, regardless of weight.

    Implements `step` by forwarding to the weightless `accumulate`;
    subclasses supply `accumulate` along with `identity`, `merge`, and
    `result`. Suits sum- or extremum-style folds where a sample's weight
    does not affect the outcome.
    """

    @override
    def step(self, state: S, value: float, weight: float) -> S:
        """Fold one sample into `state`, discarding `weight`.

        `weight` stays in the signature to honour the `Reduction.step`
        contract, but an unweighted fold has no use for it.
        """
        return self.accumulate(state, value)

    @abstractmethod
    def accumulate(self, state: S, value: float) -> S:
        """Fold one `value` into `state`, ignoring weight."""


# ========================== #
#      Online reductions     #
# ========================== #


@dataclass(frozen=True)
class Mean(Reduction[tuple[float, float]]):
    """The weighted arithmetic mean of the stream; empty -> `nan`.

    With the default `weight=1` this is the plain mean; pass per-sample
    weights (e.g. batch sizes) for a correctly pooled mean. The state is a
    `(weighted_sum, total_weight)` pair.
    """

    @override
    def identity(self) -> tuple[float, float]:
        """Return the zero accumulator `(weighted_sum=0, total_weight=0)`."""
        return (0.0, 0.0)

    @override
    def step(
        self, state: tuple[float, float], value: float, weight: float
    ) -> tuple[float, float]:
        """Add `weight * value` to the sum and `weight` to the total weight."""
        return (state[0] + weight * value, state[1] + weight)

    @override
    def merge(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> tuple[float, float]:
        """Add two `(weighted_sum, total_weight)` pairs component-wise."""
        return (a[0] + b[0], a[1] + b[1])

    @override
    def result(self, state: tuple[float, float]) -> float:
        """Divide the weighted sum by the total weight."""
        return state[0] / state[1] if state[1] else float("nan")


@dataclass(frozen=True)
class Var(Reduction[tuple[float, float, float]]):
    """The weighted population variance of the stream; empty -> `nan`.

    Accumulated online (Welford's algorithm) and merged exactly (Chan's
    parallel formula), so it nests across loop levels like every other
    reduction. Uses the population convention -- the second moment over the
    total weight, as in numpy's default `ddof=0` -- which stays well-defined
    under weighting. The state is a `(total_weight, mean, M2)` triple, where
    `M2` is the weighted sum of squared deviations from the running mean.
    """

    @override
    def identity(self) -> tuple[float, float, float]:
        """Return the zero accumulator `(total_weight=0, mean=0, M2=0)`."""
        return (0.0, 0.0, 0.0)

    @override
    def step(
        self, state: tuple[float, float, float], value: float, weight: float
    ) -> tuple[float, float, float]:
        """Fold one sample in with Welford's online moment update."""
        total, mean, m2 = state

        total += weight
        delta = value - mean
        mean += (weight / total) * delta
        m2 += weight * delta * (value - mean)

        return (total, mean, m2)

    @override
    def merge(
        self,
        a: tuple[float, float, float],
        b: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Combine two `(total_weight, mean, M2)` triples with Chan's formula."""
        total_a, mean_a, m2_a = a
        total_b, mean_b, m2_b = b

        total = total_a + total_b
        if total == 0:
            return (0.0, 0.0, 0.0)

        delta = mean_b - mean_a
        mean = mean_a + delta * total_b / total
        m2 = m2_a + m2_b + delta * delta * total_a * total_b / total

        return (total, mean, m2)

    @override
    def result(self, state: tuple[float, float, float]) -> float:
        """Divide `M2` by the total weight to get the population variance."""
        total, _mean, m2 = state
        return m2 / total if total else float("nan")


@dataclass(frozen=True)
class Std(Var):
    """The weighted population standard deviation of the stream; empty -> `nan`.

    Inherits `Var`'s online, mergeable moments and differs only in the final
    projection: a square root.
    """

    @override
    def result(self, state: tuple[float, float, float]) -> float:
        """Take the square root of the population variance."""
        variance = super().result(state)
        if math.isnan(variance):  # empty state
            return variance

        # Clamp a tiny negative variance from rounding before the square root.
        return max(variance, 0.0) ** 0.5


@dataclass(frozen=True)
class Sum(UnweightedReduction[float]):
    """The running sum of the stream's values, weight ignored; empty -> `0.0`.

    The state is the partial sum so far.
    """

    @override
    def identity(self) -> float:
        """Return the additive unit, `0.0`."""
        return 0.0

    @override
    def accumulate(self, state: float, value: float) -> float:
        """Add `value` to the running sum."""
        return state + value

    @override
    def merge(self, a: float, b: float) -> float:
        """Add two partial sums."""
        return a + b

    @override
    def result(self, state: float) -> float:
        """Return the accumulated sum unchanged."""
        return state


# ========================== #
#        Seeded folds        #
# ========================== #


class OptionalFold(UnweightedReduction[float | None]):
    """An unweighted fold seeded by its first sample; empty -> `nan`.

    `None` is the identity, so an empty stream projects to `nan`; the first
    sample seeds the state, and later samples and merges combine via the
    abstract `_combine`. Subclasses supply only that binary operator.

    Differs from `Fold`, which seeds with a concrete `initial` and so reports
    that `initial` -- not `nan` -- on an empty stream. A running extremum
    wants the `nan` that the `None` seed gives.
    """

    @override
    def identity(self) -> float | None:
        """Return `None`, the unseeded state that projects to `nan`."""
        return None

    @override
    def accumulate(self, state: float | None, value: float) -> float | None:
        """Seed with `value` when unseeded, otherwise fold it via `_combine`."""
        return value if state is None else self._combine(state, value)

    @override
    def merge(self, a: float | None, b: float | None) -> float | None:
        """Combine two states, treating `None` as "saw no samples"."""
        if a is None:
            return b
        if b is None:
            return a
        return self._combine(a, b)

    @override
    def result(self, state: float | None) -> float:
        """Return the seeded value, or `nan` if no sample was ever seen."""
        return float("nan") if state is None else state

    @abstractmethod
    def _combine(self, a: float, b: float) -> float:
        """Combine two present (non-`None`) values into one."""


@dataclass(frozen=True)
class Min(OptionalFold):
    """The smallest value seen in the stream; empty -> `nan`."""

    @override
    def _combine(self, a: float, b: float) -> float:
        """Return the smaller of `a` and `b`."""
        return min(a, b)


@dataclass(frozen=True)
class Max(OptionalFold):
    """The largest value seen in the stream; empty -> `nan`."""

    @override
    def _combine(self, a: float, b: float) -> float:
        """Return the larger of `a` and `b`."""
        return max(a, b)


@dataclass(frozen=True)
class Last(OptionalFold):
    """The most recently seen value in the stream; empty -> `nan`.

    On `merge`, "most recent" is taken to be the right-hand state.
    """

    @override
    def _combine(self, a: float, b: float) -> float:
        """Return the later value, `b`."""
        return b


# ========================== #
#        Callable fold       #
# ========================== #


@dataclass(frozen=True)
class Fold(UnweightedReduction[float]):
    """A reduction built from a binary `combine` callable; empty -> `initial`.

    Turns any scalar monoid into a reduction without a dedicated subclass --
    e.g. `Fold(operator.mul, 1.0)` for a running product. Per-sample weight is
    ignored; for a weighted reduction use `Mean` or subclass `Reduction`.

    Attributes:
        combine: A binary operator, associative and commutative with `initial`
            as its unit (e.g. `(min, inf)`, `(operator.add, 0.0)`). Because
            `Aggregator.merge` compares reductions by value, pass a stable
            callable (a module-level function), not a fresh lambda per instance,
            when you rely on that equality -- this applies to `finalize` too.
        initial: The unit value, also reported for an empty stream.
        finalize: An optional transform applied to the accumulated scalar in
            `result` (e.g. a square root for an RMS-style fold).
    """

    combine: Callable[[float, float], float]
    initial: float
    finalize: Callable[[float], float] | None = None

    @override
    def identity(self) -> float:
        """Return `initial`, the fold's unit value."""
        return self.initial

    @override
    def accumulate(self, state: float, value: float) -> float:
        """Fold `value` into `state` with `combine`."""
        return self.combine(state, value)

    @override
    def merge(self, a: float, b: float) -> float:
        """Combine two accumulated scalars with `combine`."""
        return self.combine(a, b)

    @override
    def result(self, state: float) -> float:
        """Return the accumulated scalar, applying `finalize` if set."""
        return state if self.finalize is None else self.finalize(state)


# ========================== #
#     Store-all reductions   #
# ========================== #


def _weighted_quantile(
    values: Sequence[float], weights: Sequence[float], q: float
) -> float:
    """Return the smallest value whose cumulative weight reaches `q` of the total.

    A step-function (non-interpolating) weighted quantile: samples are sorted
    by value and their weights accumulated; the result is the first value at
    which the running fraction reaches `q`. For `q=0.5` with equal weights this
    is the lower median, not the mean of the two middle values.

    Args:
        values: The sample values; assumed non-empty and non-NaN (a NaN makes
            the sort order, and hence the result, undefined).
        weights: The matching positive weights, one per value.
        q: The target cumulative-weight fraction, in `[0, 1]`.
    """
    ordered = sorted(zip(values, weights, strict=True))
    cumulative = list(accumulate(weight for _, weight in ordered))
    index = bisect_left(cumulative, q * cumulative[-1])

    return ordered[min(index, len(ordered) - 1)][0]


class StoredReduction(Reduction[list[tuple[float, float]]], ABC):
    """A reduction that keeps every `(value, weight)` pair; empty -> `nan`.

    The escape hatch for non-decomposable statistics (medians, quantiles) that
    no online fold can express -- `result` reduces the full gathered sample.
    This costs **O(n) memory**, breaking the module's constant-memory contract,
    so reach for it only when no decomposable reduction expresses the statistic.
    Unlike every other reduction the state is a mutable list, so an
    `Aggregator.state()` snapshot shares it and keeps changing under further
    updates. Subclasses reduce the gathered samples in `_reduce`.

    `merge` copies both operands, so it is O(n) in the combined sample count;
    merging many partials into one incrementally (`run.merge(ep)` each epoch)
    is therefore quadratic in the total -- another reason to prefer a
    decomposable reduction when one exists.
    """

    @override
    def identity(self) -> list[tuple[float, float]]:
        """Return a fresh empty sample list."""
        return []

    @override
    def step(
        self, state: list[tuple[float, float]], value: float, weight: float
    ) -> list[tuple[float, float]]:
        """Append the `(value, weight)` sample to the list, in place."""
        state.append((value, weight))
        return state

    @override
    def merge(
        self, a: list[tuple[float, float]], b: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        """Concatenate two sample lists into a new one."""
        return [*a, *b]

    @override
    def result(self, state: list[tuple[float, float]]) -> float:
        """Reduce the gathered samples via `_reduce`, or `nan` if there are none."""
        if not state:
            return float("nan")

        values = [value for value, _ in state]
        weights = [weight for _, weight in state]
        return self._reduce(values, weights)

    @abstractmethod
    def _reduce(self, values: Sequence[float], weights: Sequence[float]) -> float:
        """Reduce the gathered samples to the final scalar; called non-empty."""


@dataclass(frozen=True)
class Stored(StoredReduction):
    """A store-all reduction with a pluggable `reduce` callable; empty -> `nan`.

    Attributes:
        reduce: Applied to the full gathered samples (both non-empty) -- e.g.
            `Stored(lambda v, w: statistics.median(v))`. Because
            `Aggregator.merge` compares reductions by value, pass a stable
            callable (a module-level function), not a fresh lambda per
            instance, when you rely on that equality.
    """

    reduce: Callable[[Sequence[float], Sequence[float]], float]

    @override
    def _reduce(self, values: Sequence[float], weights: Sequence[float]) -> float:
        """Apply the stored `reduce` callable to the gathered samples."""
        return self.reduce(values, weights)


@dataclass(frozen=True)
class Quantile(StoredReduction):
    """The weighted `q`-quantile of the stream; empty -> `nan`.

    Non-interpolating -- the smallest value whose cumulative weight reaches
    `q` of the total.

    Attributes:
        q: The target quantile, in `[0, 1]`.
    """

    q: float

    def __post_init__(self) -> None:
        """Validate `q`.

        Raises:
            ValueError: If `q` is outside `[0, 1]`.
        """
        if not 0.0 <= self.q <= 1.0:
            msg = f"q must be in [0, 1] (got {self.q})"
            raise ValueError(msg)

    @override
    def _reduce(self, values: Sequence[float], weights: Sequence[float]) -> float:
        """Return the weighted `q`-quantile of the gathered samples."""
        return _weighted_quantile(values, weights, self.q)


@dataclass(frozen=True)
class Median(StoredReduction):
    """The weighted median (the 0.5-quantile) of the stream; empty -> `nan`."""

    @override
    def _reduce(self, values: Sequence[float], weights: Sequence[float]) -> float:
        """Return the weighted median of the gathered samples."""
        return _weighted_quantile(values, weights, 0.5)


# ========================== #
#         Aggregator         #
# ========================== #


class Aggregator:
    """A named collection of online reductions over labelled value streams.

    Each metric name maps to its own `Reduction`; `update` folds a batch of
    named values in, `compute` projects every metric to its scalar. Levels of
    a nested loop compose two ways:

        - `merge` combines another `Aggregator`'s raw states into this one
          (same reduction per metric, sample-weighted) -- e.g. an exact pooled
          mean over every batch of every epoch.
        - `update(child.compute(), weight=...)` feeds a child's *results* back
          as samples, which is how an outer level may use a different reduction
          than its children (e.g. `Min` over epoch means to find the best
          epoch).

    Metrics are created on first sight using the default reduction, unless
    named in `overrides`. Reductions are online, so memory stays constant in
    the number of samples (except store-all reductions; see `StoredReduction`).

    Not thread-safe: guard concurrent `update` / `merge` externally, or give
    each thread its own tracker and `merge` them once joined.

    Attributes:
        weight: Total weight folded in across every `update` and `merge`
            (read-only).

    Example:
        agg = Aggregator(Mean(), overrides={"lr": Last()})
        for batch in loader:
            agg.update({"loss": loss, "lr": lr}, weight=len(batch))
        agg.compute()  # {"loss": <pooled mean>, "lr": <last value>}
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

        # Reduction and accumulator live in parallel dicts (rather than paired
        # in one) so the per-sample hot path rewrites only the state entry.
        self._reductions: dict[str, Reduction[Any]] = {}
        self._states: dict[str, Any] = {}
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

        reductions, states = self._reductions, self._states
        for key, value in values.items():
            reduction = reductions.get(key)
            if reduction is None:
                reduction = self._overrides.get(key, self._default)
                reductions[key] = reduction
                states[key] = reduction.identity()
            states[key] = reduction.step(states[key], value, weight)

        self._weight += weight

    def compute(self) -> dict[str, float]:
        """Project every accumulated metric to its final scalar.

        Recomputed on each call (no caching); a store-all reduction re-reduces
        its whole sample, so call it once and reuse the result rather than in a
        tight loop.
        """
        return {
            key: reduction.result(self._states[key])
            for key, reduction in self._reductions.items()
        }

    def reset(self) -> None:
        """Clear all accumulated state, keeping the reduction configuration."""
        self._reductions.clear()
        self._states.clear()
        self._weight = 0.0

    def state(self) -> dict[str, tuple[Reduction[Any], Any]]:
        """Snapshot each metric's `(reduction, accumulator state)`.

        A shallow copy. Most reduction states are immutable values, so the
        snapshot is safe to keep or restore (for `merge` or checkpointing a
        long run); a store-all reduction (`Stored` and friends) instead
        accumulates a mutable list, whose snapshotted state changes under
        further updates -- deep-copy it if you need a stable one.
        """
        return {
            key: (reduction, self._states[key])
            for key, reduction in self._reductions.items()
        }

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
        if other is self:
            return

        for key, reduction in other._reductions.items():
            other_state = other._states[key]
            own_reduction = self._reductions.get(key)
            if own_reduction is None:
                # Adopt through the monoid identity so we copy `other`'s state
                # instead of aliasing it: a store-all list would otherwise be
                # shared, and a later `update` would mutate `other` too.
                self._reductions[key] = reduction
                self._states[key] = reduction.merge(reduction.identity(), other_state)
                continue
            if own_reduction != reduction:
                msg = (
                    f"cannot merge metric {key!r}: reductions differ "
                    f"({own_reduction} vs {reduction})"
                )
                raise ValueError(msg)
            self._states[key] = own_reduction.merge(self._states[key], other_state)

        self._weight += other.weight

    def fresh(self) -> Aggregator:
        """Build a new empty `Aggregator` with the same reduction config."""
        return Aggregator(self._default, overrides=self._overrides)

    @property
    def weight(self) -> float:
        """Total weight folded in across every `update` (and absorbed via `merge`).

        A grand total over every call, independent of which metric keys each
        call carried -- so when updates have heterogeneous key sets it need
        not equal any single metric's effective weight. A weighted reduction
        already tracks its own per-metric weight inside its state (`Mean`'s
        `total_weight`, `Var` / `Std`'s `weight`); unweighted reductions
        (`Sum`, `Min`, `Max`, `Last`) discard weight entirely.
        """
        return self._weight
