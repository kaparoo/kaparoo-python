from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Node,
    Together,
    locate,
    locate_map,
)
from kaparoo.filters import EndsWith, Glob, OneOf

from .helpers import build

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def matched(tree: Node, root: Path) -> set[tuple[str, Node]]:
    """locate() results as `{(relative_posix_path, node)}`."""
    return {(p.relative_to(root).as_posix(), n) for p, n in locate(tree, root)}


def rels(pairs: Iterable[tuple[Path, object]], root: Path) -> set[str]:
    """The relative-posix paths of `(path, node)` pairs."""
    return {p.relative_to(root).as_posix() for p, _ in pairs}


class TestLocate:
    def test_direct_children(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File("a.txt"), File("b.txt")])
        assert matched(spec, tmp_path) == {
            ("d", spec),
            ("d/a.txt", File("a.txt")),
            ("d/b.txt", File("b.txt")),
        }

    def test_open_depth_stream_is_deterministic(self, tmp_path: Path) -> None:
        # An open-depth (`depth=None`) entry makes one walk span several levels.
        # Each directory's entries are emitted alphabetically *and*
        # subdirectories are descended in sorted order, so the lazy stream is
        # fully deterministic regardless of the OS directory order. `Path.walk`
        # is top-down: a directory's own entries precede its subdirs' contents.
        build(tmp_path, ["root/b/n.txt", "root/b/m.txt", "root/a/k.txt", "root/t.txt"])
        spec = Directory("root", [File(Glob("*.txt"), depth=None)])
        rel = [p.relative_to(tmp_path).as_posix() for p, _ in locate(spec, tmp_path)]
        assert rel == [
            "root",  # the top, matched as a child of tmp_path
            "root/t.txt",  # root's own entries first (a/, b/ are dirs)
            "root/a/k.txt",  # then a/ (sorted before b/)
            "root/b/m.txt",  # then b/, entries sorted
            "root/b/n.txt",
        ]

    def test_type_must_agree(self, tmp_path: Path) -> None:
        (tmp_path / "x").mkdir()  # 'x' is a directory
        (tmp_path / "y").write_text("")  # 'y' is a file
        assert list(locate(File("x"), tmp_path)) == []  # File node vs dir
        assert list(locate(Directory("y"), tmp_path)) == []  # Directory node vs file
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
        assert list(locate(File("x"), tmp_path / "nope")) == []


