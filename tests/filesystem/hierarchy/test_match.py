from __future__ import annotations

from typing import TYPE_CHECKING

from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Node,
    Together,
    match,
)
from kaparoo.filters import Glob, OneOf

if TYPE_CHECKING:
    from pathlib import Path


def build(root: Path, files: list[str]) -> None:
    """Create each relative file path (and its parent dirs) under `root`."""
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


def matched(tree: Node, root: Path) -> set[tuple[str, Node]]:
    """match() results as `{(relative_posix_path, node)}`."""
    return {(p.relative_to(root).as_posix(), n) for p, n in match(tree, root)}


class TestMatch:
    def test_direct_children(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File("a.txt"), File("b.txt")])
        assert matched(spec, tmp_path) == {
            ("d", spec),
            ("d/a.txt", File("a.txt")),
            ("d/b.txt", File("b.txt")),
        }

    def test_type_must_agree(self, tmp_path: Path) -> None:
        (tmp_path / "x").mkdir()  # 'x' is a directory
        (tmp_path / "y").write_text("")  # 'y' is a file
        assert list(match(File("x"), tmp_path)) == []  # File node vs dir
        assert list(match(Directory("y"), tmp_path)) == []  # Directory node vs file
        assert matched(Directory("x"), tmp_path) == {("x", Directory("x"))}
        assert matched(File("y"), tmp_path) == {("y", File("y"))}

    def test_overlap_yields_every_matching_node(self, tmp_path: Path) -> None:
        build(tmp_path, ["pkg/__init__.py"])
        spec = Directory("pkg", [File(Glob("*.py")), File("__init__.py")])
        got = matched(spec, tmp_path)
        assert ("pkg/__init__.py", File(Glob("*.py"))) in got
        assert ("pkg/__init__.py", File("__init__.py")) in got

    def test_name_filter_dsl(self, tmp_path: Path) -> None:
        build(tmp_path, ["train/x.png", "val/y.png", "test/z.png"])
        spec = Directory(OneOf(["train", "val"]), [File(Glob("*.png"))])
        dirs = {rel for rel, n in matched(spec, tmp_path) if isinstance(n, Directory)}
        assert dirs == {"train", "val"}  # 'test' not in the OneOf

    def test_exact_depth_skips_intermediate(self, tmp_path: Path) -> None:
        build(tmp_path, ["a/frames/x.png", "b/frames/y.png"])
        spec = Directory("frames", [File(Glob("*.png"))], depth=2)
        dirs = {rel for rel, n in matched(spec, tmp_path) if isinstance(n, Directory)}
        assert dirs == {"a/frames", "b/frames"}

    def test_any_depth(self, tmp_path: Path) -> None:
        build(tmp_path, ["x/metrics.json", "x/y/metrics.json", "z/metrics.json"])
        spec = File("metrics.json", depth=None)
        assert {rel for rel, _ in matched(spec, tmp_path)} == {
            "x/metrics.json",
            "x/y/metrics.json",
            "z/metrics.json",
        }

    def test_bounded_depth_range_stops(self, tmp_path: Path) -> None:
        build(tmp_path, ["t.txt", "a/t.txt", "a/b/t.txt"])
        spec = File("t.txt", depth=(1, 2))
        # depth 3 (a/b/t.txt) is excluded
        assert {rel for rel, _ in matched(spec, tmp_path)} == {"t.txt", "a/t.txt"}

    def test_group_members_are_candidates(self, tmp_path: Path) -> None:
        build(tmp_path, ["p/setup.py", "m/weights.bin", "m/weights.index"])
        project = Directory("p", [Exclusive(File("setup.py"), File("pyproject.toml"))])
        model = Directory("m", [Together(File("weights.bin"), File("weights.index"))])
        assert ("p/setup.py", File("setup.py")) in matched(project, tmp_path)
        got = matched(model, tmp_path)
        assert ("m/weights.bin", File("weights.bin")) in got
        assert ("m/weights.index", File("weights.index")) in got

    def test_nonexistent_root_yields_nothing(self, tmp_path: Path) -> None:
        assert list(match(File("x"), tmp_path / "nope")) == []
