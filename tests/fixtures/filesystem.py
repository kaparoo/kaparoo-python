from __future__ import annotations

__all__ = (
    "cwd_path",
    "dummy_path",
    "tmp_dir",
    "tmp_file",
    "tmp_filesystem",
    "tmp_paths",
    "unknown_path",
)

import shutil
from pathlib import Path

import pytest


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
    yield dir_path
    dir_path.rmdir()


@pytest.fixture()
def tmp_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "file.txt"
    file_path.touch()
    yield file_path
    file_path.unlink()


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

    yield dirs

    for dirpath in dirs:
        shutil.rmtree(dirpath, ignore_errors=True)


@pytest.fixture()
def tmp_filenames() -> list[str]:
    return [f"file{i}.txt" for i in range(1, 4)]


@pytest.fixture()
def tmp_files(tmp_path: Path, tmp_filenames: list[str]) -> list[Path]:
    files = [tmp_path / filename for filename in tmp_filenames]

    for file in files:
        file.touch()

    yield files

    for file in files:
        file.unlink()


@pytest.fixture()
def tmp_filesystem(tmp_path: Path) -> list[Path]:
    root_dir = tmp_path / "root_dir"
    root_dir.mkdir()

    (file1 := root_dir / "file1.txt").touch()
    (file2 := root_dir / "file2.txt").touch()
    (file3 := root_dir / "file3.png").touch()
    (sub_dir := root_dir / "sub_dir").mkdir()
    (sub_file := sub_dir / "sub_file.txt").touch()

    yield root_dir, file1, file2, file3, sub_dir, sub_file

    sub_file.unlink()
    sub_dir.rmdir()
    file3.unlink()
    file2.unlink()
    file1.unlink()
    root_dir.rmdir()
