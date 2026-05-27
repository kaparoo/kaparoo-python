from __future__ import annotations

import pytest

from kaparoo.data.sequences import generate_batches

# --- happy path ------------------------------------------------------------


def test_generate_batches_basic_consecutive():
    # size=3, defaults otherwise: overlapping consecutive 3-windows.
    result = list(generate_batches(list(range(10)), size=3))
    assert result == [
        [0, 1, 2],
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
        [4, 5, 6],
        [5, 6, 7],
        [6, 7, 8],
        [7, 8, 9],
    ]


def test_generate_batches_non_overlapping():
    # step == size: non-overlapping windows (the classic "batch" pattern).
    result = list(generate_batches(list(range(10)), size=3, step=3))
    assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


def test_generate_batches_intra_window_skip():
    # skip=2: take every other element within each window.
    result = list(generate_batches(list(range(10)), size=3, skip=2))
    # span = (3-1)*2+1 = 5; windows at head=0..5 (with step=1).
    assert result == [
        [0, 2, 4],
        [1, 3, 5],
        [2, 4, 6],
        [3, 5, 7],
        [4, 6, 8],
        [5, 7, 9],
    ]


def test_generate_batches_combined_step_and_skip():
    # step=2, skip=2 together.
    result = list(generate_batches(list(range(10)), size=3, step=2, skip=2))
    assert result == [[0, 2, 4], [2, 4, 6], [4, 6, 8]]


# --- range bounds ----------------------------------------------------------


def test_generate_batches_with_start_and_stop():
    result = list(generate_batches(list(range(10)), size=3, start=2, stop=8))
    assert result == [[2, 3, 4], [3, 4, 5], [4, 5, 6], [5, 6, 7]]


def test_generate_batches_stop_defaults_to_full_length():
    # Explicit stop=None vs omitting -> same as stop=len(sequence).
    seq = list(range(5))
    assert list(generate_batches(seq, size=3)) == list(
        generate_batches(seq, size=3, stop=None)
    )


def test_generate_batches_empty_range_yields_nothing():
    # start == stop is allowed (Python `range` / slicing convention)
    # and yields no batches.
    assert list(generate_batches(list(range(10)), size=3, start=5, stop=5)) == []
    assert list(generate_batches(list(range(10)), size=3, start=0, stop=0)) == []


def test_generate_batches_source_too_small_drop_last_true():
    # No full window fits; drop_last=True drops everything.
    assert list(generate_batches([1, 2], size=3)) == []


# --- drop_last -------------------------------------------------------------


def test_generate_batches_drop_last_false_yields_partial():
    # 10 items, size=3, step=3: full windows at [0..2], [3..5], [6..8],
    # leaving index 9 as a 1-item partial window.
    result = list(generate_batches(list(range(10)), size=3, step=3, drop_last=False))
    assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_generate_batches_drop_last_false_partial_respects_stop():
    # Regression test: the partial window must not extend past `stop`.
    # 20 items but stop=10; with step=2, size=3, full windows are at
    # head 0, 2, 4, 6 (last full: [6,7,8] fits since tail=9 <= 10).
    # Partial: head=8, but stop=10 means only [8, 9] (NOT [8, 9, 10]).
    result = list(
        generate_batches(
            list(range(20)),
            size=3,
            step=2,
            stop=10,
            drop_last=False,
        )
    )
    assert result == [[0, 1, 2], [2, 3, 4], [4, 5, 6], [6, 7, 8], [8, 9]]
    # Last partial window must not contain 10.
    assert 10 not in result[-1]


def test_generate_batches_drop_last_false_with_full_alignment():
    # When the last full window aligns with `stop`, no partial is yielded
    # even with drop_last=False.
    result = list(generate_batches(list(range(9)), size=3, step=3, drop_last=False))
    assert result == [[0, 1, 2], [3, 4, 5], [6, 7, 8]]


# --- validation ------------------------------------------------------------


def test_generate_batches_rejects_non_positive_size_step_skip():
    for bad in (0, -1):
        with pytest.raises(ValueError, match="must be positive"):
            list(generate_batches(list(range(10)), size=bad))
        with pytest.raises(ValueError, match="must be positive"):
            list(generate_batches(list(range(10)), size=3, step=bad))
        with pytest.raises(ValueError, match="must be positive"):
            list(generate_batches(list(range(10)), size=3, skip=bad))


def test_generate_batches_rejects_invalid_range():
    seq = list(range(10))
    # start < 0
    with pytest.raises(ValueError, match="invalid range"):
        list(generate_batches(seq, size=3, start=-1))
    # stop > len
    with pytest.raises(ValueError, match="invalid range"):
        list(generate_batches(seq, size=3, stop=11))
    # start > stop
    with pytest.raises(ValueError, match="invalid range"):
        list(generate_batches(seq, size=3, start=5, stop=3))


def test_generate_batches_keyword_only_after_size():
    # Positional call past `size` must fail -- step/skip/start/stop/
    # drop_last are keyword-only.
    seq = list(range(10))
    with pytest.raises(TypeError):
        # Trying to pass step positionally.
        list(generate_batches(seq, 3, 2))  # ty: ignore[too-many-positional-arguments]
