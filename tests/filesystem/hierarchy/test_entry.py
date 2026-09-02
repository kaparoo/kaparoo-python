from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from kaparoo.filesystem.hierarchy import Directory, File, Node, nested_dirs
from kaparoo.filesystem.hierarchy.conditions import (
    And,
    ChildCount,
    Empty,
    HookResolver,
    Size,
)
from kaparoo.filters import Glob, Literal, OneOf, Template


class TestFile:
    def test_bare_str_name_is_sugar_for_literal(self) -> None:
        assert File("metadata.json").name == Literal("metadata.json")

    def test_list_name_is_sugar_for_one_of(self) -> None:
        assert File(["README.md", "README.rst"]).name == OneOf(
            ["README.md", "README.rst"]
        )

    def test_filter_name_is_passed_through(self) -> None:
        name = Glob("*.png")
        assert File(name).name is name

    def test_equal_by_name(self) -> None:
        assert File("a") == File("a")
        assert File("a") != File("b")

    def test_not_equal_to_a_plain_value(self) -> None:
        assert File("a") != "a"

    def test_repr(self) -> None:
        assert repr(File("a.txt")) == "File(Literal('a.txt'))"


class TestDirectory:
    def test_children_default_to_empty(self) -> None:
        assert Directory("empty").children == ()

    def test_children_are_frozen_to_a_tuple_in_order(self) -> None:
        kids = [File("a"), File("b")]
        directory = Directory("d", kids)
        kids.append(File("c"))
        assert directory.children == (File("a"), File("b"))

    def test_name_sugar_applies(self) -> None:
        assert Directory("images").name == Literal("images")

    def test_list_name_shares_children_across_siblings(self) -> None:
        layout = [Directory("images", [File(Glob("*.png"))]), File("labels.json")]
        grouped = Directory(["train", "val"], layout)
        name = grouped.name
        assert isinstance(name, OneOf)
        assert name == OneOf(["train", "val"])
        assert list(name.expand()) == ["train", "val"]
        assert grouped.children == tuple(layout)

    def test_equal_by_name_and_children(self) -> None:
        assert Directory("d", [File("a")]) == Directory("d", [File("a")])
        assert Directory("d", [File("a")]) != Directory("d", [File("b")])
        assert Directory("d", [File("a")]) != Directory("e", [File("a")])

    def test_not_equal_to_a_file_with_the_same_name(self) -> None:
        assert Directory("x") != File("x")

    def test_hashable(self) -> None:
        assert hash(Directory("d", [File("a")])) == hash(Directory("d", [File("a")]))

    def test_nesting_and_patterned_names(self) -> None:
        tree = Directory(
            "dataset",
            [
                File("metadata.json"),
                Directory("images", [File(Glob("*.png"))]),
                Directory(Template("shard_{:03d}", range(8)), [File("data.bin")]),
            ],
        )
        assert tree.name == Literal("dataset")
        assert len(tree.children) == 3
        shard = tree.children[2]
        assert isinstance(shard, Directory)
        assert shard.name == Template("shard_{:03d}", range(8))
        assert shard.children == (File("data.bin"),)

    def test_repr(self) -> None:
        assert repr(Directory("d", [File("a")])) == (
            "Directory(Literal('d'), (File(Literal('a')),))"
        )


