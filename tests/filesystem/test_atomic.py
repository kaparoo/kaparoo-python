from __future__ import annotations

import gc
import platform
import stat
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.atomic import AtomicWriter, _default_file_mode

if TYPE_CHECKING:
    from pathlib import Path

# --- context-manager usage -------------------------------------------------


def test_context_manager_commits_on_success(tmp_path: Path):
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest) as f:
        assert f.path == dest
        f.write(b"payload")
        f.flush()
        assert not dest.exists()  # nothing visible until commit
    assert dest.read_bytes() == b"payload"
    assert list(tmp_path.glob("*.tmp")) == []  # temp cleaned up


def test_context_manager_after_explicit_commit_is_noop(tmp_path: Path):
    # Committing inside the block, then exiting cleanly, must not re-run the
    # commit (the writer is already finalized).
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest) as f:
        f.write(b"x")
        f.commit()
    assert dest.read_bytes() == b"x"


def test_context_manager_aborts_on_exception(tmp_path: Path):
    dest = tmp_path / "data.bin"
    sentinel = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"), AtomicWriter(dest) as f:  # noqa: PT012
        f.write(b"half")
        raise sentinel
    assert not dest.exists()  # failed write leaves nothing behind
    assert list(tmp_path.glob("*.tmp")) == []


def test_exception_keeps_existing_file_intact(tmp_path: Path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"original")
    with pytest.raises(RuntimeError), AtomicWriter(dest, overwrite=True) as f:  # noqa: PT012
        f.write(b"new but doomed")
        raise RuntimeError
    assert dest.read_bytes() == b"original"  # untouched


# --- explicit usage --------------------------------------------------------


def test_explicit_commit_returns_path(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.write(b"abc")
    assert f.committed is False
    result = f.commit()
    assert result == dest
    assert f.committed is True
    assert dest.read_bytes() == b"abc"


def test_explicit_abort_discards(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.write(b"abc")
    f.abort()
    assert not dest.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_commit_is_idempotent(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.write(b"abc")
    assert f.commit() == dest
    assert f.commit() == dest  # second call is a no-op
    assert dest.read_bytes() == b"abc"


def test_abort_after_commit_is_noop(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.write(b"abc")
    f.commit()
    f.abort()  # cannot un-commit
    assert dest.read_bytes() == b"abc"


def test_commit_after_abort_raises(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.abort()
    with pytest.raises(ValueError, match="aborted"):
        f.commit()


def test_seek_and_tell(tmp_path: Path):
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest) as f:
        f.write(b"hello")
        assert f.tell() == 5
        f.seek(0)
        f.write(b"H")
    assert dest.read_bytes() == b"Hello"


def test_file_property_exposes_handle(tmp_path: Path):
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest) as f:
        f.file.write(b"via handle")
    assert dest.read_bytes() == b"via handle"


# --- text mode -------------------------------------------------------------


def test_text_mode_writes_str(tmp_path: Path):
    dest = tmp_path / "report.txt"
    with AtomicWriter(dest, text=True, encoding="utf-8") as f:
        assert f.write("héllo\n") == len("héllo\n")
        f.write("world")
    assert dest.read_text(encoding="utf-8") == "héllo\nworld"


def test_text_mode_explicit_commit(tmp_path: Path):
    dest = tmp_path / "a.txt"
    f = AtomicWriter(dest, text=True, encoding="utf-8")
    f.write("data")
    f.commit()
    assert dest.read_text(encoding="utf-8") == "data"


def test_text_mode_overwrite(tmp_path: Path):
    dest = tmp_path / "a.txt"
    dest.write_text("old", encoding="utf-8")
    with AtomicWriter(dest, text=True, overwrite=True, encoding="utf-8") as f:
        f.write("new")
    assert dest.read_text(encoding="utf-8") == "new"


# --- overwrite semantics ---------------------------------------------------


def test_overwrite_false_fail_fast_when_exists(tmp_path: Path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"existing")
    with pytest.raises(FileExistsError, match="overwrite=True"):
        AtomicWriter(dest)
    assert dest.read_bytes() == b"existing"


def test_overwrite_true_replaces(tmp_path: Path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"old")
    with AtomicWriter(dest, overwrite=True) as f:
        f.write(b"new")
    assert dest.read_bytes() == b"new"


def test_overwrite_true_when_absent_creates(tmp_path: Path):
    # overwrite=True with no existing destination exercises the "no mode to
    # inherit" branch of commit.
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest, overwrite=True) as f:
        f.write(b"fresh")
    assert dest.read_bytes() == b"fresh"


def test_commit_raises_if_destination_appears_after_init(tmp_path: Path):
    # A racing creation between init and commit must not be clobbered when
    # overwrite is False.
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)  # dest absent here
    f.write(b"mine")
    dest.write_bytes(b"theirs")  # appeared concurrently
    with pytest.raises(FileExistsError, match="overwrite=True"):
        f.commit()
    assert dest.read_bytes() == b"theirs"  # not clobbered
    assert list(tmp_path.glob("*.tmp")) == []


# --- garbage-collection cleanup --------------------------------------------


def test_garbage_collection_discards_without_committing(tmp_path: Path):
    dest = tmp_path / "data.bin"
    f = AtomicWriter(dest)
    f.write(b"never committed")

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
    dest = tmp_path / "data.bin"
    with AtomicWriter(dest) as f:
        f.write(b"x")
    # The restrictive mkstemp mode (0o600) must be replaced by the default.
    assert stat.S_IMODE(dest.stat().st_mode) == _default_file_mode()


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission bits are ignored on Windows",
)
def test_overwrite_preserves_existing_mode(tmp_path: Path):
    dest = tmp_path / "data.bin"
    dest.write_bytes(b"old")
    dest.chmod(0o640)
    with AtomicWriter(dest, overwrite=True) as f:
        f.write(b"new")
    assert stat.S_IMODE(dest.stat().st_mode) == 0o640
    assert dest.read_bytes() == b"new"


# --- re-export -------------------------------------------------------------


def test_reexported_from_package():
    from kaparoo import filesystem

    assert filesystem.AtomicWriter is AtomicWriter
