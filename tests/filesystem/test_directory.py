# -*- coding: utf-8 -*-

import os
from pathlib import Path

import pytest

from kaparoo.filesystem.directory import dir_empty, dirs_empty, get_paths, make_dirs
from kaparoo.filesystem.utils import stringify_paths


@pytest.mark.order(1)
def test_make_dirs(tmp_path: Path, tmp_dirs: list[Path]):
    # Test creating a single directory
    dir1, *_ = make_dirs([tmp_path / "new_dir1"])
    assert os.path.isdir(dir1)
    os.rmdir(dir1)

    # Test creating multiple directories
    dir2, dir3, *_ = make_dirs([tmp_path / "new_dir2", tmp_path / "new_dir3"])
    assert os.path.isdir(dir2)
    assert os.path.isdir(dir3)
    os.rmdir(dir2)
    os.rmdir(dir3)

    # Test creating directories with a common root path
    subdir1, subdir2, *_ = make_dirs(["subdir1", "subdir2"], root=tmp_path)
    assert os.path.isdir(subdir1)
    assert os.path.isdir(subdir2)
    os.rmdir(subdir1)
    os.rmdir(subdir2)

    # Test creating directories with custom permissions
    custom_mode = 0o755
    custom_mode_dir, *_ = make_dirs([tmp_path / "custom_mode_dir"], mode=custom_mode)
    assert os.path.isdir(custom_mode_dir)
    assert os.stat(custom_mode_dir).st_mode & custom_mode == custom_mode
    os.rmdir(custom_mode_dir)

    # Test creating directories with exist_ok=True for existing directories
    make_dirs(tmp_dirs, exist_ok=True)
    assert all(tmp_dir.is_dir() for tmp_dir in tmp_dirs)

    # Test creating directories with exist_ok=False for existing directories
    with pytest.raises(FileExistsError):
        make_dirs(tmp_dirs)  # `exist_ok` is False


@pytest.mark.order(1)
def test_dir_empty(tmp_dir: Path):
    # Test an empty directory
    assert dir_empty(tmp_dir) is True

    # Test a non-empty directory
    (file := tmp_dir / "file.txt").touch()
    assert dir_empty(tmp_dir) is False
    file.unlink()


@pytest.mark.order(2)
def test_dirs_empty(tmp_path: Path, tmp_dirs: list[Path], tmp_dirnames: list[str]):
    # Test multiple empty directories
    assert dirs_empty(tmp_dirs) is True

    # Test a mix of empty and non-empty directories
    (dir4 := tmp_path / "dir4").mkdir()
    (file := dir4 / "file.txt").touch()
    mixed_dirs = tmp_dirs + [dir4]
    assert dirs_empty(mixed_dirs) is False
    file.unlink()
    dir4.rmdir()

    # Test with a common root path
    assert dirs_empty(tmp_dirnames, root=tmp_path) is True


@pytest.mark.order(1)
def test_get_paths(tmp_filesystem: list[Path]):
    root_dir, file1, file2, file3, sub_dir, sub_file = tmp_filesystem

    # default
    result1 = get_paths(root_dir)
    expected1 = [file1, file2, file3, sub_dir]
    assert sorted(result1) == sorted(expected1)

    # recursive
    result2 = get_paths(root_dir, recursive=True)
    expected2 = [file1, file2, file3, sub_dir, sub_file]
    assert sorted(result2) == sorted(expected2)

    # stringify
    result3 = get_paths(root_dir, recursive=True, stringify=True)
    expected3 = stringify_paths(expected2)
    assert sorted(result3) == sorted(expected3)

    # pattern
    result4 = get_paths(root_dir, pattern="*.txt", recursive=True)
    expected4 = [file1, file2, sub_file]
    assert sorted(result4) == sorted(expected4)

    # excludes
    result5 = get_paths(root_dir, excludes=[file2, sub_dir], recursive=True)
    expected5 = [file1, file3, sub_file]
    assert sorted(result5) == sorted(expected5)

    # condition
    result6 = get_paths(root_dir, condition=os.path.isfile, recursive=True)
    expected6 = [file1, file2, file3, sub_file]
    assert sorted(result6) == sorted(expected6)

    # num_samples
    assert len(get_paths(root_dir, recursive=True, num_samples=2)) == 2

    with pytest.raises(ValueError):
        get_paths(root_dir, num_samples=0)