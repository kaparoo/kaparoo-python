"""Lazy `DataSequence` composers: slice, concat, transform, window, zip."""

from __future__ import annotations

__all__ = (
    "ConcatSequence",
    "SlicedSequence",
    "TransformedSequence",
    "WindowedSequence",
    "ZippedSequence",
)

from abc import abstractmethod
from bisect import bisect_right
from typing import TYPE_CHECKING, cast, override

from kaparoo.data.sequences.base import DataSequence

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _resolve_index(index: int, length: int) -> int:
    """Normalize a possibly-negative index against `length`, validating range.

    Used by `ConcatSequence`, `WindowedSequence`, and `ZippedSequence`.
    `SlicedSequence` intentionally opts out -- it indexes its `indices` tuple
    directly, which wraps and raises the same way but with the builtin message.

    Raises:
        IndexError: If `index` is outside `[-length, length)`.
    """
    original = index
    if index < 0:
        index += length
    if not 0 <= index < length:
        msg = f"index {original} out of range for length {length}"
        raise IndexError(msg)
    return index


class SlicedSequence[T, M](DataSequence[T, M]):
    """A view of `source` exposing only the items at `indices`, in that order.

    `indices` is taken as-is -- duplicates repeat the source item, order is
    preserved -- and is not bounds-checked against `source` until a position
    is accessed. A negative view index wraps; out of range raises `IndexError`.

    Example:
        >>> sliced = SlicedSequence(full_dataset, [3, 7, 11])
        >>> sliced[0]  # == full_dataset[3]
    """

    def __init__(
        self,
        source: DataSequence[T, M],
        indices: Sequence[int],
    ) -> None:
        self._source = source
        self._indices = tuple(indices)

    @property
    def source(self) -> DataSequence[T, M]:
        """The wrapped sequence."""
        return self._source

    @property
    def indices(self) -> tuple[int, ...]:
        """The index map into `source`, frozen at construction."""
        return self._indices

    def __len__(self) -> int:
        return len(self._indices)

    @override
    def get_item(self, index: int) -> T:
        """Fetch the source item at the mapped index `indices[index]`."""
        return self._source.get_item(self._indices[index])

    @override
    def get_meta(self, index: int) -> M:
        """Fetch the source metadata at the mapped index `indices[index]`."""
        return self._source.get_meta(self._indices[index])

    @override
    def get_items(self, indices: Sequence[int]) -> Sequence[T]:
        """Map each view index through `indices`, then batch-fetch from `source`."""
        return self._source.get_items([self._indices[i] for i in indices])

    @override
    def get_metas(self, indices: Sequence[int]) -> Sequence[M]:
        """Map each view index through `indices`, then batch-fetch metadata."""
        return self._source.get_metas([self._indices[i] for i in indices])


class TransformedSequence[T_in, M_in, T_out = T_in, M_out = M_in](
    DataSequence[T_out, M_out]
):
    """A view of `source` with `transform` applied lazily to each item.

    `transform` runs on demand in `get_item`; nothing is converted at
    construction. `get_meta` passes `source.get_meta` through unchanged, which
    is correct only when the metadata type is unchanged (the default
    `M_out == M_in`). **Override `get_meta` whenever `M_out != M_in`**: the
    passthrough's `cast` cannot catch a missing override -- generics are erased
    at runtime -- so a forgotten one silently yields an `M_in` value mistyped
    as `M_out`.

    Type Parameters:
        T_in, M_in: The source's element and metadata types.
        T_out: The transformed element type. Defaults to `T_in`.
        M_out: The transformed metadata type. Defaults to `M_in` (the
            passthrough case); set it and override `get_meta` otherwise.

    Example:
        >>> # Item-only transform; metadata passes through unchanged.
        >>> normalized = TransformedSequence(image_folder, normalize)

        >>> # Metadata transform via subclassing:
        >>> class Augmented(TransformedSequence[ndarray, Path, ndarray, AugMeta]):
        ...     def get_meta(self, index: int) -> AugMeta:
        ...         return AugMeta(self.source.get_meta(index), applied="normalize")
    """

    def __init__(
        self,
        source: DataSequence[T_in, M_in],
        transform: Callable[[T_in], T_out],
    ) -> None:
        self._source = source
        self._transform = transform

    @property
    def source(self) -> DataSequence[T_in, M_in]:
        """The wrapped sequence."""
        return self._source

    def __len__(self) -> int:
        return len(self._source)

    @override
    def get_item(self, index: int) -> T_out:
        """Fetch the source item at `index` and apply `transform`."""
        return self._transform(self._source.get_item(index))

    @override
    def get_items(self, indices: Sequence[int]) -> Sequence[T_out]:
        """Batch-fetch from `source` and apply `transform` to each item."""
        return [self._transform(item) for item in self._source.get_items(indices)]

    @override
    def get_meta(self, index: int) -> M_out:
        """Pass `source`'s metadata through unchanged.

        A subclass whose `M_out` differs from `M_in` must override this.
        """
        # The cast cannot catch a missing override -- generics are erased at runtime.
        return cast("M_out", self._source.get_meta(index))


