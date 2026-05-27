from __future__ import annotations

__all__ = (
    "TmpFilesystem",
    "cwd_path",
    "dummy_path",
    "tmp_dir",
    "tmp_dirnames",
    "tmp_dirs",
    "tmp_file",
    "tmp_filenames",
    "tmp_files",
    "tmp_filesystem",
    "tmp_paths",
    "unknown_path",
)

from pathlib import Path
from typing import NamedTuple

import pytest


class TmpFilesystem(NamedTuple):
    """Layout returned by the `tmp_filesystem` fixture.

    The layout is:

        <root>/
        ├── file1.txt
        ├── file2.txt
        ├── file3.png
        └── sub_dir/
            └── sub_file.txt

    Named-tuple unpacking is still supported (`root, *_ = fs`); the named
    fields exist so tests can reference parts of the layout by intent.
    """

    root: Path
    file1: Path
    file2: Path
    file3: Path
    sub_dir: Path
    sub_file: Path


@pytest.fixture()
def cwd_path() -> Path:
    return Path.cwd()


@pytest.fixture()
def dummy_path() -> Path:
    return Path("path/to/file")


@pytest.fixture()
def unknown_path() -> Path:
    return Path("unknown path")


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    dir_path = tmp_path / "dir"
    dir_path.mkdir()
    return dir_path


@pytest.fixture()
def tmp_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "file.txt"
    file_path.touch()
    return file_path


@pytest.fixture()
def tmp_paths(tmp_path: Path, tmp_dir: Path, tmp_file: Path) -> tuple[Path, Path, Path]:
    return tmp_path, tmp_dir, tmp_file


@pytest.fixture()
def tmp_dirnames() -> list[str]:
    return [f"dir{i}" for i in range(1, 4)]


@pytest.fixture()
def tmp_dirs(tmp_path: Path, tmp_dirnames: list[str]) -> list[Path]:
    dirs = [tmp_path / dirname for dirname in tmp_dirnames]
    for dirpath in dirs:
        dirpath.mkdir()
    return dirs


@pytest.fixture()
def tmp_filenames() -> list[str]:
    return [f"file{i}.txt" for i in range(1, 4)]


@pytest.fixture()
def tmp_files(tmp_path: Path, tmp_filenames: list[str]) -> list[Path]:
    files = [tmp_path / filename for filename in tmp_filenames]
    for file in files:
        file.touch()
    return files


@pytest.fixture()
def tmp_filesystem(tmp_path: Path) -> TmpFilesystem:
    root = tmp_path / "root_dir"
    root.mkdir()

    (file1 := root / "file1.txt").touch()
    (file2 := root / "file2.txt").touch()
    (file3 := root / "file3.png").touch()
    (sub_dir := root / "sub_dir").mkdir()
    (sub_file := sub_dir / "sub_file.txt").touch()

    return TmpFilesystem(root, file1, file2, file3, sub_dir, sub_file)
