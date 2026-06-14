"""Small validation guards: check a value against a set of options or a range."""

from __future__ import annotations

__all__ = ("ensure_in_range", "ensure_literal")

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
    min_: float | None = None,
    max_: float | None = None,
    inclusive: tuple[bool, bool] = (True, True),
    name: str,
) -> T:
    """Return `value` if it lies within the `min_` / `max_` bounds, else raise.

    Either bound may be `None` for no limit on that side (a half-open range);
    `inclusive` selects `<=` (`True`) or `<` (`False`) per side. Works for `int`
    and `float` alike. For a discrete integer grid, use `ensure_literal` with a
    `range` instead.

    Args:
        value: The number to check.
        min_: Lower bound, or `None` for no lower bound.
        max_: Upper bound, or `None` for no upper bound.
        inclusive: Whether the `(min_, max_)` bounds are inclusive. Defaults to
            inclusive on both sides.
        name: The value's name, used in the error message.

    Raises:
        ValueError: If `value` falls outside the bounds.
    """
    min_inclusive, max_inclusive = inclusive

    below = min_ is not None and (value < min_ if min_inclusive else value <= min_)
    above = max_ is not None and (value > max_ if max_inclusive else value >= max_)

    if below or above:
        left = "[" if min_inclusive and min_ is not None else "("
        right = "]" if max_inclusive and max_ is not None else ")"
        low = "-inf" if min_ is None else min_
        high = "inf" if max_ is None else max_
        msg = f"{name} must be in {left}{low}, {high}{right} (got {value!r})"
        raise ValueError(msg)

    return value
