from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.utils.timer import SegmentRecord, SegmentTimer, Timer

if TYPE_CHECKING:
    from collections.abc import Callable


# --- fixtures ---------------------------------------------------------------


@pytest.fixture()
def fake_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., None]:
    """Install a deterministic `time.perf_counter_ns` returning the given ns values."""

    def install(*values: int) -> None:
        sequence = list(values)
        index = [0]

        def clock() -> int:
            if index[0] >= len(sequence):
                msg = f"FakeClock exhausted after {index[0]} calls"
                raise RuntimeError(msg)
            value = sequence[index[0]]
            index[0] += 1
            return value

        monkeypatch.setattr(
            "kaparoo.utils.timer.time.perf_counter_ns",
            clock,
        )

    return install


# --- Timer ------------------------------------------------------------------


def test_timer_basic(fake_clock):
    fake_clock(0, 500_000_000)
    with Timer("ms") as t:
        pass
    assert t.elapsed == 500.0


@pytest.mark.parametrize(
    ("unit", "expected"),
    (
        ("s", 1.5),
        ("ms", 1500.0),
        ("us", 1_500_000.0),
        ("ns", 1_500_000_000.0),
    ),
)
def test_timer_units(fake_clock, unit: str, expected: float):
    fake_clock(0, 1_500_000_000)
    with Timer(unit) as t:  # ty: ignore[invalid-argument-type]
        pass
    assert t.elapsed == expected


def test_timer_ndigits_rounds(fake_clock):
    fake_clock(0, 123_456_789)
    with Timer("ms", ndigits=2) as t:
        pass
    assert t.elapsed == 123.46


def test_timer_no_ndigits_is_exact(fake_clock):
    fake_clock(0, 123_456_789)
    with Timer("ms") as t:
        pass
    assert t.elapsed == pytest.approx(123.456789)


def test_timer_invalid_unit():
    with pytest.raises(ValueError, match="unit must be one of"):
        Timer("invalid")  # ty: ignore[invalid-argument-type]


def test_timer_pause_resume_excludes_pause_interval(fake_clock):
    # enter=0, pause=100ms, resume=300ms (pause_dur=200ms -> _start_time=200ms),
    # finalize=500ms -> elapsed = 500 - 200 = 300ms
    fake_clock(0, 100_000_000, 300_000_000, 500_000_000)
    with Timer("ms") as t:
        t.pause()
        t.resume()
    assert t.elapsed == 300.0


def test_timer_suspend_excludes_block(fake_clock):
    fake_clock(0, 100_000_000, 300_000_000, 500_000_000)
    with Timer("ms") as t, t.suspend():
        pass
    assert t.elapsed == 300.0


def test_timer_suspend_skips_auto_resume_after_manual_resume(fake_clock):
    # enter=0, suspend's pause=100ms, manual resume=300ms (pause_dur=200ms),
    # finalize=500ms. The `finally` in suspend() must observe `_is_paused`
    # is False and skip the auto-resume -- a second `resume()` would raise.
    fake_clock(0, 100_000_000, 300_000_000, 500_000_000)
    with Timer("ms") as t, t.suspend():
        t.resume()
    assert t.elapsed == 300.0


def test_timer_auto_resumes_on_exit_while_paused(fake_clock):
    # enter=0, pause=100ms, (no manual resume),
    # __exit__: resume at 300ms -> _start_time=200ms, finalize at 500ms -> elapsed=300ms
    fake_clock(0, 100_000_000, 300_000_000, 500_000_000)
    with Timer("ms") as t:
        t.pause()
    assert t.elapsed == 300.0


def test_timer_pause_when_already_paused_raises(fake_clock):
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000)
    t = Timer()
    with t:
        t.pause()
        with pytest.raises(RuntimeError, match="already paused"):
            t.pause()


def test_timer_resume_when_not_paused_raises(fake_clock):
    fake_clock(0, 100_000_000)
    t = Timer()
    with t, pytest.raises(RuntimeError, match="not paused"):
        t.resume()


