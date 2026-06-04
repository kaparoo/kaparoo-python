from __future__ import annotations

__all__ = (
    "ensure_file_extension",
    "reserve_path",
    "reserve_paths",
    "stringify_path",
    "stringify_paths",
    "wrap_path",
    "wrap_paths",
)

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


def _stringify_path(
    path: StrPath,
    after: StrPath | None,
    tail: tuple[str, ...],
    *,
    is_windows: bool,
) -> str:
    """Core of `stringify_path` taking pre-computed loop-invariant inputs."""
    if after is not None or tail:
        path = Path(path)
        if after is not None:
            path = path.relative_to(after)  # raise ValueError if not possible
        if tail:
            if path.parts[-len(tail) :] != tail:
                msg = f"path {path} does not end with {Path(*tail)}"
                raise ValueError(msg)
            path = Path(*path.parts[: -len(tail)])
    text = os.fspath(path)
    if is_windows:
        text = text.replace("\\", "/")
    return text


def stringify_path(
    path: StrPath, after: StrPath | None = None, before: StrPath | None = None
) -> str:
    r"""Convert a path to a string and optionally trim shared head/tail parts.

    Args:
        path: The path to be converted to a string. In Windows platform,
            all "\\" will be replaced with "/".
        after: The leading base path to make `path` relative to. If provided,
            returns only the part of `path` after `after`. Defaults to None.
        before: The trailing path to trim from `path`. If provided, returns
            only the part of `path` before `before`. Defaults to None.

    Returns:
        The string representation of the `path`.

    Raises:
        ValueError: If `path` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    is_windows = platform.system() == "Windows"
    return _stringify_path(path, after, tail, is_windows=is_windows)


def stringify_paths(
    paths: StrPaths, after: StrPath | None = None, before: StrPath | None = None
) -> Sequence[str]:
    r"""Convert a sequence of paths to strings and optionally trim shared parts.

    Args:
        paths: The sequence of paths to be converted to strings.
            In Windows platform, all "\\" will be replaced with "/".
        after: The leading base path to make each path relative to. If provided,
            returns only the part of each path after `after`. Defaults to None.
        before: The trailing path to trim from each path. If provided, returns
            only the part of each path before `before`. Defaults to None.

    Returns:
        The sequence of string representations of the `paths`.

    Raises:
        ValueError: If any of `paths` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    is_windows = platform.system() == "Windows"
    return [_stringify_path(path, after, tail, is_windows=is_windows) for path in paths]


@overload
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[False] = False,
) -> Path: ...


@overload
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[True],
) -> str: ...


@overload
def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool,
) -> Path | str: ...


