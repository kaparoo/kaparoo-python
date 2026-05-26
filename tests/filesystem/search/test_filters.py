from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kaparoo.filesystem.search.filters import (
    And,
    AndFilter,
    Contains,
    ContainsAny,
    ContainsAnyFilter,
    ContainsFilter,
    EndsWith,
    EndsWithAny,
    EndsWithAnyFilter,
    EndsWithFilter,
    Equals,
    EqualsAny,
    EqualsAnyFilter,
    EqualsFilter,
    Filter,
    Glob,
    GlobFilter,
    LogicalFilter,
    MultiPatternFilter,
    Not,
    NotFilter,
    Or,
    OrFilter,
    PatternFilter,
    Regex,
    RegexFilter,
    StartsWith,
    StartsWithAny,
    StartsWithAnyFilter,
    StartsWithFilter,
)

# --- abstract bases ---------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "args"),
    (
        (Filter, ()),
        (PatternFilter, ("foo",)),
        (MultiPatternFilter, (("foo",),)),
        (LogicalFilter, ()),
    ),
)
def test_abstract_base_cannot_be_instantiated(cls: type, args: tuple):
    with pytest.raises(TypeError, match="abstract"):
        cls(*args)  # ty: ignore


# --- PatternFilter: EqualsFilter --------------------------------------------


def test_equals_matches():
    assert EqualsFilter("foo").matches("foo")
    assert not EqualsFilter("foo").matches("bar")
    assert not EqualsFilter("foo").matches("foobar")


def test_equals_case_sensitive_default_rejects_other_case():
    assert not EqualsFilter("FOO").matches("foo")


def test_equals_case_insensitive_matches_any_case():
    f = EqualsFilter("FOO", case_sensitive=False)
    assert f.matches("foo")
    assert f.matches("FOO")
    assert f.matches("FoO")


def test_equals_pattern_pre_normalized_when_case_insensitive():
    assert EqualsFilter("FOO", case_sensitive=False).pattern == "foo"
    assert EqualsFilter("FOO").pattern == "FOO"


def test_equals_semantic_equality_via_pre_normalization():
    assert EqualsFilter("FOO", case_sensitive=False) == EqualsFilter(
        "foo", case_sensitive=False
    )
    assert EqualsFilter("FOO") != EqualsFilter("foo")
    assert EqualsFilter("FOO") != EqualsFilter("FOO", case_sensitive=False)


# --- PatternFilter: StartsWithFilter ----------------------------------------


def test_startswith_matches():
    assert StartsWithFilter("foo").matches("foobar")
    assert StartsWithFilter("foo").matches("foo")
    assert not StartsWithFilter("foo").matches("xfoo")
    assert not StartsWithFilter("foo").matches("bar")


def test_startswith_case_insensitive():
    f = StartsWithFilter("TEST_", case_sensitive=False)
    assert f.matches("test_x")
    assert f.matches("TEST_X")
    assert not f.matches("foo")


# --- PatternFilter: EndsWithFilter ------------------------------------------


def test_endswith_matches():
    assert EndsWithFilter(".py").matches("foo.py")
    assert not EndsWithFilter(".py").matches("foo.txt")


def test_endswith_case_insensitive():
    f = EndsWithFilter(".PY", case_sensitive=False)
    assert f.matches("foo.py")
    assert f.matches("foo.PY")


# --- PatternFilter: ContainsFilter ------------------------------------------


def test_contains_matches():
    assert ContainsFilter("bar").matches("foobarbaz")
    assert ContainsFilter("foo").matches("foo")
    assert not ContainsFilter("xxx").matches("foobar")


def test_contains_case_insensitive():
    f = ContainsFilter("TODO", case_sensitive=False)
    assert f.matches("contains todo")
    assert f.matches("contains TODO")


# --- PatternFilter: RegexFilter ---------------------------------------------


def test_regex_fullmatch_semantics():
    # Entire string must match; partial does not.
    assert RegexFilter(r"[a-z]+").matches("hello")
    assert not RegexFilter(r"[a-z]+").matches("hello 123")


def test_regex_case_insensitive_via_ignorecase_flag():
    f = RegexFilter(r"[a-z]+", case_sensitive=False)
    assert f.matches("abc")
    assert f.matches("ABC")
    assert f.matches("AbC")


def test_regex_pattern_not_casefolded():
    # Distinct from other PatternFilters: pattern preserved as-is so
    # constructs like (?-i:[A-Z]) keep their semantics.
    f = RegexFilter(r"[A-Z]+", case_sensitive=False)
    assert f.pattern == "[A-Z]+"


def test_regex_preserves_inline_flag_scope():
    # (?-i:) inside IGNORECASE outer should disable IGNORECASE in scope.
    f = RegexFilter(r"(?-i:[A-Z])+", case_sensitive=False)
    assert f.matches("ABC")
    assert not f.matches("abc")


def test_regex_invalid_pattern_raises_at_construction():
    with pytest.raises(ValueError, match="invalid regex pattern"):
        RegexFilter("[unclosed")


def test_regex_compiled_field_excluded_from_eq_and_repr():
    f1 = RegexFilter(r"a+")
    f2 = RegexFilter(r"a+")
    # Same spec -> equal, despite different _compiled object identities.
    assert f1 == f2
    r = repr(f1)
    assert "_compiled" not in r
    assert "Pattern" not in r


# --- PatternFilter: GlobFilter ----------------------------------------------


def test_glob_basic_wildcards():
    assert GlobFilter("*.py").matches("foo.py")
    assert not GlobFilter("*.py").matches("foo.txt")


