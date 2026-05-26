from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.exceptions import DirectoryNotFoundError
from kaparoo.filesystem.search.filters import (
    And,
    EndsWith,
    EndsWithAny,
    Equals,
    Glob,
    Not,
    StartsWith,
)
from kaparoo.filesystem.search.wrappers import search_dirs, search_files, search_paths
from tests.filesystem.helpers import _stringify

if TYPE_CHECKING:
    from pathlib import Path


_SEARCH_FNS = (search_paths, search_files, search_dirs)


# --- search_paths -----------------------------------------------------------


def test_search_paths_returns_all_entries(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, sub_dir, sub_file = tmp_filesystem
    result = search_paths(root_dir)
    assert set(result) == {file1, file2, file3, sub_dir, sub_file}


def test_search_paths_ordered_default(tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    result = search_paths(root_dir)
    assert list(result) == sorted(result)


def test_search_paths_unordered_same_set(tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    ordered = set(search_paths(root_dir, ordered=True))
    unordered = set(search_paths(root_dir, ordered=False))
    assert ordered == unordered


def test_search_paths_stringify(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, sub_dir, sub_file = tmp_filesystem
    result = search_paths(root_dir, stringify=True)
    expected = {_stringify(p) for p in (file1, file2, file3, sub_dir, sub_file)}
    assert set(result) == expected


def test_search_paths_name_filter(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, _, _, sub_file = tmp_filesystem
    result = search_paths(root_dir, name_filter=EndsWith(".txt"))
    assert set(result) == {file1, file2, sub_file}


def test_search_paths_part_filter(tmp_filesystem: tuple[Path, ...]):
    root_dir, _, _, _, _, sub_file = tmp_filesystem
    # `part_filter` matches the visited directory's relative path. Only
    # entries inside a directory whose path starts with "sub_" come through.
    result = search_paths(root_dir, part_filter=StartsWith("sub_"))
    assert set(result) == {sub_file}


def test_search_paths_predicate(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, _, _, sub_file = tmp_filesystem
    result = search_paths(
        root_dir, predicate=lambda p: p.is_file() and p.suffix == ".txt"
    )
    assert set(result) == {file1, file2, sub_file}


def test_search_paths_min_depth(tmp_filesystem: tuple[Path, ...]):
    root_dir, _, _, _, _, sub_file = tmp_filesystem
    # Direct children of root are at depth 1; sub_file (inside sub_dir) is depth 2.
    result = search_paths(root_dir, min_depth=2)
    assert set(result) == {sub_file}


def test_search_paths_max_depth(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, sub_dir, _ = tmp_filesystem
    # max_depth=1 includes depth-1 entries but does not descend into sub_dir.
    result = search_paths(root_dir, max_depth=1)
    assert set(result) == {file1, file2, file3, sub_dir}


# --- search_files -----------------------------------------------------------


def test_search_files_excludes_directories(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, _, sub_file = tmp_filesystem
    result = search_files(root_dir)
    assert set(result) == {file1, file2, file3, sub_file}


def test_search_files_glob_name_filter(tmp_filesystem: tuple[Path, ...]):
    root_dir, _, _, file3, _, _ = tmp_filesystem
    result = search_files(root_dir, name_filter=Glob("*.png"))
    assert set(result) == {file3}


def test_search_files_descends_through_non_matching_dirs(
    tmp_filesystem: tuple[Path, ...],
):
    # `sub_dir` itself is not a file -- but `search_files` must still descend
    # into it to find `sub_file`.
    root_dir, _, _, _, _, sub_file = tmp_filesystem
    result = search_files(root_dir, name_filter=Equals("sub_file.txt"))
    assert set(result) == {sub_file}


# --- search_dirs ------------------------------------------------------------


def test_search_dirs_excludes_files(tmp_filesystem: tuple[Path, ...]):
    root_dir, _, _, _, sub_dir, _ = tmp_filesystem
    result = search_dirs(root_dir)
    assert set(result) == {sub_dir}


def test_search_dirs_root_not_included(tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    result = search_dirs(root_dir)
    assert root_dir not in result


def test_search_dirs_empty_when_no_subdirs_at_depth(
    tmp_filesystem: tuple[Path, ...],
):
    root_dir, *_ = tmp_filesystem
    # No sub-directories at depth 2 in the fixture.
    result = search_dirs(root_dir, min_depth=2)
    assert list(result) == []


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
def test_invalid_min_depth_raises(search_fn, tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    with pytest.raises(ValueError, match="min_depth"):
        search_fn(root_dir, min_depth=0)


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_invalid_max_depth_raises(search_fn, tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    with pytest.raises(ValueError, match="max_depth"):
        search_fn(root_dir, max_depth=0)


@pytest.mark.parametrize("search_fn", _SEARCH_FNS)
def test_min_gt_max_raises(search_fn, tmp_filesystem: tuple[Path, ...]):
    root_dir, *_ = tmp_filesystem
    with pytest.raises(ValueError, match="cannot exceed"):
        search_fn(root_dir, min_depth=2, max_depth=1)


# --- Filter composition -----------------------------------------------------


def test_compose_and_not(tmp_filesystem: tuple[Path, ...]):
    root_dir, _, file2, _, _, sub_file = tmp_filesystem
    # .txt files but not file1.txt
    result = search_files(
        root_dir,
        name_filter=And((EndsWith(".txt"), Not(Equals("file1.txt")))),
    )
    assert set(result) == {file2, sub_file}


def test_compose_endswith_any(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, _, sub_file = tmp_filesystem
    result = search_files(root_dir, name_filter=EndsWithAny((".txt", ".png")))
    assert set(result) == {file1, file2, file3, sub_file}