def wrap_path(
    path: StrPath,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool = False,
) -> Path | str:
    """Wrap a path with an optional leading and/or trailing path.

    Args:
        path: The path to wrap.
        prepend: A path to attach in front of `path`. Defaults to None.
        append: A relative path to attach after `path`. Defaults to None.
        stringify: Whether to return the result as a string. Defaults to False.

    Returns:
        A Path object or a string, depending on the value of `stringify`.

    Raises:
        ValueError: If `prepend` is given and `path` is an absolute path.
        ValueError: If `append` is given and is an absolute path.
    """
    if prepend is not None and os.path.isabs(path):  # noqa: PTH117
        msg = f"cannot prepend to absolute path: {path}"
        raise ValueError(msg)
    if append is not None and os.path.isabs(append):  # noqa: PTH117
        msg = f"cannot append an absolute path: {append}"
        raise ValueError(msg)
    result = Path(path) if prepend is None else Path(prepend, path)
    if append is not None:
        result = result / append
    return stringify_path(result) if stringify else result


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Wrap a sequence of paths with an optional leading and/or trailing path.

    Args:
        paths: The sequence of paths to wrap.
        prepend: A path to attach in front of each path. Defaults to None.
        append: A relative path to attach after each path. Defaults to None.
        stringify: Whether to return the results as strings. Defaults to False.

    Returns:
        A sequence of Path objects or strings, depending on the value of
            `stringify`.

    Raises:
        ValueError: If `prepend` is given and any path is an absolute path.
        ValueError: If `append` is given and is an absolute path.
    """
    paths = [wrap_path(path, prepend=prepend, append=append) for path in paths]
    return stringify_paths(paths) if stringify else paths


@overload
def reserve_path(
    path: StrPath,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: Literal[False] = False,
) -> Path: ...


@overload
def reserve_path(
    path: StrPath,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: Literal[True],
) -> str: ...


@overload
def reserve_path(
    path: StrPath,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool,
) -> Path | str: ...


def reserve_path(
    path: StrPath,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool = False,
) -> Path | str:
    """Reserve a path for creation: assert it is free, and return it.

    Guards a destination before something is created there. The target is
    never created or deleted -- only checked, and (with `make_parents`)
    given an existing parent directory -- so the caller goes on to create
    the target itself.

    `exist_ok` mirrors `make_dir` / `Path.mkdir`: when True an existing path
    is returned instead of raising, but nothing is removed, so a later write
    still overwrites the target on its own. For a directory destination,
    prefer `make_dir(..., exist_ok=...)`, which both guards and creates; for
    an exclusive file create, `open(path, "x")` raises the same
    `FileExistsError` directly.

    A symlink counts as occupying the path -- including a *broken* one,
    which `Path.exists` alone reports as absent yet still takes the name
    (so `open(path, "x")` would fail). Such a path is treated as existing.

    Args:
        path: The path that should not yet exist.
        exist_ok: Whether to allow an already-existing path. Defaults to False.
        make_parents: Whether to create the parent directory (with
            `parents=True`) if it is missing. Defaults to False.
        stringify: Whether to return the path as a string. Defaults to False.

    Returns:
        The path as a Path object or a string, depending on `stringify`.

    Raises:
        FileExistsError: If the path exists (or is a symlink) and `exist_ok`
            is False.
        OSError: If `make_parents` is True and the parent cannot be created
            (e.g. an ancestor along the path is a file).
    """
    path = Path(path)
    if (path.exists() or path.is_symlink()) and not exist_ok:
        msg = f"path already exists: {path}"
        raise FileExistsError(msg)
    if make_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    return stringify_path(path) if stringify else path


@overload
def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: Literal[False] = False,
) -> Sequence[Path]: ...


@overload
def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: Literal[True],
) -> Sequence[str]: ...


@overload
def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool,
) -> Sequence[Path] | Sequence[str]: ...


def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool = False,
) -> Sequence[Path] | Sequence[str]:
    """Reserve multiple paths for creation; the bulk form of `reserve_path`.

    Each path is checked with the same `exist_ok` / `make_parents` policy.
    The check is fail-fast: the first existing path raises and any
    `make_parents` side effects from earlier paths are left in place (no
    rollback), matching `make_dirs`. To resolve entries against a shared
    base directory, compose with `wrap_paths(paths, prepend=root)` first.

    Args:
        paths: The paths that should not yet exist.
        exist_ok: Whether to allow already-existing paths. Defaults to False.
        make_parents: Whether to create each path's parent directory if it is
            missing. Defaults to False.
        stringify: Whether to return the paths as strings. Defaults to False.

    Returns:
        The paths as Path objects or strings, depending on `stringify`.

    Raises:
        FileExistsError: If any path exists and `exist_ok` is False.
    """
    paths = [
        reserve_path(p, exist_ok=exist_ok, make_parents=make_parents) for p in paths
    ]
    return stringify_paths(paths) if stringify else paths


def ensure_file_extension(
    path: StrPath, ext: str | Iterable[str], *, add: bool = False
) -> Path:
    """Return `path` as a `Path`, requiring a case-insensitive `.<ext>` suffix.

    A pure path check that never touches the filesystem. `ext` is a single
    extension or an iterable of acceptable ones (e.g. `("jpg", "jpeg")`); the
    leading dot on each is optional, so `"bin"` and `".bin"` behave the same.
    Only the final suffix is considered: `archive.tar.gz` matches `ext="gz"`,
    not `ext="tar.gz"`.

    `add` mirrors `make` on `ensure_dir_exists`: when False (the default) a
    path with no suffix raises like any other mismatch; when True, the missing
    suffix is appended -- the *first* of `ext` when several are given, so pass
    an ordered list/tuple if that matters. A *wrong* suffix always raises,
    regardless of `add`.

    Args:
        path: The path to check.
        ext: The required extension, or an iterable of acceptable ones, each
            with or without a leading dot.
        add: Whether to append the (first) extension when `path` has no
            suffix, instead of raising. Defaults to False.

    Returns:
        The path as a Path object, guaranteed to end in an accepted `.<ext>`.

    Raises:
        ValueError: If `ext` is empty, or `path`'s final suffix is none of the
            accepted extensions -- except the no-suffix case resolved by
            `add=True`.
    """
    exts = [ext] if isinstance(ext, str) else list(ext)
    exts = [e.removeprefix(".") for e in exts]

    if not exts:
        msg = "ext must name at least one extension"
        raise ValueError(msg)

    path = Path(path)
    if add and not path.suffix:
        return path.with_suffix(f".{exts[0]}")

    if path.suffix.lower() not in {f".{e.lower()}" for e in exts}:
        wanted = " / ".join(f".{e}" for e in exts)
        msg = f"{path.name} must have a {wanted} extension (got {path.suffix!r})"
        raise ValueError(msg)

    return path
