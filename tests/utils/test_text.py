from __future__ import annotations

import pytest

from kaparoo.utils import quantify, strrange


def test_singular():
    assert quantify(1, "frame") == "1 frame"


def test_regular_plural():
    assert quantify(3, "frame") == "3 frames"


def test_zero_is_plural():
    assert quantify(0, "frame") == "0 frames"


def test_negative_is_plural():
    assert quantify(-1, "frame") == "-1 frames"


def test_explicit_plural():
    assert quantify(3, "entry", "entries") == "3 entries"


def test_explicit_plural_unused_when_singular():
    assert quantify(1, "entry", "entries") == "1 entry"


# --- strrange --------------------------------------------------------------


def test_stop_only_mirrors_range():
    assert strrange(3) == ("0", "1", "2")


def test_start_and_stop():
    assert strrange(1, 4) == ("1", "2", "3")


def test_start_stop_and_step():
    assert strrange(0, 10, 2) == ("0", "2", "4", "6", "8")


def test_a_range_may_be_given_whole():
    assert strrange(range(2, 5)) == strrange(2, 5) == ("2", "3", "4")


def test_template_formats_each_value():
    assert strrange(8, template="{:03d}") == (
        "000",
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
        "007",
    )


def test_template_applies_to_every_form():
    assert strrange(0, 10, 2, template="{:02d}") == ("00", "02", "04", "06", "08")
    assert strrange(range(3), template="{:+d}") == ("+0", "+1", "+2")


def test_a_template_may_carry_a_prefix_and_suffix():
    assert strrange(3, template="cam_{}") == ("cam_0", "cam_1", "cam_2")
    assert strrange(3, template="{:04d}.png") == ("0000.png", "0001.png", "0002.png")
    assert strrange(2, template="frame_{:05d}.npy") == (
        "frame_00000.npy",
        "frame_00001.npy",
    )


def test_a_template_with_too_many_fields_is_refused():
    with pytest.raises(IndexError):
        strrange(3, template="{}_{}")


def test_a_template_with_a_named_field_is_refused():
    with pytest.raises(KeyError):
        strrange(3, template="{name}")


def test_an_empty_range_never_reaches_a_broken_template():
    # Nothing is formatted, so nothing can raise -- documented on the function.
    assert strrange(0, template="{}_{}") == ()


def test_a_negative_step_keeps_the_range_order():
    assert strrange(3, 0, -1) == ("3", "2", "1")


def test_an_empty_range_gives_nothing():
    assert strrange(0) == ()
    assert strrange(5, 5) == ()
    assert strrange(range(0)) == ()


def test_a_range_with_a_stop_or_step_is_refused():
    # The two forms would disagree about which range is meant.
    with pytest.raises(TypeError, match="range alone"):
        strrange(range(3), 5)  # ty: ignore[no-matching-overload]
    with pytest.raises(TypeError, match="range alone"):
        strrange(range(3), None, 2)  # ty: ignore[no-matching-overload]


def test_a_zero_step_is_refused():
    with pytest.raises(ValueError, match="arg 3 must not be zero"):
        strrange(0, 10, 0)


def test_a_template_spec_that_does_not_apply_to_an_integer_is_refused():
    with pytest.raises(ValueError, match="Unknown format code"):
        strrange(3, template="{:s}")
