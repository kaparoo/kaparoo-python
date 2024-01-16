# -*- coding: utf-8 -*-

import platform
from pathlib import Path

import pytest

from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError
from kaparoo.filesystem.existence import (
    ensure_dir_exists,
    ensure_dirs_exist,
    ensure_file_exists,
    ensure_files_exist,
    ensure_path_exists,
    ensure_paths_exist,
)


def _stringify(path: Path) -> str:
    path = str(path)
    if platform.system() == "Windows":
        path = path.replace("\\", "/")
    return path


@pytest.mark.order(1)
def test_ensure_path_exists(cwd_path: Path, unknown_path: Path):
    cwd_str = _stringify(cwd_path)

    test_cases: list[tuple[str | Path, bool, str | Path]] = [
        (cwd_str, True, cwd_str),
        (cwd_str, False, cwd_path),
        (cwd_path, True, cwd_str),
        (cwd_path, False, cwd_path),
    ]

    for path, stringify, expected in test_cases:
        result = ensure_path_exists(path, stringify=stringify)
        assert isinstance(result, str if stringify else Path)
        assert result == expected

    with pytest.raises(FileNotFoundError):
        ensure_path_exists(unknown_path)


@pytest.mark.order(2)
def test_ensure_file_exists(tmp_dir: Path, tmp_file: Path, unknown_path: Path):
    tmp_file_str = _stringify(tmp_file)

    test_cases: list[tuple[str | Path, bool, str | Path]] = [
        (tmp_file_str, True, tmp_file_str),
        (tmp_file_str, False, tmp_file),
        (tmp_file, True, tmp_file_str),
        (tmp_file, False, tmp_file),
    ]

    for file_path, stringify, expected in test_cases:
        result = ensure_file_exists(file_path, stringify=stringify)
        assert isinstance(result, str if stringify else Path)
        assert result == expected

    with pytest.raises(FileNotFoundError):
        ensure_file_exists(unknown_path)

    with pytest.raises(NotAFileError):
        ensure_file_exists(tmp_dir)


@pytest.mark.order(2)
def test_ensure_dir_exists(tmp_paths: tuple[Path, ...], unknown_path: Path):
    tmp_path, tmp_dir, tmp_file = tmp_paths
    tmp_dir_str = _stringify(tmp_dir)

    test_cases: list[tuple[str | Path, bool, str | Path]] = [
        (tmp_dir_str, True, tmp_dir_str),
        (tmp_dir_str, False, tmp_dir),
        (tmp_dir, True, tmp_dir_str),
        (tmp_dir, False, tmp_dir),
    ]

    for dir_path, stringify, expected in test_cases:
        result = ensure_dir_exists(dir_path, stringify=stringify)
        assert isinstance(result, str if stringify else Path)
        assert result == expected

    with pytest.raises(DirectoryNotFoundError):
        ensure_dir_exists(unknown_path)

    with pytest.raises(NotADirectoryError):
        ensure_dir_exists(tmp_file)

    not_existing_dir = tmp_path / "foo"

    assert not not_existing_dir.exists()
    existing_dir = ensure_dir_exists(not_existing_dir, make=True)

    assert isinstance(existing_dir, Path) and existing_dir.is_dir()
    existing_dir.rmdir()


@pytest.mark.order(3)
def test_ensure_paths_exist(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, sub_dir, sub_file = tmp_filesystem

    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir", "sub_dir/sub_file.txt"]
    result = ensure_paths_exist(paths, root=root_dir)
    expected = [file1, file2, file3, sub_dir, sub_file]

    assert result == expected


@pytest.mark.order(3)
def test_ensure_files_exist(tmp_filesystem: tuple[Path, ...]):
    root_dir, file1, file2, file3, _, sub_file = tmp_filesystem

    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir/sub_file.txt"]
    result = ensure_files_exist(paths, root=root_dir)
    expected = [file1, file2, file3, sub_file]

    assert result == expected


@pytest.mark.order(3)
def test_ensure_dirs_exist(
    tmp_path: Path, tmp_dir: Path, tmp_filesystem: tuple[Path, ...]
):
    root_dir, *_, sub_dir, _ = tmp_filesystem

    paths = ["dir", "root_dir", "root_dir/sub_dir"]
    result = ensure_dirs_exist(paths, root=tmp_path)
    expected = [tmp_dir, root_dir, sub_dir]

    assert result == expected