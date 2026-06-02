from __future__ import annotations

import platform
from pathlib import Path

import pytest

from kaparoo.filesystem.directory import (
    dir_empty,
    dir_empty_unsafe,
    dir_not_empty,
    dir_not_empty_unsafe,
    dirs_empty,
    dirs_empty_unsafe,
    dirs_not_empty,
    dirs_not_empty_unsafe,
    make_dir,
    make_dirs,
)

from .helpers import _stringify

# --- make_dir --------------------------------------------------------------


def test_make_dir_creates_and_stringifies(tmp_path: Path):
    # Default returns a Path; `stringify=True` returns the string form.
    created = make_dir(tmp_path / "new")
    assert isinstance(created, Path)
    assert created.is_dir()

    target = tmp_path / "str_dir"
    result = make_dir(target, stringify=True)
    assert isinstance(result, str)
    assert result == _stringify(target)


def test_make_dir_exist_ok(tmp_path: Path):
    created = make_dir(tmp_path / "new")
    make_dir(created, exist_ok=True)  # idempotent
    with pytest.raises(FileExistsError):
        make_dir(created)  # exist_ok defaults to False


def test_make_dir_raises_when_not_directory(tmp_file: Path):
    with pytest.raises(NotADirectoryError):
        make_dir(tmp_file)


def test_make_dir_invalid_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # `make_dir` calls `_validate_mode` on the same range as `make_dirs`.
    monkeypatch.setattr("kaparoo.filesystem.existence.platform.system", lambda: "Linux")
    for bad_mode in (0, -1, 0o77777):
        with pytest.raises(ValueError, match="invalid directory mode"):
            make_dir(tmp_path / "new", mode=bad_mode)


def test_make_dir_clean_wipes_existing_contents(tmp_dir: Path):
    # `clean=True` removes existing contents and recreates the directory.
    (tmp_dir / "stale.txt").touch()
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "nested.txt").touch()

    result = make_dir(tmp_dir, clean=True)
    assert result.is_dir()
    assert not any(result.iterdir())  # emptied


def test_make_dir_clean_creates_when_missing(tmp_path: Path):
    # `clean=True` on a missing path just creates it (nothing to wipe).
    target = tmp_path / "fresh"
    result = make_dir(target, clean=True)
    assert result.is_dir()


def test_make_dir_clean_makes_exist_ok_moot(tmp_dir: Path):
    # An existing dir would raise with the default exist_ok=False, but
    # `clean=True` recreates it instead of raising.
    (tmp_dir / "stale.txt").touch()
    result = make_dir(tmp_dir, clean=True)  # exist_ok left at default False
    assert not any(result.iterdir())


def test_make_dir_clean_still_rejects_non_directory(tmp_file: Path):
    # `clean` never deletes a non-directory occupying the path.
    with pytest.raises(NotADirectoryError):
        make_dir(tmp_file, clean=True)
    assert tmp_file.exists()  # the file is untouched


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="symlink creation requires privilege on Windows",
)
def test_make_dir_clean_rejects_symlink(tmp_path: Path):
    # `clean` must refuse a symlink: wiping has to operate on a real
    # directory, never through a link (which would reach the link's target).
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").touch()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(NotADirectoryError):
        make_dir(link, clean=True)
    assert (target / "keep.txt").exists()  # the link's target is untouched


# --- make_dirs -------------------------------------------------------------


def test_make_dirs_creates_paths(tmp_path: Path):
    # Single and multiple inputs share the same code path; verify both.
    (one,) = make_dirs([tmp_path / "one"])
    two, three = make_dirs([tmp_path / "two", tmp_path / "three"])
    assert all(d.is_dir() for d in (one, two, three))


def test_make_dirs_with_root(tmp_path: Path):
    subdir1, subdir2 = make_dirs(["subdir1", "subdir2"], root=tmp_path)
    assert subdir1.is_dir()
    assert subdir2.is_dir()


