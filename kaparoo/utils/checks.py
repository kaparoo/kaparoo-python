"""Small validation guards: check a value against a set of options or a range."""

from __future__ import annotations

__all__ = ("ensure_in_range", "ensure_one_of")

import math
from typing import TYPE_CHECKING

from kaparoo.utils.optional import replace_if_none

if TYPE_CHECKING:
    from collections.abc import Collection


def ensure_one_of[T](value: T, options: Collection[T], *, name: str = "value") -> T:
    """Return `value` if it is one of `options`, else raise `ValueError`.

    For a discrete integer grid, pass a `range` (e.g. `range(0, 10, 2)`):
    membership is exact and O(1). For a continuous bound, use `ensure_in_range`.

    Raises:
        ValueError: If `value` is not one of `options`.
    """
    if value not in options:
        try:
            shown = sorted(options)
        except TypeError:  # `options` mixes unorderable types
            shown = list(options)
        msg = f"{name} must be one of {shown} (got {value!r})"
        raise ValueError(msg)

    return value


def ensure_in_range[T: (int, float)](
    value: T,
    *,
    lower: float | None = None,
    upper: float | None = None,
    step: float | None = None,
    inclusive: bool | tuple[bool, bool] = True,
    name: str = "value",
) -> T:
    """Return `value` if it lies within the `lower` / `upper` bounds, else raise.

    Either bound may be `None` for no limit on that side (a half-open range);
    `inclusive` selects `<=` (`True`) or `<` (`False`) per side. With `step`,
    `value` must also fall on the grid `base + k * step` (integer `k`), where
    `base` is `lower` (or `0` when `lower` is `None`); that check goes through
    `math.isclose`, so it tolerates float rounding (e.g. `0.3` on a `0.1`
    grid). Works for `int` and `float` alike.

    Args:
        value: The number to check.
        lower: Lower bound, or `None` for no lower bound.
        upper: Upper bound, or `None` for no upper bound.
        step: Grid spacing `value` must align to, anchored at `lower` (or `0`),
            or `None` to allow any value. Must be positive.
        inclusive: Whether the bounds are inclusive. A single `bool` applies to
            both sides; a `(lower, upper)` tuple sets each. Defaults to `True`.
        name: The value's name for the error message. Defaults to `"value"`.

    Raises:
        ValueError: If `step` is not positive, or `value` falls outside the
            bounds or off the `step` grid.
    """
    if step is not None and step <= 0:
        msg = f"step must be positive (got {step})"
        raise ValueError(msg)

    if isinstance(inclusive, bool):
        inclusive = (inclusive, inclusive)

    lower_inclusive, upper_inclusive = inclusive

    lower = replace_if_none(lower, float("-inf"))
    upper = replace_if_none(upper, float("inf"))

    too_low = value < lower if lower_inclusive else value <= lower
    too_high = value > upper if upper_inclusive else value >= upper

    if too_low or too_high:
        left = "[" if lower_inclusive and lower != float("-inf") else "("
        right = "]" if upper_inclusive and upper != float("inf") else ")"
        msg = f"{name} must be in {left}{lower}, {upper}{right} (got {value!r})"
        raise ValueError(msg)

    if step is not None:
        base = lower if lower != float("-inf") else 0
        nearest = base + round((value - base) / step) * step
        # `isclose` defaults to `abs_tol=0.0`, which rejects any grid line that
        # lands on zero; scale the absolute tolerance to `step` so a near-zero
        # grid point still matches.
        if not math.isclose(nearest, value, abs_tol=abs(step) * 1e-9):
            msg = f"{name} must lie on the grid {base} + k*{step} (got {value!r})"
            raise ValueError(msg)

    return value