class TestDepth:
    def test_defaults_to_a_direct_child(self) -> None:
        for node in (File("a"), Directory("d")):
            assert node.min_depth == 1
            assert node.max_depth == 1

    def test_is_direct_child_only_for_exact_depth_one(self) -> None:
        assert File("a").is_direct_child  # default (1, 1)
        assert Directory("d").is_direct_child
        assert not File("a", depth=3).is_direct_child  # min != 1
        assert not File("a", depth=None).is_direct_child  # (1, None): max != 1
        assert not File("a", depth=(1, 2)).is_direct_child

    def test_exact_depth(self) -> None:
        node = File("frames", depth=3)
        assert (node.min_depth, node.max_depth) == (3, 3)

    def test_any_depth(self) -> None:
        node = Directory("frames", depth=None)
        assert (node.min_depth, node.max_depth) == (1, None)

    def test_range_depth(self) -> None:
        assert (
            File("a", depth=(2, 4)).min_depth,
            File("a", depth=(2, 4)).max_depth,
        ) == (
            2,
            4,
        )
        unbounded = File("a", depth=(2, None))
        assert (unbounded.min_depth, unbounded.max_depth) == (2, None)

    def test_directory_forwards_depth(self) -> None:
        node = Directory("frames", [File("a")], depth=(2, None))
        assert (node.min_depth, node.max_depth) == (2, None)
        assert node.children == (File("a"),)

    @pytest.mark.parametrize("bad", (0, -1))
    def test_non_positive_depth_raises(self, bad: int) -> None:
        with pytest.raises(ValueError, match="depth must be"):
            File("a", depth=bad)

    def test_max_below_min_raises(self) -> None:
        with pytest.raises(ValueError, match="below min"):
            File("a", depth=(5, 2))

    def test_scalar_and_none_are_canonical_ranges(self) -> None:
        assert File("a", depth=3) == File("a", depth=(3, 3))
        assert File("a", depth=None) == File("a", depth=(1, None))

    def test_depth_is_part_of_identity(self) -> None:
        assert File("a", depth=2) == File("a", depth=2)
        assert File("a", depth=2) != File("a")
        assert File("a", depth=None) != File("a", depth=2)
        assert hash(File("a", depth=2)) == hash(File("a", depth=2))

    def test_repr_renders_depth_in_compact_form(self) -> None:
        assert repr(File("a")) == "File(Literal('a'))"
        assert repr(File("a", depth=3)) == "File(Literal('a'), depth=3)"
        assert repr(File("a", depth=None)) == "File(Literal('a'), depth=None)"
        assert repr(File("a", depth=(2, 4))) == "File(Literal('a'), depth=(2, 4))"
        assert repr(File("a", depth=(2, None))) == (
            "File(Literal('a'), depth=(2, None))"
        )


class TestRequired:
    def test_defaults_to_false(self) -> None:
        assert File("a").required is False
        assert Directory("d").required is False

    def test_required_flag(self) -> None:
        assert File("a", required=True).required is True
        assert Directory("d", required=True).required is True

    def test_is_part_of_identity(self) -> None:
        assert File("a", required=True) == File("a", required=True)
        assert File("a", required=True) != File("a")
        assert hash(File("a", required=True)) == hash(File("a", required=True))

    def test_repr_shows_required(self) -> None:
        assert repr(File("a", required=True)) == "File(Literal('a'), required=True)"
        assert repr(File("a", depth=2, required=True)) == (
            "File(Literal('a'), depth=2, required=True)"
        )


class TestCondition:
    def test_defaults_to_none(self) -> None:
        assert File("a").condition is None
        assert Directory("d").condition is None

    def test_exposes_the_condition(self) -> None:
        # `Empty` applies to both kinds, so it can sit on either entry.
        cond = Empty()
        assert File("a", condition=cond).condition is cond
        assert Directory("d", condition=cond).condition is cond

    def test_is_part_of_identity(self) -> None:
        assert File("a", condition=Size(min=1)) == File("a", condition=Size(min=1))
        assert File("a", condition=Size(min=1)) != File("a")
        assert File("a", condition=Size(min=1)) != File("a", condition=Size(min=2))

    def test_repr_shows_condition(self) -> None:
        assert repr(File("a", condition=Size(min=1))) == (
            "File(Literal('a'), condition=Size(min=1, max=None))"
        )

    def test_rejects_file_only_condition_on_directory(self) -> None:
        with pytest.raises(ValueError, match="does not apply"):
            Directory("d", condition=Size(min=1))

    def test_rejects_dir_only_condition_on_file(self) -> None:
        with pytest.raises(ValueError, match="does not apply"):
            File("a", condition=ChildCount(min=1))

    def test_rejects_composite_with_a_mismatched_leaf(self) -> None:
        # `And(Size, ...)` is file-only (intersection), so a Directory rejects it.
        with pytest.raises(ValueError, match="does not apply"):
            Directory("d", condition=And((Size(min=1), Empty())))

    def test_accepts_a_kind_matching_condition(self) -> None:
        assert File("a", condition=Size(min=1)).condition is not None
        assert Directory("d", condition=ChildCount(min=1)).condition is not None


class TestNameSeparator:
    @pytest.mark.parametrize("bad", ("a/b", "a\\b", "dir/sub.txt"))
    def test_str_name_with_separator_raises(self, bad: str) -> None:
        with pytest.raises(ValueError, match="single path component"):
            File(bad)

    def test_list_name_with_separator_raises(self) -> None:
        with pytest.raises(ValueError, match="single path component"):
            Directory(["ok", "a/b"])

    def test_explicit_filter_name_is_not_checked(self) -> None:
        # An explicit filter is the caller's responsibility, not sugar.
        name = Glob("a/*")
        assert File(name).name is name

    def test_empty_list_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name list must be non-empty"):
            File([])


