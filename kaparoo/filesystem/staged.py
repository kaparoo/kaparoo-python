from __future__ import annotations

__all__ = ("StagedDirectory", "StagedFile")

import contextlib
import os
import shutil
import stat
import tempfile
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, cast, overload

from kaparoo.filesystem.utils import reserve_path

if TYPE_CHECKING:
    from types import TracebackType
    from typing import IO, Literal, Self

    from kaparoo.filesystem.types import StrPath


def _discard(file: IO[str] | IO[bytes], temp_path: Path) -> None:
    """Close `file` and remove the staged temp file (the abort path).

    Lives at module level (not bound to the instance) so the
    `weakref.finalize` registration does not keep the `StagedFile` alive.
    """
    file.close()  # idempotent
    temp_path.unlink(missing_ok=True)


def _discard_dir(workdir: Path) -> None:
    """Remove the staging directory and its contents (the abort path).

    Lives at module level (not bound to the instance) so the
    `weakref.finalize` registration does not keep the `StagedDirectory` alive.
    """
    shutil.rmtree(workdir, ignore_errors=True)


def _umask_default(base: int) -> int:
    """Return `base` minus the current umask (the mode new paths would get)."""
    # Reading the umask requires setting it; restore it immediately. This
    # briefly mutates process-global state and so is not thread-safe.
    mask = os.umask(0)
    os.umask(mask)
    return base & ~mask


def _default_file_mode() -> int:
    """Return the mode new files would get (`0o666` minus the current umask)."""
    return _umask_default(0o666)


def _default_dir_mode() -> int:
    """Return the mode new directories would get (`0o777` minus the umask)."""
    return _umask_default(0o777)


