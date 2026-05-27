from __future__ import annotations

from typing import TYPE_CHECKING

from kaparoo.data.sequence import DataSequence, WindowedSequence

if TYPE_CHECKING:
    from collections.abc import Sequence


class ListDataSequence[T, M](DataSequence[T, M]):
    """In-memory `DataSequence` test fixture.

    Both `items` and `metas` must have matching length; pass
    `[None] * len(items)` when the data carries no metadata.
    """

    def __init__(self, items: Sequence[T], metas: Sequence[M]) -> None:
        if len(items) != len(metas):
            msg = (
                f"items and metas must have the same length "
                f"(got {len(items)} items, {len(metas)} metas)"
            )
            raise ValueError(msg)
        self._items = tuple(items)
        self._metas = tuple(metas)

    def __len__(self) -> int:
        return len(self._items)

    def get_item(self, index: int) -> T:
        return self._items[index]

    def get_meta(self, index: int) -> M:
        return self._metas[index]


# --- WindowedSequence concrete subclasses for tests ------------------------


class FirstMetaWindow[T, M](WindowedSequence[T, M, M]):
    """`WindowedSequence` whose meta is the first frame's metadata."""

    def get_meta(self, index: int) -> M:
        index = self._normalize_index(index)
        return self.source.get_meta(index * self.step)


class AllMetasWindow[T, M](WindowedSequence[T, M, tuple[M, ...]]):
    """`WindowedSequence` whose meta is the tuple of all frame metadata."""

    def get_meta(self, index: int) -> tuple[M, ...]:
        index = self._normalize_index(index)
        start = index * self.step
        return tuple(
            self.source.get_meta(start + j * self.skip) for j in range(self.size)
        )
