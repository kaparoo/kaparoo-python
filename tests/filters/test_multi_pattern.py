from __future__ import annotations

import pytest

from kaparoo.filters import (
    ContainsAny,
    ContainsAnyFilter,
    EndsWithAny,
    EndsWithAnyFilter,
    EqualsAny,
    EqualsAnyFilter,
    EqualsFilter,
    Filter,
    LogicalFilter,
    MultiPatternFilter,
    PatternFilter,
    StartsWithAny,
    StartsWithAnyFilter,
)

# --- abstract base ---------------------------------------------------------


def test_multi_pattern_filter_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        MultiPatternFilter(("foo",))  # ty: ignore


def test_multi_pattern_filter_isinstance_chain():
    ea = EqualsAnyFilter(("a",))
    assert isinstance(ea, MultiPatternFilter)
    assert isinstance(ea, Filter)
    assert not isinstance(ea, PatternFilter)
    assert not isinstance(ea, LogicalFilter)


# --- shared behaviors (parametrized over all 4 concretes) ------------------


_MULTI_PATTERN_CLASSES = (
    EqualsAnyFilter,
    StartsWithAnyFilter,
    EndsWithAnyFilter,
    ContainsAnyFilter,
)


@pytest.mark.parametrize("cls", _MULTI_PATTERN_CLASSES)
def test_multi_pattern_empty_patterns_raises(cls: type[MultiPatternFilter]):
    with pytest.raises(ValueError, match="requires at least one pattern"):
        cls(())


@pytest.mark.parametrize("cls", _MULTI_PATTERN_CLASSES)
def test_multi_pattern_dedup_exact_duplicates(cls: type[MultiPatternFilter]):
    f = cls(("a", "b", "a", "c", "b"))
    assert f.patterns == ("a", "b", "c")


@pytest.mark.parametrize("cls", _MULTI_PATTERN_CLASSES)
def test_multi_pattern_dedup_case_insensitive(cls: type[MultiPatternFilter]):
    f = cls(("FOO", "foo", "BAR", "bar"), case_sensitive=False)
    assert f.patterns == ("foo", "bar")


@pytest.mark.parametrize("cls", _MULTI_PATTERN_CLASSES)
def test_multi_pattern_preserves_first_seen_order(cls: type[MultiPatternFilter]):
    f = cls(("z", "a", "m"))
    assert f.patterns == ("z", "a", "m")


@pytest.mark.parametrize("cls", _MULTI_PATTERN_CLASSES)
def test_multi_pattern_coerces_list_to_tuple(cls: type[MultiPatternFilter]):
    # The annotation says tuple, but a list reaches construction unenforced.
    # `patterns` must always end up a tuple -- `str.startswith` / `endswith`
    # reject a list, so a stored list would crash `matches` later.
    f = cls(["a", "b"])
    assert isinstance(f.patterns, tuple)
    assert f.patterns == ("a", "b")


def test_startswith_endswith_match_when_built_from_list():
    # Guards the tuple contract specifically for the filters that pass
    # `patterns` straight to `str.startswith` / `str.endswith`.
    assert StartsWithAnyFilter(["test_", "spec_"]).matches("test_foo")
    assert EndsWithAnyFilter([".png", ".jpg"]).matches("photo.png")


# --- EqualsAnyFilter -------------------------------------------------------


def test_equals_any_matches():
    f = EqualsAnyFilter(("foo", "bar"))
    assert f.matches("foo")
    assert f.matches("bar")
    assert not f.matches("foobar")
    assert not f.matches("baz")


def test_equals_any_case_insensitive():
    f = EqualsAnyFilter(("FOO", "BAR"), case_sensitive=False)
    assert f.matches("foo")
    assert f.matches("BAR")
    assert not f.matches("baz")


# --- StartsWithAnyFilter ---------------------------------------------------