def test_timer_unstarted_pause_raises():
    t = Timer()
    with pytest.raises(RuntimeError, match="not been started"):
        t.pause()


def test_timer_unstarted_resume_raises():
    t = Timer()
    with pytest.raises(RuntimeError, match="not been started"):
        t.resume()


def test_timer_post_exit_pause_raises(fake_clock):
    fake_clock(0, 100_000_000)
    t = Timer()
    with t:
        pass
    with pytest.raises(RuntimeError, match="not been started"):
        t.pause()


def test_timer_reuse(fake_clock):
    fake_clock(0, 100_000_000, 200_000_000, 250_000_000)
    t = Timer("ms")
    with t:
        pass
    assert t.elapsed == 100.0
    with t:
        pass
    assert t.elapsed == 50.0


def test_timer_reentrant_use_raises(fake_clock):
    # Re-entering a still-running instance must fail loudly rather than
    # silently corrupting the outer measurement.
    fake_clock(0, 100_000_000)
    t = Timer("ms")
    with t, pytest.raises(RuntimeError, match="not reentrant"):  # noqa: SIM117
        with t:
            pass


def test_timer_as_decorator(fake_clock):
    fake_clock(0, 100_000_000)
    t = Timer("ms")

    @t
    def f() -> None:
        return

    f()
    assert t.elapsed == 100.0


def test_base_timer_is_abstract():
    from kaparoo.utils.timer import BaseTimer

    with pytest.raises(TypeError, match="abstract"):
        BaseTimer()  # ty: ignore


def test_timer_elapsed_default_is_zero():
    # `elapsed` is documented as 0.0 until the first exit.
    assert Timer().elapsed == 0.0


# --- SegmentTimer ---------------------------------------------------------------


def test_segment_timer_basic(fake_clock):
    # enter=0, A=100ms, B=250ms, C=400ms, finalize=500ms
    fake_clock(0, 100_000_000, 250_000_000, 400_000_000, 500_000_000)
    with SegmentTimer("ms") as st:
        st.lap("A")
        st.lap("B")
        st.lap("C")

    assert [r["label"] for r in st.records] == ["A", "B", "C"]
    assert st.records[0]["duration"] == 100.0
    assert st.records[0]["total_time"] == 100.0
    assert st.records[1]["duration"] == 150.0
    assert st.records[1]["total_time"] == 250.0
    assert st.records[2]["duration"] == 150.0
    assert st.records[2]["total_time"] == 400.0
    assert st.elapsed == 500.0


def test_segment_timer_summary_aggregates_duplicates(fake_clock):
    # enter=0, A=100ms, B=250ms, A=350ms, finalize=500ms
    fake_clock(0, 100_000_000, 250_000_000, 350_000_000, 500_000_000)
    with SegmentTimer("ms") as st:
        st.lap("A")
        st.lap("B")
        st.lap("A")
    assert st.summary == {"A": 200.0, "B": 150.0}


def test_segment_timer_summary_excludes_trailing_time(fake_clock):
    # The 400ms gap between the last lap and exit does NOT show up in summary
    # (summary only aggregates explicit duration values).
    fake_clock(0, 100_000_000, 500_000_000)
    with SegmentTimer("ms") as st:
        st.lap("A")
    assert st.summary == {"A": 100.0}
    assert st.elapsed == 500.0


def test_segment_timer_summary_ndigits_rounds_sum(fake_clock):
    # 100.111111 + 100.111111 = 200.222222 -> rounded to 200.22
    fake_clock(0, 100_111_111, 200_222_222, 300_000_000)
    with SegmentTimer("ms", ndigits=2) as st:
        st.lap("A")
        st.lap("A")
    assert st.summary == {"A": 200.22}


def test_segment_timer_invalid_on_same_label():
    with pytest.raises(ValueError, match="on_same_label must be one of"):
        SegmentTimer(on_same_label="invalid")  # ty: ignore[invalid-argument-type]


def test_segment_timer_merge_keeps_label_as_is(fake_clock):
    fake_clock(0, 100, 200, 300)
    with SegmentTimer() as st:
        st.lap("A")
        st.lap("A")
    assert [r["label"] for r in st.records] == ["A", "A"]


