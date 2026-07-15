from __future__ import annotations

from kaparoo.filters import (
    And,
    Any,
    AnyFilter,
    EndsWithFilter,
    Equals,
    Expandable,
    Filter,
    LogicalFilter,
    Not,
    Or,
    PatternFilter,
)

# --- matching --------------------------------------------------------------


def test_any_matches_every_string():
    f = AnyFilter()
    assert f.matches("")
    assert f.matches("anything")
    assert f.matches("a/b/c.txt")
    assert f.matches("\n\t ")
    assert f.matches("ß🌟")


# --- identity in the type hierarchy ----------------------------------------


def test_any_isinstance_chain():
    f = AnyFilter()
    assert isinstance(f, Filter)
    assert not isinstance(f, PatternFilter)
    assert not isinstance(f, LogicalFilter)


def test_any_is_not_expandable():
    # The matching set is infinite, so `Any` cannot enumerate names.
    assert not isinstance(AnyFilter(), Expandable)


# --- value semantics -------------------------------------------------------


def test_any_instances_are_equal_and_hashable():
    assert AnyFilter() == AnyFilter()
    assert hash(AnyFilter()) == hash(AnyFilter())
    assert len({AnyFilter(), AnyFilter()}) == 1


# --- composition (identity / absorbing element) ----------------------------


def test_any_is_identity_of_and():
    base = EndsWithFilter(".py")
    f = And((base, Any()))
    assert f.matches("module.py") == base.matches("module.py")
    assert f.matches("module.txt") == base.matches("module.txt")


def test_any_is_absorbing_element_of_or():
    f = Or((Equals("only-this"), Any()))
    assert f.matches("only-this")
    assert f.matches("anything-else")


def test_not_any_matches_nothing():
    f = Not(Any())
    assert not f.matches("")
    assert not f.matches("anything")


# --- serialization ---------------------------------------------------------


def test_any_to_dict_is_kind_only():
    assert AnyFilter().to_dict() == {"kind": "any"}


def test_any_round_trip():
    f = AnyFilter()
    assert Filter.from_dict(f.to_dict()) == f


def test_any_from_dict_ignores_extra_fields():
    assert Filter.from_dict({"kind": "any"}) == AnyFilter()


def test_any_parse_passes_through_instance_and_dict():
    f = AnyFilter()
    assert Filter.parse(f) is f
    assert Filter.parse({"kind": "any"}) == f


def test_any_nested_round_trip():
    f = And((EndsWithFilter(".py"), Not(Any())))
    assert Filter.from_dict(f.to_dict()) == f


# --- aliases and repr ------------------------------------------------------


def test_any_alias_is_canonical_class():
    assert Any is AnyFilter


def test_any_repr_uses_concise_alias_name():
    assert repr(AnyFilter()) == "Any()"
    assert repr(And((EndsWithFilter(".py"), Any()))) == "And(EndsWith('.py'), Any())"
