from __future__ import annotations

import gc
import platform
import stat
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.staged import StagedFile, _default_file_mode

if TYPE_CHECKING:
    from pathlib import Path

# --- context-manager usage (text by default) -------------------------------


def test_context_manager_commits_on_success(tmp_path: Path):
    dest = tmp_path / "data.txt"
    with StagedFile(dest, encoding="utf-8") as f:
        assert f.path == dest
        f.write("payload")
        f.flush()
        assert not dest.exists()  # nothing visible until commit
    assert dest.read_text(encoding="utf-8") == "payload"
    assert list(tmp_path.glob("*.tmp")) == []  # temp cleaned up


def test_context_manager_after_explicit_commit_is_noop(tmp_path: Path):
    # Committing inside the block, then exiting cleanly, must not re-run the
    # commit (the writer is already finalized).
    dest = tmp_path / "data.txt"
    with StagedFile(dest, encoding="utf-8") as f:
        f.write("x")
        f.commit()
    assert dest.read_text(encoding="utf-8") == "x"


def test_context_manager_aborts_on_exception(tmp_path: Path):
    dest = tmp_path / "data.txt"
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"), StagedFile(dest) as f:  # noqa: PT012
        f.write("half")
        raise boom
    assert not dest.exists()  # failed write leaves nothing behind
    assert list(tmp_path.glob("*.tmp")) == []


def test_exception_keeps_existing_file_intact(tmp_path: Path):
    dest = tmp_path / "data.txt"
    dest.write_text("original", encoding="utf-8")
    with pytest.raises(RuntimeError), StagedFile(dest, overwrite=True) as f:  # noqa: PT012
        f.write("new but doomed")
        raise RuntimeError
    assert dest.read_text(encoding="utf-8") == "original"  # untouched


# --- explicit usage --------------------------------------------------------


def test_explicit_commit_returns_path(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest, encoding="utf-8")
    f.write("abc")
    assert f.committed is False
    result = f.commit()
    assert result == dest
    assert f.committed is True
    assert dest.read_text(encoding="utf-8") == "abc"


def test_explicit_abort_discards(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest)
    f.write("abc")
    f.abort()
    assert not dest.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_commit_is_idempotent(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest, encoding="utf-8")
    f.write("abc")
    assert f.commit() == dest
    assert f.commit() == dest  # second call is a no-op
    assert dest.read_text(encoding="utf-8") == "abc"


def test_abort_after_commit_is_noop(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest, encoding="utf-8")
    f.write("abc")
    f.commit()
    f.abort()  # cannot un-commit
    assert dest.read_text(encoding="utf-8") == "abc"


def test_commit_after_abort_raises(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest)
    f.abort()
    with pytest.raises(ValueError, match="aborted"):
        f.commit()


def test_file_property_exposes_handle(tmp_path: Path):
    dest = tmp_path / "data.txt"
    with StagedFile(dest, encoding="utf-8") as f:
        f.file.write("via handle")
    assert dest.read_text(encoding="utf-8") == "via handle"


# --- binary mode -----------------------------------------------------------


def test_binary_mode_writes_bytes(tmp_path: Path):
    dest = tmp_path / "data.bin"
    with StagedFile(dest, binary=True) as f:
        assert f.write(b"payload") == len(b"payload")
    assert dest.read_bytes() == b"payload"


def test_binary_seek_and_tell(tmp_path: Path):
    # Binary streams have predictable byte offsets (unlike text streams).
    dest = tmp_path / "data.bin"
    with StagedFile(dest, binary=True) as f:
        f.write(b"hello")
        assert f.tell() == 5
        f.seek(0)
        f.write(b"H")
    assert dest.read_bytes() == b"Hello"


def test_binary_overwrite(tmp_path: Path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"old")
    with StagedFile(dest, binary=True, overwrite=True) as f:
        f.write(b"new")
    assert dest.read_bytes() == b"new"


# --- make_parents ----------------------------------------------------------


def test_make_parents_creates_missing_parent(tmp_path: Path):
    dest = tmp_path / "nested" / "deeper" / "data.txt"
    with StagedFile(dest, make_parents=True, encoding="utf-8") as f:
        f.write("ok")
    assert dest.read_text(encoding="utf-8") == "ok"


def test_missing_parent_without_make_parents_raises(tmp_path: Path):
    dest = tmp_path / "missing" / "data.txt"
    with pytest.raises(FileNotFoundError):
        StagedFile(dest)


# --- overwrite semantics ---------------------------------------------------


def test_overwrite_false_fail_fast_when_exists(tmp_path: Path):
    dest = tmp_path / "data.txt"
    dest.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        StagedFile(dest)
    assert dest.read_text(encoding="utf-8") == "existing"


def test_overwrite_true_replaces(tmp_path: Path):
    dest = tmp_path / "data.txt"
    dest.write_text("old", encoding="utf-8")
    with StagedFile(dest, overwrite=True, encoding="utf-8") as f:
        f.write("new")
    assert dest.read_text(encoding="utf-8") == "new"


def test_overwrite_true_when_absent_creates(tmp_path: Path):
    # overwrite=True with no existing destination exercises the "no mode to
    # inherit" branch of commit.
    dest = tmp_path / "data.txt"
    with StagedFile(dest, overwrite=True, encoding="utf-8") as f:
        f.write("fresh")
    assert dest.read_text(encoding="utf-8") == "fresh"


def test_commit_raises_if_destination_appears_after_init(tmp_path: Path):
    # A racing creation between init and commit must not be clobbered when
    # overwrite is False.
    dest = tmp_path / "data.txt"
    f = StagedFile(dest, encoding="utf-8")  # dest absent here
    f.write("mine")
    dest.write_text("theirs", encoding="utf-8")  # appeared concurrently
    with pytest.raises(FileExistsError, match="overwrite=True"):
        f.commit()
    assert dest.read_text(encoding="utf-8") == "theirs"  # not clobbered
    assert list(tmp_path.glob("*.tmp")) == []


# --- garbage-collection cleanup --------------------------------------------


def test_garbage_collection_discards_without_committing(tmp_path: Path):
    dest = tmp_path / "data.txt"
    f = StagedFile(dest)
    f.write("never committed")

    del f
    gc.collect()
    assert not dest.exists()
    assert list(tmp_path.glob("*.tmp")) == []


# --- permissions -----------------------------------------------------------


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission bits are ignored on Windows",
)
def test_committed_file_uses_umask_default_mode(tmp_path: Path):
    dest = tmp_path / "data.txt"
    with StagedFile(dest, encoding="utf-8") as f:
        f.write("x")
    # The restrictive mkstemp mode (0o600) must be replaced by the default.
    assert stat.S_IMODE(dest.stat().st_mode) == _default_file_mode()


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission bits are ignored on Windows",
)
def test_overwrite_preserves_existing_mode(tmp_path: Path):
    dest = tmp_path / "data.txt"
    dest.write_text("old", encoding="utf-8")
    dest.chmod(0o640)
    with StagedFile(dest, overwrite=True, encoding="utf-8") as f:
        f.write("new")
    assert stat.S_IMODE(dest.stat().st_mode) == 0o640
    assert dest.read_text(encoding="utf-8") == "new"


# --- re-export -------------------------------------------------------------


def test_reexported_from_package():
    from kaparoo import filesystem

    assert filesystem.StagedFile is StagedFile
