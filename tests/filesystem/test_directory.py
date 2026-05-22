from __future__ import annotations

import platform
from pathlib import Path

import pytest

from kaparoo.filesystem.directory import (
    dir_empty,
    dir_empty_unsafe,
    dirs_empty,
    dirs_empty_unsafe,
    make_dir,
    make_dirs,
)


def _stringify(path: Path) -> str:
    path = str(path)
    if platform.system() == "Windows":
        path = path.replace("\\", "/")
    return path


def test_make_dir(tmp_path: Path, tmp_file: Path):
    created = make_dir(tmp_path / "new")
    assert isinstance(created, Path)
    assert created.is_dir()

    # `exist_ok` controls the behavior when the directory already exists.
    make_dir(created, exist_ok=True)
    with pytest.raises(FileExistsError):
        make_dir(created)

    # `stringify` returns the created path as a string.
    str_target = tmp_path / "str_dir"
    result = make_dir(str_target, stringify=True)
    assert isinstance(result, str)
    assert result == _stringify(str_target)

    # An existing non-directory path raises `NotADirectoryError`.
    with pytest.raises(NotADirectoryError):
        make_dir(tmp_file)


def test_make_dirs(tmp_path: Path, tmp_dirs: list[Path]):
    # Test creating a single directory
    dir1, *_ = make_dirs([tmp_path / "new_dir1"])
    assert dir1.is_dir()
    dir1.rmdir()

    # Test creating multiple directories
    dir2, dir3, *_ = make_dirs([tmp_path / "new_dir2", tmp_path / "new_dir3"])
    assert dir2.is_dir()
    assert dir3.is_dir()
    dir2.rmdir()
    dir3.rmdir()

    # Test creating directories with a common root path
    subdir1, subdir2, *_ = make_dirs(["subdir1", "subdir2"], root=tmp_path)
    assert subdir1.is_dir()
    assert subdir2.is_dir()
    subdir1.rmdir()
    subdir2.rmdir()

    # Test creating directories with custom permissions
    custom_mode = 0o755
    custom_mode_dir, *_ = make_dirs([tmp_path / "custom_mode_dir"], mode=custom_mode)
    assert custom_mode_dir.is_dir()
    assert custom_mode_dir.stat().st_mode & custom_mode == custom_mode
    custom_mode_dir.rmdir()

    # Test that string inputs are normalized to Path objects in the result
    norm_dir, *_ = make_dirs([str(tmp_path / "norm_dir")])
    assert isinstance(norm_dir, Path)
    assert norm_dir.is_dir()
    norm_dir.rmdir()

    # Test that `stringify` returns the created paths as strings
    str_target = tmp_path / "str_dir"
    str_dir, *_ = make_dirs([str_target], stringify=True)
    assert isinstance(str_dir, str)
    assert str_dir == _stringify(str_target)
    str_target.rmdir()

    # Test creating directories with exist_ok=True for existing directories
    make_dirs(tmp_dirs, exist_ok=True)
    assert all(tmp_dir.is_dir() for tmp_dir in tmp_dirs)

    # Test creating directories with exist_ok=False for existing directories
    with pytest.raises(FileExistsError):
        make_dirs(tmp_dirs)  # `exist_ok` is False


def test_dir_empty(tmp_dir: Path):
    # Test an empty directory
    assert dir_empty(tmp_dir) is True

    # Test a non-empty directory
    (file := tmp_dir / "file.txt").touch()
    assert dir_empty(tmp_dir) is False
    file.unlink()


def test_dir_empty_unsafe(tmp_dir: Path):
    # An empty directory; both Path and str inputs are accepted.
    assert dir_empty_unsafe(tmp_dir) is True
    assert dir_empty_unsafe(str(tmp_dir)) is True

    # A non-empty directory.
    (file := tmp_dir / "file.txt").touch()
    assert dir_empty_unsafe(tmp_dir) is False
    file.unlink()


def test_dirs_empty(tmp_path: Path, tmp_dirs: list[Path], tmp_dirnames: list[str]):
    # Test multiple empty directories
    assert dirs_empty(tmp_dirs) is True

    # Test a mix of empty and non-empty directories
    (dir4 := tmp_path / "dir4").mkdir()
    (file := dir4 / "file.txt").touch()
    mixed_dirs = [*tmp_dirs, dir4]
    assert dirs_empty(mixed_dirs) is False
    file.unlink()
    dir4.rmdir()

    # Test with a common root path
    assert dirs_empty(tmp_dirnames, root=tmp_path) is True


def test_dirs_empty_unsafe(
    tmp_path: Path, tmp_dirs: list[Path], tmp_dirnames: list[str]
):
    # Multiple empty directories.
    assert dirs_empty_unsafe(tmp_dirs) is True

    # A mix of empty and non-empty directories.
    (dir4 := tmp_path / "dir4").mkdir()
    (file := dir4 / "file.txt").touch()
    assert dirs_empty_unsafe([*tmp_dirs, dir4]) is False
    file.unlink()
    dir4.rmdir()

    # `root` is prepended to each path.
    assert dirs_empty_unsafe(tmp_dirnames, root=tmp_path) is True
