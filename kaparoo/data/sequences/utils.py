from __future__ import annotations

__all__ = ("generate_batches",)

from typing import TYPE_CHECKING

from kaparoo.utils.optional import replace_if_none

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
    """Yield sliding windows from `sequence`.

    Each yielded batch is `sequence[head : tail : skip]` where `head`
    advances by `step` per iteration. With the defaults (`size=3,
    step=1, skip=1, drop_last=True`), this produces overlapping
    consecutive-frame windows; pair this with a non-overlapping `step
    >= size` for a classic non-overlapping batch loader.

    Traversal is constrained to the index range `[start, stop)`.
    `stop=None` defaults to `len(sequence)`. An empty range (`start ==
    stop`) yields nothing -- the function returns without error.

    Args:
        sequence: The sequence to slide windows over.
        size: Number of items per window. Must be positive.
        step: Position advance between consecutive windows. Defaults
            to 1 (overlapping windows by `size - 1`).
        skip: Intra-window stride. Defaults to 1 (consecutive items).
        start: Inclusive lower bound on source indices. Defaults to 0.
            Must satisfy `0 <= start <= stop`.
        stop: Exclusive upper bound on source indices. Defaults to
            `len(sequence)`. The partial window (when `drop_last=False`)
            respects `stop` and never extends past it.
        drop_last: If False, yield a final partial (possibly shorter
            than `size`) window when items remain after the last full
            window. Defaults to True.

    Yields:
        Sub-sequences of `sequence` obtained by slicing.

    Raises:
        ValueError: If `size`, `step`, or `skip` is non-positive, or
            if the range is not `0 <= start <= stop <= len(sequence)`.
    """
    if size <= 0 or step <= 0 or skip <= 0:
        msg = (
            f"size, step, skip must be positive "
            f"(got size={size}, step={step}, skip={skip})"
        )
        raise ValueError(msg)

    length = len(sequence)
    stop = replace_if_none(stop, length)
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
