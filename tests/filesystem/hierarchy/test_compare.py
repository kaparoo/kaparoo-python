from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.hierarchy import (
    Directory,
    Exclusive,
    File,
    Node,
    Together,
    conforms,
    locate,
    locate_map,
    validate,
)
from kaparoo.filesystem.hierarchy.conditions import Content, Size
from kaparoo.filters import EndsWith, Glob, OneOf

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


def dataset_spec() -> Directory:
    return Directory(
        "dataset",
        [
            File("metadata.json"),
            Directory("images", [File(Glob("*.png"))]),
        ],
    )


def build(root: Path, files: list[str]) -> None:
    """Create each relative file path (and its parent dirs) under `root`."""
    for rel in files:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")


def matched(tree: Node, root: Path) -> set[tuple[str, Node]]:
    """locate() results as `{(relative_posix_path, node)}`."""
    return {(p.relative_to(root).as_posix(), n) for p, n in locate(tree, root)}


def rels(pairs: Iterable[tuple[Path, object]], root: Path) -> set[str]:
    """The relative-posix paths of `(path, node)` pairs."""
    return {p.relative_to(root).as_posix() for p, _ in pairs}


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


class TestExclusivePriority:
    def test_lower_priority_side_becomes_unexpected(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/pyproject.toml", "d/setup.py"])
        group = Exclusive(
            File("pyproject.toml"), File("setup.py"), on_conflict="priority"
        )
        report = validate(Directory("d", [group]), tmp_path)
        assert report.violations == ()  # resolved, not flagged
        assert (tmp_path / "d" / "pyproject.toml") in report.matched  # winner kept
        assert report.unexpected == (tmp_path / "d" / "setup.py",)  # loser demoted
        assert not report.ok

    def test_declaration_order_sets_the_winner(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a", "d/b"])
        # 'b' is declared first, so 'b' wins and 'a' is demoted.
        group = Exclusive(File("b"), File("a"), on_conflict="priority")
        report = validate(Directory("d", [group]), tmp_path)
        assert (tmp_path / "d" / "b") in report.matched
        assert report.unexpected == (tmp_path / "d" / "a",)

    def test_three_sides_present_keeps_only_first(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a", "d/b", "d/c"])
        # All three alternatives present: the first declared wins, the rest
        # (b and c) are both demoted to `unexpected`.
        group = Exclusive(File("a"), File("b"), File("c"), on_conflict="priority")
        report = validate(Directory("d", [group]), tmp_path)
        assert report.violations == ()
        assert (tmp_path / "d" / "a") in report.matched
        assert set(report.unexpected) == {tmp_path / "d" / "b", tmp_path / "d" / "c"}
        assert not report.ok

    def test_single_side_present_is_clean(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/setup.py"])
        group = Exclusive(
            File("pyproject.toml"), File("setup.py"), on_conflict="priority"
        )
        report = validate(Directory("d", [group]), tmp_path)
        assert report.ok
        assert report.unexpected == ()

    def test_losing_directory_subtree_reported_once(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/keep/x.txt", "d/legacy/y.txt"])
        group = Exclusive(
            Directory("keep", [File("x.txt")]),
            Directory("legacy", [File("y.txt")]),
            on_conflict="priority",
        )
        report = validate(Directory("d", [group]), tmp_path)
        assert report.violations == ()
        assert (tmp_path / "d" / "keep" / "x.txt") in report.matched  # winner subtree
        assert report.unexpected == (tmp_path / "d" / "legacy",)  # once, then pruned
        assert (tmp_path / "d" / "legacy" / "y.txt") not in report.unexpected

    def test_required_none_present_is_missing(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        group = Exclusive(File("a"), File("b"), required=True, on_conflict="priority")
        report = validate(Directory("d", [group]), tmp_path)
        assert group in report.missing

    def test_conforms_rejects_when_a_loser_is_present(self, tmp_path: Path) -> None:
        build(tmp_path, ["proj/pyproject.toml", "proj/setup.py"])
        group = Exclusive(
            File("pyproject.toml"), File("setup.py"), on_conflict="priority"
        )
        # the loser is unexpected, so the resolved subtree is not clean
        assert not conforms(Directory("proj", [group]))(tmp_path / "proj")


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


class TestConforms:
    def test_top_directory_conforms(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json", "dataset/images/a.png"])
        keep = conforms(dataset_spec())
        assert keep(tmp_path / "dataset")  # top node, conforming subtree

    def test_inner_nodes_are_not_accepted(self, tmp_path: Path) -> None:
        # The path is tested as the *top* node only, never an inner one.
        build(tmp_path, ["dataset/metadata.json", "dataset/images/a.png"])
        keep = conforms(dataset_spec())
        assert not keep(tmp_path / "dataset" / "images")
        assert not keep(tmp_path / "dataset" / "metadata.json")
        assert not keep(tmp_path / "dataset" / "images" / "a.png")

    def test_top_dir_nonconforming_subtree_rejected(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json", "dataset/junk.bin"])  # junk: extra
        keep = conforms(dataset_spec())
        assert not keep(tmp_path / "dataset")

    def test_top_dir_name_mismatch_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "other").mkdir()
        assert not conforms(dataset_spec())(tmp_path / "other")

    def test_top_file(self, tmp_path: Path) -> None:
        build(tmp_path, ["a.csv", "b.txt"])
        (tmp_path / "d").mkdir()
        keep = conforms(File(Glob("*.csv")))
        assert keep(tmp_path / "a.csv")  # file, name matches
        assert not keep(tmp_path / "b.txt")  # file, name mismatch
        assert not keep(tmp_path / "d")  # not a file

    def test_top_group(self, tmp_path: Path) -> None:
        build(tmp_path, ["a", "c"])
        keep = conforms(Exclusive(File("a"), File("b")))
        assert keep(tmp_path / "a")  # realizes one alternative
        assert not keep(tmp_path / "c")  # realizes neither

    def test_childless_directory_must_be_empty(self, tmp_path: Path) -> None:
        (tmp_path / "logs").mkdir()
        assert conforms(Directory("logs"))(tmp_path / "logs")

    def test_childless_directory_with_contents_rejected(self, tmp_path: Path) -> None:
        build(tmp_path, ["logs/a.txt"])
        assert not conforms(Directory("logs"))(tmp_path / "logs")


class TestValidateDepth:
    def test_intermediate_dir_is_an_allowed_ancestor(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/mid/x.txt"])
        spec = Directory("d", [File("x.txt", depth=2)])
        report = validate(spec, tmp_path)
        assert report.ok  # d/mid is an ancestor of a match, not unexpected
        assert (tmp_path / "d" / "mid" / "x.txt") in report.matched

    def test_stray_inside_a_nested_matched_dir_is_unexpected(
        self, tmp_path: Path
    ) -> None:
        build(tmp_path, ["d/mid/x.txt", "d/mid/stray.txt"])
        spec = Directory("d", [File("x.txt", depth=2)])
        report = validate(spec, tmp_path)
        assert not report.ok
        assert (tmp_path / "d" / "mid" / "stray.txt") in report.unexpected


class TestRequiredEnumerable:
    def test_satisfied_by_one_present_name(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/train"])  # 'val' absent
        spec = Directory("d", [File(OneOf(["train", "val"]), required=True)])
        assert validate(spec, tmp_path).missing == ()  # one name is enough

    def test_missing_when_no_name_present(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        node = File(OneOf(["train", "val"]), required=True)
        assert node in validate(Directory("d", [node]), tmp_path).missing


class TestValidateCondition:
    def test_failing_condition_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "model.bin").write_bytes(b"")  # 0 bytes
        node = File("model.bin", condition=Size(min=1))
        report = validate(Directory("d", [node]), tmp_path)
        assert not report.ok
        assert (tmp_path / "d" / "model.bin", node) in report.failed

    def test_passing_condition_is_ok(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "model.bin").write_bytes(b"x")  # 1 byte
        spec = Directory("d", [File("model.bin", condition=Size(min=1))])
        assert validate(spec, tmp_path).ok

    def test_content_check_is_supplied_at_call_time(self, tmp_path: Path) -> None:
        (tmp_path / "d").mkdir()
        (tmp_path / "d" / "data.json").write_text("ok")
        spec = Directory("d", [File("data.json", condition=Content("valid"))])
        assert validate(
            spec, tmp_path, checks={"valid": lambda p: p.read_text() == "ok"}
        ).ok
        assert not validate(spec, tmp_path, checks={"valid": lambda _: False}).ok

    def test_missing_content_check_errors_or_skips(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/data.json"])
        spec = Directory("d", [File("data.json", condition=Content("absent"))])
        with pytest.raises(ValueError, match="no check supplied"):
            validate(spec, tmp_path)  # on_missing defaults to "error"
        assert validate(spec, tmp_path, on_missing="skip").ok

    def test_conforms_checks_the_condition(self, tmp_path: Path) -> None:
        (tmp_path / "f").write_bytes(b"")  # empty
        assert not conforms(File("f", condition=Size(min=1)))(tmp_path / "f")
        (tmp_path / "g").write_bytes(b"x")
        assert conforms(File(Glob("*"), condition=Size(min=1)))(tmp_path / "g")

    def test_content_check_can_reach_a_sibling(self, tmp_path: Path) -> None:
        # the callable gets a live Path, so it may navigate to a sibling dir
        build(tmp_path, ["d/manifest.txt", "d/other/a", "d/other/b"])
        (tmp_path / "d" / "manifest.txt").write_text("l1\nl2\n")  # 2 lines

        def lines_match_sibling_count(path: Path) -> bool:
            lines = len(path.read_text().splitlines())
            return lines == sum(1 for _ in (path.parent / "other").iterdir())

        spec = Directory(
            "d",
            [
                File("manifest.txt", condition=Content("match")),
                Directory("other", [File(Glob("*"))]),  # accept any sibling files
            ],
        )
        checks = {"match": lines_match_sibling_count}
        assert validate(spec, tmp_path, checks=checks).ok  # 2 lines == 2 files

        (tmp_path / "d" / "other" / "c").write_text("x")  # now 3 files -> mismatch
        report = validate(spec, tmp_path, checks=checks)
        assert report.unexpected == ()  # 'c' is accepted, so only the check fails
        assert (tmp_path / "d" / "manifest.txt", spec.children[0]) in report.failed


class TestValidateExclude:
    def test_excluded_path_neither_matched_nor_unexpected(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/b.txt"])
        spec = Directory("d", [File(Glob("*.txt"))])
        report = validate(spec, tmp_path, exclude=["d/b.txt"])
        assert (tmp_path / "d" / "b.txt") not in report.matched  # dropped
        assert report.unexpected == ()  # and not reported as unexpected
        assert report.ok

    def test_exclude_silences_an_unexpected_file(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/junk.txt"])
        spec = Directory("d", [File("a.txt")])
        assert not validate(spec, tmp_path).ok  # junk.txt is unexpected
        assert validate(spec, tmp_path, exclude=["d/junk.txt"]).ok

    def test_exclude_silences_an_unexpected_directory(self, tmp_path: Path) -> None:
        build(tmp_path, ["d/a.txt", "d/scratch/x.txt"])
        spec = Directory("d", [File("a.txt")])
        report = validate(spec, tmp_path, exclude=["d/scratch"])
        assert report.ok
        assert (tmp_path / "d" / "scratch") not in report.unexpected


class TestValidateAtRoot:
    def test_validates_subtree_at_its_own_path(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json", "dataset/images/cat.png"])
        ds = tmp_path / "dataset"
        report = validate(dataset_spec(), ds, at_root=True)
        assert report.ok
        assert report.matched[ds] == (dataset_spec(),)

    def test_required_child_missing(self, tmp_path: Path) -> None:
        (tmp_path / "dataset").mkdir()  # an empty dataset directory
        spec = Directory("dataset", [File("metadata.json", required=True)])
        report = validate(spec, tmp_path / "dataset", at_root=True)
        assert not report.ok
        assert report.missing == (File("metadata.json", required=True),)

    def test_name_mismatch_reports_top_missing(self, tmp_path: Path) -> None:
        (tmp_path / "myrun").mkdir()
        spec = dataset_spec()
        report = validate(spec, tmp_path / "myrun", at_root=True)
        assert not report.ok
        assert report.missing == (spec,)
        assert report.matched == {}  # did not descend
        assert report.unexpected == ()

    def test_unexpected_child_under_root(self, tmp_path: Path) -> None:
        build(
            tmp_path, ["dataset/metadata.json", "dataset/images/x.png", "dataset/junk"]
        )
        ds = tmp_path / "dataset"
        report = validate(dataset_spec(), ds, at_root=True)
        assert not report.ok
        assert (ds / "junk") in report.unexpected

    def test_file_top_condition_on_root(self, tmp_path: Path) -> None:
        empty = tmp_path / "model.bin"
        empty.write_bytes(b"")
        spec = File("model.bin", condition=Size(min=1))
        report = validate(spec, empty, at_root=True)
        assert not report.ok
        assert report.failed == ((empty, spec),)

        full = tmp_path / "good.bin"
        full.write_bytes(b"x")
        ok_spec = File("good.bin", condition=Size(min=1))
        assert validate(ok_spec, full, at_root=True).ok

    def test_file_top_name_mismatch_reports_missing(self, tmp_path: Path) -> None:
        (tmp_path / "other.bin").write_bytes(b"x")  # wrong name for the top File
        spec = File("model.bin")
        report = validate(spec, tmp_path / "other.bin", at_root=True)
        assert not report.ok
        assert report.missing == (spec,)

    def test_group_top_raises(self, tmp_path: Path) -> None:
        spec = Exclusive(File("a"), File("b"))
        with pytest.raises(TypeError, match="Entry top node"):
            validate(spec, tmp_path, at_root=True)


class TestLocate:
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


class TestLocateAtRoot:
    def test_directory_top_at_its_own_path(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json", "dataset/images/cat.png"])
        png = File(Glob("*.png"))
        images = Directory("images", [png])
        meta = File("metadata.json")
        spec = Directory("dataset", [meta, images])
        ds = tmp_path / "dataset"

        pairs = set(locate(spec, ds, at_root=True))
        assert (ds, spec) in pairs
        assert (ds / "metadata.json", meta) in pairs
        assert (ds / "images", images) in pairs
        assert (ds / "images" / "cat.png", png) in pairs
        # container mode at the same path finds no "dataset" inside it
        assert list(locate(spec, ds)) == []

    def test_file_top(self, tmp_path: Path) -> None:
        build(tmp_path, ["dataset/metadata.json"])
        f = tmp_path / "dataset" / "metadata.json"
        assert set(locate(File("metadata.json"), f, at_root=True)) == {
            (f, File("metadata.json"))
        }

    def test_patterned_top_is_verified(self, tmp_path: Path) -> None:
        build(tmp_path, ["releases/v3/data.bin"])
        spec = Directory(Glob("v*"), [File("data.bin")])
        v3 = tmp_path / "releases" / "v3"
        pairs = set(locate(spec, v3, at_root=True))
        assert (v3, spec) in pairs
        assert (v3 / "data.bin", File("data.bin")) in pairs

    def test_name_mismatch_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "myrun").mkdir()
        spec = Directory("dataset", [File("metadata.json")])
        assert list(locate(spec, tmp_path / "myrun", at_root=True)) == []

    def test_type_mismatch_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "dataset").write_text("x")  # a file, but the top is a Directory
        spec = Directory("dataset", [File("a")])
        assert list(locate(spec, tmp_path / "dataset", at_root=True)) == []

    def test_group_top_raises(self, tmp_path: Path) -> None:
        spec = Exclusive(File("a"), File("b"))
        with pytest.raises(TypeError, match="Entry top node"):
            list(locate(spec, tmp_path, at_root=True))