class TestFrozen:
    """Nodes are immutable value objects; assignment / deletion must raise."""

    def test_assignment_is_rejected(self) -> None:
        with pytest.raises(FrozenInstanceError):
            File("a")._name = Literal("b")  # noqa: SLF001

    def test_deletion_is_rejected(self) -> None:
        with pytest.raises(FrozenInstanceError):
            del File("a")._name  # noqa: SLF001


class TestAcceptsDepth:
    def test_default_depth_accepts_one(self) -> None:
        assert File("a").accepts_depth(1) is True

    def test_exact_depth_accepts_only_that_level(self) -> None:
        f = File("a", depth=3)
        assert f.accepts_depth(3) is True
        assert f.accepts_depth(2) is False
        assert f.accepts_depth(4) is False

    def test_range_depth_accepts_inclusive_bounds(self) -> None:
        f = File("a", depth=(2, 4))
        assert f.accepts_depth(1) is False
        assert f.accepts_depth(2) is True
        assert f.accepts_depth(3) is True
        assert f.accepts_depth(4) is True
        assert f.accepts_depth(5) is False

    def test_unbounded_max_accepts_any_depth_at_or_above_min(self) -> None:
        f = File("a", depth=None)
        assert f.accepts_depth(1) is True
        assert f.accepts_depth(100) is True