def test_startswith_any_matches():
    f = StartsWithAnyFilter(("test_", "conftest", "fix_"))
    assert f.matches("test_foo")
    assert f.matches("conftest.py")
    assert f.matches("fix_123")
    assert not f.matches("foo_test")


# --- EndsWithAnyFilter -----------------------------------------------------


def test_endswith_any_matches():
    f = EndsWithAnyFilter((".png", ".jpg", ".jpeg"))
    assert f.matches("photo.png")
    assert f.matches("photo.jpeg")
    assert not f.matches("photo.gif")


def test_endswith_any_case_insensitive():
    f = EndsWithAnyFilter((".PNG", ".JPG"), case_sensitive=False)
    assert f.matches("photo.png")
    assert f.matches("photo.PNG")


# --- ContainsAnyFilter -----------------------------------------------------


def test_contains_any_matches():
    f = ContainsAnyFilter(("TODO", "FIXME"))
    assert f.matches("// TODO: fix this")
    assert f.matches("FIXME later")
    assert not f.matches("all good")


def test_contains_any_case_insensitive():
    f = ContainsAnyFilter(("TODO", "FIXME"), case_sensitive=False)
    assert f.matches("// todo: fix")
    assert f.matches("fixme later")


# --- serialization (per-kind round-trip) -----------------------------------


@pytest.mark.parametrize(
    ("filter_", "expected_kind"),
    (
        (EqualsAnyFilter(("a.py", "b.py")), "equals_any"),
        (StartsWithAnyFilter(("test_", "spec_")), "starts_with_any"),
        (EndsWithAnyFilter((".log", ".bak")), "ends_with_any"),
        (ContainsAnyFilter(("data", "info")), "contains_any"),
    ),
)
def test_multi_pattern_round_trip(filter_: MultiPatternFilter, expected_kind: str):
    d = filter_.to_dict()
    assert d["kind"] == expected_kind
    restored = Filter.from_dict(d)
    assert restored == filter_


def test_multi_pattern_to_dict_uses_list():
    # JSON-friendly: list, not tuple
    d = EqualsAnyFilter(("a", "b")).to_dict()
    assert isinstance(d["patterns"], list)
    assert d["patterns"] == ["a", "b"]


def test_multi_pattern_from_dict_normalizes_to_tuple():
    f = EqualsAnyFilter.from_dict({"kind": "equals_any", "patterns": ["a", "b"]})
    assert f.patterns == ("a", "b")


def test_multi_pattern_dedup_after_case_fold_round_trips():
    # Construction casefolds and dedups; serialized form already deduped.
    f = EqualsAnyFilter(("Foo", "FOO", "foo"), case_sensitive=False)
    assert f.patterns == ("foo",)
    assert Filter.from_dict(f.to_dict()) == f


def test_multi_pattern_to_dict_omits_default_case_sensitive():
    d = EqualsAnyFilter(("a",)).to_dict()
    assert "case_sensitive" not in d


# --- aliases ---------------------------------------------------------------


def test_multi_pattern_aliases_are_canonical_classes():
    assert EqualsAny is EqualsAnyFilter
    assert StartsWithAny is StartsWithAnyFilter
    assert EndsWithAny is EndsWithAnyFilter
    assert ContainsAny is ContainsAnyFilter


# --- shared base context (used by serialization recursion) -----------------


def test_nested_multi_pattern_with_logical_filter_works():
    # Sanity check that MultiPatternFilter composes with non-logical filters
    # via plain equality (no special wiring needed).
    f1 = EqualsAnyFilter(("a", "b"))
    f2 = EqualsAnyFilter(("a", "b"))
    assert f1 == f2
    # Sanity: trivial filter usable with a single PatternFilter via equality
    assert EqualsFilter("a") != f1


def test_repr_is_concise():
    assert repr(EqualsAnyFilter(("a", "b"))) == "EqualsAnyFilter(('a', 'b'))"
    assert (
        repr(EqualsAnyFilter(("a",), case_sensitive=False))
        == "EqualsAnyFilter(('a',), case_sensitive=False)"
    )
