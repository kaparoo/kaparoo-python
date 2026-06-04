from __future__ import annotations

import platform
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.utils import (
    ensure_file_extension,
    reserve_path,
    reserve_paths,
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


# --- reserve_path ----------------------------------------------------------


@pytest.mark.parametrize("input_as_str", (True, False))
@pytest.mark.parametrize("stringify", (True, False))
def test_reserve_path_returns_expected_type(
    tmp_path: Path, input_as_str: bool, stringify: bool
):
    target = tmp_path / "fresh"
    target_str = _stringify(target)
    path_in: str | Path = target_str if input_as_str else target
    expected: str | Path = target_str if stringify else target

    result = reserve_path(path_in, stringify=stringify)
    assert isinstance(result, str if stringify else type(target))
    assert result == expected


def test_reserve_path_raises_when_present(tmp_file: Path, tmp_dir: Path):
    # Any existing entry conflicts, regardless of its kind.
    for existing in (tmp_file, tmp_dir):
        with pytest.raises(FileExistsError, match="path already exists"):
            reserve_path(existing)


def test_reserve_path_exist_ok_permits_existing_non_destructively(
    tmp_file: Path, tmp_dir: Path
):
    # Type-agnostic: an existing file *or* directory is permitted and left
    # untouched.
    for existing in (tmp_file, tmp_dir):
        result = reserve_path(existing, exist_ok=True)
        assert result == existing
        assert existing.exists()  # nothing is deleted


def test_reserve_path_make_parents_creates_parent_only(tmp_path: Path):
    target = tmp_path / "nested" / "deeper" / "data.bin"
    assert not target.parent.exists()

    result = reserve_path(target, make_parents=True)
    assert result == target
    assert target.parent.is_dir()
    assert not target.exists()  # only the parent is created, not the target


def test_reserve_path_make_parents_noop_when_parent_exists(tmp_path: Path):
    # An existing parent makes `make_parents` a no-op (exist_ok=True).
    target = tmp_path / "data.bin"
    assert reserve_path(target, make_parents=True) == target
    assert not target.exists()


def test_reserve_path_make_parents_raises_when_ancestor_is_file(tmp_file: Path):
    # A file occupying an ancestor makes parent creation impossible.
    with pytest.raises(OSError):  # noqa: PT011 - platform varies (NotADirectoryError/...)
        reserve_path(tmp_file / "sub" / "x.bin", make_parents=True)


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="symlink creation requires privilege on Windows",
)
def test_reserve_path_treats_broken_symlink_as_occupied(tmp_path: Path):
    # A broken symlink still takes the name even though `Path.exists` reports
    # it absent, so `reserve_path` must treat it as a conflict.
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "nonexistent-target")
    assert not link.exists()  # broken -> exists() is False

    with pytest.raises(FileExistsError):
        reserve_path(link)
    assert reserve_path(link, exist_ok=True) == link  # exist_ok still bypasses


# --- reserve_paths ---------------------------------------------------------


def test_reserve_paths_returns_free_paths(tmp_path: Path):
    targets = [tmp_path / "a.bin", tmp_path / "b.bin"]
    assert reserve_paths(targets) == targets


def test_reserve_paths_stringify(tmp_path: Path):
    targets = [tmp_path / "a.bin", tmp_path / "b.bin"]
    result = reserve_paths(targets, stringify=True)
    assert result == [_stringify(p) for p in targets]
    assert all(isinstance(p, str) for p in result)


def test_reserve_paths_raises_when_any_present(tmp_path: Path, tmp_file: Path):
    with pytest.raises(FileExistsError, match="path already exists"):
        reserve_paths([tmp_path / "fresh.bin", tmp_file])


def test_reserve_paths_exist_ok_and_make_parents(tmp_path: Path, tmp_file: Path):
    fresh = tmp_path / "nested" / "new.bin"
    result = reserve_paths([tmp_file, fresh], exist_ok=True, make_parents=True)
    assert result == [tmp_file, fresh]
    assert tmp_file.exists()  # exist_ok is non-destructive
    assert fresh.parent.is_dir()


# --- ensure_file_extension -------------------------------------------------


def test_ensure_file_extension_accepts_matching():
    assert ensure_file_extension("out/data.bin", "bin").as_posix() == "out/data.bin"


def test_ensure_file_extension_is_case_insensitive():
    assert ensure_file_extension("out/DATA.BIN", "bin").name == "DATA.BIN"
    assert ensure_file_extension("out/data.bin", "BIN").name == "data.bin"


def test_ensure_file_extension_leading_dot_in_ext_is_optional():
    # ".bin" and "bin" behave the same.
    assert ensure_file_extension("a.bin", ".bin").name == "a.bin"


def test_ensure_file_extension_rejects_wrong_or_missing():
    with pytest.raises(ValueError, match=r"must have a \.bin extension"):
        ensure_file_extension("a.txt", "bin")
    with pytest.raises(ValueError, match=r"must have a \.bin extension"):
        ensure_file_extension("a", "bin")  # no extension


def test_ensure_file_extension_only_final_suffix():
    # Only the last component counts: ".tar.gz" matches "gz", not "tar.gz".
    assert ensure_file_extension("a.tar.gz", "gz").name == "a.tar.gz"
    with pytest.raises(ValueError, match=r"must have a \.tar\.gz extension"):
        ensure_file_extension("a.tar.gz", "tar.gz")


def test_ensure_file_extension_accepts_str_and_pathlike(tmp_path: Path):
    src = tmp_path / "x.json"
    assert ensure_file_extension(str(src), "json") == src
    assert ensure_file_extension(src, "json") == src


# --- ensure_file_extension(add=True) (np.save-style append) -----------------


def test_ensure_file_extension_add_appends_when_absent():
    result = ensure_file_extension("out/00000_phase", "bin", add=True)
    assert result.as_posix() == "out/00000_phase.bin"


def test_ensure_file_extension_add_keeps_matching():
    assert ensure_file_extension("out/data.bin", "bin", add=True).name == "data.bin"
    # case-insensitive
    assert ensure_file_extension("out/data.BIN", "bin", add=True).name == "data.BIN"


def test_ensure_file_extension_add_with_optional_leading_dot():
    assert ensure_file_extension("out/x", ".bin", add=True).name == "x.bin"


def test_ensure_file_extension_add_still_rejects_wrong_suffix():
    # `add` only resolves the missing-suffix case; a wrong suffix still raises.
    with pytest.raises(ValueError, match=r"must have a \.bin extension"):
        ensure_file_extension("out/x.txt", "bin", add=True)
