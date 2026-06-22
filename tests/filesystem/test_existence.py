from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.exceptions import DirectoryNotFoundError, NotAFileError
from kaparoo.filesystem.existence import (
    dir_exists,
    dirs_exist,
    ensure_dir_exists,
    ensure_dirs_exist,
    ensure_file_exists,
    ensure_files_exist,
    ensure_path_exists,
    ensure_paths_exist,
    file_exists,
    files_exist,
    path_exists,
    paths_exist,
)

from .helpers import _stringify

if TYPE_CHECKING:
    from tests.fixtures.filesystem import TmpFilesystem

# --- boolean predicates -----------------------------------------------------


def test_path_exists(cwd_path: Path, tmp_file: Path, tmp_dir: Path, unknown_path: Path):
    assert path_exists(cwd_path) is True
    assert path_exists(tmp_file) is True
    assert path_exists(tmp_dir) is True
    assert path_exists(unknown_path) is False
    # `str` input is accepted equivalently.
    assert path_exists(str(tmp_file)) is True


def test_file_exists(tmp_file: Path, tmp_dir: Path, unknown_path: Path):
    assert file_exists(tmp_file) is True
    assert file_exists(tmp_dir) is False  # exists but not a file
    assert file_exists(unknown_path) is False


def test_dir_exists(tmp_dir: Path, tmp_file: Path, unknown_path: Path):
    assert dir_exists(tmp_dir) is True
    assert dir_exists(tmp_file) is False  # exists but not a directory
    assert dir_exists(unknown_path) is False


def test_paths_exist(tmp_filesystem: TmpFilesystem, unknown_path: Path):
    fs = tmp_filesystem
    # All existing, with and without `root`.
    assert paths_exist([fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file]) is True
    assert paths_exist(["file1.txt", "sub_dir/sub_file.txt"], root=fs.root) is True
    # Any missing collapses the result to False (both forms).
    assert paths_exist([fs.file1, unknown_path]) is False
    assert paths_exist(["file1.txt", "missing.txt"], root=fs.root) is False