class ConcatSequence[T, M](DataSequence[T, M]):
    """The end-to-end concatenation of zero or more `sources`.

    A logical index maps to the `(source, local index)` it falls in -- an
    O(log N) lookup in the number of sources. Negative indices wrap; out of
    range raises `IndexError`. Batch access (`get_items` / `get_metas`)
    delegates one grouped call per source, so a source's own batch
    optimization is used, with results kept in request order.

    Example:
        >>> combined = ConcatSequence(train_a, train_b, train_c)
        >>> len(combined)  # == len(train_a) + len(train_b) + len(train_c)
    """

    def __init__(self, *sources: DataSequence[T, M]) -> None:
        self._sources = sources
        cumulative = [0]
        for s in sources:
            cumulative.append(cumulative[-1] + len(s))
        self._cumulative = tuple(cumulative)

    @property
    def sources(self) -> tuple[DataSequence[T, M], ...]:
        """The wrapped sequences, in the order they were passed in."""
        return self._sources

    def __len__(self) -> int:
        return self._cumulative[-1]

    def _locate_index(self, index: int) -> tuple[int, int]:
        """Resolve a logical index to `(source position, local index)`.

        Raises:
            IndexError: If `index` is outside `[-len(self), len(self))`.
        """
        index = _resolve_index(index, self._cumulative[-1])
        i = bisect_right(self._cumulative, index) - 1
        return i, index - self._cumulative[i]

    def _locate(self, index: int) -> tuple[DataSequence[T, M], int]:
        """Resolve a logical index to `(source, local_index)`."""
        i, local = self._locate_index(index)
        return self._sources[i], local

    def _gather[R](
        self,
        indices: Sequence[int],
        fetch: Callable[[DataSequence[T, M], list[int]], Sequence[R]],
    ) -> list[R]:
        """Batch-fetch `indices` with one grouped `fetch` per source.

        The shared core of `get_items` / `get_metas`, which differ only in the
        per-source `fetch`; results are scattered back into request order.
        """
        buckets: dict[int, list[tuple[int, int]]] = {}
        for position, index in enumerate(indices):
            source_index, local = self._locate_index(index)
            buckets.setdefault(source_index, []).append((position, local))

        gathered: dict[int, R] = {}
        for source_index, entries in buckets.items():
            fetched = fetch(
                self._sources[source_index], [local for _, local in entries]
            )
            for (position, _), value in zip(entries, fetched, strict=True):
                gathered[position] = value
        return [gathered[position] for position in range(len(indices))]

    @override
    def get_item(self, index: int) -> T:
        """Locate the source for `index` and fetch its local item."""
        source, local = self._locate(index)
        return source.get_item(local)

    @override
    def get_items(self, indices: Sequence[int]) -> Sequence[T]:
        """Group `indices` by source and batch-fetch items, kept in request order."""
        return self._gather(indices, lambda source, locals_: source.get_items(locals_))

    @override
    def get_meta(self, index: int) -> M:
        """Locate the source for `index` and fetch its local metadata."""
        source, local = self._locate(index)
        return source.get_meta(local)

    @override
    def get_metas(self, indices: Sequence[int]) -> Sequence[M]:
        """Group `indices` by source and batch-fetch metadata, kept in request order."""
        return self._gather(indices, lambda source, locals_: source.get_metas(locals_))


