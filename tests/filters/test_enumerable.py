from __future__ import annotations

import pytest

from kaparoo.filters import Expandable, Filter, Glob, Literal, OneOf, Template


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

    def test_single_axis_substitutes_each_value(self) -> None:
        template = Template("shard_{:03d}", range(3))
        assert list(template.expand()) == ["shard_000", "shard_001", "shard_002"]

    def test_multiple_axes_combine_as_a_product(self) -> None:
        template = Template("{}_{}.png", ["real", "fake"], range(1, 4))
        assert list(template.expand()) == [
            "real_1.png",
            "real_2.png",
            "real_3.png",
            "fake_1.png",
            "fake_2.png",
            "fake_3.png",
        ]

    def test_matches_uses_the_enumerated_set(self) -> None:
        template = Template("{}_{}.png", ["real", "fake"], range(1, 4))
        assert template.matches("real_1.png")
        assert template.matches("fake_3.png")
        assert not template.matches("real_4.png")
        assert not template.matches("other_1.png")

    def test_axes_are_frozen_to_tuples(self) -> None:
        source = [1, 2, 3]
        template = Template("v{}", source)
        source.append(4)
        assert template.axes == ((1, 2, 3),)

    def test_no_axes_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one axis"):
            Template("constant")

    def test_empty_axis_matches_nothing(self) -> None:
        template = Template("v{}", [])
        assert list(template.expand()) == []
        assert not template.matches("v1")

    def test_serialization_round_trips(self) -> None:
        template = Template("{}_{}.png", ["real", "fake"], [1, 2])
        assert template.to_dict() == {
            "kind": "template",
            "template": "{}_{}.png",
            "axes": [["real", "fake"], [1, 2]],
        }
        assert Filter.from_dict(template.to_dict()) == template

    def test_repr(self) -> None:
        assert repr(Template("v{}", [1, 2])) == "Template('v{}', (1, 2))"
        assert repr(Template("{}_{}", ["a"], [1])) == "Template('{}_{}', ('a',), (1,))"

    def test_template_property_hash_and_inequality(self) -> None:
        template = Template("v{}", [1, 2])
        assert template.template == "v{}"
        assert template != "v{}"  # not a Template -> NotImplemented
        assert hash(template) == hash(Template("v{}", [1, 2]))


class TestOneOf:
    def test_is_an_expandable_filter(self) -> None:
        one_of = OneOf(["train", "val"])
        assert isinstance(one_of, Filter)
        assert isinstance(one_of, Expandable)

    def test_matches_any_of_the_names(self) -> None:
        one_of = OneOf(["train", "val", "test"])
        assert one_of.matches("train")
        assert one_of.matches("test")
        assert not one_of.matches("predict")

    def test_expand_yields_each_name(self) -> None:
        assert list(OneOf(["train", "val"]).expand()) == ["train", "val"]

    def test_deduplicates_preserving_order(self) -> None:
        one_of = OneOf(["a", "b", "a", "c", "b"])
        assert one_of.names == ("a", "b", "c")
        assert list(one_of.expand()) == ["a", "b", "c"]

    def test_empty_names_raise(self) -> None:
        with pytest.raises(ValueError, match="at least one name"):
            OneOf([])

    def test_serialization_round_trips(self) -> None:
        one_of = OneOf(["train", "val"])
        assert one_of.to_dict() == {"kind": "one_of", "names": ["train", "val"]}
        assert Filter.from_dict(one_of.to_dict()) == one_of

    def test_equal_ignoring_duplicate_input(self) -> None:
        assert OneOf(["a", "b"]) == OneOf(["a", "b", "a"])
        assert OneOf(["a", "b"]) != OneOf(["a", "c"])


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