def test_files_exist_distinguishes_directories(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    assert files_exist([fs.file1, fs.file2, fs.file3, fs.sub_file]) is True
    # `sub_dir` exists but is not a file.
    assert files_exist([fs.file1, fs.sub_dir]) is False


def test_dirs_exist_distinguishes_files(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    assert dirs_exist([fs.root, fs.sub_dir]) is True
    # `file1` exists but is not a directory.
    assert dirs_exist([fs.sub_dir, fs.file1]) is False


def test_paths_exist_root_validation_passthrough(unknown_path: Path):
    # Errors from `_join_root_if_provided` propagate (DirectoryNotFoundError).
    with pytest.raises(DirectoryNotFoundError):
        paths_exist(["x"], root=unknown_path)


# --- ensure_path_exists -----------------------------------------------------


@pytest.mark.parametrize("input_as_str", (True, False))
@pytest.mark.parametrize("stringify", (True, False))
def test_ensure_path_exists_returns_expected_type(
    cwd_path: Path, input_as_str: bool, stringify: bool
):
    cwd_str = _stringify(cwd_path)
    path_in: str | Path = cwd_str if input_as_str else cwd_path
    expected: str | Path = cwd_str if stringify else cwd_path

    result = ensure_path_exists(path_in, stringify=stringify)
    assert isinstance(result, str if stringify else Path)
    assert result == expected


def test_ensure_path_exists_raises_when_missing(unknown_path: Path):
    with pytest.raises(FileNotFoundError):
        ensure_path_exists(unknown_path)


# --- ensure_file_exists -----------------------------------------------------


@pytest.mark.parametrize("input_as_str", (True, False))
@pytest.mark.parametrize("stringify", (True, False))
def test_ensure_file_exists_returns_expected_type(
    tmp_file: Path, input_as_str: bool, stringify: bool
):
    tmp_file_str = _stringify(tmp_file)
    path_in: str | Path = tmp_file_str if input_as_str else tmp_file
    expected: str | Path = tmp_file_str if stringify else tmp_file

    result = ensure_file_exists(path_in, stringify=stringify)
    assert isinstance(result, str if stringify else Path)
    assert result == expected


def test_ensure_file_exists_raises_when_missing(unknown_path: Path):
    with pytest.raises(FileNotFoundError):
        ensure_file_exists(unknown_path)


def test_ensure_file_exists_raises_when_directory(tmp_dir: Path):
    with pytest.raises(NotAFileError):
        ensure_file_exists(tmp_dir)


# --- ensure_dir_exists ------------------------------------------------------


@pytest.mark.parametrize("input_as_str", (True, False))
@pytest.mark.parametrize("stringify", (True, False))
def test_ensure_dir_exists_returns_expected_type(
    tmp_dir: Path, input_as_str: bool, stringify: bool
):
    tmp_dir_str = _stringify(tmp_dir)
    path_in: str | Path = tmp_dir_str if input_as_str else tmp_dir
    expected: str | Path = tmp_dir_str if stringify else tmp_dir

    result = ensure_dir_exists(path_in, stringify=stringify)
    assert isinstance(result, str if stringify else Path)
    assert result == expected


def test_ensure_dir_exists_raises_when_missing(unknown_path: Path):
    with pytest.raises(DirectoryNotFoundError):
        ensure_dir_exists(unknown_path)


def test_ensure_dir_exists_raises_when_file(tmp_file: Path):
    with pytest.raises(NotADirectoryError):
        ensure_dir_exists(tmp_file)


def test_ensure_dir_exists_make_creates_missing(tmp_path: Path):
    target = tmp_path / "foo"
    assert not target.exists()

    created = ensure_dir_exists(target, make=True)
    assert isinstance(created, Path)
    assert created.is_dir()


def test_ensure_dir_exists_make_accepts_int_mode(tmp_path: Path):
    # `make=<int>` (non-bool) routes through `_validate_mode(make)`. Mode
    # bits are ignored on Windows, but the validation call still runs.
    target = tmp_path / "with_int_mode"
    created = ensure_dir_exists(target, make=0o755)
    assert created.is_dir()


def test_ensure_dir_exists_invalid_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Mock the OS so the validation branch engages on Windows as well.
    monkeypatch.setattr("kaparoo.filesystem.existence.platform.system", lambda: "Linux")
    for bad_mode in (0, -1, 0o77777):
        with pytest.raises(ValueError, match="invalid directory mode"):
            ensure_dir_exists(tmp_path / "new", make=bad_mode)


# --- ensure_paths_exist / ensure_files_exist / ensure_dirs_exist -----------


def test_ensure_paths_exist(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem

    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir", "sub_dir/sub_file.txt"]
    result = ensure_paths_exist(paths, root=fs.root)
    expected = [fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file]

    assert result == expected


def test_ensure_files_exist(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem

    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir/sub_file.txt"]
    result = ensure_files_exist(paths, root=fs.root)
    expected = [fs.file1, fs.file2, fs.file3, fs.sub_file]

    assert result == expected


def test_ensure_dirs_exist(
    tmp_path: Path, tmp_dir: Path, tmp_filesystem: TmpFilesystem
):
    fs = tmp_filesystem

    paths = ["dir", "root_dir", "root_dir/sub_dir"]
    result = ensure_dirs_exist(paths, root=tmp_path)
    expected = [tmp_dir, fs.root, fs.sub_dir]

    assert result == expected


def test_ensure_paths_exist_stringify(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir", "sub_dir/sub_file.txt"]
    result = ensure_paths_exist(paths, root=fs.root, stringify=True)
    expected = [fs.file1, fs.file2, fs.file3, fs.sub_dir, fs.sub_file]
    assert result == [_stringify(p) for p in expected]
    assert all(isinstance(p, str) for p in result)


def test_ensure_files_exist_stringify(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem
    paths = ["file1.txt", "file2.txt", "file3.png", "sub_dir/sub_file.txt"]
    result = ensure_files_exist(paths, root=fs.root, stringify=True)
    expected = [fs.file1, fs.file2, fs.file3, fs.sub_file]
    assert result == [_stringify(p) for p in expected]
    assert all(isinstance(p, str) for p in result)


def test_ensure_dirs_exist_stringify(
    tmp_path: Path, tmp_dir: Path, tmp_filesystem: TmpFilesystem
):
    fs = tmp_filesystem
    paths = ["dir", "root_dir", "root_dir/sub_dir"]
    result = ensure_dirs_exist(paths, root=tmp_path, stringify=True)
    expected = [tmp_dir, fs.root, fs.sub_dir]
    assert result == [_stringify(p) for p in expected]
    assert all(isinstance(p, str) for p in result)


def test_ensure_dirs_exist_make_accepts_int_mode(tmp_path: Path):
    # Mirrors `test_ensure_dir_exists_make_accepts_int_mode` for the bulk
    # variant; covers the `_validate_mode(make)` call site at module level.
    target = tmp_path / "with_int_mode"
    (result,) = ensure_dirs_exist([target], make=0o755)
    assert result.is_dir()


def test_ensure_dirs_exist_invalid_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("kaparoo.filesystem.existence.platform.system", lambda: "Linux")
    # `make` is validated even when `paths` is empty.
    for bad_mode in (0, -1, 0o77777):
        with pytest.raises(ValueError, match="invalid directory mode"):
            ensure_dirs_exist([], make=bad_mode)


def test_exceptions_reexported_from_package():
    from kaparoo import filesystem

    assert filesystem.DirectoryNotFoundError is DirectoryNotFoundError
    assert filesystem.NotAFileError is NotAFileError


# --- exception inheritance contract ----------------------------------------


def test_directory_not_found_is_a_file_not_found():
    # The docstring on DirectoryNotFoundError declares this inheritance so
    # that callers can write `except FileNotFoundError` and catch both. A
    # regression that reparents DirectoryNotFoundError would silently break
    # consumer code -- pin the contract with both a type check and an
    # `except` clause.
    assert issubclass(DirectoryNotFoundError, FileNotFoundError)
    msg = "x"
    try:
        raise DirectoryNotFoundError(msg)
    except FileNotFoundError:
        return
    pytest.fail("DirectoryNotFoundError was not caught by FileNotFoundError")
