"""Filesystem exception types (`NotAFileError`, `UnsupportedExtensionError`, ...)."""

from __future__ import annotations

__all__ = (
    "DirectoryNotFoundError",
    "NotAFileError",
    "UnsupportedExtensionError",
)

from typing import TYPE_CHECKING

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
    """Raised when an extension is none of the supported ones.

    A `ValueError` subclass, so existing `except ValueError` handlers still
    catch it. `ext` and each entry of `supported` are normalized alike --
    surrounding whitespace and leading dots are stripped, with case preserved
    -- after which `supported` is de-duplicated and empty entries are dropped
    (so `".jpg"`, `"jpg "`, and `"jpg"` collapse to a single `"jpg"`). The
    optional `kind` (whitespace-stripped) names what the extension is for and,
    when given, is woven into the message as `for <kind>`.

    Raises:
        ValueError: If `supported` names no usable extension -- empty, or
            every entry normalizes to "".
    """

    def __init__(self, ext: str, supported: Iterable[str], kind: str = "") -> None:
        def normalize(ext: str) -> str:
            return ext.strip().lstrip(".")

        supported = (normalize(ext) for ext in supported)
        supported = tuple(dict.fromkeys(ext for ext in supported if ext))
        if not supported:
            msg = "supported must list at least one extension"
            raise ValueError(msg)

        self.ext = normalize(ext)
        self.supported = supported
        self.kind = kind.strip()

        msg = f"unsupported extension {self.ext!r}"

        if self.kind:
            msg += f" for {self.kind}"

        msg += f" (supported: {', '.join(repr(ext) for ext in self.supported)})"

        super().__init__(msg)
