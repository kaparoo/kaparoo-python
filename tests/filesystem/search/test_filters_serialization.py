from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.search.filters import (
    AndFilter,
    ContainsAnyFilter,
    ContainsFilter,
    EndsWithAnyFilter,
    EndsWithFilter,
    EqualsAnyFilter,
    EqualsFilter,
    Filter,
    GlobFilter,
    NotFilter,
    OrFilter,
    RegexFilter,
    StartsWithAnyFilter,
    StartsWithFilter,
    register_filter,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


# --- per-kind round-trip ----------------------------------------------------


@pytest.mark.parametrize(
    ("filter_", "expected_kind"),
    (
        (EqualsFilter("foo.py"), "equals"),
        (StartsWithFilter("test_"), "starts_with"),
        (EndsWithFilter(".log"), "ends_with"),
        (ContainsFilter("data"), "contains"),
        (RegexFilter(r".*\.py"), "regex"),
        (GlobFilter("*.md"), "glob"),
        (EqualsAnyFilter(("a.py", "b.py")), "equals_any"),
        (StartsWithAnyFilter(("test_", "spec_")), "starts_with_any"),
        (EndsWithAnyFilter((".log", ".bak")), "ends_with_any"),
        (ContainsAnyFilter(("data", "info")), "contains_any"),
    ),
)
def test_pattern_filter_round_trip(filter_: Filter, expected_kind: str):
    d = filter_.to_dict()
    assert d["kind"] == expected_kind
    restored = Filter.from_dict(d)
    assert restored == filter_


# --- default omission --------------------------------------------------------


def test_to_dict_omits_default_case_sensitive():
    d = EqualsFilter("foo").to_dict()
    assert "case_sensitive" not in d


def test_to_dict_includes_non_default_case_sensitive():
    d = EqualsFilter("FOO", case_sensitive=False).to_dict()
    assert d["case_sensitive"] is False


def test_from_dict_defaults_case_sensitive_when_missing():
    f = EqualsFilter.from_dict({"kind": "equals", "pattern": "foo"})
    assert f.case_sensitive is True


# --- casefold is idempotent through serialization --------------------------


def test_case_insensitive_pattern_is_casefolded_in_dict():
    # Construction casefolds; to_dict records the casefolded form.
    f = EqualsFilter("FOO", case_sensitive=False)
    assert f.to_dict() == {"kind": "equals", "pattern": "foo", "case_sensitive": False}


def test_round_trip_preserves_matching_semantics():
    original = EqualsFilter("FOO", case_sensitive=False)
    restored = Filter.from_dict(original.to_dict())
    # Matching is unchanged by the round-trip.
    assert original.matches("foo") == restored.matches("foo")
    assert original.matches("FOO") == restored.matches("FOO")
    assert original == restored


# --- multi-pattern filters --------------------------------------------------


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


# --- logical filter recursion ----------------------------------------------


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


def test_logical_to_dict_uses_kind_children():
    d = AndFilter((EqualsFilter("a"), EqualsFilter("b"))).to_dict()
    assert d["kind"] == "and"
    assert isinstance(d["children"], list)
    assert len(d["children"]) == 2
    assert d["children"][0] == {"kind": "equals", "pattern": "a"}


def test_not_to_dict_uses_kind_child():
    d = NotFilter(EqualsFilter("x")).to_dict()
    assert d == {
        "kind": "not",
        "child": {"kind": "equals", "pattern": "x"},
    }


# --- JSON round-trip --------------------------------------------------------


def test_json_round_trip():
    original = AndFilter(
        (
            GlobFilter("*.py"),
            NotFilter(EqualsFilter("__init__.py")),
        )
    )
    json_text = json.dumps(original.to_dict())
    restored = Filter.from_dict(json.loads(json_text))
    assert restored == original


# --- error cases -----------------------------------------------------------


def test_from_dict_missing_kind_raises():
    with pytest.raises(ValueError, match="missing 'kind'"):
        Filter.from_dict({"pattern": "foo"})


def test_from_dict_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown filter kind"):
        Filter.from_dict({"kind": "nonexistent", "pattern": "foo"})


def test_subclass_from_dict_not_overridden_raises():
    # Defining a Filter subclass that doesn't override from_dict.
    @dataclass(frozen=True)
    class UnoverriddenFilter(Filter):
        def matches(self, target: str) -> bool:
            return False

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "unoverridden"}

    # Inherited from base; the dispatching branch only fires when
    # `cls is Filter`, so subclass usage raises.
    with pytest.raises(NotImplementedError, match="must be overridden"):
        UnoverriddenFilter.from_dict({"kind": "unoverridden"})


# --- registry / custom filter -----------------------------------------------


def test_register_filter_makes_custom_kind_discoverable():
    @register_filter("test_length_above")
    @dataclass(frozen=True)
    class LengthAboveFilter(Filter):
        threshold: int

        def matches(self, target: str) -> bool:
            return len(target) > self.threshold

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_length_above", "threshold": self.threshold}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls(threshold=data["threshold"])

    f = LengthAboveFilter(5)
    restored = Filter.from_dict(f.to_dict())
    assert restored == f


def test_register_filter_rejects_duplicate_kind_for_different_class():
    @register_filter("test_dup_kind_a")
    @dataclass(frozen=True)
    class FilterA(Filter):
        def matches(self, target: str) -> bool:
            return False

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_dup_kind_a"}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls()

    with pytest.raises(ValueError, match="already registered"):

        @register_filter("test_dup_kind_a")  # collision
        @dataclass(frozen=True)
        class FilterB(Filter):
            def matches(self, target: str) -> bool:
                return False

            def to_dict(self) -> dict[str, Any]:
                return {"kind": "test_dup_kind_a"}

            @classmethod
            def from_dict(cls, data: Mapping[str, Any]) -> Self:
                return cls()


def test_register_filter_same_class_is_idempotent():
    # Re-registering the SAME class under the SAME kind is a no-op (no raise).
    @register_filter("test_idempotent")
    @dataclass(frozen=True)
    class IdempotentFilter(Filter):
        def matches(self, target: str) -> bool:
            return False

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_idempotent"}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls()

    # Re-registration must succeed (idempotent).
    register_filter("test_idempotent")(IdempotentFilter)
