from __future__ import annotations

__all__ = ("FileFolderSequence", "SingleFileSequence")

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from kaparoo.data.sequence.base import DataSequence
from kaparoo.filesystem.existence import ensure_dir_exists, ensure_file_exists
from kaparoo.filesystem.utils import stringify_paths, wrap_path

if TYPE_CHECKING:
    from kaparoo.filesystem.types import StrPath


class FileFolderSequence[T, M = Path](DataSequence[T, M]):
    """A folder-rooted `DataSequence` whose items live in individual files.

    The base class handles file discovery, indexing, and root-relative
    path bookkeeping. Subclasses are responsible for three things:

    - **`list_files(self, root)`** (abstract): return the full `Path`
      of every file to expose, in the desired order. Called once from
      `__init__` after `root` has been validated. Every returned path
      must be under `root`; otherwise construction raises `ValueError`.
      Subclasses can read instance state to parameterize the listing
      (see "Parameterized subclasses" below).
    - **`load_file(self, path)`** (abstract): decode a single file.
      Called lazily on each `get_item`, never at construction time.
    - **`get_meta(self, index)`** (abstract): produce per-item
      metadata. When the metadata IS the source path, `M` defaults
      to `Path` and `get_meta(i)` can be the one-liner
      `return self.get_file(i)`.

    The base exposes:

    - `root: Path` — the base directory.
    - `files: tuple[Path, ...]` — full paths as an immutable snapshot.
    - `get_file(index) -> Path` — full path of the i-th file.

    Paths are kept internally in their root-relative form so that
    memory stays low for large datasets and the sequence survives
    `root` relocations; the conversion is transparent to subclasses
    and external callers.

    Parameterized subclasses:
        When a subclass needs instance-level options (e.g. `pattern`,
        `recursive`, label maps), set them on `self` **before** calling
        `super().__init__(root)` -- the base class invokes
        `self.list_files(root)` from its own `__init__`, so any state
        `list_files` will read must already be in place. State that
        `list_files` does *not* read (caches, label tables, ...) can
        be set after `super().__init__(root)` as usual.

    Type Parameters:
        T: Item type returned by `get_item`.
        M: Per-item metadata type. Defaults to `Path`; override when
            the metadata is something else (label, line number, ...).

    Args:
        root: The base directory. Must exist and be a directory.

    Raises:
        DirectoryNotFoundError: If `root` does not exist.
        NotADirectoryError: If `root` exists but is not a directory.
        ValueError: If any path returned by `list_files` is not under
            `root`.

    Example:
        >>> from pathlib import Path
        >>> class GlobFolder(FileFolderSequence[bytes]):
        ...     def __init__(
        ...         self, root, *, pattern: str = "*", recursive: bool = False
        ...     ) -> None:
        ...         # Set state BEFORE super().__init__() so list_files
        ...         # can read it.
        ...         self._pattern = pattern
        ...         self._recursive = recursive
        ...         super().__init__(root)
        ...
        ...     def list_files(self, root: Path) -> list[Path]:
        ...         glob_fn = root.rglob if self._recursive else root.glob
        ...         return sorted(p for p in glob_fn(self._pattern) if p.is_file())
        ...
        ...     def get_meta(self, index: int) -> Path:
        ...         return self.get_file(index)
        ...
        ...     def load_file(self, path: Path) -> bytes:
        ...         return path.read_bytes()
        >>>
        >>> folder = GlobFolder("data", pattern="*.png", recursive=True)
    """

    def __init__(self, root: StrPath) -> None:
        self._root = ensure_dir_exists(root)
        self._files: list[str] = list(
            stringify_paths(self.list_files(self._root), after=self._root)
        )

    def __len__(self) -> int:
        return len(self._files)

    @property
    def root(self) -> Path:
        """The base directory the sequence was constructed from."""
        return self._root

    @property
    def files(self) -> tuple[Path, ...]:
        """Immutable snapshot of the full file paths this sequence exposes.

        Returns a fresh `tuple[Path, ...]` on each access, in the order
        established by `list_files`.
        """
        return tuple(self.get_file(i) for i in range(len(self)))

    def get_file(self, index: int) -> Path:
        """Full Path of the file at `index`."""
        return wrap_path(self._files[index], prepend=self._root)

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
    """A `DataSequence` backed by a single file that holds multiple records.

    Thin abstract base for the "one file, many records" pattern
    (a video file with many frames; a CSV with many rows; a binary
    blob with fixed-size records; ...). Indexing strategies vary too
    widely across formats to abstract here -- subclasses are
    responsible for opening, indexing, and decoding the file.

    `__init__` validates that `path` exists and is a regular file and
    makes it available via the `path` property. Subclasses typically
    override `__init__` to additionally open or pre-scan the file,
    calling `super().__init__(path)` first.

    Args:
        path: The file to read. Must exist and be a regular file.

    Raises:
        FileNotFoundError: If `path` does not exist.
        NotAFileError: If `path` exists but is not a regular file.

    Example:
        >>> from pathlib import Path
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
