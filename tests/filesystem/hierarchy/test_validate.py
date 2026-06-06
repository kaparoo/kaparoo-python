from __future__ import annotations

from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Together,
    validate,
)

if TYPE_CHECKING:
    from pathlib import Path


def build(root: Path, files: list[str]) -> None:
    """Create each relative file path (and its parent dirs) under `root`."""
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


class TestConformance:
    def test_clean_tree_is_ok(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File("a.txt", required=True), File("b.txt")])
        report = validate(spec, tmp_path)
        assert report.ok
        assert bool(report) is True
        assert report.missing == ()
        assert report.unexpected == ()
        assert report.violations == ()
        assert (tmp_path / "d" / "a.txt") in report.matched

    def test_nonexistent_root_is_ok(self, tmp_path: Path) -> None:
        report = validate(File("x"), tmp_path / "nope")
        assert report.ok
        assert report.matched == {}


class TestMissing:
    def test_required_entry_absent(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        spec = Directory("d", [File("a.txt", required=True)])
        report = validate(spec, tmp_path)
        assert not report
        assert File("a.txt", required=True) in report.missing


class TestUnexpected:
    def test_stray_file_and_pruned_dir(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/junk.txt", "d/extra/x.txt"])
        spec = Directory("d", [File("a.txt")])
        report = validate(spec, tmp_path)
        assert not report.ok
        assert set(report.unexpected) == {
            tmp_path / "d" / "junk.txt",
            tmp_path / "d" / "extra",
        }
        # the unexpected directory is reported once, not descended into
        assert (tmp_path / "d" / "extra" / "x.txt") not in report.unexpected


class TestExclusive:
    def test_two_sides_present_is_a_violation(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/setup.py", "d/pyproject.toml"])
        spec = Directory("d", [Exclusive(File("setup.py"), File("pyproject.toml"))])
        report = validate(spec, tmp_path)
        assert not report.ok
        (violation,) = report.violations
        assert violation.kind == "exclusive"
        assert set(violation.present) == {File("setup.py"), File("pyproject.toml")}

    def test_one_side_present_is_ok(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/setup.py"])
        spec = Directory("d", [Exclusive(File("setup.py"), File("pyproject.toml"))])
        report = validate(spec, tmp_path)
        assert report.ok

    def test_required_with_none_present_is_missing(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        group = Exclusive(File("setup.py"), File("pyproject.toml"), required=True)
        report = validate(Directory("d", [group]), tmp_path)
        assert group in report.missing

    def test_nested_group_in_alternative(self, tmp_path: Path) -> None:
        # Exclusive(Together(a, b), c): the {a and b} side and c both present
        build(tmp_path, ["d/a", "d/b", "d/c"])
        group = Exclusive(Together(File("a"), File("b")), File("c"))
        report = validate(Directory("d", [group]), tmp_path)
        (violation,) = report.violations
        assert violation.kind == "exclusive"
        # leaves flattened through the nested Together
        assert set(violation.present) == {File("a"), File("b"), File("c")}


class TestTogether:
    def test_partial_is_a_violation(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a"])  # 'b' missing
        spec = Directory("d", [Together(File("a"), File("b"))])
        report = validate(spec, tmp_path)
        (violation,) = report.violations
        assert violation.kind == "together"
        assert set(violation.present) == {File("a")}

    def test_all_present_is_ok(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a", "d/b"])
        spec = Directory("d", [Together(File("a"), File("b"))])
        assert validate(spec, tmp_path).ok

    def test_required_none_present_is_missing(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        group = Together(File("a"), File("b"), required=True)
        report = validate(Directory("d", [group]), tmp_path)
        assert group in report.missing
        assert report.violations == ()  # all-absent is not a partial violation
