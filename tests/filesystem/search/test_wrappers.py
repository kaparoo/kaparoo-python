from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.exceptions import DirectoryNotFoundError
from kaparoo.filesystem.search.wrappers import search_dirs, search_files, search_paths
from kaparoo.filters import (
    And,
    EndsWith,
    EndsWithAny,
    Equals,
    Glob,
    Not,
    StartsWith,
)
from tests.filesystem.helpers import _stringify

if TYPE_CHECKING:
    from pathlib import Path

    from kaparoo.filters.types import (
        LogicalChildrenFilterDict,
        PatternFilterDict,
    )
    from tests.fixtures.filesystem import TmpFilesystem, TmpTree


_SEARCH_FNS = (search_paths, search_files, search_dirs)


# --- search_paths -----------------------------------------------------------


def test_search_paths_returns_all_entries(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_paths(fs.root)
    assert set(result) == {fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file}


def test_search_paths_unordered_same_set(tmp_filesystem: TmpFilesystem):
    ordered = set(search_paths(tmp_filesystem.root, ordered=True))
    unordered = set(search_paths(tmp_filesystem.root, ordered=False))
    assert ordered == unordered


def test_search_paths_stringify(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_paths(fs.root, stringify=True)
    expected = {
        _stringify(p) for p in (fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file)
    }
    assert set(result) == expected


def test_search_paths_name_filter(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_paths(fs.root, name_filter=EndsWith(".txt"))
    assert set(result) == {fs.file1, fs.file2, fs.sub_file}


def test_search_paths_part_filter(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # `part_filter` matches the visited directory's relative path. Only
    # entries inside a directory whose path starts with "sub_" come through.
    result = search_paths(fs.root, part_filter=StartsWith("sub_"))
    assert set(result) == {fs.sub_file}


def test_search_paths_part_filter_root_is_dot(tmp_filesystem: TmpFilesystem):
    # `relative_to(root)` is `Path(".")` at the root itself: `Equals(".")`
    # picks up top-level only; `Not(Equals("."))` is the mirror.
    fs = tmp_filesystem
    top_level = {fs.file1, fs.file2, fs.file3, fs.sub_dir}
    assert set(search_paths(fs.root, part_filter=Equals("."))) == top_level
    assert set(search_paths(fs.root, part_filter=Not(Equals(".")))) == {fs.sub_file}


def test_search_paths_min_and_max_depth(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    top_level = {fs.file1, fs.file2, fs.file3, fs.sub_dir}
    # min_depth excludes shallower levels; max_depth prunes deeper subtrees.
    assert set(search_paths(fs.root, min_depth=2)) == {fs.sub_file}
    assert set(search_paths(fs.root, max_depth=1)) == top_level
    # min_depth == max_depth yields exactly that level.
    assert set(search_paths(fs.root, min_depth=1, max_depth=1)) == top_level
    assert set(search_paths(fs.root, min_depth=2, max_depth=2)) == {fs.sub_file}


# --- predicate (cross-wrapper) ---------------------------------------------


def test_search_predicate_applies_per_wrapper(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # search_paths: keep only .txt files (predicate runs after wrapper-level filtering).
    assert set(
        search_paths(fs.root, predicate=lambda p: p.is_file() and p.suffix == ".txt")
    ) == {fs.file1, fs.file2, fs.sub_file}
    # search_files: already restricted to files; predicate narrows by name.
    assert set(search_files(fs.root, predicate=lambda p: p.name == "sub_file.txt")) == {
        fs.sub_file
    }
    # search_dirs: predicate narrows among surviving dirs.
    assert set(search_dirs(fs.root, predicate=lambda p: p.name.startswith("sub_"))) == {
        fs.sub_dir
    }


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_search_predicate_rejecting_all_returns_empty(
    search_fn, tmp_filesystem: TmpFilesystem
):
    assert list(search_fn(tmp_filesystem.root, predicate=lambda _: False)) == []


# --- search_files / search_dirs (wrapper-specific behavior) ----------------


def test_search_files_excludes_directories(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    assert set(search_files(fs.root)) == {fs.file1, fs.file2, fs.file3, fs.sub_file}


def test_search_files_glob_name_filter(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    assert set(search_files(fs.root, name_filter=Glob("*.png"))) == {fs.file3}


def test_search_files_descends_through_non_matching_dirs(
    tmp_filesystem: TmpFilesystem,
):
    # `sub_dir` itself is not a file -- but `search_files` must still descend
    # into it to find `sub_file`.
    fs = tmp_filesystem
    result = search_files(fs.root, name_filter=Equals("sub_file.txt"))
    assert set(result) == {fs.sub_file}


def test_search_dirs_excludes_files_and_root(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_dirs(fs.root)
    assert set(result) == {fs.sub_dir}
    assert fs.root not in result


def test_search_dirs_empty_when_no_subdirs_at_depth(tmp_filesystem: TmpFilesystem):
    # No sub-directories at depth 2 in the fixture.
    assert list(search_dirs(tmp_filesystem.root, min_depth=2)) == []


# --- Cross-cutting: error cases ---------------------------------------------


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_nonexistent_root_raises(search_fn, unknown_path: Path):
    with pytest.raises(DirectoryNotFoundError):
        search_fn(unknown_path)


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_file_root_raises(search_fn, tmp_file: Path):
    with pytest.raises(NotADirectoryError):
        search_fn(tmp_file)


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_invalid_depth_raises(search_fn, tmp_filesystem: TmpFilesystem):
    root = tmp_filesystem.root
    with pytest.raises(ValueError, match="min_depth"):
        search_fn(root, min_depth=0)
    with pytest.raises(ValueError, match="max_depth"):
        search_fn(root, max_depth=0)
    with pytest.raises(ValueError, match="cannot exceed"):
        search_fn(root, min_depth=2, max_depth=1)


# --- Filter composition -----------------------------------------------------


def test_compose_and_not(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # .txt files but not file1.txt
    result = search_files(
        fs.root,
        name_filter=And((EndsWith(".txt"), Not(Equals("file1.txt")))),
    )
    assert set(result) == {fs.file2, fs.sub_file}


def test_compose_endswith_any(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_files(fs.root, name_filter=EndsWithAny((".txt", ".png")))
    assert set(result) == {fs.file1, fs.file2, fs.file3, fs.sub_file}


# --- dict-form filters ------------------------------------------------------


def test_name_filter_accepts_nested_logical_dict(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # Equivalent to: EndsWith(".txt") and not Equals("file1.txt")
    spec: LogicalChildrenFilterDict = {
        "kind": "and",
        "children": [
            {"kind": "ends_with", "pattern": ".txt"},
            {"kind": "not", "child": {"kind": "equals", "pattern": "file1.txt"}},
        ],
    }
    assert set(search_files(fs.root, name_filter=spec)) == {fs.file2, fs.sub_file}


def test_part_filter_accepts_dict(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # Only collect from "sub_dir" (matched by `part`, which is the dirpath
    # relative to `root`).
    spec: PatternFilterDict = {"kind": "equals", "pattern": "sub_dir"}
    assert set(search_files(fs.root, part_filter=spec)) == {fs.sub_file}


def test_dict_filter_equivalent_to_instance(tmp_filesystem: TmpFilesystem):
    instance = And((EndsWith(".txt"), Not(Equals("file1.txt"))))
    a = search_files(tmp_filesystem.root, name_filter=instance)
    b = search_files(tmp_filesystem.root, name_filter=instance.to_dict())
    assert set(a) == set(b)


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_dict_filter_works_across_all_wrappers(
    search_fn, tmp_filesystem: TmpFilesystem
):
    spec: PatternFilterDict = {"kind": "ends_with", "pattern": ".txt"}
    from_dict = search_fn(tmp_filesystem.root, name_filter=spec)
    from_obj = search_fn(tmp_filesystem.root, name_filter=EndsWith(".txt"))
    assert set(from_dict) == set(from_obj)


def test_dict_filter_invalid_raises(tmp_filesystem: TmpFilesystem):
    root = tmp_filesystem.root
    with pytest.raises(ValueError, match="missing 'kind'"):
        # Intentionally malformed (no `kind`); bypasses the type system.
        search_files(
            root,
            name_filter={"pattern": ".txt"},  # ty: ignore[invalid-argument-type]
        )
    unknown_kind: PatternFilterDict = {"kind": "nope", "pattern": "x"}
    with pytest.raises(ValueError, match="unknown filter kind"):
        search_files(root, name_filter=unknown_kind)


# --- ordering ---------------------------------------------------------------


def test_search_paths_ordered_is_path_lex_sorted(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # `ordered=True` sorts by `Path` tuple lex order, so a directory comes
    # before its own children (("sub_dir",) < ("sub_dir", "sub_file.txt")).
    # `stringify=True` must respect that ordering, not re-sort on the str form.
    result = search_paths(fs.root, ordered=True)
    expected = [fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file]
    assert list(result) == expected

    result_str = search_paths(fs.root, ordered=True, stringify=True)
    assert list(result_str) == [_stringify(p) for p in expected]


def test_search_ordered_sort_key_is_full_path_not_leaf_name(tmp_path: Path):
    # Distinguish "sort by full Path" from "sort by leaf name". Layout:
    #   root/sub/a.txt   (leaf "a.txt", path ("sub", "a.txt"))
    #   root/b.txt       (leaf "b.txt", path ("b.txt",))
    # Full-path lex sort: "sub/a.txt" > "b.txt" -> [b.txt, sub/a.txt]
    # Leaf-name lex sort: "a.txt"     < "b.txt" -> [sub/a.txt, b.txt]
    root = tmp_path / "root"
    root.mkdir()
    sub = root / "sub"
    sub.mkdir()
    (a_in_sub := sub / "a.txt").touch()
    (b_at_root := root / "b.txt").touch()

    assert list(search_files(root, ordered=True)) == [b_at_root, a_in_sub]


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_search_ordered_stable_across_calls(search_fn, tmp_filesystem: TmpFilesystem):
    first = list(search_fn(tmp_filesystem.root, ordered=True))
    second = list(search_fn(tmp_filesystem.root, ordered=True))
    assert first == second


def test_search_min_depth_skips_shallow_but_descends_deeper(tmp_tree: TmpTree):
    t = tmp_tree
    # min_depth=2 omits the depth-1 entries from the results, yet still
    # descends through depth-1 `docs/` to reach the depth-2 and depth-3 paths.
    assert set(search_paths(t.root, min_depth=2)) == {t.readme, t.nested, t.deep}


def test_search_max_depth_prunes_deepest_level(tmp_tree: TmpTree):
    t = tmp_tree
    # max_depth=2 keeps depth 1-2 but prunes the depth-3 file.
    result = set(search_paths(t.root, max_depth=2))
    assert t.deep not in result
    assert {t.readme, t.nested}.issubset(result)


def test_search_dirs_finds_empty_directory(tmp_tree: TmpTree):
    # An empty directory is still a directory and must be returned.
    assert tmp_tree.empty in set(search_dirs(tmp_tree.root))


# --- exclude ----------------------------------------------------------------


def test_search_exclude_drops_a_file(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_files(fs.root, exclude=["file1.txt"])
    assert fs.file1 not in result
    assert fs.file2 in result


def test_search_exclude_prunes_a_directory(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    # excluding a directory prunes its whole subtree -- name_filter cannot,
    # since a directory failing name_filter is still descended.
    result = search_paths(fs.root, exclude=["sub_dir"])
    assert fs.sub_dir not in result
    assert fs.sub_file not in result  # never descended into


def test_search_exclude_filter_matches_relative_path(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_files(fs.root, exclude=Glob("sub_dir/*"))
    assert fs.sub_file not in result
    assert fs.file1 in result


def test_search_exclude_callable(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_files(fs.root, exclude=lambda p: p.suffix == ".png")
    assert fs.file3 not in result  # the .png file
    assert fs.file1 in result


def test_search_exclude_callable_gets_the_real_path(tmp_filesystem: TmpFilesystem):
    # The callable receives the candidate's real path, so a filesystem op
    # (here `stat`) resolves correctly instead of raising on a root-relative
    # path that would be looked up against the cwd.
    fs = tmp_filesystem
    result = search_files(fs.root, exclude=lambda p: p.stat().st_size > 10**9)
    assert fs.file1 in result  # nothing is that large; `stat()` simply resolved


def test_search_exclude_iterable_is_or_combined(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    result = search_files(fs.root, exclude=["file1.txt", Glob("*.png")])
    assert fs.file1 not in result  # by exact path
    assert fs.file3 not in result  # by filter (*.png)
    assert fs.file2 in result
