from __future__ import annotations

__all__ = ("AtomicWriter",)

import contextlib
import os
import stat
import tempfile
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, cast, overload

if TYPE_CHECKING:
    from types import TracebackType
    from typing import IO, Literal, Self

    from kaparoo.filesystem.types import StrPath


def _discard(file: IO[str] | IO[bytes], temp_path: Path) -> None:
    """Close `file` and remove the staged temp file (the abort path).

    Lives at module level (not bound to the instance) so the
    `weakref.finalize` registration does not keep the `AtomicWriter` alive.
    """
    file.close()  # idempotent
    temp_path.unlink(missing_ok=True)


def _default_file_mode() -> int:
    """Return the mode new files would get (`0o666` minus the current umask)."""
    # Reading the umask requires setting it; restore it immediately. This
    # briefly mutates process-global state and so is not thread-safe.
    mask = os.umask(0)
    os.umask(mask)
    return 0o666 & ~mask


class AtomicWriter[AnyStrT: (str, bytes)]:
    """Write a file safely: stage to a temp file, then commit by atomic move.

    Content is written to a temporary file in the destination's own directory
    and moved into place only on `commit`, so a reader never observes a
    half-written file and a failed write leaves any existing file untouched.

    The default is binary (`AtomicWriter[bytes]`); pass `text=True` for a text
    writer (`AtomicWriter[str]`) with optional `encoding` / `newline`. The
    type parameter follows the mode, so `write` and `file` are typed `bytes`
    or `str` accordingly.

    Usable as a context manager -- committing on a clean exit and discarding
    on an exception -- or explicitly, like a file object:

    Example:
        ```python
        # Binary, as a context manager: commit on success, discard on error.
        with AtomicWriter("out/data.bin") as f:
            f.write(payload)  # an exception here leaves out/ untouched

        # Text, explicitly: write, then commit (or abort to discard).
        f = AtomicWriter("out/report.json", text=True, encoding="utf-8")
        f.write(json.dumps(data))
        f.commit()
        ```

    With `overwrite=False` (the default) an existing destination is a
    fail-fast `FileExistsError`, and the commit creates the file atomically --
    it never clobbers a file that appeared meanwhile. With `overwrite=True`
    the destination is atomically replaced, inheriting its previous
    permissions.

    The committed file gets the usual umask-based permissions (not the
    restrictive mode of the internal temp file). The destination's parent
    directory must already exist.
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
        self: AtomicWriter[bytes],
        path: StrPath,
        *,
        overwrite: bool = ...,
        text: Literal[False] = ...,
    ) -> None: ...

    @overload
    def __init__(
        self: AtomicWriter[str],
        path: StrPath,
        *,
        overwrite: bool = ...,
        text: Literal[True],
        encoding: str | None = ...,
        newline: str | None = ...,
    ) -> None: ...

    def __init__(
        self,
        path: StrPath,
        *,
        overwrite: bool = False,
        text: bool = False,
        encoding: str | None = None,
        newline: str | None = None,
    ) -> None:
        """Open a staged writer for `path`.

        Args:
            path: The destination file path.
            overwrite: Whether to replace an existing file. When False, an
                existing destination raises immediately. Defaults to False.
            text: Whether to write text (`str`) instead of binary (`bytes`).
                Defaults to False.
            encoding: Text encoding (text mode only); `None` uses the platform
                default, as with `open`. Defaults to None.
            newline: Newline handling (text mode only), as with `open`.
                Defaults to None.

        Raises:
            FileExistsError: If `overwrite` is False and `path` already exists.
            FileNotFoundError: If the destination's parent directory is missing.
        """
        path = Path(path)
        if not overwrite and path.exists():
            msg = f"file already exists, pass overwrite=True to replace: {path}"
            raise FileExistsError(msg)
        fd, name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        self._path = path
        self._overwrite = overwrite
        self._committed = False
        self._temp_path = Path(name)
        raw = (
            os.fdopen(fd, "w", encoding=encoding, newline=newline)
            if text
            else os.fdopen(fd, "wb")
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
        """The underlying open file object (full file API)."""
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
            ValueError: If the writer was already aborted.
            FileExistsError: If `overwrite` is False and the destination
                appeared after this writer opened. The staged file is
                discarded and the existing file is left intact.
        """
        if self._committed:
            return self._path
        if not self._finalizer.alive:
            msg = "cannot commit an aborted writer"
            raise ValueError(msg)
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
            try:
                self._path.hardlink_to(self._temp_path)
            except FileExistsError:
                msg = (
                    f"file already exists, pass overwrite=True to replace: {self._path}"
                )
                raise FileExistsError(msg) from None
            finally:
                self._temp_path.unlink(missing_ok=True)
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
