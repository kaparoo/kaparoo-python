from __future__ import annotations

from kaparoo.filesystem.hierarchy import Expandable, Literal, Template
from kaparoo.filters import Filter, Glob


class TestLiteral:
    def test_is_an_expandable_filter(self) -> None:
        literal = Literal("data.bin")
        assert isinstance(literal, Filter)
        assert isinstance(literal, Expandable)

    def test_matches_only_the_exact_name(self) -> None:
        literal = Literal("data.bin")
        assert literal.matches("data.bin")
        assert not literal.matches("data.txt")
        assert not literal.matches("DATA.BIN")

    def test_expand_yields_the_single_name(self) -> None:
        assert list(Literal("data.bin").expand()) == ["data.bin"]

    def test_name_exposes_the_value(self) -> None:
        assert Literal("data.bin").name == "data.bin"

    def test_serialization_round_trips(self) -> None:
        literal = Literal("data.bin")
        assert literal.to_dict() == {"kind": "literal", "name": "data.bin"}
        assert Filter.from_dict(literal.to_dict()) == literal


class TestTemplate:
    def test_is_an_expandable_filter(self) -> None:
        template = Template("v{}", [])
        assert isinstance(template, Filter)
        assert isinstance(template, Expandable)

    def test_expand_substitutes_each_value(self) -> None:
        template = Template("shard_{:03d}", range(3))
        assert list(template.expand()) == ["shard_000", "shard_001", "shard_002"]

    def test_matches_uses_the_enumerated_set(self) -> None:
        template = Template("shard_{:03d}", range(8))
        assert template.matches("shard_000")
        assert template.matches("shard_007")
        assert not template.matches("shard_008")
        assert not template.matches("shard_0")

    def test_values_are_frozen_to_a_tuple(self) -> None:
        source = [1, 2, 3]
        template = Template("v{}", source)
        source.append(4)
        assert template.values == (1, 2, 3)

    def test_empty_values_match_nothing(self) -> None:
        template = Template("v{}", [])
        assert list(template.expand()) == []
        assert not template.matches("v1")

    def test_serialization_round_trips(self) -> None:
        template = Template("shard_{:03d}", range(3))
        assert template.to_dict() == {
            "kind": "template",
            "template": "shard_{:03d}",
            "values": [0, 1, 2],
        }
        assert Filter.from_dict(template.to_dict()) == template


class TestValueSemantics:
    def test_equal_when_same_type_and_fields(self) -> None:
        assert Literal("a") == Literal("a")
        assert Template("v{}", [1, 2]) == Template("v{}", [1, 2])

    def test_not_equal_when_fields_differ(self) -> None:
        assert Literal("a") != Literal("b")
        assert Template("v{}", [1]) != Template("v{}", [2])

    def test_hashable_and_usable_in_a_set(self) -> None:
        assert hash(Literal("a")) == hash(Literal("a"))
        assert {Literal("a"), Literal("a")} == {Literal("a")}


class TestExpandableCapability:
    def test_glob_matches_but_is_not_expandable(self) -> None:
        glob = Glob("*.png")
        assert isinstance(glob, Filter)
        assert not isinstance(glob, Expandable)
        assert glob.matches("frame.png")
