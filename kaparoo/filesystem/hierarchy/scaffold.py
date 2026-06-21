"""Create on disk the structure a hierarchy spec describes (`scaffold`)."""

from __future__ import annotations

__all__ = ("scaffold",)

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.exceptions import NotAFileError
from kaparoo.filesystem.hierarchy.entry import Directory, Entry, File
from kaparoo.filesystem.hierarchy.group import Exclusive, Group, Together
from kaparoo.filters import Expandable

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.types import StrPath


def scaffold(
    tree: Node,
    root: StrPath,
    *,
    on_create: Callable[[Path, File], None] | None = None,
    dirs_only: bool = False,
    root_as_top: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    """Create the structure `tree` describes under `root`, returning new paths.

    The write counterpart of `locate` / `validate`. Only *creatable* nodes are
    materialized -- an enumerable `name` (`Literal` / `OneOf` / `Template` /
    `Without` and the `str` / `list[str]` sugar) at a fixed `depth` of 1; open
    names (`Glob`, `Regex`) and ranged depths are acceptance patterns, skipped
    when optional and raising when `required`. Creation is idempotent and never
    clobbers; files are created empty. Failure is best-effort: a mid-run raise
    (a conflict, an unsatisfiable `required` node, or an `on_create` that
    raises) leaves the paths already created in place -- there is no rollback,
    but an idempotent re-run resumes safely. See the submodule README for the
    group rules and worked examples.

    Args:
        on_create: Callback `on_create(path, file_node)` run once per file
            actually created -- the seam for writing its content. Not called
            for an untouched existing file, under `dry_run`, or with `dirs_only`.
        dirs_only: Create only the directory skeleton, skipping every file
            (including `required` ones). Defaults to False.
        root_as_top: Treat `root` itself as the top node -- an `Entry` created
            only when its name matches `root`'s leaf name -- rather than the
            container holding it. Defaults to False.
        dry_run: Return the paths that *would* be created without touching disk;
            the same checks still raise. Defaults to False.

    Returns:
        The newly created paths, in creation order.

    Raises:
        ValueError: If a `required` node is not creatable, or `on_create` is
            combined with `dirs_only`.
        NotADirectoryError: If the spec describes a directory where a file
            exists.
        NotAFileError: If the spec describes a file where a directory exists.
        TypeError: If `root_as_top` is set and `tree`'s top node is a `Group`.
    """
    worker = Scaffolder(dry_run=dry_run, dirs_only=dirs_only, on_create=on_create)
    worker.visit(tree, Path(root), root_as_top=root_as_top)
    return worker.created


class Scaffolder:
    """A single, stateful walk that realizes a hierarchy spec on disk.

    One instance drives one `scaffold` run: `visit` enters at the top -- `root`
    as the container, or `root` itself with `root_as_top` -- and recurses,
    dispatching each `Node` to a kind-specific handler. Only *creatable* nodes
    are materialized: an `Entry` whose `name` is `Expandable` at a fixed depth
    of 1, a `Together` whose members are all creatable, or an `Exclusive` with
    at least one fully-creatable alternative (the first such, in order).
    Non-creatable nodes are skipped, or raise when `required`. The walk assumes
    `Node` is the closed `Entry` / `Group` world -- `_dispatch` and
    `_node_creatable` reject anything else.

    The run-wide options (`dry_run`, `dirs_only`, `on_create`) and the `created`
    accumulator live on the instance so the recursion need not thread them
    through every call. An instance is single-use: `created` holds the paths
    made (or, under `dry_run`, that would be made) by its one walk.
    """

    def __init__(
        self,
        *,
        dry_run: bool,
        dirs_only: bool = False,
        on_create: Callable[[Path, File], None] | None = None,
    ) -> None:
        if dirs_only and on_create is not None:
            msg = "on_create cannot be combined with dirs_only (no files are created)"
            raise ValueError(msg)

        self.dry_run = dry_run
        self.dirs_only = dirs_only
        self.on_create = on_create
        self.created: list[Path] = []

    def visit(self, tree: Node, root: Path, *, root_as_top: bool = False) -> None:
        """Realize `tree` against `root`, creating the directories it needs.

        By default `root` is the *container*: it is created (with parents)
        when missing and `tree`'s top node is realized inside it. With
        `root_as_top`, `tree`'s top *is* `root` itself -- it must be an `Entry`
        (a `Group` raises `TypeError`), created only when its name matches
        `root`'s leaf name. `dry_run` records what *would* be created without
        touching the disk.
        """
        if root_as_top:
            self._as_top(tree, root)
        else:
            self._ensure_dir(root)
            self._dispatch(tree, root)

    def _as_top(self, tree: Node, root: Path) -> None:
        """Realize `tree`'s top as `root` itself rather than a child of it."""
        if isinstance(tree, Group):
            msg = "root_as_top requires an Entry top node, not a Group"
            raise TypeError(msg)

        entry = cast("Entry", tree)
        if not entry.name.matches(root.name):
            if entry.required:
                msg = f"cannot scaffold required {entry!r} at {root}:"
                msg += f" its name does not match {root.name!r}"
                raise ValueError(msg)
            return

        self._ensure_dir(root.parent)  # the container that holds `root`
        match entry:
            case File() if not self.dirs_only:
                self._make_file(root, entry)
            case Directory():
                self._make_dir(root)
                for child in entry.children:
                    self._dispatch(child, root)

    def _dispatch(self, node: Node, parent: Path) -> None:
        """Dispatch one node to its kind-specific handler."""
        match node:
            case File():
                self._file(node, parent)
            case Directory():
                self._directory(node, parent)
            case Together():
                self._together(node, parent)
            case Exclusive():
                self._exclusive(node, parent)
            case _:
                raise self._unexpected(node)

    def _ensure_dir(self, container: Path) -> None:
        """Create `container` (with parents) when missing, unless `dry_run`."""
        if not self.dry_run:
            container.mkdir(parents=True, exist_ok=True)

    def _skip_or_raise(self, node: Node, *, required: bool) -> None:
        """Skip a non-creatable node, or raise when it is `required`."""
        if required:
            msg = f"cannot scaffold required {node!r}: it is not creatable."
            msg += " A creatable node has an enumerable name and a fixed depth of 1."
            raise ValueError(msg)

    def _unexpected(self, node: Node) -> TypeError:
        """A `TypeError` for a node outside the closed `Entry` / `Group` world."""
        name = type(node).__name__
        return TypeError(
            f"unsupported node type {name!r}: "
            "expected File, Directory, Together, or Exclusive"
        )

    def _creatable(self, entry: Entry) -> bool:
        """Whether `entry` has a concrete name and a fixed depth of 1."""
        return isinstance(entry.name, Expandable) and entry.is_direct_child

    def _all_creatable(self, nodes: Iterable[Node]) -> bool:
        """Whether every node in `nodes` can be fully materialized."""
        return all(self._node_creatable(node) for node in nodes)

    def _node_creatable(self, node: Node) -> bool:
        """Whether `node` (an entry or nested group) can be fully materialized."""
        match node:
            case Entry():
                return self._creatable(node)
            case Together():
                return self._all_creatable(node.members)
            case Exclusive():
                return any(self._all_creatable(side) for side in node.alternatives)
            case _:
                raise self._unexpected(node)

    def _make_file(self, path: Path, node: File) -> None:
        """Create `path` as an empty file (idempotent); record it when new.

        A file actually created (not an existing one left untouched, and not
        under `dry_run`) is then passed to the `on_create` hook -- the seam for
        filling its content.
        """
        if path.exists():
            if path.is_dir():
                msg = f"cannot scaffold file {path}: a directory exists there."
                raise NotAFileError(msg)
            return  # idempotent: leave the existing file untouched

        if not self.dry_run:
            path.touch()

        self.created.append(path)
        if self.on_create is not None and not self.dry_run:
            self.on_create(path, node)

    def _make_dir(self, path: Path) -> None:
        """Create `path` as a directory (idempotent); record it when new."""
        if path.exists():
            if not path.is_dir():
                msg = f"cannot scaffold directory {path}: a file exists there."
                raise NotADirectoryError(msg)
        else:
            if not self.dry_run:
                path.mkdir()
            self.created.append(path)

    def _file(self, node: File, parent: Path) -> None:
        if self.dirs_only:
            return  # dirs_only: skip every file, required or not

        if not self._creatable(node):
            self._skip_or_raise(node, required=node.required)
            return

        for name in cast("Expandable", node.name).expand():
            self._make_file(parent / name, node)

    def _directory(self, node: Directory, parent: Path) -> None:
        if not self._creatable(node):
            self._skip_or_raise(node, required=node.required)
            return

        for name in cast("Expandable", node.name).expand():
            path = parent / name
            self._make_dir(path)
            for child in node.children:
                self._dispatch(child, path)

    def _together(self, node: Together, parent: Path) -> None:
        # all-or-nothing: a non-creatable member skips the whole set
        if not self._node_creatable(node):
            self._skip_or_raise(node, required=node.required)
            return

        for member in node.members:
            self._dispatch(member, parent)

    def _exclusive(self, node: Exclusive, parent: Path) -> None:
        for side in node.alternatives:
            if self._all_creatable(side):
                for member in side:
                    self._dispatch(member, parent)
                return

        self._skip_or_raise(node, required=node.required)  # none creatable
