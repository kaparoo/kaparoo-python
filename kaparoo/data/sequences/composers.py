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
from typing import TYPE_CHECKING, cast

from kaparoo.data.sequences.base import DataSequence

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


class SlicedSequence[T, M](DataSequence[T, M]):
    """A view of `source` exposing only items at the given `indices`.

    `indices` is materialized as a tuple at construction time so that the
    view has a stable length and supports O(1) random access. Negative
    and out-of-range indices delegate to Python's tuple semantics
    (negative wraps, out-of-range raises `IndexError`).

    `indices` is taken as-is: duplicates are allowed (the same source
    item is yielded multiple times) and order is preserved (no sorting).
    Bounds against `source` are not validated at construction; an
    out-of-range entry surfaces only when that position is accessed.

    Example:
        >>> sliced = SlicedSequence(full_dataset, [3, 7, 11])
        >>> sliced[0]  # == full_dataset[3]
        >>> sliced[1]  # == full_dataset[7]
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

    def get_item(self, index: int) -> T:
        return self._source.get_item(self._indices[index])

    def get_meta(self, index: int) -> M:
        return self._source.get_meta(self._indices[index])


class TransformedSequence[T_in, M_in, T_out = T_in, M_out = M_in](
    DataSequence[T_out, M_out]
):
    """A view of `source` with `transform` applied lazily to each item.

    `transform` is called on demand in `get_item`; nothing is loaded or
    converted at construction time. `get_meta` passes through
    `source.get_meta` unchanged by default -- override it in a subclass
    when `M_out` differs from `M_in`.

    Type Parameters:
        T_in: Item type of `source`.
        M_in: Metadata type of `source`.
        T_out: Item type after the transform. Defaults to `T_in`.
        M_out: Metadata type exposed by this view. Defaults to `M_in`. The
            default `get_meta` passes `source.get_meta` through, which is
            correct only when `M_out == M_in`. **Always override `get_meta`**
            when `M_out != M_in`: the default's `cast` silences the type
            checker and Python erases generics at runtime, so a forgotten
            override silently returns an `M_in` value typed as `M_out` -- a
            wrong-typed value that surfaces only later in use, never at
            construction.

    Example:
        >>> # Item-only transform; metadata passes through unchanged.
        >>> normalized = TransformedSequence(image_folder, normalize)

        >>> # Meta transform via subclassing:
        >>> class Augmented(TransformedSequence[ndarray, Path, ndarray, AugMeta]):
        ...     def get_meta(self, index: int) -> AugMeta:
        ...         return AugMeta(
        ...             path=self.source.get_meta(index),
        ...             applied="normalize",
        ...         )
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

    def get_item(self, index: int) -> T_out:
        return self._transform(self._source.get_item(index))

    def get_meta(self, index: int) -> M_out:
        # Passthrough -- correct only when M_out == M_in. A subclass with a
        # different M_out MUST override this; the cast cannot catch a missing
        # override, since generics are erased at runtime.
        return cast("M_out", self._source.get_meta(index))


