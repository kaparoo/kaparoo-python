from __future__ import annotations

import pytest

from kaparoo.filters import (
    And,
    AndFilter,
    EndsWithAnyFilter,
    EndsWithFilter,
    EqualsFilter,
    Filter,
    GlobFilter,
    LogicalFilter,
    MultiPatternFilter,
    Not,
    NotFilter,
    Or,
    OrFilter,
    PatternFilter,
    StartsWithFilter,
)

# --- abstract base ---------------------------------------------------------


def test_logical_filter_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        LogicalFilter()  # ty: ignore


def test_logical_filter_isinstance_chain():
    a = AndFilter((EqualsFilter("a"),))
    assert isinstance(a, LogicalFilter)
    assert isinstance(a, Filter)
    assert not isinstance(a, PatternFilter)
    assert not isinstance(a, MultiPatternFilter)


# --- AndFilter -------------------------------------------------------------


def test_and_all_children_must_match():
    f = AndFilter((StartsWithFilter("a"), EndsWithFilter("z")))
    assert f.matches("abz")
    assert not f.matches("abx")
    assert not f.matches("xbz")


def test_and_empty_children_raises():
    with pytest.raises(ValueError, match="requires at least one"):
        AndFilter(())


def test_and_single_child():
    f = AndFilter((EqualsFilter("foo"),))
    assert f.matches("foo")
    assert not f.matches("bar")


# --- OrFilter --------------------------------------------------------------


def test_or_any_child_matches():
    f = OrFilter((EqualsFilter("a"), EqualsFilter("b")))
    assert f.matches("a")
    assert f.matches("b")
    assert not f.matches("c")


def test_or_empty_children_raises():
    with pytest.raises(ValueError, match="requires at least one"):
        OrFilter(())


# --- NotFilter -------------------------------------------------------------


def test_not_inverts_child_result():
    f = NotFilter(EqualsFilter("foo"))
    assert not f.matches("foo")
    assert f.matches("bar")


def test_not_double_negation_recovers_original():
    f = NotFilter(NotFilter(EqualsFilter("foo")))
    assert f.matches("foo")
    assert not f.matches("bar")


# --- Nesting (matching behavior across families) ---------------------------


def test_nested_and_or_not_combination():
    # Python files but not __init__.py
    f = AndFilter((EndsWithFilter(".py"), NotFilter(EqualsFilter("__init__.py"))))
    assert f.matches("foo.py")
    assert not f.matches("__init__.py")
    assert not f.matches("foo.txt")


def test_nested_multi_pattern_with_logical():
    # Image files OR favicon
    f = OrFilter((EndsWithAnyFilter((".png", ".jpg")), EqualsFilter("favicon.ico")))
    assert f.matches("photo.png")
    assert f.matches("favicon.ico")
    assert not f.matches("photo.gif")


# --- serialization ---------------------------------------------------------


def test_and_round_trip():
    f = AndFilter((GlobFilter("*.py"), EndsWithFilter("_test.py")))
    assert Filter.from_dict(f.to_dict()) == f


def test_or_round_trip():
    f = OrFilter((EqualsFilter("a"), EqualsFilter("b")))
    assert Filter.from_dict(f.to_dict()) == f


def test_not_round_trip():
    f = NotFilter(EqualsFilter("excluded"))
    assert Filter.from_dict(f.to_dict()) == f


def test_deeply_nested_round_trip():
    f = AndFilter(
        (
            GlobFilter("*.py"),
            NotFilter(
                OrFilter(
                    (
                        EqualsFilter("__init__.py"),
                        EndsWithAnyFilter((".bak", ".swp")),
                    )
                ),
            ),
        )
    )
    assert Filter.from_dict(f.to_dict()) == f


def test_and_to_dict_uses_kind_children():
    d = AndFilter((EqualsFilter("a"), EqualsFilter("b"))).to_dict()
    assert d["kind"] == "and"
    assert isinstance(d["children"], list)
    assert len(d["children"]) == 2
    assert d["children"][0] == {"kind": "equals", "pattern": "a"}


def test_or_to_dict_uses_kind_children():
    d = OrFilter((EqualsFilter("a"),)).to_dict()
    assert d["kind"] == "or"
    assert d["children"] == [{"kind": "equals", "pattern": "a"}]


def test_not_to_dict_uses_kind_child():
    d = NotFilter(EqualsFilter("x")).to_dict()
    assert d == {
        "kind": "not",
        "child": {"kind": "equals", "pattern": "x"},
    }


# --- aliases ---------------------------------------------------------------


def test_logical_aliases_are_canonical_classes():
    assert And is AndFilter
    assert Or is OrFilter
    assert Not is NotFilter


def test_repr_uses_concise_alias_name():
    nested = AndFilter((GlobFilter("*.py"), NotFilter(EqualsFilter("__init__.py"))))
    assert repr(nested) == "And(Glob('*.py'), Not(Equals('__init__.py')))"
    assert repr(NotFilter(EqualsFilter("x"))) == "Not(Equals('x'))"
