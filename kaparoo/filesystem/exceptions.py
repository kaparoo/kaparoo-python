"""Filesystem exception types (`NotAFileError`, `UnsupportedExtensionError`, ...)."""

from __future__ import annotations

__all__ = (
    "DirectoryNotFoundError",
    "NotAFileError",
    "UnsupportedExtensionError",
)

from typing import TYPE_CHECKING

from kaparoo.filesystem.utils import normalize_extension, normalize_extensions

if TYPE_CHECKING:
    from collections.abc import Iterable


class DirectoryNotFoundError(FileNotFoundError):
    """Raised when a directory does not exist.

    Note:
        Since this inherits from `FileNotFoundError`, catch it before
        `FileNotFoundError` in any combined `except` block.
    """


class NotAFileError(OSError):
    """Raised when a path exists but is not a file."""


class UnsupportedExtensionError(ValueError):
    """Raised when a path's extension is none of the expected ones.

    A `ValueError` subclass, so an existing `except ValueError` still catches
    it. `expected` is normalized (`normalize_extensions`), de-duplicated, and
    stripped of empties; an optional `kind` (e.g. `"phase"`) labels the message.
    """

    def __init__(self, ext: str, expected: Iterable[str], kind: str = "") -> None:
        expected = tuple(dict.fromkeys(e for e in normalize_extensions(expected) if e))
        if not expected:
            msg = "expected must list at least one extension"
            raise ValueError(msg)
        self.ext = normalize_extension(ext)
        self.expected = expected
        self.kind = kind
        label = f"{kind} extension" if kind else "extension"
        super().__init__(
            f"unsupported {label} {self.ext!r} (expected one of {', '.join(expected)})"
        )
