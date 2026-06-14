from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaparoo.filters import (
    AndFilter,
    EqualsAnyFilter,
    EqualsFilter,
    Filter,
    GlobFilter,
    LiteralFilter,
    NotFilter,
    OneOfFilter,
    OrFilter,
    TemplateFilter,
    WithoutFilter,
    register_filter,
)
from kaparoo.filters.types import FilterDict

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self

    from kaparoo.filters.types import (
        LiteralFilterDict,
        LogicalChildFilterDict,
        LogicalChildrenFilterDict,
        MultiPatternFilterDict,
        OneOfFilterDict,
        PatternFilterDict,
        TemplateFilterDict,
        WithoutFilterDict,
    )


# --- FilterDict inheritance ------------------------------------------------


def test_pattern_filter_dict_round_trips_via_parse():
    # The annotation makes `spec` a PatternFilterDict (a TypedDict
    # inheriting from FilterDict); `Filter.parse` accepts FilterDict.
    spec: PatternFilterDict = {"kind": "equals", "pattern": "foo"}
    assert Filter.parse(spec) == EqualsFilter("foo")


def test_pattern_filter_dict_with_case_sensitive():
    spec: PatternFilterDict = {
        "kind": "glob",
        "pattern": "*.PY",
        "case_sensitive": False,
    }
    assert Filter.parse(spec) == GlobFilter("*.PY", case_sensitive=False)


def test_multi_pattern_filter_dict_round_trips():
    spec: MultiPatternFilterDict = {
        "kind": "equals_any",
        "patterns": ["a", "b", "c"],
    }
    assert Filter.parse(spec) == EqualsAnyFilter(("a", "b", "c"))


def test_logical_children_filter_dict_round_trips():
    spec: LogicalChildrenFilterDict = {
        "kind": "and",
        "children": [
            {"kind": "glob", "pattern": "*.py"},
            {"kind": "equals", "pattern": "__init__.py"},
        ],
    }
    assert Filter.parse(spec) == AndFilter(
        (GlobFilter("*.py"), EqualsFilter("__init__.py"))
    )


def test_logical_child_filter_dict_round_trips():
    spec: LogicalChildFilterDict = {
        "kind": "not",
        "child": {"kind": "equals", "pattern": "x"},
    }
    assert Filter.parse(spec) == NotFilter(EqualsFilter("x"))


def test_or_via_logical_children_filter_dict():
    # Same TypedDict shape works for both AndFilter and OrFilter -- they
    # share `children` in their dataclass field as well.
    spec: LogicalChildrenFilterDict = {
        "kind": "or",
        "children": [{"kind": "equals", "pattern": "a"}],
    }
    assert Filter.parse(spec) == OrFilter((EqualsFilter("a"),))


def test_literal_filter_dict_round_trips():
    spec: LiteralFilterDict = {"kind": "literal", "name": "data.bin"}
    assert Filter.parse(spec) == LiteralFilter("data.bin")


def test_one_of_filter_dict_round_trips():
    spec: OneOfFilterDict = {"kind": "one_of", "names": ["train", "val"]}
    assert Filter.parse(spec) == OneOfFilter(["train", "val"])


def test_template_filter_dict_round_trips():
    spec: TemplateFilterDict = {
        "kind": "template",
        "template": "shard_{:03d}",
        "axes": [[0, 1, 2]],
    }
    assert Filter.parse(spec) == TemplateFilter("shard_{:03d}", [0, 1, 2])


def test_without_filter_dict_round_trips():
    # `base` and each `excluded` entry are nested FilterDicts (the shape is
    # recursive through the base `FilterDict`).
    spec: WithoutFilterDict = {
        "kind": "without",
        "base": {"kind": "one_of", "names": ["a", "b"]},
        "excluded": [{"kind": "literal", "name": "b"}],
    }
    assert Filter.parse(spec) == WithoutFilter(OneOfFilter(["a", "b"]), "b")


# --- Custom subclass of FilterDict for user-defined filters ----------------


def test_user_filter_dict_subclass_round_trips():
    """A user-defined Filter subclass and matching FilterDict subclass."""

    @register_filter("test_user_typed_filter_dict")
    @dataclass(frozen=True)
    class ThresholdFilter(Filter):
        threshold: int

        def matches(self, target: str) -> bool:
            return len(target) > self.threshold

        def _payload(self) -> dict[str, Any]:
            return {"threshold": self.threshold}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls(threshold=data["threshold"])

    class ThresholdFilterDict(FilterDict):
        threshold: int

    # Annotation is `ThresholdFilterDict` (a subclass of FilterDict),
    # so `Filter.parse` (accepting FilterDict) is happy.
    spec: ThresholdFilterDict = {
        "kind": "test_user_typed_filter_dict",
        "threshold": 5,
    }
    result = Filter.parse(spec)
    assert result == ThresholdFilter(5)


# --- FilterDict base ------------------------------------------------------


def test_filter_dict_base_only_requires_kind():
    # `FilterDict` itself requires only `kind`. A bare `kind` dict is
    # accepted by the parser if it routes to a no-arg constructor.
    @register_filter("test_kind_only")
    @dataclass(frozen=True)
    class KindOnlyFilter(Filter):
        def matches(self, target: str) -> bool:
            return False

        def _payload(self) -> dict[str, Any]:
            return {}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls()

    spec: FilterDict = {"kind": "test_kind_only"}
    assert Filter.parse(spec) == KindOnlyFilter()


# --- TypedDicts work as plain dicts at runtime ----------------------------


def test_filter_dict_instances_are_plain_dicts():
    # TypedDicts are just regular dicts at runtime; isinstance check
    # against dict succeeds.
    spec: PatternFilterDict = {"kind": "equals", "pattern": "x"}
    assert isinstance(spec, dict)
    assert spec == {"kind": "equals", "pattern": "x"}
