from __future__ import annotations

import pytest

from kaparoo.data.sequences import DataSequence
from tests.data.sequences.helpers import ListDataSequence

# --- shared fixture --------------------------------------------------------


@pytest.fixture()
def ds() -> ListDataSequence[str, int]:
    """5-item sequence with positional integer metadata."""
    return ListDataSequence(items=["a", "b", "c", "d", "e"], metas=[0, 1, 2, 3, 4])


# --- abstractness ----------------------------------------------------------


def test_is_abstract():
    # `__len__`, `get_item`, and `get_meta` are all abstract.
    with pytest.raises(TypeError, match="abstract"):
        DataSequence()  # ty: ignore[missing-argument]


# --- default get_items / get_metas -----------------------------------------


def test_get_items_default(ds: ListDataSequence[str, int]):
    # Default `get_items` iterates via `get_item` in the given order.
    assert ds.get_items([0, 2, 4]) == ["a", "c", "e"]


def test_get_items_preserves_order_and_duplicates(ds: ListDataSequence[str, int]):
    # Order is preserved as-is; duplicates yield the same item again.
    assert ds.get_items([4, 0, 2, 0]) == ["e", "a", "c", "a"]


def test_get_metas_default(ds: ListDataSequence[str, int]):
    assert ds.get_metas([0, 2, 4]) == [0, 2, 4]


def test_get_items_empty(ds: ListDataSequence[str, int]):
    assert ds.get_items([]) == []


def test_get_metas_empty(ds: ListDataSequence[str, int]):
    assert ds.get_metas([]) == []


# --- default get_pair / get_pairs ------------------------------------------


def test_get_pair_default(ds: ListDataSequence[str, int]):
    # `get_pair(i)` is `(get_item(i), get_meta(i))`.
    assert ds.get_pair(0) == ("a", 0)
    assert ds.get_pair(3) == ("d", 3)


def test_get_pairs_default(ds: ListDataSequence[str, int]):
    assert ds.get_pairs([1, 3]) == [("b", 1), ("d", 3)]


def test_get_pairs_empty(ds: ListDataSequence[str, int]):
    assert ds.get_pairs([]) == []


# --- __getitem__ -----------------------------------------------------------


def test_getitem_int(ds: ListDataSequence[str, int]):
    assert ds[0] == "a"
    assert ds[4] == "e"


def test_getitem_returns_item_only(ds: ListDataSequence[str, int]):
    # `__getitem__` exposes the item, not the (item, meta) pair.
    assert ds[2] == "c"
    assert not isinstance(ds[2], tuple)


def test_getitem_slice(ds: ListDataSequence[str, int]):
    # Slicing delegates to `get_items(range(start, stop, step))`.
    assert ds[1:4] == ["b", "c", "d"]


def test_getitem_slice_with_step(ds: ListDataSequence[str, int]):
    assert ds[::2] == ["a", "c", "e"]


def test_getitem_slice_reversed(ds: ListDataSequence[str, int]):
    assert ds[::-1] == ["e", "d", "c", "b", "a"]


def test_getitem_slice_empty(ds: ListDataSequence[str, int]):
    assert ds[2:2] == []
    assert ds[10:20] == []


def test_getitem_slice_clips_out_of_range(ds: ListDataSequence[str, int]):
    # `slice.indices(len)` clips; oversize slices do not raise.
    assert ds[-100:100] == ["a", "b", "c", "d", "e"]


# --- inherited Sequence protocol -------------------------------------------


def test_len(ds: ListDataSequence[str, int]):
    assert len(ds) == 5


def test_iter(ds: ListDataSequence[str, int]):
    assert list(iter(ds)) == ["a", "b", "c", "d", "e"]


def test_reversed(ds: ListDataSequence[str, int]):
    assert list(reversed(ds)) == ["e", "d", "c", "b", "a"]


def test_contains(ds: ListDataSequence[str, int]):
    assert "c" in ds
    assert "z" not in ds


def test_index_and_count(ds: ListDataSequence[str, int]):
    assert ds.index("c") == 2
    assert ds.count("a") == 1
    # `count` walks via `__iter__` -> `get_item`; duplicates aggregate.
    dupes = ListDataSequence(items=["x", "y", "x"], metas=[0, 1, 2])
    assert dupes.count("x") == 2


# --- metadata-free subclass (M defaults to None) ---------------------------


def test_metadata_optional_via_none_default():
    """`DataSequence[T]` defaults `M` to `None`; `get_meta` returns `None`."""

    class Bare(DataSequence[str]):
        def __init__(self, items):
            self._items = tuple(items)

        def __len__(self):
            return len(self._items)

        def get_item(self, index):
            return self._items[index]

        def get_meta(self, index):
            return None

    bare = Bare(["x", "y"])
    assert bare[0] == "x"
    assert bare.get_meta(0) is None
    assert bare.get_pair(1) == ("y", None)