def test_make_dirs_normalizes_str_input_to_path(tmp_path: Path):
    (result,) = make_dirs([str(tmp_path / "norm_dir")])
    assert isinstance(result, Path)
    assert result.is_dir()


def test_make_dirs_stringify(tmp_path: Path):
    target = tmp_path / "str_dir"
    (result,) = make_dirs([target], stringify=True)
    assert isinstance(result, str)
    assert result == _stringify(target)


def test_make_dirs_exist_ok_branches(tmp_dirs: list[Path]):
    # exist_ok=True is idempotent for existing dirs; default raises.
    make_dirs(tmp_dirs, exist_ok=True)
    assert all(d.is_dir() for d in tmp_dirs)

    with pytest.raises(FileExistsError):
        make_dirs(tmp_dirs)


def test_make_dirs_clean_wipes_each_existing(tmp_path: Path, tmp_dirs: list[Path]):
    for d in tmp_dirs:
        (d / "stale.txt").touch()

    result = make_dirs(tmp_dirs, clean=True)
    assert all(d.is_dir() and not any(d.iterdir()) for d in result)


def test_make_dirs_clean_creates_missing(tmp_path: Path):
    targets = [tmp_path / "x", tmp_path / "y"]
    result = make_dirs(targets, clean=True)
    assert all(d.is_dir() for d in result)


def test_make_dirs_rejects_non_directory_before_creating(
    tmp_path: Path, tmp_file: Path
):
    # A file in the list raises NotADirectoryError (matching `make_dir`, which
    # previously diverged with FileExistsError), and validation happens before
    # any directory is created.
    ok = tmp_path / "ok"
    with pytest.raises(NotADirectoryError):
        make_dirs([ok, tmp_file])
    assert not ok.exists()  # nothing created before the bad entry was rejected


def test_make_dirs_clean_validates_before_wiping(tmp_path: Path, tmp_file: Path):
    # A bad entry later in the list must not cause earlier directories to be
    # wiped: every path is validated before any destructive operation runs.
    existing = tmp_path / "data"
    existing.mkdir()
    (existing / "keep.txt").touch()

    with pytest.raises(NotADirectoryError):
        make_dirs([existing, tmp_file], clean=True)
    assert (existing / "keep.txt").exists()  # earlier directory not wiped


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="directory mode is ignored on Windows",
)
def test_make_dirs_custom_mode(tmp_path: Path):
    custom_mode = 0o755
    (created,) = make_dirs([tmp_path / "custom_mode_dir"], mode=custom_mode)
    assert created.is_dir()
    assert created.stat().st_mode & custom_mode == custom_mode


# --- dir_empty / dir_empty_unsafe ------------------------------------------


def test_dir_empty(tmp_dir: Path):
    assert dir_empty(tmp_dir) is True
    (tmp_dir / "file.txt").touch()
    assert dir_empty(tmp_dir) is False


def test_dir_empty_unsafe_accepts_str_and_path(tmp_dir: Path):
    # `dir_empty_unsafe` skips validation; check both input types and both
    # outcomes in a single test.
    assert dir_empty_unsafe(tmp_dir) is True
    assert dir_empty_unsafe(str(tmp_dir)) is True
    (tmp_dir / "file.txt").touch()
    assert dir_empty_unsafe(tmp_dir) is False


def test_dir_empty_matches_unsafe_on_valid_input(tmp_dir: Path):
    # The two APIs are documented to differ only in pre-validation; on
    # inputs that pass `ensure_dir_exists` they must agree.
    assert dir_empty(tmp_dir) == dir_empty_unsafe(tmp_dir)
    (tmp_dir / "file.txt").touch()
    assert dir_empty(tmp_dir) == dir_empty_unsafe(tmp_dir)


# --- dirs_empty / dirs_empty_unsafe ----------------------------------------


