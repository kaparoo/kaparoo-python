from __future__ import annotations

__all__ = ("generate_batches",)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


def generate_batches[T](
    sequence: Sequence[T],
    size: int,
    *,
    step: int = 1,
    skip: int = 1,
    start: int = 0,
    stop: int | None = None,
    drop_last: bool = True,
) -> Iterator[Sequence[T]]:
    """Yield sliding windows from `sequence`, each a slice of `size` items.

    The window advances by `step` and strides by `skip` within itself. The
    default `step`/`skip` of 1/1 gives overlapping consecutive-item windows;
    `step >= size` gives non-overlapping batches. Traversal is confined to
    `[start, stop)` (`stop=None` means the full length); an empty range yields
    nothing.

    Args:
        size: Items per window. Must be positive.
        step: Advance between windows. Defaults to 1 (overlap by `size - 1`).
        skip: Intra-window stride. Defaults to 1 (consecutive items).
        start: Inclusive lower bound on source indices. Defaults to 0.
        stop: Exclusive upper bound. Defaults to `len(sequence)`; a partial
            window (with `drop_last=False`) never extends past it.
        drop_last: If False, yield a final shorter window for leftover items.
            Defaults to True.

    Yields:
        Sub-sequences of `sequence`.

    Raises:
        ValueError: If `size`, `step`, or `skip` is non-positive, or the range
            is not `0 <= start <= stop <= len(sequence)`.
    """
    if size <= 0 or step <= 0 or skip <= 0:
        msg = f"size, step, skip must be positive (got {size=}, {step=}, {skip=})"
        raise ValueError(msg)

    length = len(sequence)
    stop = stop if stop is not None else length
    if not 0 <= start <= stop <= length:
        msg = f"invalid range [{start}, {stop}) for sequence of length {length}"
        raise ValueError(msg)

    head = start
    tail = head + (size - 1) * skip + 1

    while tail <= stop:
        yield sequence[head:tail:skip]
        head += step
        tail += step

    # Final partial window must respect `stop` (not `tail`, which has
    # advanced past `stop` by the time we get here).
    if not drop_last and head < stop:
        yield sequence[head:stop:skip]
