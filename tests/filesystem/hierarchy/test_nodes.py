from __future__ import annotations

import pytest

from kaparoo.filesystem.hierarchy import (
    Directory,
    Entry,
    Exclusive,
    File,
    Group,
    Literal,
    Node,
    OneOf,
    Template,
    Together,
)
from kaparoo.filters import Glob


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
        assert repr(File("a.txt")) == "File(Literal(name='a.txt'))"


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
            "Directory(Literal(name='d'), (File(Literal(name='a')),))"
        )


class TestDepth:
    def test_defaults_to_a_direct_child(self) -> None:
        for node in (File("a"), Directory("d")):
            assert node.min_depth == 1
            assert node.max_depth == 1

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
        assert repr(File("a")) == "File(Literal(name='a'))"
        assert repr(File("a", depth=3)) == "File(Literal(name='a'), depth=3)"
        assert repr(File("a", depth=None)) == "File(Literal(name='a'), depth=None)"
        assert repr(File("a", depth=(2, 4))) == "File(Literal(name='a'), depth=(2, 4))"
        assert repr(File("a", depth=(2, None))) == (
            "File(Literal(name='a'), depth=(2, None))"
        )


class TestExclusive:
    def test_is_a_group_node_but_not_an_entry(self) -> None:
        ex = Exclusive(File("setup.py"), File("pyproject.toml"))
        assert isinstance(ex, Node)
        assert isinstance(ex, Group)
        assert not isinstance(ex, Entry)

    def test_entries_flatten_the_alternatives(self) -> None:
        ex = Exclusive([File("a"), File("b")], File("c"))
        assert ex.entries == (File("a"), File("b"), File("c"))

    def test_nested_group_alternative(self) -> None:
        # "{a and b together} or c" -- an alternative is itself a Together.
        together = Together(File("a"), File("b"))
        ex = Exclusive(together, File("c"))
        assert ex.alternatives == ((together,), (File("c"),))
        assert ex.entries == (File("a"), File("b"), File("c"))  # recursive leaves

    def test_single_entry_alternatives(self) -> None:
        ex = Exclusive(File("setup.py"), File("pyproject.toml"))
        assert ex.alternatives == ((File("setup.py"),), (File("pyproject.toml"),))

    def test_group_alternatives(self) -> None:
        ex = Exclusive([Directory("src"), File("setup.cfg")], Directory("legacy"))
        assert ex.alternatives == (
            (Directory("src"), File("setup.cfg")),
            (Directory("legacy"),),
        )

    def test_required_defaults_to_false(self) -> None:
        assert Exclusive(File("a"), File("b")).required is False
        assert Exclusive(File("a"), File("b"), required=True).required is True

    def test_files_and_directories_are_both_accepted(self) -> None:
        ex = Exclusive(Directory("build"), Directory("dist"))
        assert ex.alternatives == ((Directory("build"),), (Directory("dist"),))

    def test_fewer_than_two_alternatives_raises(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            Exclusive(File("only"))

    def test_empty_alternative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            Exclusive([], File("a"))

    def test_value_semantics(self) -> None:
        assert Exclusive(File("a"), File("b")) == Exclusive(File("a"), File("b"))
        assert Exclusive(File("a"), File("b")) != Exclusive(File("a"), File("c"))
        assert Exclusive(File("a"), File("b")) != Exclusive(
            File("a"), File("b"), required=True
        )
        assert hash(Exclusive(File("a"), File("b"))) == hash(
            Exclusive(File("a"), File("b"))
        )

    def test_not_equal_to_an_entry(self) -> None:
        assert Exclusive(File("a"), File("b")) != File("a")

    def test_can_be_a_directory_child(self) -> None:
        ex = Exclusive(File("setup.py"), File("pyproject.toml"))
        project = Directory("project", [File("README.md"), ex])
        assert project.children == (File("README.md"), ex)

    def test_repr(self) -> None:
        assert repr(Exclusive(File("a"), File("b"))) == (
            "Exclusive(File(Literal(name='a')), File(Literal(name='b')))"
        )
        assert repr(Exclusive(File("a"), File("b"), required=True)) == (
            "Exclusive(File(Literal(name='a')), File(Literal(name='b')), required=True)"
        )
        assert repr(Exclusive([File("a"), File("b")], File("c"))) == (
            "Exclusive((File(Literal(name='a')), File(Literal(name='b'))), "
            "File(Literal(name='c')))"
        )


class TestTogether:
    def test_is_a_group_node_but_not_an_entry(self) -> None:
        together = Together(File("weights.bin"), File("weights.index"))
        assert isinstance(together, Node)
        assert isinstance(together, Group)
        assert not isinstance(together, Entry)

    def test_members(self) -> None:
        together = Together(File("cert.pem"), File("key.pem"))
        assert together.members == (File("cert.pem"), File("key.pem"))

    def test_entries_are_the_members(self) -> None:
        together = Together(File("a"), File("b"))
        assert together.entries == together.members == (File("a"), File("b"))

    def test_nested_group_member_flattens_recursively(self) -> None:
        inner = Exclusive(File("a"), File("b"))
        together = Together(inner, File("c"))
        assert together.members == (inner, File("c"))
        assert together.entries == (File("a"), File("b"), File("c"))

    def test_files_and_directories_both_accepted(self) -> None:
        together = Together(Directory("src"), File("setup.cfg"))
        assert together.members == (Directory("src"), File("setup.cfg"))

    def test_required_defaults_to_false(self) -> None:
        assert Together(File("a"), File("b")).required is False
        assert Together(File("a"), File("b"), required=True).required is True

    def test_fewer_than_two_members_raises(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            Together(File("only"))

    def test_value_semantics(self) -> None:
        assert Together(File("a"), File("b")) == Together(File("a"), File("b"))
        assert Together(File("a"), File("b")) != Together(File("a"), File("c"))
        assert Together(File("a"), File("b")) != Together(
            File("a"), File("b"), required=True
        )
        assert hash(Together(File("a"), File("b"))) == hash(
            Together(File("a"), File("b"))
        )

    def test_not_equal_to_exclusive_with_same_members(self) -> None:
        assert Together(File("a"), File("b")) != Exclusive(File("a"), File("b"))

    def test_can_be_a_directory_child(self) -> None:
        together = Together(File("weights.bin"), File("weights.index"))
        model = Directory("model", [together])
        assert model.children == (together,)

    def test_repr(self) -> None:
        assert repr(Together(File("a"), File("b"))) == (
            "Together(File(Literal(name='a')), File(Literal(name='b')))"
        )
        assert repr(Together(File("a"), File("b"), required=True)) == (
            "Together(File(Literal(name='a')), File(Literal(name='b')), required=True)"
        )


class TestGroup:
    def test_entries_are_not_groups(self) -> None:
        assert not isinstance(File("a"), Group)
        assert not isinstance(Directory("d"), Group)

    def test_required_is_shared_across_constraint_kinds(self) -> None:
        for group in (
            Exclusive(File("a"), File("b"), required=True),
            Together(File("a"), File("b"), required=True),
        ):
            assert isinstance(group, Group)
            assert group.required is True
            assert group.entries == (File("a"), File("b"))
