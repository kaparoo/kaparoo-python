"""Small validation guards: check a value against a set of options or a range."""

from __future__ import annotations

__all__ = ("ensure_in_range", "ensure_literal")

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


def ensure_literal[T](value: T, allowed: Collection[T], *, name: str) -> T:
    """Return `value` if it is in `allowed`, else raise `ValueError`.

    For a discrete integer grid, pass a `range` (e.g. `range(0, 10, 2)`):
    membership is exact and O(1). For a continuous bound, use `ensure_in_range`.

    Raises:
        ValueError: If `value` is not a member of `allowed`.
    """
    if value not in allowed:
        try:
            shown = sorted(allowed)
        except TypeError:  # `allowed` mixes unorderable types
            shown = list(allowed)
        msg = f"{name} must be one of {shown} (got {value!r})"
        raise ValueError(msg)

    return value


def ensure_in_range[T: (int, float)](
    value: T,
    *,
    lower: float | None = None,
    upper: float | None = None,
    step: float | None = None,
    inclusive: tuple[bool, bool] = (True, True),
    name: str,
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
        inclusive: Whether the `(lower, upper)` bounds are inclusive. Defaults
            to inclusive on both sides.
        name: The value's name, used in the error message.

    Raises:
        ValueError: If `step` is not positive, or `value` falls outside the
            bounds or off the `step` grid.
    """
    if step is not None and step <= 0:
        msg = f"step must be positive (got {step})"
        raise ValueError(msg)

    lower_inclusive, upper_inclusive = inclusive

    too_low = lower is not None and (
        value < lower if lower_inclusive else value <= lower
    )
    too_high = upper is not None and (
        value > upper if upper_inclusive else value >= upper
    )

    if too_low or too_high:
        left = "[" if lower_inclusive and lower is not None else "("
        right = "]" if upper_inclusive and upper is not None else ")"
        low = "-inf" if lower is None else lower
        high = "inf" if upper is None else upper
        msg = f"{name} must be in {left}{low}, {high}{right} (got {value!r})"
        raise ValueError(msg)

    if step is not None:
        base = lower if lower is not None else 0
        nearest = base + round((value - base) / step) * step
        # `isclose` defaults to `abs_tol=0.0`, which rejects any grid line that
        # lands on zero; scale the absolute tolerance to `step` so a near-zero
        # grid point still matches.
        if not math.isclose(nearest, value, abs_tol=abs(step) * 1e-9):
            msg = f"{name} must lie on the grid {base} + k*{step} (got {value!r})"
            raise ValueError(msg)

    return value
