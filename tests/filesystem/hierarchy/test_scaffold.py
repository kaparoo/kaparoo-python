from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem import NotAFileError
from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Together,
    scaffold,
)
from kaparoo.filesystem.hierarchy.base import Node
from kaparoo.filters import Glob, Template

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


def rel(paths: list[Path], root: Path) -> list[str]:
    """Root-relative POSIX strings, for order-sensitive assertions."""
    return [p.relative_to(root).as_posix() for p in paths]


class FakeNode(Node):
    """A `Node` outside the File/Directory/Together/Exclusive closed world."""

    __slots__ = ()

    def _key(self) -> tuple[object, ...]:
        return ()

    def to_dict(self) -> dict[str, Any]:
        return {"node": "fake"}


class TestScaffoldBasics:
    def test_creates_files_and_dirs_empty_in_order(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt"), Directory("sub", [File("b.txt")])])
        created = scaffold(spec, tmp_path)
        assert rel(created, tmp_path) == ["d", "d/a.txt", "d/sub", "d/sub/b.txt"]
        assert (tmp_path / "d" / "a.txt").is_file()
        assert (tmp_path / "d" / "a.txt").read_text() == ""  # empty skeleton
        assert (tmp_path / "d" / "sub").is_dir()

    def test_root_created_when_absent(self, tmp_path: Path) -> None:
        root = tmp_path / "nope" / "deep"
        scaffold(File("x"), root)
        assert (root / "x").is_file()  # parents made too

    def test_top_node_can_be_a_group(self, tmp_path: Path) -> None:
        created = scaffold(Together(File("a"), File("b")), tmp_path)
        assert rel(created, tmp_path) == ["a", "b"]


class TestEnumerableNames:
    def test_list_sugar_creates_each_sibling(self, tmp_path: Path) -> None:
        scaffold(Directory(["train", "val"], [File("data.csv")]), tmp_path)
        assert (tmp_path / "train" / "data.csv").is_file()
        assert (tmp_path / "val" / "data.csv").is_file()

    def test_template_creates_every_combination(self, tmp_path: Path) -> None:
        created = scaffold(File(Template("shard_{:02d}.bin", range(3))), tmp_path)
        assert rel(created, tmp_path) == [
            "shard_00.bin",
            "shard_01.bin",
            "shard_02.bin",
        ]


class TestNonCreatable:
    def test_open_filter_optional_is_skipped(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("keep.txt"), File(Glob("*.log"))])
        created = scaffold(spec, tmp_path)
        assert rel(created, tmp_path) == ["d", "d/keep.txt"]  # glob skipped

    def test_open_filter_required_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not creatable"):
            scaffold(File(Glob("*.log"), required=True), tmp_path)

    def test_open_directory_optional_is_skipped(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("keep"), Directory(Glob("sub*"), [File("x")])])
        created = scaffold(spec, tmp_path)
        assert rel(created, tmp_path) == ["d", "d/keep"]  # open dir skipped

    def test_non_fixed_depth_optional_is_skipped(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("here"), File("deep", depth=2)])
        created = scaffold(spec, tmp_path)
        assert rel(created, tmp_path) == ["d", "d/here"]

    def test_non_fixed_depth_required_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="fixed depth of 1"):
            scaffold(File("any", depth=None, required=True), tmp_path)


class TestTogether:
    def test_creates_all_members(self, tmp_path: Path) -> None:
        created = scaffold(Together(File("cert.pem"), File("key.pem")), tmp_path)
        assert rel(created, tmp_path) == ["cert.pem", "key.pem"]

    def test_non_creatable_member_skips_whole_group(self, tmp_path: Path) -> None:
        # all-or-nothing: an open member skips the set, so 'b' is NOT created
        group = Together(File("b"), File(Glob("*.idx")))
        spec = Directory("d", [File("solo"), group])
        created = scaffold(spec, tmp_path)
        assert rel(created, tmp_path) == ["d", "d/solo"]
        assert not (tmp_path / "d" / "b").exists()

    def test_required_non_creatable_member_raises(self, tmp_path: Path) -> None:
        group = Together(File("b"), File(Glob("*.idx")), required=True)
        with pytest.raises(ValueError, match="required"):
            scaffold(Directory("d", [group]), tmp_path)


