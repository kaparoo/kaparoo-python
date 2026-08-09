from __future__ import annotations

from enum import Enum

import pytest

from kaparoo.utils import resolve_enum


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
    UNKNOWN = 4


def test_resolves_case_insensitively():
    assert resolve_enum("red", Color) is Color.RED
    assert resolve_enum("GREEN", Color) is Color.GREEN


def test_case_sensitive_lookup():
    assert resolve_enum("RED", Color, case_sensitive=True) is Color.RED
    with pytest.raises(ValueError, match="must be one of"):
        resolve_enum("red", Color, case_sensitive=True)


def test_exclude_rejects_the_member():
    with pytest.raises(ValueError, match="must be one of") as info:
        resolve_enum("unknown", Color, exclude=(Color.UNKNOWN,))
    assert "UNKNOWN" not in str(info.value)


def test_exclude_still_allows_other_members():
    assert resolve_enum("red", Color, exclude=(Color.UNKNOWN,)) is Color.RED


def test_unknown_name_names_the_options():
    with pytest.raises(ValueError, match=r"must be one of .* \(got 'nope'\)"):
        resolve_enum("nope", Color)
