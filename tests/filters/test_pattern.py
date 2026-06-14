from __future__ import annotations

import pytest

from kaparoo.filters import (
    Contains,
    ContainsFilter,
    EndsWith,
    EndsWithFilter,
    Equals,
    EqualsFilter,
    Filter,
    Glob,
    GlobFilter,
    LogicalFilter,
    MultiPatternFilter,
    PatternFilter,
    Regex,
    RegexFilter,
    StartsWith,
    StartsWithFilter,
)

# --- abstract base ---------------------------------------------------------


def test_pattern_filter_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        PatternFilter("foo")  # ty: ignore


def test_pattern_filter_isinstance_chain():
    e = EqualsFilter("a")
    assert isinstance(e, PatternFilter)
    assert isinstance(e, Filter)
    assert not isinstance(e, LogicalFilter)
    assert not isinstance(e, MultiPatternFilter)


# --- EqualsFilter ----------------------------------------------------------


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


# --- StartsWithFilter ------------------------------------------------------


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


# --- EndsWithFilter --------------------------------------------------------


def test_endswith_matches():
    assert EndsWithFilter(".py").matches("foo.py")
    assert not EndsWithFilter(".py").matches("foo.txt")


def test_endswith_case_insensitive():
    f = EndsWithFilter(".PY", case_sensitive=False)
    assert f.matches("foo.py")
    assert f.matches("foo.PY")


# --- ContainsFilter --------------------------------------------------------


def test_contains_matches():
    assert ContainsFilter("bar").matches("foobarbaz")
    assert ContainsFilter("foo").matches("foo")
    assert not ContainsFilter("xxx").matches("foobar")


def test_contains_case_insensitive():
    f = ContainsFilter("TODO", case_sensitive=False)
    assert f.matches("contains todo")
    assert f.matches("contains TODO")


# --- RegexFilter -----------------------------------------------------------


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


# --- GlobFilter ------------------------------------------------------------


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


def test_glob_case_insensitive_keeps_pattern_and_match_length():
    # Glob CI uses re.IGNORECASE (like Regex), so the pattern is not casefolded
    # and `?` stays one character even when the target's fold would expand.
    assert GlobFilter("*.PY", case_sensitive=False).pattern == "*.PY"
    assert GlobFilter("?", case_sensitive=False).matches("ß")


# --- serialization (per-kind round-trip) -----------------------------------


@pytest.mark.parametrize(
    ("filter_", "expected_kind"),
    (
        (EqualsFilter("foo.py"), "equals"),
        (StartsWithFilter("test_"), "starts_with"),
        (EndsWithFilter(".log"), "ends_with"),
        (ContainsFilter("data"), "contains"),
        (RegexFilter(r".*\.py"), "regex"),
        (GlobFilter("*.md"), "glob"),
    ),
)
def test_pattern_filter_round_trip(filter_: PatternFilter, expected_kind: str):
    d = filter_.to_dict()
    assert d["kind"] == expected_kind
    restored = Filter.from_dict(d)
    assert restored == filter_


def test_case_sensitive_serialization():
    # `case_sensitive=True` is the default and is omitted from `to_dict`;
    # construction casefolds the pattern when `False` and records the
    # casefolded form. `from_dict` defaults to True when the key is missing.
    assert "case_sensitive" not in EqualsFilter("foo").to_dict()
    assert EqualsFilter("FOO", case_sensitive=False).to_dict() == {
        "kind": "equals",
        "pattern": "foo",
        "case_sensitive": False,
    }
    assert EqualsFilter.from_dict({"kind": "equals", "pattern": "foo"}).case_sensitive


def test_round_trip_preserves_matching_semantics():
    original = EqualsFilter("FOO", case_sensitive=False)
    restored = Filter.from_dict(original.to_dict())
    assert original.matches("foo") == restored.matches("foo")
    assert original.matches("FOO") == restored.matches("FOO")
    assert original == restored


def test_regex_round_trip_preserves_matching_behavior():
    # `RegexFilter` excludes its compiled-pattern cache from __eq__/__repr__,
    # so the per-kind round-trip above passes on equality alone even if
    # `from_dict` skips recompilation. Drive `matches()` on the restored
    # instance to pin the behavioral contract (both case-sensitive and not).
    original = RegexFilter(r"[a-z]+\d{2}")
    restored = Filter.from_dict(original.to_dict())
    assert isinstance(restored, RegexFilter)
    assert restored.matches("abc12") is True
    assert restored.matches("abc1") is False
    assert restored.matches("ABC12") is False

    ci_original = RegexFilter(r"[a-z]+", case_sensitive=False)
    ci_restored = Filter.from_dict(ci_original.to_dict())
    assert isinstance(ci_restored, RegexFilter)
    assert ci_restored.matches("abc") is True
    assert ci_restored.matches("ABC") is True


# --- aliases ---------------------------------------------------------------


def test_pattern_aliases_are_canonical_classes():
    assert Equals is EqualsFilter
    assert StartsWith is StartsWithFilter
    assert EndsWith is EndsWithFilter
    assert Contains is ContainsFilter
    assert Regex is RegexFilter
    assert Glob is GlobFilter


def test_repr_uses_concise_alias_name():
    assert repr(EqualsFilter("README")) == "Equals('README')"
    assert (
        repr(EqualsFilter("readme", case_sensitive=False))
        == "Equals('readme', case_sensitive=False)"
    )
    assert repr(GlobFilter("*.png")) == "Glob('*.png')"
