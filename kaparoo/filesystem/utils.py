"""Path-string helpers: stringify, wrap, reserve, and extension checks."""

from __future__ import annotations

__all__ = (
    "ensure_file_extension",
    "file_extension",
    "normalize_extension",
    "normalize_extensions",
    "reserve_path",
    "reserve_paths",
    "stringify_path",
    "stringify_paths",
    "wrap_path",
    "wrap_paths",
)

from pathlib import Path
from typing import TYPE_CHECKING, overload

from kaparoo.filesystem.exceptions import UnsupportedExtensionError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Literal

    from kaparoo.filesystem.types import StrPath, StrPaths


# ========================== #
#         Stringify          #
# ========================== #


def _stringify_path(
    path: StrPath,
    after: StrPath | None,
    tail: tuple[str, ...],
) -> str:
    """Core of `stringify_path` taking pre-computed loop-invariant inputs."""
    path_ = Path(path)

    if after is not None:
        try:
            path_ = path_.relative_to(after)
        except ValueError as error:
            msg = f"path {path!r} does not start with {after!r}"
            raise ValueError(msg) from error

    if tail:
        if path_.parts[-len(tail) :] != tail:
            msg = f"path {path!r} does not end with {Path(*tail)}"
            raise ValueError(msg)
        path_ = Path(*path_.parts[: -len(tail)])

    return path_.as_posix()


def stringify_path(
    path: StrPath, after: StrPath | None = None, before: StrPath | None = None
) -> str:
    """Convert a path to a string and optionally trim shared head/tail parts.

    Args:
        path: The path to be converted to a string.
        after: The leading base path to make `path` relative to. If provided,
            returns only the part of `path` after `after`. Defaults to None.
        before: The trailing path to trim from `path`. If provided, returns
            only the part of `path` before `before`. Defaults to None.

    Returns:
        A POSIX-form string (`/` separators on every platform); `"."` when
        nothing remains after trimming.

    Raises:
        ValueError: If `path` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    return _stringify_path(path, after, tail)


def stringify_paths(
    paths: StrPaths, after: StrPath | None = None, before: StrPath | None = None
) -> list[str]:
    """Convert a sequence of paths to strings and optionally trim shared parts.

    Args:
        paths: The sequence of paths to be converted to strings.
        after: The leading base path to make each path relative to. If provided,
            returns only the part of each path after `after`. Defaults to None.
        before: The trailing path to trim from each path. If provided, returns
            only the part of each path before `before`. Defaults to None.

    Returns:
        A sequence of POSIX-form strings (`/` separators on every platform);
        `"."` when nothing remains after trimming.

    Raises:
        ValueError: If any of `paths` does not start with `after`,
            or does not end with `before`.
    """
    tail = Path(before).parts if before is not None else ()
    return [_stringify_path(path, after, tail) for path in paths]


# ========================== #
#            Wrap            #
# ========================== #


def _is_anchored(path: StrPath) -> bool:
    """Whether `path` carries a drive and/or root, so joining it discards a prefix.

    A purely relative path has an empty `Path.anchor`; an absolute path
    (`/foo`, `C:/foo`) or a Windows drive-relative path (`C:foo`) does not.
    Such a path silently overrides the left-hand side when joined --
    `Path("base", "C:foo")` is just `Path("C:foo")` -- so `wrap_path` rejects
    it rather than dropping the `prepend` / `append`. `Path.anchor` is
    platform-aware, so `C:foo` is drive-relative on Windows but an ordinary
    relative name on POSIX (where `os.path.isabs` and this both report it
    relative).
    """
    return Path(path).anchor != ""


def _ensure_appendable(append: StrPath | None) -> None:
    """Reject an `append` that is absolute or drive-relative.

    Loop-invariant across a `wrap_paths` batch (`append` is shared), so both
    entry points run it once, outside the per-path work.

    Raises:
        ValueError: If `append` is given and is absolute or drive-relative.
    """
    if append is not None and _is_anchored(append):
        msg = f"cannot append an absolute or drive-relative path: {append}"
        raise ValueError(msg)


def _wrap_path(path: StrPath, prepend: StrPath | None, append: StrPath | None) -> Path:
    """Attach `prepend` / `append` to one `path` (the shared per-path core).

    `append` must already be validated by `_ensure_appendable`; only the
    prepend guard stays here, since it depends on the per-path `path`.

    Raises:
        ValueError: If `prepend` is given and `path` is absolute or
            drive-relative (prepending to it would be silently discarded).
    """
    if prepend is not None and _is_anchored(path):
        msg = f"cannot prepend to an absolute or drive-relative path: {path}"
        raise ValueError(msg)

    parts = [p for p in (prepend, path, append) if p is not None]
    return Path(*parts)


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
        ValueError: If `prepend` is given and `path` is absolute or
            drive-relative (carries a drive or root).
        ValueError: If `append` is given and is absolute or drive-relative.
    """
    _ensure_appendable(append)
    result = _wrap_path(path, prepend, append)
    return stringify_path(result) if stringify else result


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[False] = False,
) -> list[Path]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: Literal[True],
) -> list[str]: ...