def test_segment_timer_reject_raises(fake_clock):
    fake_clock(0, 100, 200)
    with SegmentTimer(on_same_label="reject") as st:
        st.lap("A")
        with pytest.raises(ValueError, match="already used"):
            st.lap("A")


def test_segment_timer_reject_failed_lap_not_recorded(fake_clock):
    fake_clock(0, 100, 200)
    with SegmentTimer(on_same_label="reject") as st:
        st.lap("A")
        with pytest.raises(ValueError, match="already used"):
            st.lap("A")  # raises before append
    # Only the successful lap is in records.
    assert len(st.records) == 1


def test_segment_timer_separate_suffix(fake_clock):
    fake_clock(0, 100, 200, 300, 400)
    with SegmentTimer(on_same_label="separate") as st:
        st.lap("A")
        st.lap("A")
        st.lap("A")
    assert [r["label"] for r in st.records] == ["A", "A (2)", "A (3)"]


def test_segment_timer_pause_resume_excludes_interval(fake_clock):
    # enter=0, A=100ms, pause=200ms, resume=400ms (pause_dur=200ms),
    # B=500ms, finalize=600ms
    fake_clock(0, 100_000_000, 200_000_000, 400_000_000, 500_000_000, 600_000_000)
    with SegmentTimer("ms") as st:
        st.lap("A")
        st.pause()
        st.resume()
        st.lap("B")
    assert st.records[0]["duration"] == 100.0  # 100 - 0
    # After resume: _start_time=200, _last_time was 100 -> 100+200=300.
    # B at 500: duration = 500-300 = 200, total = 500-200 = 300.
    assert st.records[1]["duration"] == 200.0
    assert st.records[1]["total_time"] == 300.0
    assert st.elapsed == 400.0  # 600 - 200


def test_segment_timer_lap_while_paused_raises(fake_clock):
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000)
    with SegmentTimer() as st:
        st.pause()
        with pytest.raises(RuntimeError, match="while paused"):
            st.lap("X")


def test_segment_timer_reuse_resets_state(fake_clock):
    # First `with` uses 3 ticks (enter, lap, finalize); second uses the same.
    fake_clock(0, 100, 200, 300, 400, 500)
    st = SegmentTimer(on_same_label="reject")
    with st:
        st.lap("X")
    assert len(st.records) == 1
    with st:
        st.lap("X")  # would raise if state weren't reset
    assert len(st.records) == 1


def test_segment_timer_empty_run(fake_clock):
    fake_clock(0, 100_000_000)
    with SegmentTimer("ms") as st:
        pass
    assert st.records == []
    assert st.summary == {}
    assert st.elapsed == 100.0


def test_segment_timer_post_exit_lap_raises(fake_clock):
    fake_clock(0, 100)
    st = SegmentTimer()
    with st:
        pass
    with pytest.raises(RuntimeError, match="not been started"):
        st.lap("X")


def test_segment_record_typeddict_construction():
    record: SegmentRecord = {"label": "test", "duration": 1.0, "total_time": 2.0}
    assert record == {"label": "test", "duration": 1.0, "total_time": 2.0}


def test_segment_timer_defaults_are_empty():
    # Documented defaults before the first `__enter__`.
    st = SegmentTimer()
    assert st.elapsed == 0.0
    assert st.records == []
    assert st.summary == {}


# --- SegmentTimer.measure ---------------------------------------------------


def test_segment_timer_measure_records_block_only(fake_clock):
    # enter=0, setup gap (untimed), block start=100ms, block end=250ms,
    # finalize=300ms. The 0->100 gap is excluded from the "A" segment.
    fake_clock(0, 100_000_000, 250_000_000, 300_000_000)
    with SegmentTimer("ms") as st:  # noqa: SIM117
        with st.measure("A"):
            pass
    assert st.records[0]["label"] == "A"
    assert st.records[0]["duration"] == 150.0  # 250 - 100, not 250 - 0
    assert st.records[0]["total_time"] == 250.0  # since start
    assert st.summary == {"A": 150.0}
    assert st.elapsed == 300.0