def test_glob_single_char_wildcard():
    f = GlobFilter("test_?.py")
    assert f.matches("test_1.py")
    assert not f.matches("test_11.py")


def test_glob_character_class():
    f = GlobFilter("[abc]oo")
    assert f.matches("aoo")
    assert f.matches("boo")
    assert f.matches("coo")
    assert not f.matches("doo")


def test_glob_negated_character_class():
    f = GlobFilter("[!abc]oo")
    assert f.matches("doo")
    assert not f.matches("aoo")


def test_glob_case_insensitive():
    f = GlobFilter("*.PY", case_sensitive=False)
    assert f.matches("foo.py")
    assert f.matches("foo.PY")


def test_glob_pattern_pre_normalized_when_case_insensitive():
    assert GlobFilter("*.PY", case_sensitive=False).pattern == "*.py"


# --- MultiPatternFilter: shared behaviors -----------------------------------


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


# --- MultiPatternFilter: EqualsAnyFilter ------------------------------------


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


# --- MultiPatternFilter: StartsWithAnyFilter --------------------------------


def test_startswith_any_matches():
    f = StartsWithAnyFilter(("test_", "conftest", "fix_"))
    assert f.matches("test_foo")
    assert f.matches("conftest.py")
    assert f.matches("fix_123")
    assert not f.matches("foo_test")


# --- MultiPatternFilter: EndsWithAnyFilter ----------------------------------


def test_endswith_any_matches():
    f = EndsWithAnyFilter((".png", ".jpg", ".jpeg"))
    assert f.matches("photo.png")
    assert f.matches("photo.jpeg")
    assert not f.matches("photo.gif")


def test_endswith_any_case_insensitive():
    f = EndsWithAnyFilter((".PNG", ".JPG"), case_sensitive=False)
    assert f.matches("photo.png")
    assert f.matches("photo.PNG")


# --- MultiPatternFilter: ContainsAnyFilter ----------------------------------


def test_contains_any_matches():
    f = ContainsAnyFilter(("TODO", "FIXME"))
    assert f.matches("// TODO: fix this")
    assert f.matches("FIXME later")
    assert not f.matches("all good")


def test_contains_any_case_insensitive():
    f = ContainsAnyFilter(("TODO", "FIXME"), case_sensitive=False)
    assert f.matches("// todo: fix")
    assert f.matches("fixme later")


# --- LogicalFilter: AndFilter -----------------------------------------------


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


# --- LogicalFilter: OrFilter ------------------------------------------------


def test_or_any_child_matches():
    f = OrFilter((EqualsFilter("a"), EqualsFilter("b")))
    assert f.matches("a")
    assert f.matches("b")
    assert not f.matches("c")


def test_or_empty_children_raises():
    with pytest.raises(ValueError, match="requires at least one"):
        OrFilter(())


# --- LogicalFilter: NotFilter -----------------------------------------------


def test_not_inverts_child_result():
    f = NotFilter(EqualsFilter("foo"))
    assert not f.matches("foo")
    assert f.matches("bar")


def test_not_double_negation_recovers_original():
    f = NotFilter(NotFilter(EqualsFilter("foo")))
    assert f.matches("foo")
    assert not f.matches("bar")


# --- Nesting ----------------------------------------------------------------


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


# --- Aliases ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("alias", "canonical"),
    (
        (And, AndFilter),
        (Or, OrFilter),
        (Not, NotFilter),
        (Equals, EqualsFilter),
        (StartsWith, StartsWithFilter),
        (EndsWith, EndsWithFilter),
        (Contains, ContainsFilter),
        (Regex, RegexFilter),
        (Glob, GlobFilter),
        (EqualsAny, EqualsAnyFilter),
        (StartsWithAny, StartsWithAnyFilter),
        (EndsWithAny, EndsWithAnyFilter),
        (ContainsAny, ContainsAnyFilter),
    ),
)
def test_alias_is_canonical_class(alias: type, canonical: type):
    assert alias is canonical


# --- Hashability & frozen ---------------------------------------------------


@pytest.mark.parametrize(
    "f",
    (
        EqualsFilter("a"),
        RegexFilter(r"a+"),
        GlobFilter("*.py"),
        EqualsAnyFilter(("a", "b")),
        AndFilter((EqualsFilter("a"),)),
        OrFilter((EqualsFilter("a"),)),
        NotFilter(EqualsFilter("a")),
    ),
)
def test_filter_is_hashable(f: Filter):
    hash(f)


def test_filter_is_frozen():
    f = EqualsFilter("a")
    with pytest.raises(FrozenInstanceError):
        f.pattern = "b"  # ty: ignore


# --- isinstance hierarchy ---------------------------------------------------


def test_pattern_filter_isinstance_chain():
    e = EqualsFilter("a")
    assert isinstance(e, PatternFilter)
    assert isinstance(e, Filter)
    assert not isinstance(e, LogicalFilter)
    assert not isinstance(e, MultiPatternFilter)


def test_multi_pattern_filter_isinstance_chain():
    ea = EqualsAnyFilter(("a",))
    assert isinstance(ea, MultiPatternFilter)
    assert isinstance(ea, Filter)
    assert not isinstance(ea, PatternFilter)
    assert not isinstance(ea, LogicalFilter)


def test_logical_filter_isinstance_chain():
    a = AndFilter((EqualsFilter("a"),))
    assert isinstance(a, LogicalFilter)
    assert isinstance(a, Filter)
    assert not isinstance(a, PatternFilter)
    assert not isinstance(a, MultiPatternFilter)
