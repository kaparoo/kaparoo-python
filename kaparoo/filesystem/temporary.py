from __future__ import annotations

__all__ = ("TemporaryFile",)

import os
import tempfile
import weakref
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import IO, Self

    from kaparoo.filesystem.types import StrPath


def _cleanup(file: IO[bytes], path: Path, *, delete: bool) -> None:
    """Close `file` and, when `delete`, remove `path`.

    Lives at module level (not bound to the instance) so the
    `weakref.finalize` registration does not keep the `TemporaryFile` alive.
    """
    file.close()  # idempotent: a no-op when already closed
    if delete:
        path.unlink(missing_ok=True)


class TemporaryFile:
    """A scratch temporary file, usable as a context manager or explicitly.

    On construction a real, named temporary file is created (via
    `tempfile.mkstemp`) and opened for binary read/write. The file is removed
    when it is closed -- on `with`-block exit, an explicit `close()`, or
    garbage collection -- unless `delete=False`, in which case it persists at
    `path` for the caller to keep or move.

    Two usage styles are supported:

    Example:
        ```python
        # As a context manager -- cleaned up on exit:
        with TemporaryFile() as tmp:
            tmp.write(b"scratch")
            tmp.seek(0)
            data = tmp.read()

        # Explicitly, like a file object:
        tmp = TemporaryFile()
        tmp.write(b"scratch")
        tmp.close()  # removes the file
        ```

    The file is opened in binary `w+b` mode; for text, wrap `file` in an
    `io.TextIOWrapper` or encode before writing. While the file is open,
    reopening `path` by name may fail on Windows; write through this object.
    """

    __slots__ = ("__weakref__", "_file", "_finalizer", "_path")

    def __init__(
        self,
        *,
        suffix: str | None = None,
        prefix: str | None = None,
        directory: StrPath | None = None,
        delete: bool = True,
    ) -> None:
        """Create and open a temporary file.

        Args:
            suffix: Trailing portion of the file name (e.g. `".tmp"`).
            prefix: Leading portion of the file name.
            directory: Directory to create the file in. Defaults to the
                platform temporary directory.
            delete: Whether to remove the file on close. Defaults to True.
        """
        fd, name = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=directory)
        self._path = Path(name)
        self._file: IO[bytes] = os.fdopen(fd, "w+b")
        self._finalizer = weakref.finalize(
            self, _cleanup, self._file, self._path, delete=delete
        )

    @property
    def path(self) -> Path:
        """The filesystem path of the temporary file."""
        return self._path

    @property
    def file(self) -> IO[bytes]:
        """The underlying open binary file object (full file API)."""
        return self._file

    @property
    def closed(self) -> bool:
        """Whether the file has been closed (and cleaned up)."""
        return not self._finalizer.alive

    def write(self, data: bytes, /) -> int:
        """Write `data` to the file and return the number of bytes written."""
        return self._file.write(data)

    def read(self, size: int = -1, /) -> bytes:
        """Read up to `size` bytes (all remaining when `size` is negative)."""
        return self._file.read(size)

    def flush(self) -> None:
        """Flush the write buffer to the operating system."""
        self._file.flush()

    def seek(self, offset: int, whence: int = os.SEEK_SET, /) -> int:
        """Move the stream position and return the new absolute position."""
        return self._file.seek(offset, whence)

    def tell(self) -> int:
        """Return the current stream position."""
        return self._file.tell()

    def close(self) -> None:
        """Close the file and remove it, unless created with `delete=False`.

        Idempotent: repeated calls (and a later context-manager exit or
        garbage collection) do nothing.
        """
        self._finalizer()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
