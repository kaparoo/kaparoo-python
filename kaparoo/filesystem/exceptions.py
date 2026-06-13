from __future__ import annotations

__all__ = ("DirectoryNotFoundError", "NotAFileError")


class DirectoryNotFoundError(FileNotFoundError):
    """Raised when a directory does not exist.

    Note:
        Since this inherits from `FileNotFoundError`, catch it before
        `FileNotFoundError` in any combined `except` block.
    """


class NotAFileError(OSError):
    """Raised when a path exists but is not a file."""
