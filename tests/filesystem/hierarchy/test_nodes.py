from __future__ import annotations

import pytest

from kaparoo.filesystem.hierarchy import Directory, File, Literal, OneOf, Template
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
    def test_defaults_to_one(self) -> None:
        assert File("a").depth == 1
        assert Directory("d").depth == 1

    def test_exact_depth(self) -> None:
        assert File("frames", depth=3).depth == 3

    def test_any_depth(self) -> None:
        assert Directory("frames", depth=None).depth is None

    def test_directory_forwards_depth(self) -> None:
        node = Directory("frames", [File("a")], depth=2)
        assert node.depth == 2
        assert node.children == (File("a"),)

    @pytest.mark.parametrize("bad", (0, -1))
    def test_non_positive_depth_raises(self, bad: int) -> None:
        with pytest.raises(ValueError, match="depth must be"):
            File("a", depth=bad)

    def test_depth_is_part_of_identity(self) -> None:
        assert File("a", depth=2) == File("a", depth=2)
        assert File("a", depth=2) != File("a")
        assert File("a", depth=None) != File("a", depth=2)
        assert hash(File("a", depth=2)) == hash(File("a", depth=2))

    def test_repr_hides_default_depth_but_shows_others(self) -> None:
        assert repr(File("a")) == "File(Literal(name='a'))"
        assert repr(File("a", depth=3)) == "File(Literal(name='a'), depth=3)"
        assert repr(Directory("d", depth=None)) == (
            "Directory(Literal(name='d'), (), depth=None)"
        )