def _fsync_parent(path: Path) -> None:
    """Best-effort fsync of `path`'s parent directory entry.

    Makes a just-completed rename/link into `path` durable across a crash on
    POSIX (the file's own data is fsynced separately). A no-op where a
    directory cannot be opened for fsync, e.g. Windows.
    """
    try:
        fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class StagedFile[AnyStrT: (str, bytes)]:
    """Write a file safely: stage to a temp file, then commit by atomic move.

    Content is written to a temporary file in the destination's own directory
    and moved into place only on `commit`, so a reader never observes a
    half-written file and a failed write leaves any existing file untouched.

    The default is text (`StagedFile[str]`) with optional `encoding` /
    `newline`, as with `open`; pass `binary=True` for a binary writer
    (`StagedFile[bytes]`). The type parameter follows the mode, so `write`
    and `file` are typed `str` or `bytes` accordingly.

    Usable as a context manager -- committing on a clean exit and discarding
    on an exception -- or explicitly, like a file object:

    Example:
        ```python
        # Text (the default), as a context manager: commit on success,
        # discard on error.
        with StagedFile("out/report.json", encoding="utf-8") as f:
            f.write(json.dumps(data))  # an exception here leaves out/ untouched

        # Binary, explicitly: write, then commit (or abort to discard).
        f = StagedFile("out/data.bin", binary=True)
        f.write(payload)
        f.commit()
        ```

    With `overwrite=False` (the default) an existing destination is a
    fail-fast `FileExistsError`, and the commit creates the file atomically
    via a hardlink -- it never clobbers a file that appeared meanwhile. On a
    filesystem without hardlink support (FAT/exFAT, some network mounts) the
    commit falls back to a best-effort existence check plus replace, leaving
    a small window where a file appearing concurrently could be clobbered.
    With `overwrite=True` the destination is atomically replaced, inheriting
    its previous permissions.

    The committed file gets the usual umask-based permissions (not the
    restrictive mode of the internal temp file). The destination's parent
    directory must already exist, unless `make_parents=True`.
    """

    __slots__ = (
        "__weakref__",
        "_committed",
        "_file",
        "_finalizer",
        "_overwrite",
        "_path",
        "_temp_path",
    )

    @overload
    def __init__(
        self: StagedFile[str],
        path: StrPath,
        *,
        overwrite: bool = ...,
        make_parents: bool = ...,
        binary: Literal[False] = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
    ) -> None: ...

    @overload
    def __init__(
        self: StagedFile[bytes],
        path: StrPath,
        *,
        overwrite: bool = ...,
        make_parents: bool = ...,
        binary: Literal[True],
    ) -> None: ...

    def __init__(
        self,
        path: StrPath,
        *,
        overwrite: bool = False,
        make_parents: bool = False,
        binary: bool = False,
        encoding: str | None = None,
        newline: str | None = None,
    ) -> None:
        """Open a staged writer for `path`.

        Args:
            path: The destination file path.
            overwrite: Whether to replace an existing file. When False, an
                existing destination raises immediately. Defaults to False.
            make_parents: Whether to create the destination's parent directory
                if it is missing. Defaults to False.
            binary: Whether to write binary (`bytes`) instead of text (`str`).
                Defaults to False.
            encoding: Text encoding (text mode only); `None` uses the platform
                default, as with `open`. Defaults to None.
            newline: Newline handling (text mode only), as with `open`.
                Defaults to None.

        Raises:
            FileExistsError: If `overwrite` is False and `path` already exists.
            FileNotFoundError: If the parent directory is missing and
                `make_parents` is False.
        """
        path = reserve_path(path, exist_ok=overwrite, make_parents=make_parents)
        fd, name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        self._path = path
        self._overwrite = overwrite
        self._committed = False
        self._temp_path = Path(name)
        raw = (
            os.fdopen(fd, "wb")
            if binary
            else os.fdopen(fd, "w", encoding=encoding, newline=newline)
        )
        self._file = cast("IO[AnyStrT]", raw)
        self._finalizer = weakref.finalize(
            self, _discard, cast("IO[str] | IO[bytes]", self._file), self._temp_path
        )

    @property
    def path(self) -> Path:
        """The destination path the staged content commits to."""
        return self._path

    @property
    def file(self) -> IO[AnyStrT]:
        """The underlying open file object (full file API).

        Use it for methods this class does not proxy (e.g. `writelines`) or to
        pass to file-consuming APIs (`json.dump`, `pickle.dump`, ...). Do not
        close it yourself; `commit` / `abort` manage the lifecycle, and
        committing after an external close raises `ValueError`.
        """
        return self._file

    @property
    def committed(self) -> bool:
        """Whether the staged content has been committed to `path`."""
        return self._committed

    def write(self, data: AnyStrT, /) -> int:
        """Write `data` to the staged file and return the units written."""
        return self._file.write(data)

    def flush(self) -> None:
        """Flush the write buffer to the operating system."""
        self._file.flush()

    def seek(self, offset: int, whence: int = os.SEEK_SET, /) -> int:
        """Move the stream position and return the new absolute position."""
        return self._file.seek(offset, whence)

    def tell(self) -> int:
        """Return the current stream position."""
        return self._file.tell()

    def commit(self) -> Path:
        """Flush, fsync, and atomically move the staged file into `path`.

        Returns the destination path. Idempotent: a second call (or a
        context-manager exit after an explicit commit) returns `path`
        without redoing the work.

        Raises:
            ValueError: If the writer was already aborted, or if `file` was
                closed externally (which would make the commit unsafe).
            IsADirectoryError: If `overwrite` is True and the destination
                exists but is a directory.
            FileExistsError: If `overwrite` is False and the destination
                appeared after this writer opened. The staged file is
                discarded and the existing file is left intact.
        """
        if self._committed:
            return self._path
        if not self._finalizer.alive:
            msg = "cannot commit an aborted writer"
            raise ValueError(msg)
        if self._file.closed:
            msg = "cannot commit: the underlying file was closed externally"
            raise ValueError(msg)
        if self._overwrite and self._path.is_dir():
            msg = f"is a directory: {self._path}"
            raise IsADirectoryError(msg)
        self._file.flush()
        os.fsync(self._file.fileno())
        self._file.close()
        mode = _default_file_mode()
        if self._overwrite:
            # Inherit the replaced file's mode; fall back to the default when
            # the destination does not exist yet.
            with contextlib.suppress(OSError):
                mode = stat.S_IMODE(self._path.stat().st_mode)
        self._temp_path.chmod(mode)
        if self._overwrite:
            self._temp_path.replace(self._path)
        else:
            # Atomic exclusive create via hardlink where supported. A
            # filesystem without hardlinks (FAT/exFAT, some network mounts)
            # raises a non-`FileExistsError` `OSError`; fall back to a
            # best-effort existence check plus `replace` (which leaves a
            # small TOCTOU window where a file appearing meanwhile could be
            # clobbered -- unavoidable without an atomic no-clobber move).
            try:
                self._path.hardlink_to(self._temp_path)
            except OSError as exc:
                if isinstance(exc, FileExistsError) or self._path.exists():
                    self._temp_path.unlink(missing_ok=True)
                    msg = (
                        "file already exists, pass overwrite=True to replace: "
                        f"{self._path}"
                    )
                    raise FileExistsError(msg) from None
                self._temp_path.replace(self._path)
            else:
                self._temp_path.unlink()
        _fsync_parent(self._path)
        self._committed = True
        self._finalizer.detach()
        return self._path

    def abort(self) -> None:
        """Discard the staged file without writing to `path`.

        Idempotent, and a no-op once committed.
        """
        if self._committed:
            return
        self._finalizer()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.abort()
        elif self._finalizer.alive:
            self.commit()