class TestAcceptsKind:
    def test_file_entry_matches_a_file_path(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.touch()
        assert File("x.txt").accepts_kind(p) is True

    def test_file_entry_rejects_a_directory_path(self, tmp_path: Path) -> None:
        d = tmp_path / "sub"
        d.mkdir()
        assert File("sub").accepts_kind(d) is False

    def test_directory_entry_matches_a_directory_path(self, tmp_path: Path) -> None:
        d = tmp_path / "sub"
        d.mkdir()
        assert Directory("sub").accepts_kind(d) is True

    def test_directory_entry_rejects_a_file_path(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.touch()
        assert Directory("x.txt").accepts_kind(p) is False

    def test_directory_children_are_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            Directory("d", [File("a")])._children = ()  # noqa: SLF001


class TestDirectoryAllowExtra:
    def test_defaults_false(self) -> None:
        assert Directory("d").allow_extra is False

    def test_stored(self) -> None:
        assert Directory("d", allow_extra=True).allow_extra is True

    def test_distinguishes_equality(self) -> None:
        assert Directory("d", allow_extra=True) != Directory("d")
        assert Directory("d", allow_extra=True) == Directory("d", allow_extra=True)

    def test_repr_shows_only_when_set(self) -> None:
        assert "allow_extra=True" in repr(Directory("d", allow_extra=True))
        assert "allow_extra" not in repr(Directory("d"))

    def test_round_trips(self) -> None:
        spec = Directory("d", [File("a")], allow_extra=True)
        assert spec.to_dict()["allow_extra"] is True
        assert Directory.from_dict(spec.to_dict()) == spec

    def test_filter_form(self) -> None:
        spec = Directory("d", allow_extra=Glob("*.zip"))
        assert spec.allow_extra == Glob("*.zip")
        assert spec != Directory("d", allow_extra=Glob("*.tar"))
        assert "*.zip" in repr(spec)
        assert Directory.from_dict(spec.to_dict()) == spec  # round-trips the filter


class TestMatches:
    def test_true_when_name_and_kind_both_fit(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.touch()
        assert File("x.txt").matches(p) is True

    def test_false_on_name_mismatch(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.touch()
        assert File("other.txt").matches(p) is False

    def test_false_on_kind_mismatch(self, tmp_path: Path) -> None:
        d = tmp_path / "sub"
        d.mkdir()
        assert File("sub").matches(d) is False  # name fits, kind does not

    def test_ignores_depth(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.touch()
        assert File("x.txt", depth=2).matches(p) is True  # depth is not weighed


class TestAcceptsCondition:
    def test_no_condition_is_satisfied(self, tmp_path: Path) -> None:
        assert File("f").accepts_condition(tmp_path / "f", HookResolver()) is True

    def test_passing_condition_is_satisfied(self, tmp_path: Path) -> None:
        f = tmp_path / "f"
        f.write_bytes(b"x")  # 1 byte
        node = File("f", condition=Size(min=1))
        assert node.accepts_condition(f, HookResolver()) is True

    def test_failing_condition_is_not_satisfied(self, tmp_path: Path) -> None:
        f = tmp_path / "f"
        f.write_bytes(b"")  # 0 bytes
        node = File("f", condition=Size(min=1))
        assert node.accepts_condition(f, HookResolver()) is False


class TestDirectoryChildrenCoercion:
    def test_a_single_node_is_taken_as_one_child(self) -> None:
        assert Directory("d", File("a")).children == (File("a"),)

    def test_a_single_node_equals_the_one_element_iterable(self) -> None:
        assert Directory("d", File("a")) == Directory("d", [File("a")])

    def test_a_nested_directory_may_be_passed_bare(self) -> None:
        inner = Directory("images", File(Glob("*.png")))
        assert Directory("dataset", inner).children == (inner,)

    def test_a_generator_of_nodes_is_consumed(self) -> None:
        kids = [File("a"), File("b")]
        assert Directory("d", (kid for kid in kids)).children == tuple(kids)

    @pytest.mark.parametrize(
        ("children", "match"),
        (
            ("abc", "expected a Node or an iterable of Nodes"),
            ("", "expected a Node or an iterable of Nodes"),
            (123, "expected a Node or an iterable of Nodes"),
            (None, "expected a Node or an iterable of Nodes"),
            (["a.txt"], "expected every node to be a Node"),
            ([1, 2], "expected every node to be a Node"),
        ),
    )
    def test_a_non_node_is_refused_at_construction(self, children, match) -> None:
        # A non-`Node` reaching a spec tree is otherwise only caught when a
        # traversal dereferences it, far from where it was written.
        with pytest.raises(TypeError, match=match):
            Directory("d", children)

    def test_a_str_never_splits_into_characters(self) -> None:
        with pytest.raises(TypeError):
            Directory("d", "abc")


class TestNestedDirs:
    def test_one_directory_per_level(self) -> None:
        spec = nested_dirs([["dataset"], ["train", "val"], ["images", "labels"]])
        assert spec == Directory(
            "dataset",
            Directory(["train", "val"], Directory(["images", "labels"])),
        )

    def test_a_one_name_level_reads_as_that_name(self) -> None:
        assert nested_dirs([["dataset"]]).name == Literal("dataset")
        assert nested_dirs(["dataset"]).name == Literal("dataset")

    def test_a_level_may_be_a_filter(self) -> None:
        spec = nested_dirs([["ds"], Glob("run_*")])
        assert spec.children[0].name == Glob("run_*")  # ty: ignore[unresolved-attribute]

    def test_plain_children_land_at_the_innermost_level(self) -> None:
        spec = nested_dirs([["ds"], ["a", "b"]], File("index.json"))
        assert spec.children[0].children == (File("index.json"),)  # ty: ignore[unresolved-attribute]

    def test_plain_children_agree_with_the_innermost_key(self) -> None:
        levels = [["ds"], ["a", "b"]]
        assert nested_dirs(levels, File("i")) == nested_dirs(levels, {-1: File("i")})

    def test_children_are_placed_beside_the_sub_directory(self) -> None:
        spec = nested_dirs([["ds"], ["a"]], {0: File("README.md")})
        assert spec.children == (File("README.md"), Directory("a"))

    def test_both_index_directions_name_the_same_level(self) -> None:
        levels = [["ds"], ["a"], ["b"]]
        assert nested_dirs(levels, {0: File("x")}) == nested_dirs(
            levels, {-3: File("x")}
        )

    def test_several_nodes_may_share_a_level(self) -> None:
        spec = nested_dirs([["ds"], ["a"]], {0: [File("x"), Directory("logs")]})
        assert spec.children == (File("x"), Directory("logs"), Directory("a"))

    def test_the_result_is_an_ordinary_directory(self) -> None:
        spec = nested_dirs([["ds"], ["a"]], File("x"))
        assert type(spec) is Directory
        assert Node.from_dict(spec.to_dict()) == spec

    def test_empty_levels_are_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one level"):
            nested_dirs([])

    def test_a_level_naming_nothing_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least one directory"):
            nested_dirs([["ds"], []])

    @pytest.mark.parametrize("key", (3, -4, 99))
    def test_a_key_outside_the_levels_is_refused(self, key) -> None:
        with pytest.raises(IndexError, match="out of range for 3 levels"):
            nested_dirs([["a"], ["b"], ["c"]], {key: File("x")})

    def test_two_keys_naming_one_level_are_refused(self) -> None:
        # `0` and `-3` are the same level; silently dropping one would lose nodes.
        with pytest.raises(ValueError, match="same level as an earlier key"):
            nested_dirs([["a"], ["b"], ["c"]], {0: File("x"), -3: File("y")})
