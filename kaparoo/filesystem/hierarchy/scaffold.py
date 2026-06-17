"""Create on disk the structure a hierarchy spec describes (`scaffold`)."""

from __future__ import annotations

__all__ = ("scaffold",)

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kaparoo.filesystem.hierarchy.entry import Directory, Entry, File
from kaparoo.filesystem.hierarchy.group import Exclusive, Group, Together
from kaparoo.filters import Expandable

if TYPE_CHECKING:
    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.types import StrPath


def scaffold(
    tree: Node, root: StrPath, *, root_as_top: bool = False, dry_run: bool = False
) -> list[Path]:
    """Create the structure `tree` describes under `root`, returning new paths.

    The write counterpart of `locate` / `validate`: by default `root` is the
    *container*, so `tree`'s top node is created directly inside it (a
    nonexistent `root` is created first). Only *enumerable* nodes are
    materialized -- a node is creatable when its `name` is an `Expandable`
    filter (`Literal`, `OneOf`, `Template`, `Without`, and the `str` /
    `list[str]` sugar) **and** it sits at a fixed `depth` of 1. Open-ended
    names (`Glob`, `Regex`, ...) and non-fixed depths are acceptance patterns,
    not generators: they are skipped when optional, but a `required` one
    cannot be satisfied and raises. Files are created empty (scaffold builds
    the skeleton, not its contents).

    Groups resolve to a single concrete shape: `Together` creates all its
    members (or, if any is non-creatable, the whole group -- preserving
    all-or-nothing -- unless `required`, which raises); `Exclusive` creates
    the first alternative that is fully creatable (declaration order is the
    priority), skipping non-creatable leading ones and raising only when none
    is creatable and the group is `required`.

    Creation is idempotent: an existing directory is descended without
    change and an existing file is left untouched (never clobbered); only the
    paths newly created are returned, in creation order. A path that exists
    with the wrong kind (a file where a directory is described, or vice
    versa) is a conflict and raises.

    Args:
        root_as_top: Treat `root` *itself* as the realized top rather than its
            container. The top must be an `Entry` (a `Group` raises) and is
            created only when its name matches `root`'s leaf name -- otherwise
            it is skipped, or raises when `required`. A `Directory` top creates
            `root` and its children; a `File` top creates `root` as an empty
            file.
        dry_run: When True, touch nothing on disk and return the paths that
            *would* be created. The same checks run, so an unsatisfiable
            `required` node or a type conflict still raises -- a faithful
            preview.

    Returns:
        The newly created paths, in creation order (`dry_run` returns the
        paths that would be created).

    Raises:
        ValueError: If a `required` node is not creatable, or a target path
            exists with the wrong kind.
        TypeError: If `root_as_top` is set and `tree`'s top node is a `Group`.
    """
    worker = Scaffolder(dry_run=dry_run)
    worker.visit(tree, Path(root), root_as_top=root_as_top)
    return worker.created


class Scaffolder:
    """A single scaffold run: walks a spec, accumulating the paths it makes.

    Bundles the `dry_run` flag and the `created` accumulator so the recursive
    walk does not thread them through every call.
    """

    def __init__(self, *, dry_run: bool) -> None:
        self.dry_run = dry_run
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
                msg = (
                    f"cannot scaffold required {entry!r} at {root}: "
                    f"its name does not match {root.name!r}"
                )
                raise ValueError(msg)
            return  # optional top whose name does not match `root`: skip

        self._ensure_dir(root.parent)  # the container that holds `root`
        if isinstance(entry, Directory):
            self._make_dir(root)
            for child in entry.children:
                self._dispatch(child, root)
        else:
            self._make_file(root)

    def _dispatch(self, node: Node, parent: Path) -> None:
        """Dispatch one node to its kind-specific handler."""
        if isinstance(node, File):
            self._file(node, parent)
        elif isinstance(node, Directory):
            self._directory(node, parent)
        elif isinstance(node, Together):
            self._together(node, parent)
        else:
            self._exclusive(cast("Exclusive", node), parent)

    def _ensure_dir(self, container: Path) -> None:
        """Create `container` (with parents) when missing, unless `dry_run`."""
        if not self.dry_run:
            container.mkdir(parents=True, exist_ok=True)

    def _skip_or_raise(self, node: Node, *, required: bool) -> None:
        """Skip a non-creatable node, or raise when it is `required`."""
        if required:
            msg = (
                f"cannot scaffold required {node!r}: its name is not "
                f"enumerable, or its depth is not fixed at 1."
            )
            raise ValueError(msg)

    def _creatable(self, entry: Entry) -> bool:
        """Whether `entry` has a concrete name and a fixed depth of 1."""
        return (
            isinstance(entry.name, Expandable)
            and entry.min_depth == 1
            and entry.max_depth == 1
        )

    def _node_creatable(self, node: Node) -> bool:
        """Whether `node` (an entry or nested group) can be fully materialized."""
        if isinstance(node, Entry):
            return self._creatable(node)
        if isinstance(node, Together):
            return all(self._node_creatable(member) for member in node.members)
        exclusive = cast("Exclusive", node)
        return any(
            all(self._node_creatable(member) for member in side)
            for side in exclusive.alternatives
        )

    def _make_file(self, path: Path) -> None:
        """Create `path` as an empty file (idempotent); record it when new."""
        if path.exists():
            if path.is_dir():
                msg = f"cannot scaffold file {path}: a directory exists there."
                raise ValueError(msg)
            return  # idempotent: leave the existing file untouched
        if not self.dry_run:
            path.touch()
        self.created.append(path)

    def _make_dir(self, path: Path) -> None:
        """Create `path` as a directory (idempotent); record it when new."""
        if path.exists():
            if not path.is_dir():
                msg = f"cannot scaffold directory {path}: a file exists there."
                raise ValueError(msg)
        else:
            if not self.dry_run:
                path.mkdir()
            self.created.append(path)

    def _file(self, node: File, parent: Path) -> None:
        if not self._creatable(node):
            self._skip_or_raise(node, required=node.required)
            return

        for name in cast("Expandable", node.name).expand():
            self._make_file(parent / name)

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
        if not all(self._node_creatable(member) for member in node.members):
            # all-or-nothing: a non-creatable member skips the whole set
            self._skip_or_raise(node, required=node.required)
            return

        for member in node.members:
            self._dispatch(member, parent)

    def _exclusive(self, node: Exclusive, parent: Path) -> None:
        for side in node.alternatives:
            if all(self._node_creatable(member) for member in side):
                for member in side:
                    self._dispatch(member, parent)
                return

        self._skip_or_raise(node, required=node.required)  # none creatable
