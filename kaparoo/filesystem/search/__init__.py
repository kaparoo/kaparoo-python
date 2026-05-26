from __future__ import annotations

__all__ = (
    "get_dirs",
    "get_files",
    "get_paths",
    "search_dirs",
    "search_files",
    "search_paths",
)

from kaparoo.filesystem.search.deprecated import (
    get_dirs,
    get_files,
    get_paths,
)
from kaparoo.filesystem.search.wrappers import (
    search_dirs,
    search_files,
    search_paths,
)