class ConcatSequence[T, M](DataSequence[T, M]):
    """The end-to-end concatenation of zero or more `sources`.

    Indexing maps to `(source, local_index)` via a precomputed cumulative
    length array and `bisect`, so a lookup is O(log N) in the number of
    sources. Negative indices are normalized; out-of-range indices raise
    `IndexError`.

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

    def _locate(self, index: int) -> tuple[DataSequence[T, M], int]:
        """Resolve a logical index to `(source, local_index)`.

        Raises:
            IndexError: If `index` is outside `[-len(self), len(self))`.
        """
        n = self._cumulative[-1]
        original = index
        if index < 0:
            index += n
        if not 0 <= index < n:
            msg = f"index {original} out of range for length {n}"
            raise IndexError(msg)
        i = bisect_right(self._cumulative, index) - 1
        return self._sources[i], index - self._cumulative[i]

    def get_item(self, index: int) -> T:
        source, local = self._locate(index)
        return source.get_item(local)

    def get_meta(self, index: int) -> M:
        source, local = self._locate(index)
        return source.get_meta(local)


class WindowedSequence[T, M_in, M_out = M_in](DataSequence[tuple[T, ...], M_out]):
    """An abstract sliding-window view over `source`.

    Each item is a tuple of `size` items from `source`, starting at
    position `i * step`, with intra-window stride `skip`. Indexed item
    access (`get_item`) is implemented; **the window's metadata
    strategy is intentionally left abstract** so the relationship
    between per-frame `M_in` and window-level `M_out` is decided at
    subclass-definition time.

    Subclasses use the `source`, `size`, `step`, `skip` properties and
    should call `_normalize_index` from `get_meta` so negative and
    out-of-range window indices behave the same way as in `get_item`.

    Type Parameters:
        T: Item type of `source` (also the per-frame type within each
            window).
        M_in: Metadata type of `source` (per-frame metadata).
        M_out: Metadata type of the window. Defaults to `M_in`.
            Determined by the subclass's `get_meta` return.

    Args:
        source: The sequence to window over.
        size: Number of items per window. Must be positive.
        step: Position advance between consecutive windows. Defaults
            to 1 (overlapping windows by `size - 1`).
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
        n = self._length
        original = index
        if index < 0:
            index += n
        if not 0 <= index < n:
            msg = f"index {original} out of range for length {n}"
            raise IndexError(msg)
        return index

    def get_item(self, index: int) -> tuple[T, ...]:
        index = self._normalize_index(index)
        start = index * self._step
        return tuple(
            self._source.get_item(start + j * self._skip) for j in range(self._size)
        )

    @abstractmethod
    def get_meta(self, index: int) -> M_out:
        raise NotImplementedError


class ZippedSequence[T1, T2, M1 = None, M2 = None](
    DataSequence[tuple[T1, T2], tuple[M1, M2]]
):
    """Element-wise zip of two sequences.

    Item `i` is `(first[i], second[i])` and metadata `i` is
    `(first.get_meta(i), second.get_meta(i))` -- the "paired image + label"
    pattern that `ConcatSequence` (end-to-end) cannot express.

    With `strict=True` (the default) the two sequences must have the same
    length; a mismatch raises `ValueError` at construction. With
    `strict=False` the view is truncated to the shorter length, like the
    builtin `zip`. For a different combined-metadata shape, subclass and
    override `get_meta`.

    Type Parameters:
        T1: Item type of the first source.
        T2: Item type of the second source.
        M1: Metadata type of the first source. Defaults to `None`.
        M2: Metadata type of the second source. Defaults to `None`.

    Args:
        first: The first sequence.
        second: The second sequence.
        strict: When True (default), require equal lengths and raise on a
            mismatch. When False, truncate to the shorter length.

    Raises:
        ValueError: If `strict` is True and the sequences differ in length.

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
        n = self._length
        original = index
        if index < 0:
            index += n
        if not 0 <= index < n:
            msg = f"index {original} out of range for length {n}"
            raise IndexError(msg)
        return index

    def get_item(self, index: int) -> tuple[T1, T2]:
        index = self._normalize_index(index)
        return self._first.get_item(index), self._second.get_item(index)

    def get_items(self, indices: Sequence[int]) -> Sequence[tuple[T1, T2]]:
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

    def get_meta(self, index: int) -> tuple[M1, M2]:
        index = self._normalize_index(index)
        return self._first.get_meta(index), self._second.get_meta(index)

    def get_metas(self, indices: Sequence[int]) -> Sequence[tuple[M1, M2]]:
        normalized = [self._normalize_index(i) for i in indices]
        return list(
            zip(
                self._first.get_metas(normalized),
                self._second.get_metas(normalized),
                strict=True,
            )
        )
