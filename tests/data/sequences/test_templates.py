from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.data.sequences import FileFolderSequence, SingleFileSequence
from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError

if TYPE_CHECKING:
    from pathlib import Path

# --- test subclasses --------------------------------------------------------


class BytesFolder(FileFolderSequence[bytes]):
    """`FileFolderSequence` whose items are raw file bytes.

    Demonstrates the "set state before super().__init__()" pattern
    for parameterized subclasses: `pattern` and `recursive` are
    stored on `self` first so that `list_files` (an instance method)
    can read them.
    """

    def __init__(self, root, *, pattern: str = "*", recursive: bool = False) -> None:
        self._pattern = pattern
        self._recursive = recursive
        super().__init__(root)

    def list_files(self, root: Path) -> list[Path]:
        glob_fn = root.rglob if self._recursive else root.glob
        return sorted(p for p in glob_fn(self._pattern) if p.is_file())

    def get_meta(self, index: int) -> Path:
        return self.get_file(index)

    def load_file(self, path: Path) -> bytes:
        return path.read_bytes()


class TextLinesFile(SingleFileSequence[str, int]):
    """A `SingleFileSequence` exposing a text file line by line."""

    def __init__(self, path):
        super().__init__(path)
        self._lines = tuple(self.path.read_text().splitlines())

    def __len__(self) -> int:
        return len(self._lines)

    def get_item(self, index: int) -> str:
        return self._lines[index]

    def get_meta(self, index: int) -> int:
        # 1-based line number
        return index + 1


# --- FileFolderSequence -----------------------------------------------------


def test_file_folder_is_abstract(tmp_dir: Path):
    with pytest.raises(TypeError, match="abstract"):
        FileFolderSequence(tmp_dir)  # ty: ignore[missing-argument]


def test_file_folder_basic(tmp_dir: Path):
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta")
    (tmp_dir / "c.txt").write_text("gamma")

    folder = BytesFolder(tmp_dir)
    assert len(folder) == 3
    # sorted lex order
    assert folder[0] == b"alpha"
    assert folder[1] == b"beta"
    assert folder[2] == b"gamma"


def test_file_folder_metadata_is_path(tmp_dir: Path):
    (tmp_dir / "a.txt").write_text("alpha")
    folder = BytesFolder(tmp_dir)
    assert folder.get_meta(0) == tmp_dir / "a.txt"


def test_file_folder_subclass_options_reach_list_files(tmp_dir: Path):
    # `pattern` is stored on `self` before `super().__init__()` and
    # read by `list_files` when the base invokes it.
    (tmp_dir / "keep.txt").write_text("k")
    (tmp_dir / "skip.png").write_text("s")
    (tmp_dir / "also.txt").write_text("a")

    folder = BytesFolder(tmp_dir, pattern="*.txt")
    assert {p.name for p in folder.files} == {"keep.txt", "also.txt"}


def test_file_folder_non_recursive_skips_subdirs(tmp_dir: Path):
    # Default `recursive=False` -> uses `glob`, not `rglob`.
    (tmp_dir / "top.txt").write_text("t")
    (sub := tmp_dir / "sub").mkdir()
    (sub / "inner.txt").write_text("i")

    folder = BytesFolder(tmp_dir)
    assert [p.name for p in folder.files] == ["top.txt"]


def test_file_folder_recursive_via_subclass_option(tmp_dir: Path):
    # `recursive=True` is read by `list_files` from `self._recursive`.
    (tmp_dir / "top.txt").write_text("t")
    (sub := tmp_dir / "sub").mkdir()
    (sub / "inner.txt").write_text("i")

    folder = BytesFolder(tmp_dir, recursive=True)
    assert {p.name for p in folder.files} == {"top.txt", "inner.txt"}


def test_file_folder_directories_excluded(tmp_dir: Path):
    # The BytesFolder `list_files` filters by `is_file()` -- subdirectories
    # under `root` are not surfaced as items.
    (tmp_dir / "a.txt").write_text("a")
    (tmp_dir / "subdir").mkdir()
    folder = BytesFolder(tmp_dir)
    assert [p.name for p in folder.files] == ["a.txt"]


def test_file_folder_empty(tmp_dir: Path):
    folder = BytesFolder(tmp_dir)
    assert len(folder) == 0
    assert list(folder) == []


def test_file_folder_loads_lazily(tmp_dir: Path):
    (tmp_dir / "a.txt").write_text("alpha")
    (tmp_dir / "b.txt").write_text("beta")

    load_count = [0]

    class CountingFolder(FileFolderSequence[bytes]):
        def list_files(self, root: Path) -> list[Path]:
            return sorted(p for p in root.glob("*") if p.is_file())

        def get_meta(self, index: int) -> Path:
            return self.get_file(index)

        def load_file(self, path: Path) -> bytes:
            load_count[0] += 1
            return path.read_bytes()

    folder = CountingFolder(tmp_dir)
    assert load_count[0] == 0  # No loads at construction.

    _ = folder[0]
    assert load_count[0] == 1

    _ = folder[1]
    assert load_count[0] == 2

    _ = folder[0]  # Re-access triggers another load (no caching by design).
    assert load_count[0] == 3


def test_file_folder_root_property(tmp_dir: Path):
    folder = BytesFolder(tmp_dir)
    assert folder.root == tmp_dir


def test_file_folder_files_is_tuple(tmp_dir: Path):
    (tmp_dir / "a.txt").write_text("a")
    folder = BytesFolder(tmp_dir)
    assert isinstance(folder.files, tuple)


def test_file_folder_missing_root_raises(unknown_path: Path):
    with pytest.raises(DirectoryNotFoundError):
        BytesFolder(unknown_path)


def test_file_folder_root_is_file_raises(tmp_file: Path):
    with pytest.raises(NotADirectoryError):
        BytesFolder(tmp_file)


# --- SingleFileSequence -----------------------------------------------------


def test_single_file_is_abstract(tmp_file: Path):
    with pytest.raises(TypeError, match="abstract"):
        SingleFileSequence(tmp_file)  # ty: ignore[missing-argument]


def test_single_file_basic(tmp_file: Path):
    tmp_file.write_text("first\nsecond\nthird\n")
    seq = TextLinesFile(tmp_file)
    assert len(seq) == 3
    assert seq[0] == "first"
    assert seq[1] == "second"
    assert seq[2] == "third"


def test_single_file_metadata(tmp_file: Path):
    tmp_file.write_text("a\nb\n")
    seq = TextLinesFile(tmp_file)
    assert seq.get_meta(0) == 1
    assert seq.get_meta(1) == 2


def test_single_file_path_property(tmp_file: Path):
    tmp_file.write_text("x")
    seq = TextLinesFile(tmp_file)
    assert seq.path == tmp_file


def test_single_file_missing_raises(unknown_path: Path):
    with pytest.raises(FileNotFoundError):
        TextLinesFile(unknown_path)


def test_single_file_is_a_directory_raises(tmp_dir: Path):
    with pytest.raises(NotAFileError):
        TextLinesFile(tmp_dir)
