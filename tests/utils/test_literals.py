from __future__ import annotations

from typing import Literal

import pytest

from kaparoo.utils import literal_values

type _Policy = Literal["error", "reuse"]
type _Chained = _Policy
type _PlainInt = int


def test_reads_a_plain_literal():
    assert literal_values(Literal["a", "b", "c"]) == ("a", "b", "c")


def test_reads_through_a_pep695_alias():
    assert literal_values(_Policy) == ("error", "reuse")


def test_reads_through_a_chained_alias():
    assert literal_values(_Chained) == ("error", "reuse")


def test_rejects_a_non_literal_alias():
    with pytest.raises(TypeError, match="expected a Literal"):
        literal_values(_PlainInt)


def test_rejects_a_plain_type():
    with pytest.raises(TypeError, match="expected a Literal"):
        literal_values(int)
