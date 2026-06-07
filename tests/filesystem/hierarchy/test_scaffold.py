from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Together,
    scaffold,
)
from kaparoo.filters import Glob, Template

if TYPE_CHECKING:
    from pathlib import Path


def rel(paths: list[Path], root: Path) -> list[str]:
    """Root-relative POSIX strings, for order-sensitive assertions."""
    return [p.relative_to(root).as_posix() for p in paths]


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
        with pytest.raises(ValueError, match="enumerable"):
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
        with pytest.raises(ValueError, match="fixed at 1"):
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
        with pytest.raises(ValueError, match="a file exists there"):
            scaffold(Directory("d", [File("x")]), tmp_path)

    def test_directory_where_file_expected_raises(self, tmp_path: Path) -> None:
        (tmp_path / "x").mkdir()
        with pytest.raises(ValueError, match="a directory exists there"):
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
