from __future__ import annotations

import gc
import platform
import stat
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem import staged
from kaparoo.filesystem.staged import (
    StagedDirectory,
    StagedFile,
    _default_dir_mode,
    _default_file_mode,
    _fsync_parent,
)

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
        f.file.writelines(["a\n", "b\n"])  # method this class does not proxy
    assert dest.read_text(encoding="utf-8") == "a\nb\n"


def test_commit_after_external_close_raises(tmp_path: Path):
    # Closing the underlying handle would make a commit unsafe; it is rejected
    # with a clear error rather than a confusing "I/O on closed file".
    dest = tmp_path / "data.txt"
    f = StagedFile(dest, encoding="utf-8")
    f.write("x")
    f.file.close()  # misuse
    with pytest.raises(ValueError, match="closed externally"):
        f.commit()
    assert not dest.exists()
    f.abort()  # cleans up the staged temp file
    assert list(tmp_path.glob("*.tmp")) == []


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


def test_overwrite_on_directory_raises(tmp_path: Path):
    # overwrite=True cannot replace a directory with a file; reject clearly
    # instead of letting `replace` fail with a platform-specific OSError.
    dest = tmp_path / "x"
    dest.mkdir()
    f = StagedFile(dest, overwrite=True, encoding="utf-8")
    f.write("data")
    with pytest.raises(IsADirectoryError):
        f.commit()
    assert dest.is_dir()  # untouched
    f.abort()


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


