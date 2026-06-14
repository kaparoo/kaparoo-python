from __future__ import annotations

__all__ = (
    "TmpFilesystem",
    "TmpTree",
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
    "tmp_tree",
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


class TmpTree(NamedTuple):
    """Layout returned by the `tmp_tree` fixture.

    A deeper, more varied tree than `tmp_filesystem` -- three levels, an
    empty directory, a dotfile, and mixed extensions -- for depth, pruning,
    empty-directory, and extension-filter cases:

        <root>/
        ├── a.txt
        ├── b.log
        ├── .hidden
        ├── empty/
        └── docs/
            ├── readme.md
            └── nested/
                └── deep.txt

    Named fields let tests reference parts of the layout by intent; the depth
    of each is noted on its field.
    """

    root: Path
    a: Path  # a.txt, depth 1
    b: Path  # b.log, depth 1
    hidden: Path  # .hidden, depth 1
    empty: Path  # empty/, depth 1 (an empty directory)
    docs: Path  # docs/, depth 1
    readme: Path  # docs/readme.md, depth 2
    nested: Path  # docs/nested/, depth 2
    deep: Path  # docs/nested/deep.txt, depth 3


@pytest.fixture()
def tmp_tree(tmp_path: Path) -> TmpTree:
    root = tmp_path / "tree"
    root.mkdir()

    (a := root / "a.txt").touch()
    (b := root / "b.log").touch()
    (hidden := root / ".hidden").touch()
    (empty := root / "empty").mkdir()
    (docs := root / "docs").mkdir()
    (readme := docs / "readme.md").touch()
    (nested := docs / "nested").mkdir()
    (deep := nested / "deep.txt").touch()

    return TmpTree(root, a, b, hidden, empty, docs, readme, nested, deep)
