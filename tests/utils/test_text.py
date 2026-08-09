from __future__ import annotations

from kaparoo.utils import quantify


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
