"""Path-aware `select`: `.json` / `.txt` file specs and POSIX subpath normalization.

The filesystem extension of `kaparoo.filters.selection`: it loads a spec from a
`.json` / `.txt` file (the only disk access) and normalizes exact-name subpaths
to POSIX `/`, then delegates the in-memory matching to the base module.
"""

from __future__ import annotations

__all__ = (
    "SPEC_FILE_SUFFIXES",
    "Selector",
    "is_spec_file",
    "resolve_selector",
    "select",
)

import json
import os
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from kaparoo.filters import selection as _base

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Final

    from kaparoo.filesystem.types import StrPath
    from kaparoo.filters import Filter


type Selector = _base.Selector | StrPath

SPEC_FILE_SUFFIXES: Final = (".json", ".txt")


def is_spec_file(source: StrPath) -> bool:
    """Whether `select` reads `source` as a spec file rather than an inline name.

    True when `source`'s suffix is one of `SPEC_FILE_SUFFIXES` (`.json` / `.txt`),
    matched case-insensitively. This is the same test `select` and `resolve_selector`
    apply, so a leading-dot name such as `.json` (which has no suffix) counts as an
    inline name, not a spec file.
    """
    return PurePath(source).suffix.lower() in SPEC_FILE_SUFFIXES


def _posix(subpath: str) -> str:
    """Normalize a subpath's separators to POSIX `/`."""
    return PurePath(subpath).as_posix()


def _read_listing(path: StrPath) -> list[str]:
    """Read subpaths from a `.txt` listing, dropping blanks and `#` comments.

    Everything from the first `#` onward is a comment; the surviving text is
    stripped. A line that is blank or wholly a comment is skipped, so an empty
    or comment-only file yields no entries.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [entry for line in lines if (entry := line.split("#", 1)[0].strip())]


def _load(selector: Selector | None) -> _base.Selector | None:
    """Turn a `.json` / `.txt` file spec into an in-memory spec; pass others through.

    A bare `str` / `PathLike` ending in `.json` or `.txt` is read from disk (a
    `FilterDict` object / array, or a subpath listing); any other bare `str` /
    `PathLike` becomes a single inline subpath string, and a sequence, mapping,
    `Filter`, or `None` passes through unchanged for the base to resolve.

    Raises:
        ValueError: If a `.json` file is neither an object nor an array.
        FileNotFoundError: If a `.json` / `.txt` file does not exist.
    """
    if isinstance(selector, str | os.PathLike):
        text = os.fspath(selector)
        suffix = PurePath(text).suffix.lower()
        if suffix == ".json":
            data = json.loads(Path(text).read_text(encoding="utf-8"))
            if isinstance(data, dict | list):
                return data
            msg = f"filter JSON must be an object or array, got {type(data).__name__}"
            raise ValueError(msg)
        if suffix == ".txt":
            return _read_listing(text)
        return text  # a bare inline subpath, as a plain string

    return selector


def resolve_selector(selector: Selector | None) -> Filter | None:
    """Resolve a selector into a filter, loading a `.json` / `.txt` file spec first.

    The path-aware counterpart of `kaparoo.filters.selection.resolve_selector`:
    a bare string ending in `.json` / `.txt` is read from disk, any other bare
    string is a single inline subpath, and exact-name subpaths are normalized
    to POSIX `/`. `None`, an empty sequence, and a comment-only `.txt` listing
    all resolve to `None`.

    Raises:
        ValueError: If a `FilterDict` is malformed, or a `.json` file is
            neither an object nor an array.
        FileNotFoundError: If a `.json` / `.txt` spec names a missing file.
    """
    return _base.resolve_selector(_load(selector), normalize=_posix)


def select[T](
    items: Iterable[T],
    *,
    key: Callable[[T], str],
    include: Selector | None = None,
    exclude: Selector | None = None,
) -> list[T]:
    """Keep the items `include` matches, then drop the ones `exclude` matches.

    The path-aware counterpart of `kaparoo.filters.selection.select`: `include`
    / `exclude` additionally accept a `.json` / `.txt` file path, and exact-name
    subpaths are normalized to POSIX `/`. Everything else matches the base: the
    exact-name / pattern forms, the `include` then `exclude` order (`exclude`
    wins on overlap), and the typo check on exact names.

    Args:
        items: The items to select from.
        key: The name to match an item by (e.g. its root-relative subpath).
        include: The names / patterns to keep, or `None` for all of them.
        exclude: The names / patterns to drop, applied after `include`.

    Returns:
        The surviving items, in the order `items` gave them.

    Raises:
        ValueError: If an exact-name spec names something no item holds, a
            `FilterDict` is malformed, or a `.json` file is neither an object
            nor an array.
        FileNotFoundError: If a `.json` / `.txt` spec names a missing file.
    """
    return _base.select(
        items,
        key=key,
        include=_load(include),
        exclude=_load(exclude),
        normalize=_posix,
    )
