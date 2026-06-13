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
    Median,
    Min,
    OptionalFold,
    Quantile,
    Reduction,
    Std,
    Stored,
    Sum,
    Var,
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


def _accumulate(reduction: Reduction[object], values: list[float]) -> object:
    state = reduction.identity()
    for v in values:
        state = reduction.step(state, v, 1.0)
    return state


def _accumulate_weighted(
    reduction: Reduction[object], pairs: list[tuple[float, float]]
) -> object:
    state = reduction.identity()
    for value, weight in pairs:
        state = reduction.step(state, value, weight)
    return state


# --- Store-all reductions (Stored / Median / Quantile) ----------------------


def test_optional_fold_is_abstract():
    with pytest.raises(TypeError):
        OptionalFold()  # abstract `_combine`


def test_median_lower_for_even_count():
    assert Median().result(_accumulate(Median(), [1.0, 2.0, 3.0])) == 2.0
    # even count: the lower median, not the 2.5 interpolation
    assert Median().result(_accumulate(Median(), [1.0, 2.0, 3.0, 4.0])) == 2.0


def test_median_weighted():
    med = Median()
    # 10 carries weight 3 of the total 4, so it holds the 0.5 mark
    state = _accumulate_weighted(med, [(10.0, 3.0), (20.0, 1.0)])
    assert med.result(state) == 10.0


def test_median_empty_is_nan():
    assert math.isnan(Median().result(Median().identity()))


def test_median_merge_concatenates():
    med = Median()
    a = _accumulate(med, [1.0])
    b = _accumulate(med, [3.0, 5.0])
    assert med.result(med.merge(a, b)) == 3.0  # median(1, 3, 5)


def test_quantile_endpoints_are_min_and_max():
    q0, q1 = Quantile(0.0), Quantile(1.0)
    assert q0.result(_accumulate(q0, [5.0, 1.0, 3.0])) == 1.0
    assert q1.result(_accumulate(q1, [5.0, 1.0, 3.0])) == 5.0


def test_quantile_half_equals_median():
    values = [4.0, 2.0, 8.0, 6.0, 1.0]
    q = Quantile(0.5)
    assert q.result(_accumulate(q, values)) == Median().result(
        _accumulate(Median(), values)
    )


def test_quantile_out_of_range_raises():
    with pytest.raises(ValueError, match=r"q must be in \[0, 1\]"):
        Quantile(1.5)
    with pytest.raises(ValueError, match="q must be in"):
        Quantile(-0.1)


def test_stored_with_custom_reduce_and_empty():
    s = Stored(lambda values, weights: sum(values) / len(values))
    assert s.result(_accumulate(s, [2.0, 4.0, 6.0])) == 4.0
    assert math.isnan(s.result(s.identity()))


def test_stored_merge_concatenates():
    s = Stored(lambda values, _weights: max(values))
    a = _accumulate(s, [1.0, 2.0])
    b = _accumulate(s, [9.0])
    assert s.result(s.merge(a, b)) == 9.0


def test_store_all_value_equality():
    assert Stored(max) == Stored(max)  # a stable callable -> equal
    assert Median() == Median()
    assert Quantile(0.9) == Quantile(0.9)
    assert Quantile(0.9) != Quantile(0.5)


def test_stored_fresh_lambdas_block_merge():
    # Documented footgun: a fresh lambda per instance compares unequal, so two
    # such Stored reductions cannot merge -- use a module-level callable to rely
    # on merge.
    a = Aggregator(Stored(lambda v, w: max(v)))
    a.update({"x": 1.0})
    b = Aggregator(Stored(lambda v, w: max(v)))
    b.update({"x": 2.0})
    with pytest.raises(ValueError, match="reductions differ"):
        a.merge(b)


def test_stored_state_is_mutable_in_place():
    # documented exception to the immutable-state contract: `step` appends
    med = Median()
    state = med.identity()
    assert med.step(state, 1.0, 1.0) is state  # same list, mutated in place
    assert state == [(1.0, 1.0)]


def test_aggregate_names_reexported_from_package():
    from kaparoo import utils

    assert utils.Aggregator is Aggregator
    assert utils.Median is Median
    assert utils.OptionalFold is OptionalFold
    assert utils.Quantile is Quantile
    assert utils.Stored is Stored


