from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.search import get_dirs, get_files, get_paths
from kaparoo.filesystem.utils import stringify_paths

if TYPE_CHECKING:
    from tests.fixtures.filesystem import TmpFilesystem


def _deprecation_match(name: str) -> str:
    return rf"`{name}\(\)` is deprecated"


# --- get_paths --------------------------------------------------------------


def test_get_paths(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    match = _deprecation_match("get_paths")

    # default
    with pytest.warns(DeprecationWarning, match=match):
        result1 = get_paths(fs.root)
    expected1 = [fs.file1, fs.file2, fs.file3, fs.sub_dir]
    assert sorted(result1) == sorted(expected1)

    # recursive
    with pytest.warns(DeprecationWarning, match=match):
        result2 = get_paths(fs.root, recursive=True)
    expected2 = [fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file]
    assert sorted(result2) == sorted(expected2)

    # stringify
    with pytest.warns(DeprecationWarning, match=match):
        result3 = get_paths(fs.root, recursive=True, stringify=True)
    expected3 = stringify_paths(expected2)
    assert sorted(result3) == sorted(expected3)

    # pattern
    with pytest.warns(DeprecationWarning, match=match):
        result4 = get_paths(fs.root, pattern="*.txt", recursive=True)
    expected4 = [fs.file1, fs.file2, fs.sub_file]
    assert sorted(result4) == sorted(expected4)

    # excludes
    with pytest.warns(DeprecationWarning, match=match):
        result5 = get_paths(fs.root, excludes=[fs.file2, fs.sub_dir], recursive=True)
    expected5 = [fs.file1, fs.file3, fs.sub_file]
    assert sorted(result5) == sorted(expected5)

    # condition
    with pytest.warns(DeprecationWarning, match=match):
        result6 = get_paths(fs.root, condition=os.path.isfile, recursive=True)
    expected6 = [fs.file1, fs.file2, fs.file3, fs.sub_file]
    assert sorted(result6) == sorted(expected6)


# --- get_files --------------------------------------------------------------


def test_get_files(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    match = _deprecation_match("get_files")

    # default: emits the warning and returns only files (the wrapper applies
    # `file_exists` as its built-in condition).
    with pytest.warns(DeprecationWarning, match=match):
        result1 = get_files(fs.root, recursive=True)
    assert sorted(result1) == sorted([fs.file1, fs.file2, fs.file3, fs.sub_file])

    # callable `condition` is ANDed with the built-in file check.
    with pytest.warns(DeprecationWarning, match=match):
        result2 = get_files(
            fs.root, recursive=True, condition=lambda p: p.suffix == ".txt"
        )
    assert sorted(result2) == sorted([fs.file1, fs.file2, fs.sub_file])


# --- get_dirs ---------------------------------------------------------------


def test_get_dirs(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    match = _deprecation_match("get_dirs")

    # default: warns and returns only directories.
    with pytest.warns(DeprecationWarning, match=match):
        result1 = get_dirs(fs.root, recursive=True)
    assert sorted(result1) == sorted([fs.sub_dir])

    # callable `condition` is ANDed with the built-in directory check.
    with pytest.warns(DeprecationWarning, match=match):
        result2 = get_dirs(
            fs.root, recursive=True, condition=lambda p: p.name == "sub_dir"
        )
    assert sorted(result2) == sorted([fs.sub_dir])