@overload
def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool,
) -> list[Path] | list[str]: ...


def wrap_paths(
    paths: StrPaths,
    *,
    prepend: StrPath | None = None,
    append: StrPath | None = None,
    stringify: bool = False,
) -> list[Path] | list[str]:
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
        ValueError: If `prepend` is given and any path is absolute or
            drive-relative (carries a drive or root).
        ValueError: If `append` is given and is absolute or drive-relative.
    """
    _ensure_appendable(append)
    paths = [_wrap_path(path, prepend, append) for path in paths]
    return stringify_paths(paths) if stringify else paths


# ========================== #
#          Reserve           #
# ========================== #


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
) -> list[Path]: ...


@overload
def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: Literal[True],
) -> list[str]: ...


@overload
def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool,
) -> list[Path] | list[str]: ...


def reserve_paths(
    paths: StrPaths,
    *,
    exist_ok: bool = False,
    make_parents: bool = False,
    stringify: bool = False,
) -> list[Path] | list[str]:
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


# ========================== #
#         Extension          #
# ========================== #


def normalize_extension(ext: str, *, lowercase: bool = False) -> str:
    """Strip surrounding whitespace and leading dots from an extension; lower-case when asked."""
    ext = ext.strip().lstrip(".")
    return ext.lower() if lowercase else ext


def normalize_extensions(exts: Iterable[str], *, lowercase: bool = False) -> list[str]:
    """Strip surrounding whitespace and leading dots from each extension; lower-case when asked."""
    return [normalize_extension(ext, lowercase=lowercase) for ext in exts]


def file_extension(path: StrPath, *, level: int = 1, lowercase: bool = True) -> str:
    """Return the last (up to) `level` suffix(es) of `path`, dot-joined and normalized.

    Args:
        path: The path to read the extension from.
        level: How many trailing suffixes to join. `level=2` turns `data.tar.gz`
            into `"tar.gz"`. Defaults to 1.
        lowercase: Whether to lower-case the result. Defaults to True.

    Returns:
        The dot-joined suffixes without a leading dot, or `""` when `path` has
            no suffix.

    Raises:
        ValueError: If `level` is less than 1.
    """
    if level < 1:
        msg = f"level must be >= 1, got {level}"
        raise ValueError(msg)
    suffix = "".join(Path(path).suffixes[-level:])
    return normalize_extension(suffix, lowercase=lowercase)


def ensure_file_extension(
    path: StrPath, ext: str | Iterable[str], *, add: bool = False
) -> Path:
    """Return `path` as a `Path`, requiring a case-insensitive `.<ext>` suffix.

    A pure path check that never touches the filesystem. Only the final suffix
    is considered, so `archive.tar.gz` matches `ext="gz"`, not `ext="tar.gz"`.
    A wrong suffix always raises; `add` only fills in a missing one.

    Args:
        path: The path to check.
        ext: The required extension, or an iterable of acceptable ones, each
            with or without a leading dot. Compared case-insensitively.
        add: Whether to append the first of `ext` when `path` has no suffix,
            instead of raising. Defaults to False.

    Returns:
        The path as a Path object, guaranteed to end in an accepted `.<ext>`.

    Raises:
        ValueError: If `ext` is empty.
        UnsupportedExtensionError: If `path`'s final suffix is none of the
            accepted extensions, except the no-suffix case resolved by
            `add=True`. A `ValueError` subclass.
    """
    exts = [ext] if isinstance(ext, str) else list(ext)
    exts = list(dict.fromkeys(normalize_extensions(exts, lowercase=True)))

    if not exts:
        msg = "ext must name at least one extension"
        raise ValueError(msg)

    path = Path(path)
    path_ext = file_extension(path, lowercase=True)

    if add and not path_ext:
        return path.with_suffix(f".{exts[0]}")

    if path_ext not in exts:
        raise UnsupportedExtensionError(path_ext, exts)

    return path