class StagedDirectory:
    """Build a directory safely: populate a temp dir, then commit by atomic move.

    Files are written into a temporary directory (`workdir`) in the
    destination's own parent, which is moved into place only on `commit`, so
    a reader never observes a partially-built directory and a failed build
    leaves any existing directory untouched.

    Usable as a context manager -- committing on a clean exit and discarding
    on an exception -- or explicitly:

    Example:
        ```python
        with StagedDirectory("out/dataset", make_parents=True) as d:
            (d.workdir / "train.json").write_text(payload)
            (d.workdir / "shards").mkdir()
        # out/dataset now appears in one step

        d = StagedDirectory("out/dataset", overwrite=True)
        (d.workdir / "x.bin").write_bytes(blob)
        d.commit()
        ```

    Creating a new directory (`overwrite=False`, the default) is atomic: the
    staged directory is moved into place with a single rename, and an existing
    destination is a fail-fast `FileExistsError`. Replacing an existing one
    (`overwrite=True`) is *not* fully atomic -- the old directory is swapped
    aside, the staged one moved in, then the old removed. A failed move
    restores the original; only a crash *between* the two renames leaves the
    previous contents in a sibling ``<name>.old`` directory for recovery.

    Durability note: `commit` makes the directory's *appearance* durable (it
    fsyncs the parent directory entry), but the files you write into `workdir`
    are not individually fsynced -- their contents may still be buffered when
    `commit` returns. If they must survive a crash immediately after commit,
    fsync them yourself (for example, write each via `StagedFile` inside
    `workdir`). Atomicity for concurrent readers always holds regardless.

    The committed directory gets the usual umask-based permissions. Pass
    `make_parents=True` to create the destination's parent if it is missing.
    An uncommitted instance discards its staging directory on garbage
    collection.
    """

    __slots__ = (
        "__weakref__",
        "_committed",
        "_finalizer",
        "_overwrite",
        "_path",
        "_workdir",
    )

    def __init__(
        self,
        path: StrPath,
        *,
        overwrite: bool = False,
        make_parents: bool = False,
    ) -> None:
        """Open a staged directory builder for `path`.

        Args:
            path: The destination directory path.
            overwrite: Whether to replace an existing directory. When False, an
                existing destination raises immediately. Defaults to False.
            make_parents: Whether to create the destination's parent directory
                if it is missing. Defaults to False.

        Raises:
            FileExistsError: If `overwrite` is False and `path` already exists.
            FileNotFoundError: If the parent directory is missing and
                `make_parents` is False.
        """
        path = reserve_path(path, exist_ok=overwrite, make_parents=make_parents)
        self._path = path
        self._overwrite = overwrite
        self._committed = False
        self._workdir = Path(
            tempfile.mkdtemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        )
        self._finalizer = weakref.finalize(self, _discard_dir, self._workdir)

    @property
    def path(self) -> Path:
        """The destination path the staged directory commits to."""
        return self._path

    @property
    def workdir(self) -> Path:
        """The staging directory to populate before commit."""
        return self._workdir

    @property
    def committed(self) -> bool:
        """Whether the staging directory has been committed to `path`."""
        return self._committed

    def commit(self) -> Path:
        """Atomically move the staged directory into `path`.

        Returns the destination path. Idempotent: a second call (or a
        context-manager exit after an explicit commit) returns `path`
        without redoing the work.

        Raises:
            ValueError: If the builder was already aborted.
            FileExistsError: If `overwrite` is False and the destination
                appeared after this builder opened.
            NotADirectoryError: If `overwrite` is True and the destination
                exists but is not a directory.
            OSError: If replacing an existing directory and moving the staged
                one into place fails; the original is restored first.
        """
        if self._committed:
            return self._path
        if not self._finalizer.alive:
            msg = "cannot commit an aborted staged directory"
            raise ValueError(msg)
        exists = self._path.exists()
        if exists:
            if not self._overwrite:
                msg = (
                    "directory already exists, pass overwrite=True to replace: "
                    f"{self._path}"
                )
                raise FileExistsError(msg)
            if not self._path.is_dir():
                msg = f"not a directory: {self._path}"
                raise NotADirectoryError(msg)
        mode = _default_dir_mode()
        if self._overwrite:
            # Inherit the replaced directory's mode; fall back to the default
            # when the destination does not exist yet.
            with contextlib.suppress(OSError):
                mode = stat.S_IMODE(self._path.stat().st_mode)
        self._workdir.chmod(mode)
        if exists:
            # Replacing an existing directory. There is no portable atomic
            # directory replace, so swap the old one aside, move the staged one
            # in, then remove the old. If the second move fails, restore the
            # original; removing the backup is best-effort (the destination is
            # already correct). A crash *between* the two moves is the residual
            # non-atomic window -- the previous contents remain in a sibling
            # `<name>.old` directory for manual recovery.
            backup = self._path.with_name(f"{self._workdir.name}.old")
            self._path.rename(backup)
            try:
                self._workdir.rename(self._path)
            except OSError:
                backup.rename(self._path)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        else:
            self._workdir.rename(self._path)
        _fsync_parent(self._path)
        self._committed = True
        self._finalizer.detach()
        return self._path

    def abort(self) -> None:
        """Discard the staging directory without creating `path`.

        Idempotent, and a no-op once committed.
        """
        if self._committed:
            return
        self._finalizer()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            self.abort()
        elif self._finalizer.alive:
            self.commit()
