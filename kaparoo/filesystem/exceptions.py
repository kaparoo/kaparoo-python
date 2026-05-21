from __future__ import annotations

__all__ = ("DirectoryNotFoundError", "NotAFileError")


class DirectoryNotFoundError(FileNotFoundError):
    """Exception to raise when a directory does not exist.

    Note:
        Since this exception inherits from `FileNotFoundError`,
        it should be handled before handling `FileNotFoundError`
        in the exception handling block.
    """


class NotAFileError(OSError):
    """Exception to raise when a path exists but is not a file."""
