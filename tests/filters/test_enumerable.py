from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kaparoo.filters import Expandable, Filter, Glob, Literal, OneOf, Template, Without


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

    def test_repr_is_concise(self) -> None:
        assert repr(Literal("train")) == "Literal('train')"


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

    def test_repr_compacts_integer_arithmetic_axis_to_range(self) -> None:
        # An integer arithmetic progression (>= 3 terms) shows as range(...);
        # `range` is a valid axis input, so the compact form round-trips.
        assert repr(Template("v{}", range(10))) == "Template('v{}', range(0, 10))"
        assert repr(Template("v{}", range(1, 11))) == "Template('v{}', range(1, 11))"
        assert repr(Template("v{}", range(0, 10, 2))) == (
            "Template('v{}', range(0, 10, 2))"
        )
        assert repr(Template("v{}", [5, 4, 3, 2, 1])) == (
            "Template('v{}', range(5, 0, -1))"
        )
        assert eval(repr(Template("img_{:04d}", range(1000)))) == Template(  # noqa: S307
            "img_{:04d}", range(1000)
        )

    def test_repr_keeps_non_progression_axes_as_tuples(self) -> None:
        # Falls back to the plain tuple when an axis is too short, irregular,
        # constant (step 0), or non-integer.
        assert repr(Template("v{}", [0, 1])) == "Template('v{}', (0, 1))"
        assert repr(Template("v{}", [0, 1, 2, 5])) == "Template('v{}', (0, 1, 2, 5))"
        assert repr(Template("v{}", [5, 5, 5])) == "Template('v{}', (5, 5, 5))"
        assert repr(Template("v{}", [1.0, 2.0, 3.0])) == (
            "Template('v{}', (1.0, 2.0, 3.0))"
        )
        assert repr(Template("{}_{}", ["a", "b"], range(3))) == (
            "Template('{}_{}', ('a', 'b'), range(0, 3))"
        )

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

    def test_repr_is_concise(self) -> None:
        assert repr(OneOf(["train", "val"])) == "OneOf(('train', 'val'))"


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


class TestWithout:
    def test_is_an_expandable_filter(self) -> None:
        without = Without(Template("v{}", range(3)), "v1")
        assert isinstance(without, Filter)
        assert isinstance(without, Expandable)

    def test_expand_removes_excluded(self) -> None:
        without = Without(Template("cam_{:02d}", range(4)), "cam_02")
        assert list(without.expand()) == ["cam_00", "cam_01", "cam_03"]

    def test_matches_the_difference(self) -> None:
        without = Without(Template("cam_{:02d}", range(4)), "cam_02")
        assert without.matches("cam_00")
        assert not without.matches("cam_02")  # excluded
        assert not without.matches("cam_09")  # not in base

    def test_exclude_by_filter(self) -> None:
        without = Without(Template("img_{:02d}", range(5)), Glob("*_03"))
        assert list(without.expand()) == ["img_00", "img_01", "img_02", "img_04"]

    def test_str_excluded_is_sugar_for_literal(self) -> None:
        without = Without(OneOf(["a", "b", "c"]), "b")
        assert without.excluded == (Literal("b"),)
        assert list(without.expand()) == ["a", "c"]

    def test_base_property(self) -> None:
        base = Template("v{}", range(2))
        assert Without(base, "v0").base == base

    def test_no_exclusion_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one exclusion"):
            Without(OneOf(["a", "b"]))

    def test_nested_without(self) -> None:
        without = Without(Without(Template("v{}", range(4)), "v0"), "v3")
        assert list(without.expand()) == ["v1", "v2"]

    def test_serialization_round_trips(self) -> None:
        without = Without(Template("cam_{:02d}", range(4)), "cam_02", Glob("*_03"))
        assert Filter.from_dict(without.to_dict()) == without

    def test_value_semantics(self) -> None:
        assert Without(OneOf(["a", "b"]), "a") == Without(OneOf(["a", "b"]), "a")
        assert Without(OneOf(["a", "b"]), "a") != Without(OneOf(["a", "b"]), "b")
        assert Without(OneOf(["a", "b"]), "a") != "a"
        assert hash(Without(OneOf(["a", "b"]), "a")) == hash(
            Without(OneOf(["a", "b"]), "a")
        )

    def test_repr(self) -> None:
        assert repr(Without(OneOf(["a", "b"]), "a")) == (
            "Without(OneOf(('a', 'b')), Literal('a'))"
        )

    def test_from_dict_rejects_non_expandable_base(self) -> None:
        # A `Without` whose serialized `base` is open-ended (a glob) cannot
        # `expand`; `from_dict` must reject it rather than fail later.
        data = {
            "kind": "without",
            "base": {"kind": "glob", "pattern": "*.png"},
            "excluded": [{"kind": "literal", "name": "x"}],
        }
        with pytest.raises(TypeError, match="Expandable"):
            Without.from_dict(data)


class TestFrozen:
    """`Template` / `Without` are non-`@dataclass` `Expandable`s, so guard
    that they are still frozen (they would silently be mutable otherwise).

    Probing a private field is the point of the test, so `SLF001` is waived.
    """

    def test_template_rejects_assignment(self) -> None:
        template = Template("x_{}", range(2))
        with pytest.raises(FrozenInstanceError):
            template._template = "y_{}"  # noqa: SLF001

    def test_template_rejects_deletion(self) -> None:
        template = Template("x_{}", range(2))
        with pytest.raises(FrozenInstanceError):
            del template._axes  # noqa: SLF001

    def test_without_rejects_assignment(self) -> None:
        without = Without(Literal("a"), "b")
        with pytest.raises(FrozenInstanceError):
            without._base = Literal("z")  # noqa: SLF001
