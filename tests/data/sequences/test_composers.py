from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.data.sequences import (
    ConcatSequence,
    DataSequence,
    SlicedSequence,
    TransformedSequence,
    WindowedSequence,
    ZippedSequence,
)
from tests.data.sequences.helpers import (
    AllMetasWindow,
    FirstMetaWindow,
    ListDataSequence,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# --- shared fixtures --------------------------------------------------------


@pytest.fixture()
def src() -> ListDataSequence[str, int]:
    """10-item sequence with positional integer metadata."""
    return ListDataSequence(
        items=["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
        metas=list(range(10)),
    )


# --- SlicedSequence ---------------------------------------------------------


def test_sliced_basic_access(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [3, 7, 1])
    assert len(sliced) == 3
    assert sliced[0] == "d"
    assert sliced[1] == "h"
    assert sliced[2] == "b"


def test_sliced_metadata_and_pair(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [3, 7])
    assert sliced.get_meta(0) == 3
    assert sliced.get_meta(1) == 7
    # Default `get_metas` / `get_pair` / `get_pairs` from `DataSequence`.
    assert sliced.get_metas([0, 1]) == [3, 7]
    assert sliced.get_pair(0) == ("d", 3)
    assert sliced.get_pairs([0, 1]) == [("d", 3), ("h", 7)]


def test_sliced_empty(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [])
    assert len(sliced) == 0
    assert list(sliced) == []


def test_sliced_with_duplicates(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [5, 5, 5])
    assert len(sliced) == 3
    assert list(sliced) == ["f", "f", "f"]


def test_sliced_source_property(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [0])
    assert sliced.source is src


def test_sliced_indices_property_is_immutable_tuple(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [1, 2, 3])
    assert isinstance(sliced.indices, tuple)
    assert sliced.indices == (1, 2, 3)


def test_sliced_materializes_iterator_at_construction(src: ListDataSequence[str, int]):
    # `range` is iterable but not a list; should be materialized to tuple.
    sliced = SlicedSequence(src, range(0, 10, 2))
    assert sliced.indices == (0, 2, 4, 6, 8)
    assert list(sliced) == ["a", "c", "e", "g", "i"]


def test_sliced_supports_negative_source_indices(src: ListDataSequence[str, int]):
    # -1 in `indices` maps to source's last item via tuple semantics.
    sliced = SlicedSequence(src, [-1, -2])
    assert sliced[0] == "j"
    assert sliced[1] == "i"


def test_sliced_out_of_range_raises(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [100])
    with pytest.raises(IndexError):
        _ = sliced[0]


def test_sliced_inherited_slice_indexing(src: ListDataSequence[str, int]):
    # `__getitem__` is inherited from `DataSequence`; slice -> get_items.
    sliced = SlicedSequence(src, [3, 7, 1, 5])
    assert list(sliced[1:3]) == ["h", "b"]


def test_sliced_composition(src: ListDataSequence[str, int]):
    # SlicedSequence over another SlicedSequence.
    outer = SlicedSequence(SlicedSequence(src, [0, 2, 4, 6, 8]), [0, 2])
    assert outer[0] == "a"
    assert outer[1] == "e"


# --- ConcatSequence ---------------------------------------------------------


def test_concat_basic_two_sources(src: ListDataSequence[str, int]):
    a = ListDataSequence(["x", "y"], [100, 101])
    combined = ConcatSequence(a, src)
    assert len(combined) == 12
    assert combined[0] == "x"
    assert combined[1] == "y"
    assert combined[2] == "a"
    assert combined.get_meta(0) == 100
    assert combined.get_meta(2) == 0


def test_concat_three_sources():
    a = ListDataSequence(["a"], [0])
    b = ListDataSequence(["b1", "b2"], [10, 11])
    c = ListDataSequence(["c1", "c2", "c3"], [20, 21, 22])
    combined = ConcatSequence(a, b, c)
    assert len(combined) == 6
    assert list(combined) == ["a", "b1", "b2", "c1", "c2", "c3"]


def test_concat_metadata_across_boundaries():
    a = ListDataSequence(["a"], ["meta_a"])
    b = ListDataSequence(["b1", "b2"], ["meta_b1", "meta_b2"])
    combined = ConcatSequence(a, b)
    assert combined.get_meta(0) == "meta_a"
    assert combined.get_meta(1) == "meta_b1"
    assert combined.get_meta(2) == "meta_b2"


def test_concat_with_empty_in_middle():
    a = ListDataSequence(["a"], [0])
    empty = ListDataSequence[str, int]([], [])
    b = ListDataSequence(["b"], [1])
    combined = ConcatSequence(a, empty, b)
    assert len(combined) == 2
    assert list(combined) == ["a", "b"]


def test_concat_negative_index_normalizes(src: ListDataSequence[str, int]):
    a = ListDataSequence(["x"], [100])
    combined = ConcatSequence(a, src)
    # Combined length is 11. Last item ("j") accessible via -1.
    assert combined[-1] == "j"
    assert combined.get_meta(-1) == 9
    # -11 is the first item ("x").
    assert combined[-11] == "x"


def test_concat_out_of_range_raises(src: ListDataSequence[str, int]):
    a = ListDataSequence(["x"], [100])
    combined = ConcatSequence(a, src)
    with pytest.raises(IndexError, match="out of range"):
        _ = combined.get_item(100)
    with pytest.raises(IndexError, match="out of range"):
        _ = combined.get_item(-100)


def test_concat_no_sources_is_empty():
    # The docstring promises "zero or more" sources; the empty case is a
    # valid, empty sequence.
    combined = ConcatSequence()
    assert len(combined) == 0
    assert list(combined) == []
    with pytest.raises(IndexError, match="out of range"):
        _ = combined.get_item(0)


def test_concat_sources_property():
    a = ListDataSequence(["a"], [0])
    b = ListDataSequence(["b"], [1])
    combined = ConcatSequence(a, b)
    assert isinstance(combined.sources, tuple)
    assert combined.sources == (a, b)


def test_concat_slice_across_boundary():
    a = ListDataSequence(["a", "b"], [0, 1])
    b = ListDataSequence(["c", "d"], [2, 3])
    combined = ConcatSequence(a, b)
    # Inherited slice; spans both sources.
    assert list(combined[1:3]) == ["b", "c"]


def test_concat_supports_sequence_mixin_methods():
    # `Sequence`'s mixin methods (__contains__, count, index, reversed)
    # rely on a correct __getitem__ + __len__.
    a = ListDataSequence(["a", "b"], [0, 1])
    b = ListDataSequence(["c", "a"], [2, 3])
    combined = ConcatSequence(a, b)

    assert "a" in combined
    assert "z" not in combined
    assert combined.count("a") == 2
    assert combined.index("a") == 0
    assert list(reversed(combined)) == ["a", "c", "b", "a"]


class RecordingSequence(DataSequence[str, str]):
    """Records the indices passed to each batch `get_items` / `get_metas`."""

    def __init__(self, items: list[str]) -> None:
        self._items = items
        self.item_calls: list[list[int]] = []
        self.meta_calls: list[list[int]] = []

    def __len__(self) -> int:
        return len(self._items)

    def get_item(self, index: int) -> str:
        return self._items[index]

    def get_meta(self, index: int) -> str:
        return f"m{self._items[index]}"

    def get_items(self, indices: Sequence[int]) -> Sequence[str]:
        self.item_calls.append(list(indices))
        return [self._items[i] for i in indices]

    def get_metas(self, indices: Sequence[int]) -> Sequence[str]:
        self.meta_calls.append(list(indices))
        return [f"m{self._items[i]}" for i in indices]


def test_concat_get_items_preserves_order_and_duplicates():
    a = ListDataSequence(["a0", "a1", "a2"], [0, 1, 2])
    b = ListDataSequence(["b0", "b1"], [3, 4])
    combined = ConcatSequence(a, b)  # a -> [0, 2], b -> [3, 4]
    req = [4, 0, 4, 2, 1]  # spans both sources, out of order, with a duplicate
    assert combined.get_items(req) == ["b1", "a0", "b1", "a2", "a1"]
    assert combined.get_metas(req) == [4, 0, 4, 2, 1]
    assert combined.get_items([]) == []  # empty request


def test_concat_get_items_delegates_one_batch_per_source():
    a = RecordingSequence(["a0", "a1", "a2"])
    b = RecordingSequence(["b0", "b1"])
    combined = ConcatSequence(a, b)  # a -> [0, 2], b -> [3, 4]
    assert combined.get_items([3, 0, 4, 2]) == ["b0", "a0", "b1", "a2"]
    # each source receives exactly one batched call, locals in request order
    assert a.item_calls == [[0, 2]]
    assert b.item_calls == [[0, 1]]


def test_concat_get_metas_delegates_one_batch_per_source():
    a = RecordingSequence(["a0", "a1"])
    b = RecordingSequence(["b0"])
    combined = ConcatSequence(a, b)  # a -> [0, 1], b -> [2]
    assert combined.get_metas([2, 0, 1]) == ["mb0", "ma0", "ma1"]
    assert a.meta_calls == [[0, 1]]
    assert b.meta_calls == [[0]]


# --- Cross-composition ------------------------------------------------------


def test_sliced_over_concat():
    a = ListDataSequence(["a", "b"], [0, 1])
    b = ListDataSequence(["c", "d"], [2, 3])
    sliced = SlicedSequence(ConcatSequence(a, b), [0, 2, 3])
    assert list(sliced) == ["a", "c", "d"]
    assert sliced.get_meta(0) == 0
    assert sliced.get_meta(1) == 2
    assert sliced.get_meta(2) == 3


def test_concat_of_sliced():
    base = ListDataSequence(["a", "b", "c", "d"], [0, 1, 2, 3])
    left = SlicedSequence(base, [0, 1])
    right = SlicedSequence(base, [2, 3])
    combined = ConcatSequence(left, right)
    assert list(combined) == ["a", "b", "c", "d"]
    assert combined.get_meta(2) == 2


# --- WindowedSequence ------------------------------------------------------


def test_windowed_is_abstract(src: ListDataSequence[str, int]):
    # `get_meta` is abstract; direct instantiation must fail.
    with pytest.raises(TypeError, match="abstract"):
        WindowedSequence(src, size=3)  # ty: ignore[missing-argument]


def test_windowed_basic_consecutive_frames(src: ListDataSequence[str, int]):
    # 10 items, size=3, step=1, skip=1 -> span=3, n_windows=(10-3)//1+1=8
    ws = FirstMetaWindow(src, size=3)
    assert len(ws) == 8
    assert ws[0] == ("a", "b", "c")
    assert ws[1] == ("b", "c", "d")
    assert ws[7] == ("h", "i", "j")


def test_windowed_meta_strategies_via_subclasses(src: ListDataSequence[str, int]):
    # Two distinct M_out types from the same base class.
    ws_first = FirstMetaWindow(src, size=3)  # M_out = int (= M_in)
    ws_all = AllMetasWindow(src, size=3)  # M_out = tuple[int, ...]

    assert ws_first.get_meta(0) == 0
    assert ws_first.get_meta(7) == 7
    assert ws_all.get_meta(0) == (0, 1, 2)
    assert ws_all.get_meta(7) == (7, 8, 9)


def test_windowed_user_defined_subclass(src: ListDataSequence[str, int]):
    """A user-defined subclass with an arbitrary M_out type."""

    class BookendsWindow(WindowedSequence[str, int, tuple[int, int]]):
        def get_meta(self, index: int) -> tuple[int, int]:
            index = self._normalize_index(index)
            start = index * self.step
            last = start + (self.size - 1) * self.skip
            return self.source.get_meta(start), self.source.get_meta(last)

    ws = BookendsWindow(src, size=3)
    assert ws.get_meta(0) == (0, 2)
    assert ws.get_meta(7) == (7, 9)


def test_windowed_step_advances_window(src: ListDataSequence[str, int]):
    # step=2: n_windows = (10 - 3) // 2 + 1 = 4
    ws = FirstMetaWindow(src, size=3, step=2)
    assert len(ws) == 4
    assert ws[0] == ("a", "b", "c")
    assert ws[1] == ("c", "d", "e")
    assert ws[3] == ("g", "h", "i")


def test_windowed_skip_intra_stride(src: ListDataSequence[str, int]):
    # skip=2: span = (3-1)*2+1 = 5; n_windows = (10-5)//1+1 = 6
    ws = FirstMetaWindow(src, size=3, skip=2)
    assert len(ws) == 6
    assert ws[0] == ("a", "c", "e")
    assert ws[1] == ("b", "d", "f")
    assert ws[5] == ("f", "h", "j")


def test_windowed_source_too_small_yields_empty():
    short = ListDataSequence(["a", "b"], [0, 1])
    ws = FirstMetaWindow(short, size=3)
    assert len(ws) == 0
    assert list(ws) == []


def test_windowed_source_exactly_one_window():
    exact = ListDataSequence(["a", "b", "c"], [0, 1, 2])
    ws = FirstMetaWindow(exact, size=3)
    assert len(ws) == 1
    assert ws[0] == ("a", "b", "c")
    assert ws.get_meta(0) == 0


def test_windowed_invalid_params_raise(src: ListDataSequence[str, int]):
    for bad in (0, -1):
        with pytest.raises(ValueError, match="must be positive"):
            FirstMetaWindow(src, size=bad)
        with pytest.raises(ValueError, match="must be positive"):
            FirstMetaWindow(src, size=3, step=bad)
        with pytest.raises(ValueError, match="must be positive"):
            FirstMetaWindow(src, size=3, skip=bad)


def test_windowed_out_of_range_raises(src: ListDataSequence[str, int]):
    ws = FirstMetaWindow(src, size=3)
    with pytest.raises(IndexError, match="out of range"):
        _ = ws.get_item(100)
    with pytest.raises(IndexError, match="out of range"):
        _ = ws.get_meta(-100)


def test_windowed_negative_index_normalizes(src: ListDataSequence[str, int]):
    ws = FirstMetaWindow(src, size=3)
    assert ws[-1] == ws[len(ws) - 1]
    assert ws.get_meta(-1) == ws.get_meta(len(ws) - 1)


def test_windowed_properties(src: ListDataSequence[str, int]):
    ws = FirstMetaWindow(src, size=3, step=2, skip=4)
    assert ws.source is src
    assert ws.size == 3
    assert ws.step == 2
    assert ws.skip == 4


def test_windowed_composition_with_concat():
    """The original use case: per-video windowing + cross-video concat.

    Each video is windowed independently (no cross-video windows), then
    the per-video window sequences are concatenated into one dataset.
    """
    video1 = ListDataSequence(list("abc"), [0, 1, 2])
    video2 = ListDataSequence(list("def"), [10, 11, 12])
    video3 = ListDataSequence(list("ghi"), [20, 21, 22])

    w1 = FirstMetaWindow(video1, size=3)
    w2 = FirstMetaWindow(video2, size=3)
    w3 = FirstMetaWindow(video3, size=3)

    dataset = ConcatSequence(w1, w2, w3)
    assert len(dataset) == 3  # one window per video
    assert dataset[0] == ("a", "b", "c")
    assert dataset[1] == ("d", "e", "f")
    assert dataset[2] == ("g", "h", "i")
    # Window's first-frame meta tracks which video it came from.
    assert dataset.get_meta(0) == 0
    assert dataset.get_meta(1) == 10
    assert dataset.get_meta(2) == 20


def test_windowed_composition_with_sliced(src: ListDataSequence[str, int]):
    # Select every other window via SlicedSequence on top of WindowedSequence.
    ws = FirstMetaWindow(src, size=3)
    every_other = SlicedSequence(ws, [0, 2, 4, 6])
    assert len(every_other) == 4
    assert every_other[0] == ("a", "b", "c")
    assert every_other[1] == ("c", "d", "e")
    assert every_other[3] == ("g", "h", "i")


# --- TransformedSequence ----------------------------------------------------


def test_transformed_applies_transform(src: ListDataSequence[str, int]):
    t = TransformedSequence(src, str.upper)
    assert t.get_item(0) == "A"
    assert t.get_item(4) == "E"
    assert len(t) == len(src)


def test_transformed_meta_passthrough(src: ListDataSequence[str, int]):
    # Default get_meta delegates to source unchanged.
    t = TransformedSequence(src, str.upper)
    for i in range(len(src)):
        assert t.get_meta(i) == src.get_meta(i)


def test_transformed_source_property(src: ListDataSequence[str, int]):
    t = TransformedSequence(src, str.upper)
    assert t.source is src


def test_transformed_loads_lazily(src: ListDataSequence[str, int]):
    calls: list[str] = []

    def recording_transform(x: str) -> str:
        calls.append(x)
        return x.upper()

    TransformedSequence(src, recording_transform)
    assert calls == []  # nothing called at construction


def test_transformed_negative_and_slice_indexing(src: ListDataSequence[str, int]):
    t = TransformedSequence(src, str.upper)
    assert t[-1] == "J"
    assert list(t[0:3]) == ["A", "B", "C"]


def test_transformed_meta_override_is_type_safe():
    # Subclass overrides get_meta to produce a different type, while
    # get_item keeps the transform from the base.
    base = ListDataSequence(["x", "y", "z"], [10, 20, 30])

    class PrefixedMeta(TransformedSequence[str, int, str, str]):
        def get_meta(self, index: int) -> str:
            return f"meta:{self.source.get_meta(index)}"

    t = PrefixedMeta(base, str.upper)
    assert t.get_item(0) == "X"  # transform applied
    assert t.get_meta(0) == "meta:10"  # overridden meta
    assert t.get_meta(2) == "meta:30"


def test_transformed_chaining():
    src = ListDataSequence(["a", "b", "c"], [0, 1, 2])
    upper = TransformedSequence(src, str.upper)
    exclaimed = TransformedSequence(upper, lambda s: s + "!")
    assert list(exclaimed) == ["A!", "B!", "C!"]
    assert exclaimed.get_meta(0) == 0  # meta passes through both layers


def test_transformed_composition_with_sliced(src: ListDataSequence[str, int]):
    t = TransformedSequence(src, str.upper)
    sliced = SlicedSequence(t, [0, 2, 4])
    assert list(sliced) == ["A", "C", "E"]
    assert sliced.get_meta(1) == 2


def test_transformed_composition_with_concat():
    a = ListDataSequence(["a", "b"], [0, 1])
    b = ListDataSequence(["c", "d"], [2, 3])
    t = TransformedSequence(ConcatSequence(a, b), str.upper)
    assert list(t) == ["A", "B", "C", "D"]
    assert t.get_meta(3) == 3


# --- ZippedSequence ---------------------------------------------------------


@pytest.fixture()
def images() -> ListDataSequence[str, int]:
    return ListDataSequence(items=["a", "b", "c"], metas=[10, 11, 12])


@pytest.fixture()
def labels() -> ListDataSequence[int, str]:
    return ListDataSequence(items=[0, 1, 2], metas=["x", "y", "z"])


def test_zipped_basic_item_and_len(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    zipped = ZippedSequence(images, labels)
    assert len(zipped) == 3
    assert zipped[0] == ("a", 0)
    assert zipped[2] == ("c", 2)


def test_zipped_metadata_pair(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    zipped = ZippedSequence(images, labels)
    assert zipped.get_meta(1) == (11, "y")
    assert zipped.get_pair(0) == (("a", 0), (10, "x"))


def test_zipped_length_mismatch_raises():
    a = ListDataSequence(["a", "b"], [0, 1])
    b = ListDataSequence([0, 1, 2], ["x", "y", "z"])
    with pytest.raises(ValueError, match="differ in length"):
        ZippedSequence(a, b)


def test_zipped_batch_items_and_metas(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    zipped = ZippedSequence(images, labels)
    assert zipped.get_items([2, 0]) == [("c", 2), ("a", 0)]
    assert zipped.get_metas([2, 0]) == [(12, "z"), (10, "x")]
    # `__getitem__` slicing routes through `get_items`.
    assert list(zipped[0:2]) == [("a", 0), ("b", 1)]


def test_zipped_negative_index_delegates(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    zipped = ZippedSequence(images, labels)
    assert zipped[-1] == ("c", 2)
    assert zipped.get_meta(-1) == (12, "z")


def test_zipped_source_properties(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    zipped = ZippedSequence(images, labels)
    assert zipped.first is images
    assert zipped.second is labels


def test_zipped_nesting_for_three(
    images: ListDataSequence[str, int], labels: ListDataSequence[int, str]
):
    extra = ListDataSequence(items=[1.0, 2.0, 3.0], metas=[None, None, None])
    triple = ZippedSequence(images, ZippedSequence(labels, extra))
    assert triple[0] == ("a", (0, 1.0))


def test_zipped_strict_false_truncates_to_shorter():
    a = ListDataSequence(items=["a", "b", "c", "d"], metas=[0, 1, 2, 3])
    b = ListDataSequence(items=[10, 11], metas=["x", "y"])
    zipped = ZippedSequence(a, b, strict=False)
    assert len(zipped) == 2
    assert list(zipped) == [("a", 10), ("b", 11)]
    # Negative and out-of-range resolve against the truncated length, so the
    # pair stays aligned rather than delegating to each source's own length.
    assert zipped[-1] == ("b", 11)
    assert zipped.get_metas([1, 0]) == [(1, "y"), (0, "x")]
    with pytest.raises(IndexError):
        zipped[2]


# --- batch get_items / get_metas equal the scalar path ----------------------


def test_sliced_batch_matches_scalar(src: ListDataSequence[str, int]):
    sliced = SlicedSequence(src, [3, 7, 1, 9])
    idx = [2, 0, 3]
    assert sliced.get_items(idx) == [sliced.get_item(i) for i in idx]
    assert sliced.get_metas(idx) == [sliced.get_meta(i) for i in idx]


def test_transformed_batch_matches_scalar(src: ListDataSequence[str, int]):
    transformed = TransformedSequence(src, str.upper)
    idx = [0, 4, 2]
    assert transformed.get_items(idx) == [transformed.get_item(i) for i in idx]
