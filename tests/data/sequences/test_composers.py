from __future__ import annotations

import pytest

from kaparoo.data.sequences import (
    ConcatSequence,
    SlicedSequence,
    TransformedSequence,
    WindowedSequence,
)
from tests.data.sequences.helpers import (
    AllMetasWindow,
    FirstMetaWindow,
    ListDataSequence,
)

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