class TestUnique:
    def test_duplicates_allowed_by_default(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt"])
        # two equal File nodes both match d/a.txt -> the pair appears twice
        spec = Directory("d", [File("a.txt"), File("a.txt")])
        pairs = [(p, n) for p, n in locate(spec, tmp_path) if n == File("a.txt")]
        assert len(pairs) == 2

    def test_unique_suppresses_duplicates(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt"])
        spec = Directory("d", [File("a.txt"), File("a.txt")])
        pairs = [
            (p, n) for p, n in locate(spec, tmp_path, unique=True) if n == File("a.txt")
        ]
        assert len(pairs) == 1


class TestLocateMap:
    def test_groups_overlapping_nodes(self, tmp_path: Path) -> None:
        build(tmp_path, ["pkg/__init__.py"])
        spec = Directory("pkg", [File(Glob("*.py")), File("__init__.py")])
        mapping = locate_map(spec, tmp_path)
        init = tmp_path / "pkg" / "__init__.py"
        assert mapping[init] == (File(Glob("*.py")), File("__init__.py"))

    def test_single_match_is_one_tuple(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt"])
        spec = Directory("d", [File("a.txt")])
        mapping = locate_map(spec, tmp_path)
        assert mapping[tmp_path / "d" / "a.txt"] == (File("a.txt"),)

    def test_distinct_within_a_path(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt"])
        # reused node -> locate_map collapses it (built on unique=True)
        spec = Directory("d", [File("a.txt"), File("a.txt")])
        assert locate_map(spec, tmp_path)[tmp_path / "d" / "a.txt"] == (File("a.txt"),)


class TestLocateExclude:
    def test_concrete_cell(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        got = rels(locate(spec, tmp_path, exclude=["d/b.txt"]), tmp_path)
        assert "d/a.txt" in got
        assert "d/b.txt" not in got

    def test_callable(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        got = rels(
            locate(spec, tmp_path, exclude=lambda p: p.name == "b.txt"), tmp_path
        )
        assert "d/a.txt" in got
        assert "d/b.txt" not in got

    def test_single_strpath_is_not_iterated(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        got = rels(locate(spec, tmp_path, exclude="d/b.txt"), tmp_path)  # one excluder
        assert "d/a.txt" in got
        assert "d/b.txt" not in got

    def test_directory_excluder_prunes_subtree(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/keep/x.txt", "d/drop/x.txt"])
        spec = Directory("d", [File("x.txt", depth=None)])
        got = rels(locate(spec, tmp_path, exclude=["d/drop"]), tmp_path)
        assert "d/keep/x.txt" in got
        assert "d/drop/x.txt" not in got  # pruned, never descended

    def test_directory_excluder_via_callable_prunes(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/keep/x.txt", "d/drop/x.txt"])
        spec = Directory("d", [File("x.txt", depth=None)])
        got = rels(locate(spec, tmp_path, exclude=lambda p: p.name == "drop"), tmp_path)
        assert "d/keep/x.txt" in got
        assert "d/drop/x.txt" not in got

    def test_iterable_mixed(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt", "d/c.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        exclude = ["d/a.txt", lambda p: p.name == "c.txt"]
        got = rels(locate(spec, tmp_path, exclude=exclude), tmp_path)
        assert "d/b.txt" in got
        assert "d/a.txt" not in got
        assert "d/c.txt" not in got

    def test_locate_map_exclude(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        mapping = locate_map(spec, tmp_path, exclude=["d/b.txt"])
        assert (tmp_path / "d" / "a.txt") in mapping
        assert (tmp_path / "d" / "b.txt") not in mapping

    def test_filter_excluder(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/keep.log", "d/b.txt"])
        spec = Directory("d", [File(Glob("*"))])
        # a lone Filter is one excluder, matched on the root-relative path
        got = rels(locate(spec, tmp_path, exclude=EndsWith(".txt")), tmp_path)
        assert "d/keep.log" in got
        assert "d/a.txt" not in got
        assert "d/b.txt" not in got

    def test_filter_excluder_prunes_directory(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/keep/x.txt", "d/scratch/y.txt"])
        spec = Directory("d", [File("x.txt", depth=None), File("y.txt", depth=None)])
        got = rels(locate(spec, tmp_path, exclude=Glob("d/scratch")), tmp_path)
        assert "d/keep/x.txt" in got
        assert "d/scratch/y.txt" not in got  # the matched directory is pruned

    def test_empty_iterable_excludes_nothing(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        # an iterable that yields no excluders is a no-op (nothing dropped)
        assert "d/a.txt" in rels(locate(spec, tmp_path, exclude=[]), tmp_path)


class TestLocateAtRoot:
    def test_directory_top_at_its_own_path(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json", "dataset/images/cat.png"])
        png = File(Glob("*.png"))
        images = Directory("images", [png])
        meta = File("metadata.json")
        spec = Directory("dataset", [meta, images])
        ds = tmp_path / "dataset"

        pairs = set(locate(spec, ds, root_as_top=True))
        assert (ds, spec) in pairs
        assert (ds / "metadata.json", meta) in pairs
        assert (ds / "images", images) in pairs
        assert (ds / "images" / "cat.png", png) in pairs
        # container mode at the same path finds no "dataset" inside it
        assert list(locate(spec, ds)) == []

    def test_file_top(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json"])
        f = tmp_path / "dataset" / "metadata.json"
        assert set(locate(File("metadata.json"), f, root_as_top=True)) == {
            (f, File("metadata.json"))
        }

    def test_patterned_top_is_verified(self, tmp_path: Path) -> None:
        build(tmp_path, ["releases/v3/data.bin"])
        spec = Directory(Glob("v*"), [File("data.bin")])
        v3 = tmp_path / "releases" / "v3"
        pairs = set(locate(spec, v3, root_as_top=True))
        assert (v3, spec) in pairs
        assert (v3 / "data.bin", File("data.bin")) in pairs

    def test_name_mismatch_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "myrun").mkdir()
        spec = Directory("dataset", [File("metadata.json")])
        assert list(locate(spec, tmp_path / "myrun", root_as_top=True)) == []

    def test_type_mismatch_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "dataset").write_text("x")  # a file, but the top is a Directory
        spec = Directory("dataset", [File("a")])
        assert list(locate(spec, tmp_path / "dataset", root_as_top=True)) == []

    def test_group_top_raises(self, tmp_path: Path) -> None:
        spec = Exclusive(File("a"), File("b"))
        with pytest.raises(TypeError, match="Entry top node"):
            list(locate(spec, tmp_path, root_as_top=True))
