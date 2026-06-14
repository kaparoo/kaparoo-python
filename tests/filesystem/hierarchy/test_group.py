from __future__ import annotations

from dataclasses import FrozenInstanceError

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

    def test_on_conflict_defaults_to_error(self) -> None:
        assert Exclusive(File("a"), File("b")).on_conflict == "error"
        ex = Exclusive(File("a"), File("b"), on_conflict="priority")
        assert ex.on_conflict == "priority"

    def test_invalid_on_conflict_raises(self) -> None:
        with pytest.raises(ValueError, match="on_conflict"):
            Exclusive(File("a"), File("b"), on_conflict="first")  # ty: ignore[invalid-argument-type]

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
        assert Exclusive(File("a"), File("b")) != Exclusive(
            File("a"), File("b"), on_conflict="priority"
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
            "Exclusive(File(Literal('a')), File(Literal('b')))"
        )
        assert repr(Exclusive(File("a"), File("b"), required=True)) == (
            "Exclusive(File(Literal('a')), File(Literal('b')), required=True)"
        )
        assert repr(Exclusive([File("a"), File("b")], File("c"))) == (
            "Exclusive((File(Literal('a')), File(Literal('b'))), File(Literal('c')))"
        )
        assert repr(Exclusive(File("a"), File("b"), on_conflict="priority")) == (
            "Exclusive(File(Literal('a')), File(Literal('b')), on_conflict='priority')"
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
            "Together(File(Literal('a')), File(Literal('b')))"
        )
        assert repr(Together(File("a"), File("b"), required=True)) == (
            "Together(File(Literal('a')), File(Literal('b')), required=True)"
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

    def test_groups_are_frozen(self) -> None:
        for group in (
            Exclusive(File("a"), File("b")),
            Together(File("a"), File("b")),
        ):
            with pytest.raises(FrozenInstanceError):
                group._required = True  # noqa: SLF001
