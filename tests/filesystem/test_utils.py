from __future__ import annotations

import platform
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.utils import (
    stringify_path,
    stringify_paths,
    wrap_path,
    wrap_paths,
)

if TYPE_CHECKING:
    from pathlib import Path


def _stringify(path: Path) -> str:
    path = str(path)
    if platform.system() == "Windows":
        path = path.replace("\\", "/")
    return path


def test_stringify_path(
    cwd_path: Path, dummy_path: Path, tmp_paths: tuple[Path, Path, Path]
):
    assert stringify_path(cwd_path) == _stringify(cwd_path)
    assert stringify_path(dummy_path) == _stringify(dummy_path)

    for path in tmp_paths:
        assert stringify_path(path) == _stringify(path)

    # The dummy_path fixture is the relative path "path/to/file".
    assert stringify_path(dummy_path, after="path") == "to/file"
    assert stringify_path(dummy_path, after="path/to") == "file"

    # `before` trims trailing components; with `after` it extracts a span.
    assert stringify_path(dummy_path, before="file") == "path/to"
    assert stringify_path(dummy_path, before="to/file") == "path"
    assert stringify_path(dummy_path, before="path/to/file") == "."
    assert stringify_path(dummy_path, after="path", before="file") == "to"

    # `before` matches whole components, not bare string suffixes.
    with pytest.raises(ValueError, match="does not end with"):
        stringify_path(dummy_path, before="ile")

    # tmp_paths holds the temp root plus a child dir and a child file.
    tmp_path, tmp_dir, tmp_file = tmp_paths
    assert stringify_path(tmp_dir, after=tmp_path) == "dir"
    assert stringify_path(tmp_file, after=tmp_path) == "file.txt"

    with pytest.raises(ValueError, match="is not in the subpath of"):
        stringify_path(tmp_dir, after=tmp_file)


def test_stringify_paths(
    dummy_path: Path,
    tmp_paths: tuple[Path, Path, Path],
    tmp_dirs: list[Path],
    tmp_files: list[Path],
):
    tmp_path, _, tmp_file = tmp_paths
    assert stringify_paths(tmp_paths) == [_stringify(p) for p in tmp_paths]
    assert stringify_paths(tmp_paths, after=tmp_path) == [".", "dir", "file.txt"]

    assert stringify_paths(tmp_files) == [_stringify(p) for p in tmp_files]
    assert stringify_paths(tmp_files, after=tmp_path) == [p.name for p in tmp_files]

    assert stringify_paths(tmp_dirs) == [_stringify(p) for p in tmp_dirs]
    assert stringify_paths(tmp_dirs, after=tmp_path) == [p.name for p in tmp_dirs]

    # `before` is threaded through to every path.
    assert stringify_paths([dummy_path], before="file") == ["path/to"]

    with pytest.raises(ValueError, match="is not in the subpath of"):
        stringify_paths(tmp_paths, after=tmp_file)

    with pytest.raises(ValueError, match="does not end with"):
        stringify_paths([dummy_path], before="ile")


def test_wrap_path(tmp_path: Path, cwd_path: Path):
    # `prepend` attaches a leading path (the former prepend_path behavior).
    expected = tmp_path / "dir"
    assert wrap_path("dir", prepend=tmp_path) == expected
    assert wrap_path("dir", prepend=tmp_path, stringify=True) == _stringify(expected)

    # `append` attaches a trailing path.
    assert wrap_path(tmp_path, append="dir") == expected

    # `prepend` and `append` together.
    nested = expected / "file.txt"
    assert wrap_path("dir", prepend=tmp_path, append="file.txt") == nested

    # `prepend` rejects an absolute `path`.
    with pytest.raises(ValueError, match="cannot prepend to absolute path"):
        wrap_path(cwd_path, prepend=tmp_path)

    # `append` must not be an absolute path.
    with pytest.raises(ValueError, match="cannot append an absolute path"):
        wrap_path("dir", append=cwd_path)


def test_wrap_paths(
    cwd_path: Path,
    tmp_path: Path,
    tmp_dirs: list[Path],
    tmp_dirnames: list[str],
):
    # `prepend` is applied to every path (the former prepend_paths behavior).
    assert wrap_paths(tmp_dirnames, prepend=tmp_path) == tmp_dirs
    expected_str = [_stringify(dirpath) for dirpath in tmp_dirs]
    assert wrap_paths(tmp_dirnames, prepend=tmp_path, stringify=True) == expected_str

    # `append` is applied to every path.
    assert wrap_paths(tmp_dirs, append="x") == [dirpath / "x" for dirpath in tmp_dirs]

    with pytest.raises(ValueError, match="cannot prepend to absolute path"):
        wrap_paths([cwd_path], prepend=tmp_path)

    with pytest.raises(ValueError, match="cannot append an absolute path"):
        wrap_paths(tmp_dirnames, append=cwd_path)
