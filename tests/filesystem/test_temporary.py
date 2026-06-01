from __future__ import annotations

import gc
from pathlib import Path

from kaparoo.filesystem.temporary import TemporaryFile

# --- context-manager usage -------------------------------------------------


def test_context_manager_creates_and_cleans_up():
    with TemporaryFile() as tmp:
        assert isinstance(tmp.path, Path)
        assert tmp.path.is_file()  # exists during the block
        captured = tmp.path
        assert tmp.closed is False
    assert tmp.closed is True
    assert not captured.exists()  # removed on exit


def test_context_manager_yields_self_with_file_api():
    with TemporaryFile() as tmp:
        assert tmp.write(b"scratch") == len(b"scratch")
        tmp.flush()
        assert tmp.tell() == len(b"scratch")
        tmp.seek(0)
        assert tmp.read() == b"scratch"


# --- explicit usage --------------------------------------------------------


def test_explicit_usage_round_trip():
    tmp = TemporaryFile()
    path = tmp.path
    try:
        tmp.write(b"hello")
        tmp.seek(0)
        assert tmp.read() == b"hello"
        assert path.is_file()
    finally:
        tmp.close()
    assert tmp.closed is True
    assert not path.exists()


def test_close_is_idempotent():
    tmp = TemporaryFile()
    tmp.close()
    tmp.close()  # no error on repeated close
    assert tmp.closed is True


# --- delete flag -----------------------------------------------------------


def test_delete_false_persists_after_close():
    tmp = TemporaryFile(delete=False)
    tmp.write(b"keep me")
    path = tmp.path
    tmp.close()
    try:
        assert tmp.closed is True
        assert path.is_file()  # not removed
        assert path.read_bytes() == b"keep me"
    finally:
        path.unlink(missing_ok=True)


# --- placement options -----------------------------------------------------


def test_directory_suffix_prefix(tmp_path: Path):
    with TemporaryFile(directory=tmp_path, prefix="pre_", suffix=".dat") as tmp:
        assert tmp.path.parent == tmp_path
        assert tmp.path.name.startswith("pre_")
        assert tmp.path.suffix == ".dat"


def test_file_property_exposes_handle():
    with TemporaryFile() as tmp:
        tmp.file.write(b"abc")
        tmp.file.seek(0)
        assert tmp.file.read() == b"abc"


# --- garbage-collection cleanup --------------------------------------------


def test_garbage_collection_removes_unclosed_file():
    # An instance dropped without `close()` is still cleaned up by the
    # weakref finalizer when collected.
    tmp = TemporaryFile()
    path = tmp.path
    assert path.is_file()

    del tmp
    gc.collect()
    assert not path.exists()


def test_garbage_collection_respects_delete_false():
    tmp = TemporaryFile(delete=False)
    path = tmp.path
    try:
        del tmp
        gc.collect()
        assert path.is_file()  # finalizer must not remove it
    finally:
        path.unlink(missing_ok=True)


# --- re-export -------------------------------------------------------------


def test_reexported_from_package():
    from kaparoo import filesystem

    assert filesystem.TemporaryFile is TemporaryFile