def test_store_all_via_aggregator():
    agg = Aggregator(Median())
    for x in (4.0, 2.0, 8.0, 6.0):
        agg.update({"loss": x})
    assert agg.compute()["loss"] == 4.0  # lower median of (2, 4, 6, 8)


def test_var_population_value():
    # Classic dataset: mean 5, population variance 4 (sum of sq. dev. 32 / 8).
    var = Var()
    assert var.result(_accumulate(var, [2, 4, 4, 4, 5, 5, 7, 9])) == 4.0


def test_var_empty_is_nan():
    var = Var()
    assert math.isnan(var.result(var.identity()))


def test_var_merge_matches_flat():
    # Splitting the stream and merging the partial moments must equal the
    # variance of the whole stream (Chan's parallel algorithm).
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    var = Var()
    left = _accumulate(var, data[:3])
    right = _accumulate(var, data[3:])
    assert var.result(var.merge(left, right)) == pytest.approx(
        var.result(_accumulate(var, data))
    )


def test_var_merge_of_empties_is_empty():
    var = Var()
    assert var.merge(var.identity(), var.identity()) == var.identity()


def test_var_merge_with_one_empty_side():
    # Merging an empty partial with a populated one yields the populated one.
    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    var = Var()
    populated = _accumulate(var, data)
    assert var.merge(var.identity(), populated) == pytest.approx(populated)
    assert var.merge(populated, var.identity()) == pytest.approx(populated)


def test_var_numerically_stable_under_large_offset():
    # The whole point of Welford over naive sum-of-squares: a tiny spread
    # riding on a huge mean must not lose precision.
    var = Var()
    shifted = [1e9 + 1.0, 1e9 + 2.0, 1e9 + 3.0]
    assert var.result(_accumulate(var, shifted)) == pytest.approx(2.0 / 3.0)
    assert Std().result(_accumulate(Std(), shifted)) == pytest.approx(
        (2.0 / 3.0) ** 0.5
    )


def test_var_weight_equals_repetition():
    # A value with weight n must match n unit-weight copies of it.
    var = Var()
    weighted = var.step(var.step(var.identity(), 2.0, 3.0), 8.0, 1.0)
    expanded = _accumulate(var, [2.0, 2.0, 2.0, 8.0])
    assert var.result(weighted) == pytest.approx(var.result(expanded))


def test_std_is_sqrt_of_var():
    std = Std()
    assert std.result(_accumulate(std, [2, 4, 4, 4, 5, 5, 7, 9])) == 2.0  # sqrt(4)


def test_std_empty_is_nan():
    std = Std()
    assert math.isnan(std.result(std.identity()))


def test_std_clamps_negative_variance_from_rounding():
    # Float rounding can drive M2 slightly below zero; without the clamp the
    # square root would return a *complex* number rather than 0.0.
    std = Std()
    result = std.result((4.0, 5.0, -1e-15))  # (total_weight, mean, M2 < 0)
    assert isinstance(result, float)
    assert result == 0.0


def test_var_std_nest_via_aggregator():
    # epoch-level Var, merged into a run-level Var, equals the flat variance.
    epochs = [[(1.0, 2), (3.0, 1)], [(2.0, 1), (5.0, 2)]]
    run = Aggregator(Var())
    for epoch in epochs:
        ep = run.fresh()
        for value, n in epoch:
            ep.update({"x": value}, weight=n)
        run.merge(ep)

    flat = Var()
    flat_state = flat.identity()
    for epoch in epochs:
        for value, n in epoch:
            flat_state = flat.step(flat_state, value, n)
    assert run.compute()["x"] == pytest.approx(flat.result(flat_state))


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


def test_var_single_sample_is_zero():
    # Population convention (ddof=0): one sample has zero variance, not nan.
    var = Var()
    state = var.step(var.identity(), 5.0, 1.0)
    assert var.result(state) == 0.0
    assert Std().result(state) == 0.0


def test_mean_propagates_nan():
    mean = Mean()
    state = mean.step(mean.identity(), float("nan"), 1.0)
    assert math.isnan(mean.result(state))


def test_var_propagates_nan():
    var = Var()
    state = var.step(var.step(var.identity(), 1.0, 1.0), float("nan"), 1.0)
    assert math.isnan(var.result(state))
