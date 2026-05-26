from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.utils.timer import LapRecord, LapTimer, Timer

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


# --- LapTimer ---------------------------------------------------------------


def test_lap_timer_basic(fake_clock):
    # enter=0, A=100ms, B=250ms, C=400ms, finalize=500ms
    fake_clock(0, 100_000_000, 250_000_000, 400_000_000, 500_000_000)
    with LapTimer("ms") as lt:
        lt.lap("A")
        lt.lap("B")
        lt.lap("C")

    assert [r["label"] for r in lt.records] == ["A", "B", "C"]
    assert lt.records[0]["lap_time"] == 100.0
    assert lt.records[0]["total_time"] == 100.0
    assert lt.records[1]["lap_time"] == 150.0
    assert lt.records[1]["total_time"] == 250.0
    assert lt.records[2]["lap_time"] == 150.0
    assert lt.records[2]["total_time"] == 400.0
    assert lt.final is not None
    assert lt.final["label"] == "End"
    assert lt.final["lap_time"] == 100.0
    assert lt.final["total_time"] == 500.0
    assert lt.total_elapsed == 500.0


def test_lap_timer_summary_aggregates_duplicates(fake_clock):
    # enter=0, A=100ms, B=250ms, A=350ms, finalize=500ms
    fake_clock(0, 100_000_000, 250_000_000, 350_000_000, 500_000_000)
    with LapTimer("ms") as lt:
        lt.lap("A")
        lt.lap("B")
        lt.lap("A")
    assert lt.summary == {"A": 200.0, "B": 150.0}


def test_lap_timer_summary_excludes_final(fake_clock):
    fake_clock(0, 100_000_000, 500_000_000)
    with LapTimer("ms") as lt:
        lt.lap("A")
    assert lt.summary == {"A": 100.0}
    assert lt.final is not None
    assert lt.final["lap_time"] == 400.0


def test_lap_timer_summary_user_can_use_end_label(fake_clock):
    # User's "End" lap is preserved in records AND summary (unlike `final`).
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000)
    with LapTimer("ms") as lt:
        lt.lap("A")
        lt.lap("End")
    assert [r["label"] for r in lt.records] == ["A", "End"]
    assert lt.summary == {"A": 100.0, "End": 100.0}
    assert lt.final is not None
    assert lt.final["label"] == "End"


def test_lap_timer_summary_ndigits_rounds_sum(fake_clock):
    # 100.111111 + 100.111111 = 200.222222 -> rounded to 200.22
    fake_clock(0, 100_111_111, 200_222_222, 300_000_000)
    with LapTimer("ms", ndigits=2) as lt:
        lt.lap("A")
        lt.lap("A")
    assert lt.summary == {"A": 200.22}


def test_lap_timer_invalid_on_same_label():
    with pytest.raises(ValueError, match="on_same_label must be one of"):
        LapTimer(on_same_label="invalid")  # ty: ignore[invalid-argument-type]


def test_lap_timer_merge_keeps_label_as_is(fake_clock):
    fake_clock(0, 100, 200, 300)
    with LapTimer() as lt:
        lt.lap("A")
        lt.lap("A")
    assert [r["label"] for r in lt.records] == ["A", "A"]


def test_lap_timer_reject_raises(fake_clock):
    fake_clock(0, 100, 200)
    with LapTimer(on_same_label="reject") as lt:
        lt.lap("A")
        with pytest.raises(ValueError, match="already used"):
            lt.lap("A")


def test_lap_timer_reject_failed_lap_not_recorded(fake_clock):
    fake_clock(0, 100, 200)
    with LapTimer(on_same_label="reject") as lt:
        lt.lap("A")
        with pytest.raises(ValueError, match="already used"):
            lt.lap("A")  # raises before append
    # Only the successful lap is in records.
    assert len(lt.records) == 1


def test_lap_timer_separate_suffix(fake_clock):
    fake_clock(0, 100, 200, 300, 400)
    with LapTimer(on_same_label="separate") as lt:
        lt.lap("A")
        lt.lap("A")
        lt.lap("A")
    assert [r["label"] for r in lt.records] == ["A", "A (2)", "A (3)"]


def test_lap_timer_auto_end_bypasses_reject_policy(fake_clock):
    # Even in reject mode, the auto-`final` record uses "End" without raising.
    fake_clock(0, 100, 200)
    with LapTimer(on_same_label="reject") as lt:
        lt.lap("End")  # user's "End" — first occurrence, OK
    assert lt.final is not None
    assert lt.final["label"] == "End"


def test_lap_timer_pause_resume_excludes_interval(fake_clock):
    # enter=0, A=100ms, pause=200ms, resume=400ms (pause_dur=200ms),
    # B=500ms, finalize=600ms
    fake_clock(0, 100_000_000, 200_000_000, 400_000_000, 500_000_000, 600_000_000)
    with LapTimer("ms") as lt:
        lt.lap("A")
        lt.pause()
        lt.resume()
        lt.lap("B")
    assert lt.records[0]["lap_time"] == 100.0  # 100 - 0
    # After resume: _start_time=200, _last_time was 100 -> 100+200=300.
    # B at 500: lap_time = 500-300 = 200, total = 500-200 = 300.
    assert lt.records[1]["lap_time"] == 200.0
    assert lt.records[1]["total_time"] == 300.0
    assert lt.final is not None
    assert lt.final["lap_time"] == 100.0  # 600 - 500
    assert lt.total_elapsed == 400.0  # 600 - 200


def test_lap_timer_lap_while_paused_raises(fake_clock):
    fake_clock(0, 100_000_000, 200_000_000, 300_000_000)
    with LapTimer() as lt:
        lt.pause()
        with pytest.raises(RuntimeError, match="while paused"):
            lt.lap("X")


def test_lap_timer_reuse_resets_state(fake_clock):
    # First `with` uses 3 ticks (enter, lap, finalize); second uses the same.
    fake_clock(0, 100, 200, 300, 400, 500)
    lt = LapTimer(on_same_label="reject")
    with lt:
        lt.lap("X")
    assert len(lt.records) == 1
    with lt:
        lt.lap("X")  # would raise if state weren't reset
    assert len(lt.records) == 1
    assert lt.final is not None  # reset and re-populated


def test_lap_timer_empty_run(fake_clock):
    fake_clock(0, 100_000_000)
    with LapTimer("ms") as lt:
        pass
    assert lt.records == []
    assert lt.summary == {}
    assert lt.final is not None
    assert lt.final["label"] == "End"
    assert lt.final["lap_time"] == 100.0
    assert lt.total_elapsed == 100.0


def test_lap_timer_post_exit_lap_raises(fake_clock):
    fake_clock(0, 100)
    lt = LapTimer()
    with lt:
        pass
    with pytest.raises(RuntimeError, match="not been started"):
        lt.lap("X")


def test_lap_timer_final_is_none_before_exit(fake_clock):
    fake_clock(0, 100, 200)
    lt = LapTimer()
    with lt:
        lt.lap("A")
        assert lt.final is None
    assert lt.final is not None


def test_lap_record_typeddict_construction():
    record: LapRecord = {"label": "test", "lap_time": 1.0, "total_time": 2.0}
    assert record == {"label": "test", "lap_time": 1.0, "total_time": 2.0}
