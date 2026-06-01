from __future__ import annotations

import math
import operator
from dataclasses import dataclass

import pytest

from kaparoo.utils.aggregate import (
    Aggregator,
    Fold,
    Last,
    Max,
    Mean,
    Min,
    Reduction,
    Sum,
)

# --- Reductions: direct unit tests ------------------------------------------


def test_mean_weighted():
    m = Mean()
    s = m.identity()
    s = m.step(s, 2.0, 3.0)  # (6, 3)
    s = m.step(s, 4.0, 1.0)  # (10, 4)
    assert m.result(s) == 2.5


def test_mean_empty_is_nan():
    m = Mean()
    assert math.isnan(m.result(m.identity()))


def test_mean_merge_matches_flat():
    m = Mean()
    a = m.step(m.identity(), 1.0, 2.0)  # (2, 2)
    b = m.step(m.identity(), 3.0, 1.0)  # (3, 1)
    assert m.result(m.merge(a, b)) == (2.0 + 3.0) / (2.0 + 1.0)


def test_sum_ignores_weight_and_empty_is_zero():
    s = Sum()
    assert s.result(s.identity()) == 0.0
    state = s.accumulate(s.identity(), 2.0)
    state = s.accumulate(state, 3.0)
    assert s.result(state) == 5.0
    assert s.merge(2.0, 3.0) == 5.0


def test_min_merge_branches_and_empty():
    m = Min()
    assert math.isnan(m.result(m.identity()))  # empty -> nan
    assert m.merge(None, 3.0) == 3.0  # a is identity
    assert m.merge(3.0, None) == 3.0  # b is identity
    assert m.merge(3.0, 1.0) == 1.0  # both present
    assert m.accumulate(None, 5.0) == 5.0
    assert m.accumulate(5.0, 2.0) == 2.0


def test_max_merge_branches_and_empty():
    m = Max()
    assert math.isnan(m.result(m.identity()))
    assert m.merge(None, 3.0) == 3.0
    assert m.merge(3.0, None) == 3.0
    assert m.merge(3.0, 7.0) == 7.0
    assert m.accumulate(None, 5.0) == 5.0
    assert m.accumulate(5.0, 9.0) == 9.0


def test_last_keeps_latest_and_merge():
    last = Last()
    assert math.isnan(last.result(last.identity()))
    s = last.accumulate(last.identity(), 1.0)
    s = last.accumulate(s, 2.0)
    assert last.result(s) == 2.0
    assert last.merge(1.0, 2.0) == 2.0  # right (later) wins
    assert last.merge(1.0, None) == 1.0  # b is identity -> a


def test_fold_product():
    agg = Aggregator(Fold(operator.mul, 1.0))
    for v in (2.0, 3.0, 4.0):
        agg.update({"x": v})
    assert agg.compute()["x"] == 24.0


def test_fold_finalize_and_merge():
    f = Fold(operator.add, 0.0, finalize=lambda s: s * 2)
    s = f.accumulate(f.identity(), 5.0)
    assert f.result(s) == 10.0
    g = Fold(min, float("inf"))
    assert g.merge(3.0, 1.0) == 1.0
    assert g.result(g.identity()) == float("inf")  # no finalize -> raw state


# --- Aggregator -------------------------------------------------------------


def test_default_reduction_is_mean():
    agg = Aggregator()
    agg.update({"x": 1.0})
    agg.update({"x": 3.0})
    assert agg.compute()["x"] == 2.0


def test_compute_empty_aggregator():
    assert Aggregator().compute() == {}


def test_weighted_mean_via_aggregator():
    agg = Aggregator(Mean())
    agg.update({"loss": 1.0}, weight=3)
    agg.update({"loss": 2.0}, weight=1)
    assert agg.compute()["loss"] == (3 * 1.0 + 1 * 2.0) / 4
    assert agg.weight == 4.0


def test_sum_via_aggregator_drops_weight():
    agg = Aggregator(Sum())
    agg.update({"x": 2.0}, weight=10)
    agg.update({"x": 3.0}, weight=10)
    assert agg.compute()["x"] == 5.0  # weight ignored by Sum


def test_overrides_and_dynamic_keys():
    agg = Aggregator(Mean(), overrides={"lr": Last(), "grad": Max()})
    agg.update({"loss": 1.0, "lr": 0.1, "grad": 0.5}, weight=2)
    agg.update({"loss": 3.0, "lr": 0.05, "grad": 0.9}, weight=2)
    r = agg.compute()
    assert r["loss"] == 2.0  # Mean default
    assert r["lr"] == 0.05  # Last override
    assert r["grad"] == 0.9  # Max override