def test_segment_timer_measure_excludes_time_between_blocks(fake_clock):
    # Two blocks with untimed gaps before, between, and after; summary sums
    # only the wrapped spans (100 + 150), well under elapsed (600).
    fake_clock(0, 100_000_000, 200_000_000, 350_000_000, 500_000_000, 600_000_000)
    with SegmentTimer("ms") as st:
        with st.measure("A"):
            pass
        with st.measure("B"):
            pass
    assert st.summary == {"A": 100.0, "B": 150.0}
    assert st.elapsed == 600.0


def test_segment_timer_measure_as_decorator(fake_clock):
    # enter=0, block start=100ms, block end=300ms, finalize=400ms.
    fake_clock(0, 100_000_000, 300_000_000, 400_000_000)
    st = SegmentTimer("ms")

    @st.measure("load")
    def load() -> None:
        return

    with st:
        load()
    assert st.records == [{"label": "load", "duration": 200.0, "total_time": 300.0}]
    assert st.elapsed == 400.0


def test_segment_timer_measure_excludes_pause(fake_clock):
    # enter=0, block start=100ms, pause=200ms, resume=400ms (pause_dur=200ms),
    # block end=500ms, finalize=600ms. duration excludes the 200ms pause.
    fake_clock(0, 100_000_000, 200_000_000, 400_000_000, 500_000_000, 600_000_000)
    with SegmentTimer("ms") as st:  # noqa: SIM117
        with st.measure("A"):
            st.pause()
            st.resume()
    assert st.records[0]["duration"] == 200.0  # 500 - (100 + 200 pause)
    assert st.records[0]["total_time"] == 300.0  # 500 - (0 + 200 pause)
    assert st.elapsed == 400.0  # 600 - 200 pause


def test_segment_timer_measure_not_recorded_on_exception(fake_clock):
    # enter=0, block start=100ms, body raises (no lap recorded), finalize=300ms.
    fake_clock(0, 100_000_000, 300_000_000)
    with SegmentTimer("ms") as st:
        msg = "boom"
        with pytest.raises(ValueError, match="boom"):  # noqa: SIM117
            with st.measure("A"):
                raise ValueError(msg)
        assert st.records == []  # nothing recorded on a failed block


def test_segment_timer_measure_while_paused_raises(fake_clock):
    # enter=0, pause=100ms, then __exit__ resume=200ms, finalize=300ms.
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000)
    with SegmentTimer("ms") as st:
        st.pause()
        with pytest.raises(RuntimeError, match="while paused"):  # noqa: SIM117
            with st.measure("A"):
                pass


def test_segment_timer_measure_unstarted_raises():
    st = SegmentTimer()
    with pytest.raises(RuntimeError, match="not been started"):  # noqa: SIM117
        with st.measure("A"):
            pass


def test_segment_timer_measure_respects_on_same_label(fake_clock):
    # First block records "A"; the second reuses "A" under reject and raises
    # on exit, leaving only the first segment.
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000, 400_000_000)
    with SegmentTimer("ms", on_same_label="reject") as st:
        with st.measure("A"):
            pass
        with pytest.raises(ValueError, match="already used"):  # noqa: SIM117
            with st.measure("A"):
                pass
    assert len(st.records) == 1
    assert st.records[0]["label"] == "A"


def test_segment_timer_lap_and_measure_mixed(fake_clock):
    # lap("A") splits from start; the 100->250 gap before measure("B") is
    # dropped; lap("C") resumes from B's end.
    fake_clock(0, 100_000_000, 250_000_000, 400_000_000, 500_000_000, 600_000_000)
    with SegmentTimer("ms") as st:
        st.lap("A")
        with st.measure("B"):
            pass
        st.lap("C")
    assert [r["label"] for r in st.records] == ["A", "B", "C"]
    assert [r["duration"] for r in st.records] == [100.0, 150.0, 100.0]
    assert st.summary == {"A": 100.0, "B": 150.0, "C": 100.0}