def test_dirs_empty(tmp_path: Path, tmp_dirs: list[Path]):
    assert dirs_empty(tmp_dirs) is True

    (extra := tmp_path / "extra").mkdir()
    (extra / "file.txt").touch()
    assert dirs_empty([*tmp_dirs, extra]) is False


def test_dirs_empty_unsafe(tmp_path: Path, tmp_dirs: list[Path]):
    assert dirs_empty_unsafe(tmp_dirs) is True

    (extra := tmp_path / "extra").mkdir()
    (extra / "file.txt").touch()
    assert dirs_empty_unsafe([*tmp_dirs, extra]) is False


@pytest.mark.usefixtures("tmp_dirs")
def test_dirs_empty_with_root(tmp_path: Path, tmp_dirnames: list[str]):
    # `tmp_dirs` materializes the directories that `tmp_dirnames` names;
    # both APIs treat `root` identically.
    assert dirs_empty(tmp_dirnames, root=tmp_path) is True
    assert dirs_empty_unsafe(tmp_dirnames, root=tmp_path) is True


def test_dirs_empty_matches_unsafe_on_valid_input(tmp_path: Path, tmp_dirs: list[Path]):
    assert dirs_empty(tmp_dirs) == dirs_empty_unsafe(tmp_dirs)

    (extra := tmp_path / "extra").mkdir()
    (extra / "file.txt").touch()
    mixed = [*tmp_dirs, extra]
    assert dirs_empty(mixed) == dirs_empty_unsafe(mixed)


# --- dir_not_empty / dir_not_empty_unsafe ----------------------------------


def test_dir_not_empty(tmp_dir: Path):
    assert dir_not_empty(tmp_dir) is False
    (tmp_dir / "file.txt").touch()
    assert dir_not_empty(tmp_dir) is True


def test_dir_not_empty_is_inverse_of_empty(tmp_dir: Path):
    # `dir_not_empty` must be the exact negation of `dir_empty`.
    assert dir_not_empty(tmp_dir) == (not dir_empty(tmp_dir))
    (tmp_dir / "file.txt").touch()
    assert dir_not_empty(tmp_dir) == (not dir_empty(tmp_dir))


def test_dir_not_empty_unsafe_accepts_str_and_path(tmp_dir: Path):
    assert dir_not_empty_unsafe(tmp_dir) is False
    assert dir_not_empty_unsafe(str(tmp_dir)) is False
    (tmp_dir / "file.txt").touch()
    assert dir_not_empty_unsafe(tmp_dir) is True


# --- dirs_not_empty / dirs_not_empty_unsafe --------------------------------


def test_dirs_not_empty(tmp_path: Path, tmp_dirs: list[Path]):
    # `dirs_not_empty` is True only when *every* directory is non-empty.
    assert dirs_not_empty(tmp_dirs) is False  # all start empty
    for d in tmp_dirs:
        (d / "file.txt").touch()
    assert dirs_not_empty(tmp_dirs) is True

    (extra := tmp_path / "extra").mkdir()  # one empty dir flips it back
    assert dirs_not_empty([*tmp_dirs, extra]) is False


def test_dirs_not_empty_unsafe(tmp_path: Path, tmp_dirs: list[Path]):
    assert dirs_not_empty_unsafe(tmp_dirs) is False
    for d in tmp_dirs:
        (d / "file.txt").touch()
    assert dirs_not_empty_unsafe(tmp_dirs) is True

    (extra := tmp_path / "extra").mkdir()
    assert dirs_not_empty_unsafe([*tmp_dirs, extra]) is False


@pytest.mark.usefixtures("tmp_dirs")
def test_dirs_not_empty_with_root(tmp_path: Path, tmp_dirnames: list[str]):
    # Empty dirs -> not all non-empty; `root` handled identically by both.
    assert dirs_not_empty(tmp_dirnames, root=tmp_path) is False
    assert dirs_not_empty_unsafe(tmp_dirnames, root=tmp_path) is False
