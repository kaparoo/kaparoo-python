from __future__ import annotations

__all__ = ("generate_batches",)

from typing import TYPE_CHECKING

from kaparoo.utils.optional import replace_if_none

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from typing import Any

    from kaparoo.utils.types import T_co


def generate_batches(
    sequence: Sequence[T_co],
    size: int,
    step: int = 1,
    skip: int = 1,
    start: int = 0,
    stop: int | None = None,
    *,
    drop_last: bool = True,
) -> Generator[Sequence[T_co], Any, None]:
    def die_if_not_positive(var: int, name: str) -> None:
        if var <= 0:
            raise ValueError(f"{name} must be positive (got {var})")

    die_if_not_positive(size, "size")
    die_if_not_positive(step, "step")
    die_if_not_positive(skip, "skip")

    stop = replace_if_none(stop, len_ := len(sequence))
    if not (start < stop <= len_ and start >= 0):
        raise ValueError(
            f"invalid range [{start}, {stop}) for sequence of length {len_}"
        )

    head = start
    tail = head + (size - 1) * skip + 1

    while tail <= stop:
        yield sequence[head:tail:skip]
        head += step
        tail += step

    if not drop_last and head < stop:
        yield sequence[head:tail:skip]
