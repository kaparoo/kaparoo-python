"""Named hierarchy nodes: the `Entry` base and `File` / `Directory`."""

from __future__ import annotations

__all__ = ("Directory", "Entry", "File")

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from kaparoo.filesystem.hierarchy.base import Node
from kaparoo.filesystem.hierarchy.conditions import Condition
from kaparoo.filesystem.hierarchy.utils import register_node
from kaparoo.filters import Filter, Literal, OneOf

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path
    from typing import Any, ClassVar, Self

    from kaparoo.filesystem.hierarchy.conditions import EntryKind, HookResolver


def _reject_separator(name: str) -> None:
    """Reject a sugar name that is not a single path component.

    Raises:
        ValueError: If `name` contains a `/` or `\\` separator.
    """
    if "/" in name or "\\" in name:
        msg = f"name must be a single path component (no separators), got {name!r}"
        raise ValueError(msg)


def _as_filter(name: str | list[str] | Filter) -> Filter:
    """Coerce a bare name into a pattern; pass a filter through.

    A `Filter` is returned unchanged, a `str` becomes a `Literal`, and a
    `list[str]` becomes a `OneOf` (the shared-structure shorthand). A bare
    `str` / `list[str]` names a single path component, so a separator in it
    is rejected; pass an explicit filter for anything more exotic.
    """
    if isinstance(name, Filter):
        return name
    if isinstance(name, str):
        _reject_separator(name)
        return Literal(name)
    if not name:
        msg = "name list must be non-empty"
        raise ValueError(msg)
    for part in name:
        _reject_separator(part)
    return OneOf(name)


def _depth_suffix(depth: tuple[int, int | None]) -> str:
    """Render the `depth=` part of a `repr` in its most compact form.

    Omitted for the `(1, 1)` default; an exact `(n, n)` renders as
    `depth=n`, `(1, None)` as `depth=None`, and any other range as
    `depth=(min, max)`.
    """
    min_depth, max_depth = depth
    if min_depth == 1 and max_depth == 1:
        return ""
    if min_depth == max_depth:
        return f", depth={min_depth!r}"
    if min_depth == 1 and max_depth is None:
        return ", depth=None"
    return f", depth=({min_depth!r}, {max_depth!r})"


def _normalize_depth(
    depth: int | tuple[int, int | None] | None,
) -> tuple[int, int | None]:
    """Normalize the `depth` argument to an inclusive `(min, max)` range.

    `None` becomes `(1, None)` (any depth), an `int` becomes `(int, int)`
    (an exact level), and a `(min, max)` tuple is taken as-is.

    Raises:
        ValueError: If a bound is less than 1, or `max` is below `min`.
    """
    match depth:
        case None:
            return (1, None)
        case tuple():
            min_depth, max_depth = depth
        case _:
            min_depth = max_depth = depth

    if min_depth < 1:
        msg = f"depth must be >= 1, got {min_depth!r}"
        raise ValueError(msg)

    if max_depth is not None and max_depth < min_depth:
        msg = f"depth max {max_depth!r} is below min {min_depth!r}"
        raise ValueError(msg)

    return (min_depth, max_depth)


def _depth_arg(data: Mapping[str, Any]) -> int | tuple[int, int | None]:
    """Read the depth constructor argument from a node dict.

    A missing `depth` defaults to `1` (a direct child); otherwise the
    serialized `[min, max]` pair is returned as a tuple.
    """
    depth = data.get("depth")
    return 1 if depth is None else (depth[0], depth[1])


def _condition_arg(data: Mapping[str, Any]) -> Condition | None:
    """Read the optional `condition` from a node dict (absent -> `None`)."""
    raw = data.get("condition")
    return None if raw is None else Condition.from_dict(raw)


def _allow_extra_arg(data: Mapping[str, Any]) -> bool | Filter:
    """Read the optional `allow_extra` from a directory dict (absent -> `False`)."""
    raw = data.get("allow_extra", False)
    return raw if isinstance(raw, bool) else Filter.from_dict(raw)


