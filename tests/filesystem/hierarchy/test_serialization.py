from __future__ import annotations

import pytest

from kaparoo.filesystem.hierarchy import (
    Directory,
    Entry,
    Exclusive,
    File,
    Group,
    Node,
    Together,
)
from kaparoo.filters import Glob, Template


def roundtrip(node: Node) -> Node:
    return Node.from_dict(node.to_dict())


class TestFileSerialization:
    @pytest.mark.parametrize(
        "node",
        (
            File("a.txt"),
            File(Glob("*.png")),
            File("frames", depth=None),
            File("x", depth=(2, 4)),
        ),
    )
    def test_round_trips(self, node: File) -> None:
        assert roundtrip(node) == node

    def test_to_dict_shape(self) -> None:
        assert File("a.txt").to_dict() == {
            "node": "file",
            "name": {"kind": "literal", "name": "a.txt"},
        }
        assert File("a", depth=3).to_dict()["depth"] == [3, 3]


class TestDirectorySerialization:
    @pytest.mark.parametrize(
        "node",
        (
            Directory("empty"),
            Directory("d", [File("a"), File("b")]),
            Directory(["train", "val"], [File("x")], depth=(1, None)),
        ),
    )
    def test_round_trips(self, node: Directory) -> None:
        assert roundtrip(node) == node

    def test_empty_directory_omits_children_key(self) -> None:
        assert "children" not in Directory("empty").to_dict()


class TestGroupSerialization:
    @pytest.mark.parametrize(
        "node",
        (
            Exclusive(File("setup.py"), File("pyproject.toml")),
            Exclusive([File("a"), File("b")], File("c"), required=True),
            Together(File("cert.pem"), File("key.pem")),
            Together(File("a"), File("b"), required=True),
            Exclusive(Together(File("a"), File("b")), File("c")),  # nested
        ),
    )
    def test_round_trips(self, node: Group) -> None:
        assert roundtrip(node) == node

    def test_required_omitted_when_false(self) -> None:
        assert "required" not in Exclusive(File("a"), File("b")).to_dict()
        assert "required" not in Together(File("a"), File("b")).to_dict()


class TestTreeSerialization:
    def test_full_tree_round_trips(self) -> None:
        tree = Directory(
            "dataset",
            [
                File("metadata.json"),
                Directory(
                    ["train", "val"],
                    [
                        Directory(
                            Template("shard_{:03d}", range(4)), [File("data.bin")]
                        ),
                    ],
                ),
                Directory("images", [File(Glob("*.png"))]),
                Exclusive(
                    Together(File("setup.py"), File("setup.cfg")),
                    File("pyproject.toml"),
                    required=True,
                ),
                File("notes.txt", depth=None),
            ],
        )
        assert roundtrip(tree) == tree

    def test_round_trip_keeps_equality_not_identity(self) -> None:
        shared = Directory("images", [File(Glob("*.png"))])
        tree = Directory("d", [shared, shared])
        restored = roundtrip(tree)
        assert restored == tree  # value equality survives
        assert isinstance(restored, Directory)
        first, second = restored.children
        assert first == second  # equal subtrees
        assert first is not second  # but distinct objects (JSON has no aliasing)


class TestFromDictErrors:
    def test_missing_node_discriminator(self) -> None:
        with pytest.raises(ValueError, match="missing 'node'"):
            Node.from_dict({"name": {"kind": "literal", "name": "x"}})

    def test_unknown_node_kind(self) -> None:
        with pytest.raises(ValueError, match="unknown node kind"):
            Node.from_dict({"node": "bogus"})

    @pytest.mark.parametrize("base", (Entry, Group))
    def test_abstract_base_from_dict_not_implemented(self, base: type[Node]) -> None:
        with pytest.raises(NotImplementedError, match="must be overridden"):
            base.from_dict({"node": "file"})
