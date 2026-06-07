from __future__ import annotations

__all__ = ("FileFolderSequence", "FileListSequence", "SingleFileSequence")

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from kaparoo.data.sequences.base import DataSequence
from kaparoo.filesystem.existence import ensure_dir_exists, ensure_file_exists
from kaparoo.filesystem.utils import stringify_paths, wrap_path

if TYPE_CHECKING:
    from kaparoo.filesystem.types import StrPath, StrPaths


class FileListSequence[T, M = Path](DataSequence[T, M]):
    """A `DataSequence` over an explicit, ordered list of files.

    One item per file; subclasses implement `load_file` (decode a file) and
    `get_meta`. Files are given directly rather than discovered under a root,
    so they may live in unrelated directories (or, on Windows, different
    drives) -- `FileFolderSequence` is the rooted special case. Order is
    preserved and duplicates kept; paths are not checked for existence until
    `load_file` runs lazily on `get_item`. `M` defaults to `Path` (the source
    path); override it for other metadata.

    Example:
        >>> class BytesList(FileListSequence[bytes]):
        ...     def get_meta(self, index: int) -> Path:
        ...         return self.get_file(index)
        ...
        ...     def load_file(self, path: Path) -> bytes:
        ...         return path.read_bytes()
        >>> data = BytesList(["images/a.png", "/other/b.png"])
    """

    def __init__(self, files: StrPaths) -> None:
        self._files = list(stringify_paths(files))
        self._files_cache: tuple[Path, ...] | None = None

    def __len__(self) -> int:
        return len(self._files)

    @property
    def files(self) -> tuple[Path, ...]:
        """Immutable snapshot of the full file paths, in order.

        Built once and cached (the paths are immutable), so repeated access
        returns the same tuple without rebuilding it.
        """
        if self._files_cache is None:
            self._files_cache = tuple(self.get_file(i) for i in range(len(self)))
        return self._files_cache

    def get_file(self, index: int) -> Path:
        """Full Path of the file at `index`."""
        return Path(self._files[index])

    def get_item(self, index: int) -> T:
        return self.load_file(self.get_file(index))

    @abstractmethod
    def get_meta(self, index: int) -> M:
        raise NotImplementedError

    @abstractmethod
    def load_file(self, path: Path) -> T:
        """Decode a single file into an item of type `T`.

        Called lazily on each `get_item` -- not at construction time.
        Subclasses may freely use external libraries (PIL, librosa,
        cv2, ...) to decode.
        """
        raise NotImplementedError


class FileFolderSequence[T, M = Path](FileListSequence[T, M]):
    """A `FileListSequence` whose file list is discovered under one `root`.

    `list_files(root)` returns the files; they are validated to be under
    `root` and stored root-relative, so memory stays low for large datasets
    and the list survives a `root` move (`get_file` re-prepends it).
    Subclasses implement `list_files` and `load_file` (and `get_meta`, which
    can be `return self.get_file(i)` when the metadata is the path).

    Parameterized subclasses:
        `__init__` calls `self.list_files(root)`, so set any state
        `list_files` reads (a `pattern`, a `recursive` flag, ...) on `self`
        **before** `super().__init__(root)`. State `list_files` does not read
        can be set after, as usual.

    Raises:
        DirectoryNotFoundError: If `root` does not exist.
        NotADirectoryError: If `root` is not a directory.
        ValueError: If `list_files` returns a path not under `root`.

    Example:
        >>> class GlobFolder(FileFolderSequence[bytes]):
        ...     def __init__(self, root, *, pattern="*", recursive=False) -> None:
        ...         self._pattern, self._recursive = pattern, recursive  # before super
        ...         super().__init__(root)
        ...
        ...     def list_files(self, root: Path) -> list[Path]:
        ...         glob = root.rglob if self._recursive else root.glob
        ...         return sorted(p for p in glob(self._pattern) if p.is_file())
        ...
        ...     def get_meta(self, index: int) -> Path:
        ...         return self.get_file(index)
        ...
        ...     def load_file(self, path: Path) -> bytes:
        ...         return path.read_bytes()
        >>> folder = GlobFolder("data", pattern="*.png", recursive=True)
    """

    def __init__(self, root: StrPath) -> None:
        self._root = ensure_dir_exists(root)
        # `after=root` makes each path root-relative and raises ValueError if
        # any file is not under `root`. The base then stores the relative
        # form; `get_file` re-prepends `root`.
        super().__init__(stringify_paths(self.list_files(self._root), after=self._root))

    @property
    def root(self) -> Path:
        """The base directory the sequence was constructed from."""
        return self._root

    def get_file(self, index: int) -> Path:
        """Full Path of the file at `index`."""
        return wrap_path(self._files[index], prepend=self._root)

    @abstractmethod
    def list_files(self, root: Path) -> list[Path]:
        """Return the full Path of every file to expose, in order.

        Called once from `__init__` after `root` has been validated.
        Every returned path must be under `root`; construction raises
        `ValueError` otherwise. May read instance state set before
        `super().__init__(root)` -- see the class docstring's
        "Parameterized subclasses" note.
        """
        raise NotImplementedError


class SingleFileSequence[T, M = None](DataSequence[T, M]):
    """A `DataSequence` backed by a single file that holds many records.

    The "one file, many records" pattern (a video's frames, a CSV's rows, a
    binary blob's fixed-size records). Indexing strategies vary too widely
    across formats to abstract, so subclasses own opening, indexing, and
    decoding. `__init__` only validates that `path` is an existing regular
    file (exposed as `path`); subclasses usually override it to open or
    pre-scan the file, calling `super().__init__(path)` first.

    Raises:
        FileNotFoundError: If `path` does not exist.
        NotAFileError: If `path` is not a regular file.

    Example:
        >>> class LinesFile(SingleFileSequence[str, int]):
        ...     def __init__(self, path) -> None:
        ...         super().__init__(path)
        ...         self._lines = tuple(self.path.read_text().splitlines())
        ...
        ...     def __len__(self) -> int:
        ...         return len(self._lines)
        ...
        ...     def get_item(self, index: int) -> str:
        ...         return self._lines[index]
        ...
        ...     def get_meta(self, index: int) -> int:
        ...         return index + 1  # 1-based line number
    """

    def __init__(self, path: StrPath) -> None:
        self._path = ensure_file_exists(path)

    @property
    def path(self) -> Path:
        """The wrapped file's path."""
        return self._path