class WindowedSequence[T, M_in, M_out = M_in](DataSequence[tuple[T, ...], M_out]):
    """An abstract sliding-window view over `source`.

    Each item is a tuple of `size` items from `source`, the window starting at
    `i * step` with intra-window stride `skip`. `get_item` is implemented;
    **the window's metadata is intentionally left abstract** so a subclass
    decides how per-frame metadata becomes window metadata (`M_in` -> `M_out`).
    Subclasses should call `_normalize_index` in their `get_meta` so window
    indices behave as in `get_item`.

    Type Parameters:
        T: The source's element type; each item is a `tuple[T, ...]`.
        M_in: The source's per-frame metadata type.
        M_out: The window's metadata type a subclass produces. Defaults to
            `M_in`.

    Args:
        source: The sequence to window over.
        size: Items per window. Must be positive.
        step: Advance between consecutive windows. Defaults to 1 (windows
            overlap by `size - 1`).
        skip: Intra-window stride. Defaults to 1 (consecutive frames).

    Raises:
        ValueError: If `size`, `step`, or `skip` is non-positive.
    """

    def __init__(
        self,
        source: DataSequence[T, M_in],
        size: int,
        *,
        step: int = 1,
        skip: int = 1,
    ) -> None:
        if size <= 0 or step <= 0 or skip <= 0:
            msg = (
                f"size, step, skip must be positive "
                f"(got size={size}, step={step}, skip={skip})"
            )
            raise ValueError(msg)
        self._source = source
        self._size = size
        self._step = step
        self._skip = skip
        # The window spans `(size - 1) * skip + 1` source positions; the
        # number of complete windows is then `(len(source) - span) // step + 1`.
        span = (size - 1) * skip + 1
        self._length = max(0, (len(source) - span) // step + 1)

    @property
    def source(self) -> DataSequence[T, M_in]:
        """The wrapped sequence."""
        return self._source

    @property
    def size(self) -> int:
        """Number of items per window."""
        return self._size

    @property
    def step(self) -> int:
        """Position advance between consecutive windows."""
        return self._step

    @property
    def skip(self) -> int:
        """Intra-window stride."""
        return self._skip

    def __len__(self) -> int:
        return self._length

    def _normalize_index(self, index: int) -> int:
        """Normalize a possibly-negative window index and validate range.

        Subclasses should call this from `get_meta` to apply the same
        negative-index handling and bounds checking that `get_item`
        performs.

        Raises:
            IndexError: If `index` is outside `[-len(self), len(self))`.
        """
        return _resolve_index(index, self._length)

    @override
    def get_item(self, index: int) -> tuple[T, ...]:
        """Build the window at `index` as a tuple of `size` strided source items."""
        index = self._normalize_index(index)
        start = index * self._step
        stop = start + self._size * self._skip
        return tuple(self._source.get_items(range(start, stop, self._skip)))

    @abstractmethod
    def get_meta(self, index: int) -> M_out:
        """Return the metadata for window `index` (the `M_in` -> `M_out` policy)."""


class ZippedSequence[T1, T2, M1 = None, M2 = None](
    DataSequence[tuple[T1, T2], tuple[M1, M2]]
):
    """Element-wise zip of two sequences.

    Item `i` is `(first[i], second[i])` and metadata `i` is
    `(first.get_meta(i), second.get_meta(i))` -- the "paired image + label"
    pattern that `ConcatSequence` (end-to-end) cannot express.

    With `strict=True` (the default) the sequences must be the same length, or
    construction raises `ValueError`; with `strict=False` the view truncates to
    the shorter, like the builtin `zip`. For a different combined-metadata
    shape, subclass and override `get_meta`.

    Type Parameters:
        T1, T2: Element types of the first and second sequence; items are
            `tuple[T1, T2]`.
        M1, M2: Their metadata types; metadata is `tuple[M1, M2]`. Each
            defaults to `None` (a sequence without metadata).

    Example:
        >>> pairs = ZippedSequence(images, labels)
        >>> pairs[0]  # (images[0], labels[0])
        >>> pairs.get_meta(0)  # (images.get_meta(0), labels.get_meta(0))
    """

    def __init__(
        self,
        first: DataSequence[T1, M1],
        second: DataSequence[T2, M2],
        *,
        strict: bool = True,
    ) -> None:
        if strict and len(first) != len(second):
            msg = f"sequences differ in length: {len(first)} != {len(second)}"
            raise ValueError(msg)
        self._first = first
        self._second = second
        self._length = len(first) if strict else min(len(first), len(second))

    @property
    def first(self) -> DataSequence[T1, M1]:
        """The first wrapped sequence."""
        return self._first

    @property
    def second(self) -> DataSequence[T2, M2]:
        """The second wrapped sequence."""
        return self._second

    def __len__(self) -> int:
        return self._length

    def _normalize_index(self, index: int) -> int:
        """Normalize a possibly-negative index and validate range.

        Indices resolve against the zipped length (the shorter source when
        `strict=False`), so they address the same position in both sources.

        Raises:
            IndexError: If `index` is outside `[-len(self), len(self))`.
        """
        return _resolve_index(index, self._length)

    @override
    def get_item(self, index: int) -> tuple[T1, T2]:
        """Fetch the paired `(first[index], second[index])` item."""
        index = self._normalize_index(index)
        return self._first.get_item(index), self._second.get_item(index)

    @override
    def get_items(self, indices: Sequence[int]) -> Sequence[tuple[T1, T2]]:
        """Normalize indices, then batch-fetch and pair items from both sources."""
        # Normalize, then bulk-delegate so each source's `get_items`
        # optimization is used.
        normalized = [self._normalize_index(i) for i in indices]
        return list(
            zip(
                self._first.get_items(normalized),
                self._second.get_items(normalized),
                strict=True,
            )
        )

    @override
    def get_meta(self, index: int) -> tuple[M1, M2]:
        """Fetch the paired `(first, second)` metadata at `index`."""
        index = self._normalize_index(index)
        return self._first.get_meta(index), self._second.get_meta(index)

    @override
    def get_metas(self, indices: Sequence[int]) -> Sequence[tuple[M1, M2]]:
        """Normalize indices, then batch-fetch and pair metadata from both sources."""
        normalized = [self._normalize_index(i) for i in indices]
        return list(
            zip(
                self._first.get_metas(normalized),
                self._second.get_metas(normalized),
                strict=True,
            )
        )
