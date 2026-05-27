from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.utils import (
    stringify_path,
    stringify_paths,
    wrap_path,
    wrap_paths,
)

from .helpers import _stringify

if TYPE_CHECKING:
    from pathlib import Path


# --- stringify_path --------------------------------------------------------


def test_stringify_path_basic_paths(
    cwd_path: Path, dummy_path: Path, tmp_paths: tuple[Path, Path, Path]
):
    assert stringify_path(cwd_path) == _stringify(cwd_path)
    assert stringify_path(dummy_path) == _stringify(dummy_path)
    for path in tmp_paths:
        assert stringify_path(path) == _stringify(path)


def test_stringify_path_after(dummy_path: Path, tmp_paths: tuple[Path, Path, Path]):
    # The dummy_path fixture is "path/to/file".
    assert stringify_path(dummy_path, after="path") == "to/file"
    assert stringify_path(dummy_path, after="path/to") == "file"

    tmp_path, tmp_dir, tmp_file = tmp_paths
    assert stringify_path(tmp_dir, after=tmp_path) == "dir"
    assert stringify_path(tmp_file, after=tmp_path) == "file.txt"

    with pytest.raises(ValueError, match="is not in the subpath of"):
        stringify_path(tmp_dir, after=tmp_file)


def test_stringify_path_before(dummy_path: Path):
    # `before` trims trailing components; combined with `after` it extracts
    # a span. `before` matches whole components, not bare string suffixes.
    assert stringify_path(dummy_path, before="file") == "path/to"
    assert stringify_path(dummy_path, before="to/file") == "path"
    assert stringify_path(dummy_path, before="path/to/file") == "."
    assert stringify_path(dummy_path, after="path", before="file") == "to"

    with pytest.raises(ValueError, match="does not end with"):
        stringify_path(dummy_path, before="ile")


# --- stringify_paths -------------------------------------------------------


def test_stringify_paths(
    dummy_path: Path,
    tmp_paths: tuple[Path, Path, Path],
    tmp_dirs: list[Path],
    tmp_files: list[Path],
):
    tmp_path, _, tmp_file = tmp_paths

    # Basic: each path is stringified.
    assert stringify_paths(tmp_paths) == [_stringify(p) for p in tmp_paths]
    assert stringify_paths(tmp_files) == [_stringify(p) for p in tmp_files]
    assert stringify_paths(tmp_dirs) == [_stringify(p) for p in tmp_dirs]

    # `after` and `before` are threaded through to every entry.
    assert stringify_paths(tmp_paths, after=tmp_path) == [".", "dir", "file.txt"]
    assert stringify_paths(tmp_files, after=tmp_path) == [p.name for p in tmp_files]
    assert stringify_paths([dummy_path], before="file") == ["path/to"]

    with pytest.raises(ValueError, match="is not in the subpath of"):
        stringify_paths(tmp_paths, after=tmp_file)
    with pytest.raises(ValueError, match="does not end with"):
        stringify_paths([dummy_path], before="ile")


# --- wrap_path -------------------------------------------------------------


def test_wrap_path(tmp_path: Path):
    expected = tmp_path / "dir"
    # `prepend` attaches a leading path.
    assert wrap_path("dir", prepend=tmp_path) == expected
    assert wrap_path("dir", prepend=tmp_path, stringify=True) == _stringify(expected)
    # `append` attaches a trailing path; combined with `prepend`, both.
    assert wrap_path(tmp_path, append="dir") == expected
    assert (
        wrap_path("dir", prepend=tmp_path, append="file.txt") == expected / "file.txt"
    )


def test_wrap_path_rejects_absolute(cwd_path: Path, tmp_path: Path):
    with pytest.raises(ValueError, match="cannot prepend to absolute path"):
        wrap_path(cwd_path, prepend=tmp_path)
    with pytest.raises(ValueError, match="cannot append an absolute path"):
        wrap_path("dir", append=cwd_path)


# --- wrap_paths ------------------------------------------------------------


def test_wrap_paths(tmp_path: Path, tmp_dirs: list[Path], tmp_dirnames: list[str]):
    # `prepend` and `append` are applied to every entry.
    assert wrap_paths(tmp_dirnames, prepend=tmp_path) == tmp_dirs
    assert wrap_paths(tmp_dirnames, prepend=tmp_path, stringify=True) == [
        _stringify(p) for p in tmp_dirs
    ]
    assert wrap_paths(tmp_dirs, append="x") == [p / "x" for p in tmp_dirs]


def test_wrap_paths_rejects_absolute(
    cwd_path: Path, tmp_path: Path, tmp_dirnames: list[str]
):
    with pytest.raises(ValueError, match="cannot prepend to absolute path"):
        wrap_paths([cwd_path], prepend=tmp_path)
    with pytest.raises(ValueError, match="cannot append an absolute path"):
        wrap_paths(tmp_dirnames, append=cwd_path)