@pytest.fixture()
def no_hardlink_support(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a filesystem without hardlinks (FAT/exFAT, some network FS)."""
    import pathlib

    def raiser(self: pathlib.Path, *args: object, **kwargs: object) -> None:
        msg = "hardlinks unsupported"
        raise OSError(msg)

    monkeypatch.setattr(pathlib.Path, "hardlink_to", raiser)


@pytest.mark.usefixtures("no_hardlink_support")
def test_commit_falls_back_to_replace_without_hardlink_support(tmp_path: Path):
    # The non-FileExistsError OSError from a no-hardlink filesystem must not
    # lose the staged content: commit falls back to replace.
    dest = tmp_path / "data.txt"
    with StagedFile(dest, encoding="utf-8") as f:
        f.write("hello")
    assert dest.read_text(encoding="utf-8") == "hello"
    assert list(tmp_path.glob("*.tmp")) == []  # temp moved, not left behind


@pytest.mark.usefixtures("no_hardlink_support")
def test_commit_fallback_refuses_to_clobber_concurrent_file(tmp_path: Path):
    # Even on the fallback path, an existing destination is not overwritten
    # when overwrite is False.
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


# --- durability (parent fsync) ---------------------------------------------


def test_fsync_parent_fsyncs_then_closes(monkeypatch: pytest.MonkeyPatch):
    # Success path forced via monkeypatch so it runs even on Windows, which
    # cannot open a directory for fsync.
    events: list[tuple[str, int]] = []
    monkeypatch.setattr(staged.os, "open", lambda _p, _flags: 4242)
    monkeypatch.setattr(staged.os, "fsync", lambda fd: events.append(("fsync", fd)))
    monkeypatch.setattr(staged.os, "close", lambda fd: events.append(("close", fd)))

    _fsync_parent(staged.Path("any") / "child")
    assert events == [("fsync", 4242), ("close", 4242)]


def test_fsync_parent_ignores_unopenable_directory(monkeypatch: pytest.MonkeyPatch):
    # A directory that cannot be opened (e.g. on Windows) is a silent no-op.
    def boom(_p: object, _flags: object) -> int:
        msg = "cannot open directory"
        raise OSError(msg)

    monkeypatch.setattr(staged.os, "open", boom)
    _fsync_parent(staged.Path("any") / "child")  # must not raise


# --- re-export -------------------------------------------------------------


def test_reexported_from_package():
    from kaparoo import filesystem

    assert filesystem.StagedFile is StagedFile
    assert filesystem.StagedDirectory is StagedDirectory


# ===========================================================================
# StagedDirectory
# ===========================================================================


def test_dir_context_manager_commits_on_success(tmp_path: Path):
    dest = tmp_path / "dataset"
    with StagedDirectory(dest) as d:
        assert d.path == dest
        assert d.workdir.is_dir()
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
        (d.workdir / "sub").mkdir()
        assert not dest.exists()  # nothing visible until commit
        staging = d.workdir
    assert d.committed is True
    assert (dest / "a.txt").read_text(encoding="utf-8") == "a"
    assert (dest / "sub").is_dir()
    assert not staging.exists()  # staging moved into place
    assert list(tmp_path.glob("*.tmp")) == []


def test_dir_context_manager_aborts_on_exception(tmp_path: Path):
    dest = tmp_path / "dataset"
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"), StagedDirectory(dest) as d:  # noqa: PT012
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
        raise boom
    assert not dest.exists()  # failed build leaves nothing behind
    assert list(tmp_path.glob("*.tmp")) == []


def test_dir_context_manager_after_explicit_commit_is_noop(tmp_path: Path):
    # Committing inside the block, then exiting cleanly, must not re-run it.
    dest = tmp_path / "dataset"
    with StagedDirectory(dest) as d:
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
        d.commit()
    assert (dest / "a.txt").read_text(encoding="utf-8") == "a"


def test_dir_explicit_commit_returns_path(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert d.committed is False
    assert d.commit() == dest
    assert d.committed is True
    assert (dest / "a.txt").read_text(encoding="utf-8") == "a"


def test_dir_explicit_abort_discards(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    d.abort()
    assert not dest.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_dir_commit_is_idempotent(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert d.commit() == dest
    assert d.commit() == dest  # second call is a no-op
    assert (dest / "a.txt").exists()


def test_dir_abort_after_commit_is_noop(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    d.commit()
    d.abort()  # cannot un-commit
    assert (dest / "a.txt").exists()


def test_dir_commit_after_abort_raises(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    d.abort()
    with pytest.raises(ValueError, match="aborted"):
        d.commit()


def test_dir_make_parents(tmp_path: Path):
    dest = tmp_path / "nested" / "deeper" / "dataset"
    with StagedDirectory(dest, make_parents=True) as d:
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert (dest / "a.txt").is_file()


def test_dir_missing_parent_without_make_parents_raises(tmp_path: Path):
    dest = tmp_path / "missing" / "dataset"
    with pytest.raises(FileNotFoundError):
        StagedDirectory(dest)


def test_dir_overwrite_false_fail_fast_when_exists(tmp_path: Path):
    dest = tmp_path / "dataset"
    dest.mkdir()
    (dest / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        StagedDirectory(dest)
    assert (dest / "keep.txt").exists()


def test_dir_overwrite_true_replaces_nonempty(tmp_path: Path):
    dest = tmp_path / "dataset"
    dest.mkdir()
    (dest / "old.txt").write_text("old", encoding="utf-8")
    with StagedDirectory(dest, overwrite=True) as d:
        (d.workdir / "new.txt").write_text("new", encoding="utf-8")
    assert (dest / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (dest / "old.txt").exists()  # old contents replaced
    assert list(tmp_path.glob("*.old")) == []  # backup removed


def test_dir_overwrite_on_file_raises(tmp_path: Path):
    # overwrite=True cannot replace a non-directory with a directory; reject
    # before the swap so the existing file is left intact.
    dest = tmp_path / "x"
    dest.write_text("file", encoding="utf-8")
    d = StagedDirectory(dest, overwrite=True)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        d.commit()
    assert dest.read_text(encoding="utf-8") == "file"  # untouched
    assert list(tmp_path.glob("*.old")) == []
    d.abort()


def test_dir_overwrite_true_when_absent_creates(tmp_path: Path):
    dest = tmp_path / "dataset"
    with StagedDirectory(dest, overwrite=True) as d:
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert (dest / "a.txt").exists()


def test_dir_commit_raises_if_destination_appears_after_init(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)  # dest absent here
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    dest.mkdir()  # appeared concurrently
    with pytest.raises(FileExistsError, match="already exists"):
        d.commit()
    assert dest.is_dir()


def test_dir_garbage_collection_discards_without_committing(tmp_path: Path):
    dest = tmp_path / "dataset"
    d = StagedDirectory(dest)
    (d.workdir / "a.txt").write_text("a", encoding="utf-8")

    del d
    gc.collect()
    assert not dest.exists()
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission bits are ignored on Windows",
)
def test_dir_committed_uses_umask_default_mode(tmp_path: Path):
    dest = tmp_path / "dataset"
    with StagedDirectory(dest) as d:
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert stat.S_IMODE(dest.stat().st_mode) == _default_dir_mode()


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="POSIX permission bits are ignored on Windows",
)
def test_dir_overwrite_preserves_existing_mode(tmp_path: Path):
    dest = tmp_path / "dataset"
    dest.mkdir()
    dest.chmod(0o750)
    with StagedDirectory(dest, overwrite=True) as d:
        (d.workdir / "a.txt").write_text("a", encoding="utf-8")
    assert stat.S_IMODE(dest.stat().st_mode) == 0o750