def test_update_nonpositive_weight_raises():
    with pytest.raises(ValueError, match="weight must be positive"):
        Aggregator().update({"x": 1.0}, weight=0)


def test_reset_clears_state():
    agg = Aggregator(Mean())
    agg.update({"x": 1.0}, weight=2)
    agg.reset()
    assert agg.compute() == {}
    assert agg.weight == 0.0


def test_state_snapshot():
    agg = Aggregator(Mean())
    agg.update({"x": 2.0}, weight=1)
    reduction, state = agg.state()["x"]
    assert isinstance(reduction, Mean)
    assert reduction.result(state) == 2.0


def test_fresh_preserves_config():
    agg = Aggregator(Max(), overrides={"avg": Mean()})
    fresh = agg.fresh()
    assert fresh.compute() == {}
    fresh.update({"m": 1.0, "avg": 1.0})
    fresh.update({"m": 5.0, "avg": 3.0})
    r = fresh.compute()
    assert r["m"] == 5.0  # Max default preserved
    assert r["avg"] == 2.0  # Mean override preserved


def test_merge_shared_key_is_sample_weighted():
    a = Aggregator(Mean())
    a.update({"x": 1.0}, weight=2)
    b = Aggregator(Mean())
    b.update({"x": 4.0}, weight=1)
    a.merge(b)
    assert a.compute()["x"] == (2 * 1.0 + 1 * 4.0) / 3
    assert a.weight == 3.0


def test_merge_adopts_new_key():
    a = Aggregator(Mean())
    a.update({"x": 1.0})
    b = Aggregator(Mean())
    b.update({"y": 2.0})
    a.merge(b)
    assert set(a.compute()) == {"x", "y"}


def test_merge_incompatible_reductions_raise():
    a = Aggregator(Mean())
    a.update({"x": 1.0})
    b = Aggregator(Max())
    b.update({"x": 2.0})
    with pytest.raises(ValueError, match="reductions differ"):
        a.merge(b)


# --- Nested-loop scenarios --------------------------------------------------


def test_weighted_nesting_matches_flat_aggregation():
    # epochs of (loss, batch_size); last batch of each epoch is smaller
    epochs = [[(1.0, 32), (2.0, 11)], [(3.0, 32), (4.0, 16)]]
    run = Aggregator(Mean())
    for epoch in epochs:
        ep = run.fresh()
        for loss, n in epoch:
            ep.update({"loss": loss}, weight=n)
        run.merge(ep)
    flat = sum(loss * n for ep in epochs for (loss, n) in ep) / sum(
        n for ep in epochs for (_, n) in ep
    )
    assert run.compute()["loss"] == pytest.approx(flat)


def test_different_reduction_per_level_best_epoch():
    run = Aggregator(Min())  # outer level: min over epoch means
    for epoch_vals in ([1.0, 3.0], [0.5, 0.5], [2.0, 2.0]):
        ep = Aggregator(Mean())
        for v in epoch_vals:
            ep.update({"loss": v})
        run.update(ep.compute(), weight=1)
    assert run.compute()["loss"] == 0.5  # the best (lowest) epoch mean


@dataclass(frozen=True)
class _RMS(Reduction[tuple[float, float]]):
    """A user-defined weighted reduction, to exercise the extension path."""

    def identity(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def step(
        self, state: tuple[float, float], value: float, weight: float
    ) -> tuple[float, float]:
        return (state[0] + weight * value * value, state[1] + weight)

    def merge(
        self, a: tuple[float, float], b: tuple[float, float]
    ) -> tuple[float, float]:
        return (a[0] + b[0], a[1] + b[1])

    def result(self, state: tuple[float, float]) -> float:
        return (state[0] / state[1]) ** 0.5 if state[1] else float("nan")


def test_custom_reduction_subclass_nests_correctly():
    epochs = [[(1.0, 2), (3.0, 1)], [(2.0, 1)]]
    run = Aggregator(_RMS())
    for epoch in epochs:
        ep = run.fresh()
        for value, n in epoch:
            ep.update({"x": value}, weight=n)
        run.merge(ep)
    flat = (
        sum(v * v * n for ep in epochs for (v, n) in ep)
        / sum(n for ep in epochs for (_, n) in ep)
    ) ** 0.5
    assert run.compute()["x"] == pytest.approx(flat)
