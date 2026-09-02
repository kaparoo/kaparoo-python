"""Small text helpers."""

from __future__ import annotations

__all__ = ("quantify", "strrange")

from typing import overload


def quantify(count: int, noun: str, plural: str | None = None) -> str:
    """Return `count` followed by `noun`, pluralized for every count but one.

    Args:
        count: How many there are.
        noun: The singular form.
        plural: The form for every count but one, or `None` to append `"s"` to
            `noun`. Since it is the whole word, it also covers an irregular
            plural a suffix cannot (a stem change or a replacement).
    """
    if count == 1:
        return f"{count} {noun}"

    word = plural if plural is not None else f"{noun}s"
    return f"{count} {word}"


@overload
def strrange(stop: int, /, *, template: str = ...) -> tuple[str, ...]: ...


@overload
def strrange(
    start: int, stop: int, step: int = ..., /, *, template: str = ...
) -> tuple[str, ...]: ...


@overload
def strrange(values: range, /, *, template: str = ...) -> tuple[str, ...]: ...


def strrange(
    start: int | range,
    stop: int | None = None,
    step: int = 1,
    /,
    *,
    template: str = "{}",
) -> tuple[str, ...]:
    """Format a range of integers, as `range` takes them, into strings.

    The positional arguments are `range`'s own -- one `stop`, a `start` and
    `stop`, or those with a `step` -- and an existing `range` is accepted in
    their place, so a range read from configuration needs no unpacking.

    `template` is a `str.format` string with one positional field, so it
    carries both the number's spelling and whatever surrounds it:
    `"{:03d}"` zero-pads to three digits, `"shard_{:03d}"` names a series.
    For a pattern that also *matches* the names it stands for, rather than a
    plain tuple of them, reach for `kaparoo.filters.Template` instead.

    Args:
        start: The range's `stop` when it is the only argument, its `start`
            otherwise; or the whole `range`, given one.
        stop: The range's exclusive end, when `start` is its beginning.
        step: The stride between values. Defaults to 1.
        template: Applied to each value as `template.format(value)`. Defaults
            to `"{}"`, which renders as `str` does.

    Returns:
        One string per value, in the range's own order. Empty when the range
        is -- the one case a broken `template` goes unreported, since nothing
        is ever formatted through it.

    Raises:
        TypeError: If a `range` is given alongside `stop` or `step`.
        ValueError: If `step` is zero, or `template`'s format spec does not
            apply to an integer.
        IndexError: If `template` has more fields than the one value.
        KeyError: If `template` has a named field.

    Example:
        ```python
        strrange(3)  # ('0', '1', '2')
        strrange(8, template="{:03d}")  # ('000', '001', ..., '007')
        strrange(1, 4)  # ('1', '2', '3')
        strrange(0, 10, 2, template="{:02d}")  # ('00', '02', ..., '08')
        strrange(3, template="cam_{}")  # ('cam_0', 'cam_1', 'cam_2')
        strrange(range(2, 5))  # ('2', '3', '4')
        ```
    """
    if isinstance(start, range):
        if stop is not None or step != 1:
            msg = "strrange takes a range alone, not with a stop or step"
            raise TypeError(msg)
        values = start
    elif stop is None:
        values = range(start)
    else:
        values = range(start, stop, step)

    return tuple(template.format(value) for value in values)