class TestExclusive:
    def test_creates_first_alternative(self, tmp_path: Path) -> None:
        group = Exclusive(File("pyproject.toml"), File("setup.py"))
        created = scaffold(Directory("d", [group]), tmp_path)
        assert rel(created, tmp_path) == ["d", "d/pyproject.toml"]
        assert not (tmp_path / "d" / "setup.py").exists()

    def test_skips_non_creatable_leading_alternative(self, tmp_path: Path) -> None:
        # first alternative is open -> fall through to the concrete one
        group = Exclusive(File(Glob("*.cfg")), File("pyproject.toml"))
        created = scaffold(Directory("d", [group]), tmp_path)
        assert rel(created, tmp_path) == ["d", "d/pyproject.toml"]

    def test_no_creatable_alternative_optional_is_skipped(self, tmp_path: Path) -> None:
        group = Exclusive(File(Glob("*.a")), File(Glob("*.b")))
        created = scaffold(Directory("d", [group]), tmp_path)
        assert rel(created, tmp_path) == ["d"]

    def test_no_creatable_alternative_required_raises(self, tmp_path: Path) -> None:
        group = Exclusive(File(Glob("*.a")), File(Glob("*.b")), required=True)
        with pytest.raises(ValueError, match="required"):
            scaffold(Directory("d", [group]), tmp_path)


class TestNestedGroupCreatability:
    def test_nested_together_member(self, tmp_path: Path) -> None:
        group = Together(Together(File("a"), File("b")), File("c"))
        created = scaffold(group, tmp_path)
        assert rel(created, tmp_path) == ["a", "b", "c"]

    def test_nested_exclusive_member(self, tmp_path: Path) -> None:
        group = Together(Exclusive(File("a"), File("b")), File("c"))
        created = scaffold(group, tmp_path)
        assert rel(created, tmp_path) == ["a", "c"]  # Exclusive picks first


