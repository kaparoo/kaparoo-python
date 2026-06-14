from __future__ import annotations

import pytest

from kaparoo.utils.checks import ensure_in_range, ensure_literal

# --- ensure_literal ---------------------------------------------------------


def test_ensure_literal_returns_value_when_allowed():
    assert ensure_literal("ms", ("s", "ms", "us"), name="unit") == "ms"


def test_ensure_literal_raises_when_not_allowed():
    with pytest.raises(ValueError, match=r"unit must be one of .* \(got 'x'\)"):
        ensure_literal("x", ("s", "ms"), name="unit")


def test_ensure_literal_accepts_range_for_integer_grid():
    assert ensure_literal(4, range(0, 10, 2), name="index") == 4
    with pytest.raises(ValueError, match="index must be one of"):
        ensure_literal(3, range(0, 10, 2), name="index")


def test_ensure_literal_message_is_sorted_when_orderable():
    with pytest.raises(ValueError, match=r"\['a', 'b'\]"):
        ensure_literal("z", {"b", "a"}, name="x")


def test_ensure_literal_falls_back_when_unorderable():
    # `sorted` raises TypeError on mixed types; the message still lists them.
    with pytest.raises(ValueError, match="must be one of"):
        ensure_literal(object(), {1, "a"}, name="x")


# --- ensure_in_range --------------------------------------------------------


def test_ensure_in_range_within_inclusive_bounds():
    assert ensure_in_range(0.5, min_=0.0, max_=1.0, name="q") == 0.5
    assert ensure_in_range(0.0, min_=0.0, max_=1.0, name="q") == 0.0  # lower edge
    assert ensure_in_range(1.0, min_=0.0, max_=1.0, name="q") == 1.0  # upper edge


def test_ensure_in_range_accepts_int_value():
    assert ensure_in_range(5, min_=1, max_=10, name="n") == 5


def test_ensure_in_range_below_min_raises():
    with pytest.raises(ValueError, match=r"q must be in \[0.0, 1.0\] \(got -0.1\)"):
        ensure_in_range(-0.1, min_=0.0, max_=1.0, name="q")


def test_ensure_in_range_above_max_raises():
    with pytest.raises(ValueError, match=r"q must be in \[0.0, 1.0\] \(got 1.5\)"):
        ensure_in_range(1.5, min_=0.0, max_=1.0, name="q")


def test_ensure_in_range_exclusive_lower_rejects_the_bound():
    # (0, inf): a positive value passes; exactly 0 is rejected.
    assert ensure_in_range(0.5, min_=0.0, inclusive=(False, True), name="w") == 0.5
    with pytest.raises(ValueError, match=r"w must be in \(0.0, inf\) \(got 0.0\)"):
        ensure_in_range(0.0, min_=0.0, inclusive=(False, True), name="w")


def test_ensure_in_range_exclusive_upper_rejects_the_bound():
    with pytest.raises(ValueError, match=r"i must be in \[0, 10\) \(got 10\)"):
        ensure_in_range(10, min_=0, max_=10, inclusive=(True, False), name="i")


def test_ensure_in_range_half_bounded_uses_open_infinity_bracket():
    # No lower bound -> "(-inf, ...".
    with pytest.raises(ValueError, match=r"x must be in \(-inf, 5\] \(got 6\)"):
        ensure_in_range(6, max_=5, name="x")


def test_ensure_in_range_no_bounds_is_a_noop():
    assert ensure_in_range(123.0, name="x") == 123.0


def test_ensure_in_range_step_on_grid_passes():
    assert ensure_in_range(4, min_=0, max_=10, step=2, name="n") == 4
    # 0.3 on a 0.1 grid: a modulo check would fail, round + isclose passes.
    assert ensure_in_range(0.3, min_=0.0, max_=1.0, step=0.1, name="q") == 0.3
    assert ensure_in_range(0.7, min_=0.0, max_=1.0, step=0.1, name="q") == 0.7


def test_ensure_in_range_step_off_grid_raises():
    with pytest.raises(ValueError, match=r"n must lie on the grid 0 \+ k\*2 \(got 3\)"):
        ensure_in_range(3, min_=0, max_=10, step=2, name="n")


def test_ensure_in_range_step_anchored_at_min():
    assert ensure_in_range(3, min_=1, step=2, name="n") == 3  # grid 1, 3, 5, ...
    with pytest.raises(ValueError, match=r"grid 1 \+ k\*2"):
        ensure_in_range(4, min_=1, step=2, name="n")


def test_ensure_in_range_step_anchored_at_zero_without_min():
    assert ensure_in_range(6, step=3, name="n") == 6
    with pytest.raises(ValueError, match=r"grid 0 \+ k\*3"):
        ensure_in_range(7, step=3, name="n")


def test_ensure_in_range_step_grid_point_at_zero():
    # A grid line landing on zero must still match -- `math.isclose`'s default
    # `abs_tol=0.0` would reject it, so the absolute tolerance scales to `step`.
    assert ensure_in_range(0.0, min_=-0.3, step=0.1, name="x") == 0.0


def test_ensure_in_range_step_must_be_positive():
    with pytest.raises(ValueError, match="step must be positive"):
        ensure_in_range(1.0, step=0, name="x")
    with pytest.raises(ValueError, match="step must be positive"):
        ensure_in_range(1.0, step=-1, name="x")
