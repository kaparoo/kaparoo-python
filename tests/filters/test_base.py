from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from typing import TYPE_CHECKING

import pytest

from kaparoo.filters import (
    AndFilter,
    EqualsAnyFilter,
    EqualsFilter,
    Filter,
    GlobFilter,
    NotFilter,
    OrFilter,
    RegexFilter,
)

if TYPE_CHECKING:
    from typing import Any

    from kaparoo.filters.types import (
        LogicalChildrenFilterDict,
        PatternFilterDict,
    )


# --- abstract base ---------------------------------------------------------


def test_filter_cannot_be_instantiated():
    with pytest.raises(TypeError, match="abstract"):
        Filter()  # ty: ignore[missing-argument]


# --- shared dataclass contract ---------------------------------------------


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
        f.pattern = "b"  # ty: ignore[invalid-assignment]


# --- from_dict polymorphic dispatcher --------------------------------------


def test_from_dict_missing_kind_raises():
    with pytest.raises(ValueError, match="missing 'kind'"):
        Filter.from_dict({"pattern": "foo"})


def test_from_dict_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown filter kind"):
        Filter.from_dict({"kind": "nonexistent", "pattern": "foo"})


def test_from_dict_null_kind_treated_as_missing():
    # A null discriminator is treated the same as an absent one.
    with pytest.raises(ValueError, match="missing 'kind'"):
        Filter.from_dict({"kind": None, "pattern": "foo"})


def test_from_dict_non_mapping_raises_type_error():
    for bad in (None, 42, "x", ["a"]):
        with pytest.raises(TypeError, match="expected a filter dict"):
            Filter.from_dict(bad)  # ty: ignore[invalid-argument-type]


def test_subclass_from_dict_not_overridden_raises():
    # A Filter subclass that doesn't override from_dict inherits the
    # base dispatcher, which only dispatches when `cls is Filter`.
    @dataclass(frozen=True)
    class UnoverriddenFilter(Filter):
        def matches(self, target: str) -> bool:
            return False

        def _payload(self) -> dict[str, Any]:
            return {}

    with pytest.raises(NotImplementedError, match="must be overridden"):
        UnoverriddenFilter.from_dict({"kind": "unoverridden"})


# --- cross-cutting round-trip via Filter.from_dict -------------------------


def test_json_round_trip_via_base_dispatcher():
    import json

    original = AndFilter(
        (
            GlobFilter("*.py"),
            NotFilter(EqualsFilter("__init__.py")),
        )
    )
    json_text = json.dumps(original.to_dict())
    restored = Filter.from_dict(json.loads(json_text))
    assert restored == original


def test_dispatcher_returns_correct_subclass_instance():
    # Filter.from_dict should return the specific subclass, not just Filter.
    d = EqualsFilter("foo").to_dict()
    restored = Filter.from_dict(d)
    assert type(restored) is EqualsFilter


# --- Filter.parse ----------------------------------------------------------


def test_parse_passes_through_filter_instance():
    f = EqualsFilter("foo")
    assert Filter.parse(f) is f


def test_parse_deserializes_filter_dict():
    spec: PatternFilterDict = {"kind": "equals", "pattern": "foo"}
    assert Filter.parse(spec) == EqualsFilter("foo")


def test_parse_deserializes_nested_logical_dict():
    spec: LogicalChildrenFilterDict = {
        "kind": "and",
        "children": [
            {"kind": "glob", "pattern": "*.py"},
            {"kind": "not", "child": {"kind": "equals", "pattern": "__init__.py"}},
        ],
    }
    assert Filter.parse(spec) == AndFilter(
        (
            GlobFilter("*.py"),
            NotFilter(EqualsFilter("__init__.py")),
        )
    )


def test_parse_invalid_dict_raises():
    with pytest.raises(ValueError, match="missing 'kind'"):
        Filter.parse({"pattern": "foo"})  # ty: ignore[invalid-argument-type]


def test_parse_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown filter kind"):
        Filter.parse({"kind": "nope"})


def test_parse_non_mapping_raises_type_error():
    for bad in (None, 42, "x", ["a"]):
        with pytest.raises(TypeError, match="expected a filter dict"):
            Filter.parse(bad)  # ty: ignore[invalid-argument-type]
