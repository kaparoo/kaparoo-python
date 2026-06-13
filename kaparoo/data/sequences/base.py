from __future__ import annotations

__all__ = ("DataSequence",)

from abc import abstractmethod
from collections.abc import Sequence
from typing import overload


class DataSequence[T, M = None](Sequence[T]):
    """An ordered, lazily-loaded, read-only sequence with per-item metadata.

    Subclasses implement `get_item` (and `__len__`) to fetch a single
    item by index. Sequence operations (`ds[i]`, `ds[i:j]`, `for x in
    ds`, `x in ds`, `reversed(ds)`, ...) come from the inherited
    `collections.abc.Sequence` protocol; only `get_item` need be
    overridden, and `get_items` may be overridden for batch-fetch
    optimization.

    The second type parameter `M` carries per-item metadata (labels,
    source paths, timestamps, ...). Subclasses implement `get_meta`.
    When the data has no metadata, parameterize as `DataSequence[T]`
    (so `M` defaults to `None`) and let `get_meta` simply return
    `None`.

    Type Parameters:
        T: Element type. `ds[i]` and `get_item(i)` return `T`.
        M: Per-item metadata type. `get_meta(i)` returns `M`. Defaults
            to `None` -- meaning "no metadata", in which case
            subclasses still implement `get_meta` but as a no-op.
    """

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of items in the sequence."""

    # --- item access -------------------------------------------------------

    @overload
    def __getitem__(self, index: int, /) -> T: ...

    @overload
    def __getitem__(self, index: slice, /) -> Sequence[T]: ...

    def __getitem__(self, index: int | slice, /) -> T | Sequence[T]:
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return self.get_items(range(start, stop, step))
        return self.get_item(index)

    @abstractmethod
    def get_item(self, index: int) -> T:
        """Fetch and return the item at `index`."""

    def get_items(self, indices: Sequence[int]) -> Sequence[T]:
        """Fetch many items at once, in `indices` order.

        Defaults to one `get_item` per index; override to use a backing
        store's native batch read.
        """
        return [self.get_item(index) for index in indices]

    # --- metadata access ---------------------------------------------------

    @abstractmethod
    def get_meta(self, index: int) -> M:
        """Return the metadata for the item at `index` (`None` when `M` is `None`)."""

    def get_metas(self, indices: Sequence[int]) -> Sequence[M]:
        """Fetch many metadata values at once, in `indices` order.

        Defaults to one `get_meta` per index; override alongside
        `get_items` when a batch read is cheaper.
        """
        return [self.get_meta(index) for index in indices]

    # --- combined item + metadata ------------------------------------------

    def get_pair(self, index: int) -> tuple[T, M]:
        """Return the `(item, metadata)` pair at `index`."""
        return self.get_item(index), self.get_meta(index)

    def get_pairs(self, indices: Sequence[int]) -> Sequence[tuple[T, M]]:
        """Fetch many `(item, metadata)` pairs at once, in `indices` order."""
        return [self.get_pair(index) for index in indices]
