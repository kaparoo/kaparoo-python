from __future__ import annotations

__all__ = ("ValidationReport", "Violation", "conforms", "validate")

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from kaparoo.filesystem.hierarchy.entry import Directory, Entry, File
from kaparoo.filesystem.hierarchy.group import (
    Exclusive,
    Group,
    Together,
    flatten_entries,
)
from kaparoo.filesystem.hierarchy.match import match_map

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from kaparoo.filesystem.hierarchy.base import Node
    from kaparoo.filesystem.types import StrPath


@dataclass(frozen=True)
class Violation:
    """A constraint that a matched tree breaks.

    `kind` is the group's type, `node` the offending `Exclusive` /
    `Together`, and `present` the leaf entries found present: for
    `exclusive`, the entries across the more-than-one sides that coexist;
    for `together`, the members present while others are absent.
    """

    kind: Literal["exclusive", "together"]
    node: Group
    present: tuple[Entry, ...]


@dataclass(frozen=True)
class ValidationReport:
    """The outcome of checking a real directory against a spec tree.

    `matched` maps each on-disk path to the node(s) it matched (exactly
    `match_map`); `unexpected` are paths matching no node; `missing` are
    `required` entries / groups left unsatisfied; `violations` are broken
    `Exclusive` / `Together` constraints. `ok` -- and the report's
    truthiness -- is `True` only when `unexpected`, `missing`, and
    `violations` are all empty.
    """

    matched: dict[Path, tuple[Node, ...]]
    unexpected: tuple[Path, ...]
    missing: tuple[Node, ...]
    violations: tuple[Violation, ...]

    @property
    def ok(self) -> bool:
        return not (self.unexpected or self.missing or self.violations)

    def __bool__(self) -> bool:
        return self.ok


def validate(tree: Node, root: StrPath) -> ValidationReport:
    """Check the directory at `root` (the container, as in `match`) against
    the spec `tree`, returning a `ValidationReport`.

    A path is `unexpected` when it is neither matched nor an ancestor of a
    match, so an unspecified directory's contents count too. A `required`
    enumerable name (`OneOf` / `Template`) is satisfied by *at least one*
    present match.
    """
    return _build_report((tree,), Path(root))


def conforms(spec: Node) -> Callable[[StrPath], bool]:
    """Build a `search` predicate accepting a path that realizes `spec`'s
    *top* node.

    The returned `Callable[[Path], bool]` accepts `path` when it realizes
    the top of `spec`: a `File` whose name matches (and is a file), or a
    `Directory` whose name matches *and* whose subtree conforms (via
    `validate`); a top `Group` is realized by any one of its alternatives /
    members. The path is always tested as the top of `spec`, never against
    one of its inner nodes -- e.g. `conforms(Directory("dataset", [...]))`
    accepts a conforming `dataset/` directory, not the files inside it.

    (File *attribute* conditions are planned and will tighten the file
    case. Checking whether a concrete path or a sub-spec is *contained*
    anywhere within a spec is a separate, future capability.)
    """

    def check(path: StrPath) -> bool:
        return _top_conforms(spec, Path(path))

    return check


def _top_conforms(node: Node, path: Path) -> bool:
    """Whether `path` realizes `node` as the top of a spec."""
    if isinstance(node, Group):
        return any(_node_conforms(entry, path) for entry in node.entries)
    return _node_conforms(cast("Entry", node), path)


def _node_conforms(entry: Entry, path: Path) -> bool:
    """Whether `path` realizes `entry` (a file match, or a conforming dir)."""
    if isinstance(entry, File):
        return path.is_file() and entry.name.matches(path.name)
    directory = cast("Directory", entry)
    if not (path.is_dir() and directory.name.matches(path.name)):
        return False
    return _build_report(directory.children, path).ok


def _build_report(top_nodes: tuple[Node, ...], root_path: Path) -> ValidationReport:
    """Validate `top_nodes` matched directly under `root_path`."""
    matched = _merge_matched(top_nodes, root_path)
    present: set[Node] = {node for nodes in matched.values() for node in nodes}

    missing: list[Node] = []
    violations: list[Violation] = []
    for top in top_nodes:
        for node in _walk_nodes(top):
            if isinstance(node, Entry):
                if node.required and node not in present:
                    missing.append(node)
            else:
                group = cast("Group", node)
                violation, group_missing = _check_group(group, present)
                if violation is not None:
                    violations.append(violation)
                if group_missing:
                    missing.append(group)

    return ValidationReport(
        matched=matched,
        unexpected=tuple(_unexpected(root_path, matched)),
        missing=tuple(missing),
        violations=tuple(violations),
    )


def _merge_matched(
    top_nodes: tuple[Node, ...], root_path: Path
) -> dict[Path, tuple[Node, ...]]:
    """Union the `match_map` of each top node, by path (spec order kept)."""
    merged: dict[Path, tuple[Node, ...]] = {}
    for node in top_nodes:
        for path, nodes in match_map(node, root_path).items():
            merged[path] = merged.get(path, ()) + nodes
    return merged


def _check_group(group: Group, present: set[Node]) -> tuple[Violation | None, bool]:
    """Inspect one constraint; return its `(violation, is_missing)`."""
    if isinstance(group, Exclusive):
        present_sides = [
            side for side in group.alternatives if _present_leaves(side, present)
        ]
        if len(present_sides) > 1:
            leaves = _present_leaves(group.entries, present)
            return Violation("exclusive", group, leaves), False
        return None, group.required and not present_sides

    together = cast("Together", group)
    present_members = [
        member for member in together.members if _present_leaves((member,), present)
    ]
    if 0 < len(present_members) < len(together.members):
        leaves = _present_leaves(together.entries, present)
        return Violation("together", together, leaves), False
    return None, together.required and not present_members


def _unexpected(root_path: Path, matched: dict[Path, tuple[Node, ...]]) -> list[Path]:
    """List paths under `root_path` matching no node (subtrees included).

    A path is unexpected unless it is matched or an ancestor of a match;
    an unexpected directory is reported once and not descended.
    """
    allowed: set[Path] = set(matched)
    for path in matched:
        allowed.update(path.parents)

    result: list[Path] = []
    for dirpath, dirnames, filenames in root_path.walk(top_down=True):
        for name in filenames:
            candidate = dirpath / name
            if candidate not in allowed:
                result.append(candidate)
        kept: list[str] = []
        for name in dirnames:
            candidate = dirpath / name
            if candidate in allowed:
                kept.append(name)
            else:
                result.append(candidate)
        dirnames[:] = kept
    return result


def _walk_nodes(node: Node) -> Iterator[Node]:
    """Yield `node` and every node beneath it (descending into groups)."""
    yield node
    if isinstance(node, Directory):
        for child in node.children:
            yield from _walk_nodes(child)
    elif isinstance(node, Exclusive):
        for alternative in node.alternatives:
            for member in alternative:
                yield from _walk_nodes(member)
    elif isinstance(node, Together):
        for member in node.members:
            yield from _walk_nodes(member)


def _present_leaves(nodes: Iterable[Node], present: set[Node]) -> tuple[Entry, ...]:
    """The leaf entries of `nodes` that are present on disk."""
    return tuple(entry for entry in flatten_entries(nodes) if entry in present)