class Entry(Node, ABC):
    """A named node in a filesystem hierarchy: a `File` or a `Directory`.

    Those are the only two subclasses, which `locate` / `validate` rely on to
    narrow a non-`File` `Entry` to a `Directory`. Every entry carries a
    `name` filter (any `kaparoo.filters.Filter`, so
    the full DSL describes which siblings it matches). As sugar, a bare
    `str` becomes a `Literal` and a `list[str]` a `OneOf` -- one node
    standing for several literally-named siblings that share a structure.
    Entries are immutable value objects -- equal by type, name, depth,
    condition, and (for a directory) children -- and hashable.

    `depth` is how far below its parent the entry sits, as an inclusive
    `(min_depth, max_depth)` range past intermediate directories of unknown
    name; the default `1` is a direct child.

    Args:
        name: The entry's name -- a `kaparoo.filters.Filter`, or `str` /
            `list[str]` sugar naming a single path component (a separator
            in sugar raises `ValueError`).
        depth: How far below the parent the entry sits, exposed as
            `min_depth` / `max_depth`. An `int >= 1` is an exact level,
            `None` is any depth (one or more levels), and a `(min, max)`
            tuple is an inclusive range whose `max` may be `None` for
            unbounded. Defaults to `1`.
        required: Whether the entry must be present. Defaults to `False`
            (opt-in): `validate` reports a `missing` entry only for
            `required` ones, so a spec asserts nothing exists until asked.
        condition: An optional `Condition` on the matched path's filesystem
            attributes (size, child count, content hook, ...), checked by
            `validate` (not by `locate`, which stays structural). Must apply
            to this entry's kind -- a kind-mismatched condition (a
            `ChildCount` on a `File`, a `Size` on a `Directory`, ...) raises
            at construction. Defaults to `None`.

    Raises:
        ValueError: If a sugar name contains a path separator, a depth
            bound is below 1, `max` is below `min`, or `condition` does not
            apply to this entry's kind.
    """

    __slots__ = ("_condition", "_depth", "_name", "_required")

    _kind: ClassVar[EntryKind]
    _name: Filter
    _depth: tuple[int, int | None]
    _required: bool
    _condition: Condition | None

    def __init__(
        self,
        name: str | list[str] | Filter,
        *,
        depth: int | tuple[int, int | None] | None = 1,
        required: bool = False,
        condition: Condition | None = None,
    ) -> None:
        if condition is not None and not condition.applies_to(self._kind):
            msg = (
                f"{type(condition).__name__} condition does not apply to a "
                f"{type(self).__name__}"
            )
            raise ValueError(msg)

        object.__setattr__(self, "_name", _as_filter(name))
        object.__setattr__(self, "_depth", _normalize_depth(depth))
        object.__setattr__(self, "_required", required)
        object.__setattr__(self, "_condition", condition)

    @property
    def name(self) -> Filter:
        """The filter naming this entry (one or many siblings)."""
        return self._name

    @property
    def min_depth(self) -> int:
        """The shallowest level below the parent the entry may sit at."""
        return self._depth[0]

    @property
    def max_depth(self) -> int | None:
        """The deepest level below the parent (`None` is unbounded)."""
        return self._depth[1]

    @property
    def required(self) -> bool:
        """Whether this entry must be present (vs optional)."""
        return self._required

    @property
    def condition(self) -> Condition | None:
        """The optional attribute condition `validate` checks (or `None`)."""
        return self._condition

    def accepts_depth(self, depth: int) -> bool:
        """Whether `depth` falls in this entry's inclusive depth range."""
        return self.max_depth is None or self.min_depth <= depth <= self.max_depth

    def accepts_kind(self, path: Path) -> bool:
        """Whether `path`'s on-disk kind matches this entry's (file vs dir)."""
        return path.is_dir() if self._kind == "dir" else path.is_file()

    def matches(self, path: Path) -> bool:
        """Whether `path`'s leaf name and on-disk kind both fit this entry.

        Combines the name filter with `accepts_kind`; it does not weigh
        `depth`, the positional concern checked separately via `accepts_depth`.
        """
        return self.name.matches(path.name) and self.accepts_kind(path)

    def accepts_condition(self, path: Path, resolver: HookResolver) -> bool:
        """Whether `path` satisfies this entry's attribute `condition`.

        A `None` condition is vacuously satisfied. `resolver` supplies the
        `Content` hooks (`hooks` / `on_missing`) the condition may consult.
        """
        return self.condition is None or self.condition.check(path, resolver)

    @abstractmethod
    def _fields(self) -> tuple[object, ...]:
        """Return the identity fields shown in `repr`, excluding `depth`."""
        raise NotImplementedError

    @override
    def _key(self) -> tuple[object, ...]:
        return (*self._fields(), self._depth, self._required, self._condition)

    def _common_payload(self) -> dict[str, Any]:
        """The non-default `depth` / `required` / `condition` `to_dict` parts.

        The entry-level fields shared by every `Entry`; a concrete `to_dict`
        merges these after its own `name` (and `children`). Distinct from a
        `Filter` / `Condition` `_payload`, which is the *whole* field set.
        """
        payload: dict[str, Any] = {}
        if self._depth != (1, 1):
            payload["depth"] = list(self._depth)
        if self._required:
            payload["required"] = True
        if self._condition is not None:
            payload["condition"] = self._condition.to_dict()

        return payload

    def _repr_suffix(self) -> str:
        """The keyword-argument tail of `repr` (`depth` / `required` / `condition`)."""
        suffix = _depth_suffix(self._depth)
        if self._required:
            suffix += ", required=True"
        if self._condition is not None:
            suffix += f", condition={self._condition!r}"
        return suffix

    def __repr__(self) -> str:
        inner = ", ".join(repr(field) for field in self._fields())
        return f"{type(self).__name__}({inner}{self._repr_suffix()})"