class TestIdempotency:
    def test_rerun_creates_nothing_and_preserves_content(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt")])
        scaffold(spec, tmp_path)
        (tmp_path / "d" / "a.txt").write_text("kept")
        again = scaffold(spec, tmp_path)
        assert again == []  # nothing new
        assert (tmp_path / "d" / "a.txt").read_text() == "kept"  # not clobbered

    def test_existing_dir_is_descended(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        created = scaffold(Directory("d", [File("new.txt")]), tmp_path)
        assert rel(created, tmp_path) == ["d/new.txt"]  # only the new child


class TestTypeConflict:
    def test_file_where_directory_expected_raises(self, tmp_path: Path) -> None:
        (tmp_path / "d").write_text("i am a file")
        with pytest.raises(NotADirectoryError, match="a file exists there"):
            scaffold(Directory("d", [File("x")]), tmp_path)

    def test_directory_where_file_expected_raises(self, tmp_path: Path) -> None:
        (tmp_path / "x").mkdir()
        with pytest.raises(NotAFileError, match="a directory exists there"):
            scaffold(File("x"), tmp_path)


class TestDryRun:
    def test_returns_plan_without_touching_disk(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a"), Directory("sub", [File("b")])])
        plan = scaffold(spec, tmp_path, dry_run=True)
        assert rel(plan, tmp_path) == ["d", "d/a", "d/sub", "d/sub/b"]
        assert not (tmp_path / "d").exists()  # disk untouched

    def test_reflects_existing_paths(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "a").touch()
        plan = scaffold(Directory("d", [File("a"), File("b")]), tmp_path, dry_run=True)
        assert rel(plan, tmp_path) == ["d/b"]  # 'd' and 'a' already exist

    def test_still_raises_on_unsatisfiable_required(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="required"):
            scaffold(File(Glob("*.log"), required=True), tmp_path, dry_run=True)


class TestScaffoldAtRoot:
    def test_directory_top_creates_root_and_children(self, tmp_path: Path) -> None:
        spec = Directory("dataset", [File("meta.json"), Directory("imgs", [])])
        root = tmp_path / "dataset"
        created = scaffold(spec, root, root_as_top=True)
        assert rel(created, tmp_path) == [
            "dataset",
            "dataset/meta.json",
            "dataset/imgs",
        ]
        assert (root / "meta.json").is_file()
        assert (root / "imgs").is_dir()

    def test_file_top_creates_root_itself(self, tmp_path: Path) -> None:
        root = tmp_path / "model.bin"
        created = scaffold(File("model.bin"), root, root_as_top=True)
        assert created == [root]
        assert root.is_file()

    def test_root_parent_created_when_absent(self, tmp_path: Path) -> None:
        root = tmp_path / "deep" / "nested" / "dataset"
        scaffold(Directory("dataset", [File("x")]), root, root_as_top=True)
        assert (root / "x").is_file()  # intermediate parents made too

    def test_name_mismatch_optional_is_skipped(self, tmp_path: Path) -> None:
        spec = Directory("dataset", [File("x")])
        created = scaffold(spec, tmp_path / "other", root_as_top=True)
        assert created == []
        assert not (tmp_path / "other").exists()  # nothing created

    def test_name_mismatch_required_raises(self, tmp_path: Path) -> None:
        spec = File("model.bin", required=True)
        with pytest.raises(ValueError, match="does not match"):
            scaffold(spec, tmp_path / "other.bin", root_as_top=True)

    def test_group_top_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="Entry top node"):
            scaffold(Exclusive(File("a"), File("b")), tmp_path, root_as_top=True)

    def test_existing_root_is_descended(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        root.mkdir()
        created = scaffold(Directory("dataset", [File("new")]), root, root_as_top=True)
        assert rel(created, tmp_path) == ["dataset/new"]  # only the new child

    def test_dry_run_plans_without_touching_disk(self, tmp_path: Path) -> None:
        spec = Directory("dataset", [File("a"), File("b")])
        root = tmp_path / "dataset"
        plan = scaffold(spec, root, root_as_top=True, dry_run=True)
        assert rel(plan, tmp_path) == ["dataset", "dataset/a", "dataset/b"]
        assert not root.exists()  # disk untouched


class TestOnCreate:
    def test_called_for_each_new_file_to_fill_content(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt"), Directory("sub", [File("b.txt")])])

        def fill(path: Path, node: File) -> None:
            path.write_text(f"content of {path.name}")

        scaffold(spec, tmp_path, on_create=fill)
        assert (tmp_path / "d" / "a.txt").read_text() == "content of a.txt"
        assert (tmp_path / "d" / "sub" / "b.txt").read_text() == "content of b.txt"

    def test_receives_the_spec_file_node(self, tmp_path: Path) -> None:
        leaf = File(Template("shard_{:02d}.bin", range(2)))
        calls: list[tuple[str, File]] = []
        scaffold(leaf, tmp_path, on_create=lambda p, n: calls.append((p.name, n)))
        assert [name for name, _ in calls] == ["shard_00.bin", "shard_01.bin"]
        assert all(node is leaf for _, node in calls)  # same spec node each time

    def test_not_called_for_existing_file(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt")])
        scaffold(spec, tmp_path)  # create the file first
        (tmp_path / "d" / "a.txt").write_text("kept")
        seen: list[Path] = []
        again = scaffold(spec, tmp_path, on_create=lambda p, n: seen.append(p))
        assert again == []  # nothing new
        assert seen == []  # idempotent: hook not fired
        assert (tmp_path / "d" / "a.txt").read_text() == "kept"  # not clobbered

    def test_not_called_under_dry_run(self, tmp_path: Path) -> None:
        seen: list[Path] = []
        plan = scaffold(
            File("a.txt"), tmp_path, on_create=lambda p, n: seen.append(p), dry_run=True
        )
        assert rel(plan, tmp_path) == ["a.txt"]  # planned
        assert seen == []  # but the hook never ran
        assert not (tmp_path / "a.txt").exists()

    def test_fires_for_a_file_top(self, tmp_path: Path) -> None:
        root = tmp_path / "model.bin"
        scaffold(
            File("model.bin"),
            root,
            root_as_top=True,
            on_create=lambda p, n: p.write_text("weights"),
        )
        assert root.read_text() == "weights"

    def test_combined_with_dirs_only_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="dirs_only"):
            scaffold(File("a"), tmp_path, on_create=lambda p, n: None, dirs_only=True)


class TestDirsOnly:
    def test_creates_only_directories(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt"), Directory("sub", [File("b.txt")])])
        created = scaffold(spec, tmp_path, dirs_only=True)
        assert rel(created, tmp_path) == ["d", "d/sub"]  # files skipped
        assert not (tmp_path / "d" / "a.txt").exists()
        assert (tmp_path / "d" / "sub").is_dir()

    def test_skips_required_files_too(self, tmp_path: Path) -> None:
        # a required file would normally be enforced; dirs_only overrides that
        spec = Directory("d", [File("must.txt", required=True)])
        created = scaffold(spec, tmp_path, dirs_only=True)
        assert rel(created, tmp_path) == ["d"]
        assert not (tmp_path / "d" / "must.txt").exists()

    def test_file_top_creates_nothing(self, tmp_path: Path) -> None:
        root = tmp_path / "model.bin"
        created = scaffold(File("model.bin"), root, root_as_top=True, dirs_only=True)
        assert created == []
        assert not root.exists()


class TestUnknownNodeType:
    # The Node hierarchy is closed (File / Directory / Together / Exclusive),
    # so these guard the defensive `case _` arms against a future subtree.
    def test_dispatch_rejects_unknown_node(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="unsupported node type"):
            scaffold(FakeNode(), tmp_path)

    def test_node_creatability_rejects_unknown_node(self, tmp_path: Path) -> None:
        # reached when a group computes its members' creatability
        with pytest.raises(TypeError, match="unsupported node type"):
            scaffold(Together(FakeNode(), File("a")), tmp_path)


class TestBestEffortFailure:
    # scaffold's documented failure contract: a mid-run raise is NOT rolled
    # back -- paths already created stay, and an idempotent re-run resumes.
    def test_on_create_raise_leaves_earlier_paths(self, tmp_path: Path) -> None:
        spec = Directory("d", [File("a.txt"), File("b.txt"), File("c.txt")])

        def fill(path: Path, node: File) -> None:
            if path.name == "b.txt":
                msg = "boom"
                raise RuntimeError(msg)
            path.write_text(f"content of {path.name}")

        with pytest.raises(RuntimeError, match="boom"):
            scaffold(spec, tmp_path, on_create=fill)

        d = tmp_path / "d"
        assert d.is_dir()
        assert (d / "a.txt").read_text() == "content of a.txt"  # created before
        assert (d / "b.txt").is_file()  # touched before its hook ran...
        assert (d / "b.txt").read_text() == ""  # ...but content never written
        assert not (d / "c.txt").exists()  # never reached

    def test_idempotent_rerun_resumes_after_partial_failure(
        self, tmp_path: Path
    ) -> None:
        spec = Directory("d", [File("a.txt"), File("b.txt"), File("c.txt")])

        def failing(path: Path, node: File) -> None:
            if path.name == "b.txt":
                msg = "boom"
                raise RuntimeError(msg)
            path.write_text("first")

        with pytest.raises(RuntimeError):
            scaffold(spec, tmp_path, on_create=failing)

        seen: list[str] = []

        def fill(path: Path, node: File) -> None:
            seen.append(path.name)
            path.write_text("second")

        again = scaffold(spec, tmp_path, on_create=fill)
        assert rel(again, tmp_path) == ["d/c.txt"]  # only the still-missing file
        assert seen == ["c.txt"]  # hook fires only for the newly created file
        assert (tmp_path / "d" / "a.txt").read_text() == "first"  # not clobbered
        assert (tmp_path / "d" / "c.txt").read_text() == "second"