@register_node("file")
class File(Entry):
    """A leaf entry: a file named by its `name` filter."""

    __slots__ = ()

    _kind = "file"

    @override
    def _fields(self) -> tuple[object, ...]:
        return (self._name,)

    @override
    def to_dict(self) -> dict[str, Any]:
        return {"node": "file", "name": self._name.to_dict(), **self._common_payload()}

    @classmethod
    @override
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            Filter.from_dict(data["name"]),
            depth=_depth_arg(data),
            required=data.get("required", False),
            condition=_condition_arg(data),
        )


@register_node("directory")
class Directory(Entry):
    """An internal entry: a directory named by `name`, holding `children`.

    `children` is materialized to a tuple at construction and preserves
    insertion order. Each child is any `Node` -- a nested `File` /
    `Directory`, or a `Group` constraint over some of them. When `name`
    matches many sibling directories, `children` describes the shape
    shared by every one of them.
    """

    __slots__ = ("_allow_extra", "_children")

    _kind = "dir"
    _children: tuple[Node, ...]
    _allow_extra: bool | Filter

    def __init__(
        self,
        name: str | list[str] | Filter,
        children: Iterable[Node] = (),
        *,
        depth: int | tuple[int, int | None] | None = 1,
        required: bool = False,
        condition: Condition | None = None,
        allow_extra: bool | Filter = False,
    ) -> None:
        super().__init__(name, depth=depth, required=required, condition=condition)
        object.__setattr__(self, "_children", tuple(children))
        object.__setattr__(self, "_allow_extra", allow_extra)

    @property
    def children(self) -> tuple[Node, ...]:
        """The contained nodes, in insertion order."""
        return self._children

    @property
    def allow_extra(self) -> bool | Filter:
        """How `validate` treats contents matching no child spec.

        `True` ignores any such on-disk entry (and its subtree) rather than
        reporting it `unexpected`; a `Filter` ignores only those whose *name*
        it matches, so real strays still surface. `False` (default) keeps the
        directory strict. A matched subdirectory keeps its own setting. Only
        `validate` / `conformer` read this; `locate` and `scaffold` ignore it.
        """
        return self._allow_extra

    @override
    def _fields(self) -> tuple[object, ...]:
        return (self._name, self._children)

    @override
    def _key(self) -> tuple[object, ...]:
        return (*super()._key(), self._allow_extra)

    @override
    def _repr_suffix(self) -> str:
        suffix = super()._repr_suffix()
        if self._allow_extra is not False:
            suffix += f", allow_extra={self._allow_extra!r}"
        return suffix

    @override
    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"node": "directory", "name": self._name.to_dict()}
        if self._children:
            result["children"] = [child.to_dict() for child in self._children]
        if self._allow_extra is not False:
            result["allow_extra"] = (
                True if self._allow_extra is True else self._allow_extra.to_dict()
            )
        result.update(self._common_payload())
        return result

    @classmethod
    @override
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        children = [Node.from_dict(child) for child in data.get("children", ())]
        return cls(
            Filter.from_dict(data["name"]),
            children,
            depth=_depth_arg(data),
            required=data.get("required", False),
            condition=_condition_arg(data),
            allow_extra=_allow_extra_arg(data),
        )
