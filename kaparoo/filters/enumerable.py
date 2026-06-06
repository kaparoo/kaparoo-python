from __future__ import annotations

__all__ = (
    "Expandable",
    "Literal",
    "OneOf",
    "Template",
    "Without",
)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import product
from typing import TYPE_CHECKING, cast

from kaparoo.filters.base import Filter
from kaparoo.filters.utils import register_filter

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from typing import Any, Self


@dataclass(frozen=True)
class Expandable(Filter, ABC):
    """A `Filter` that can also *enumerate* the names it matches.

    A plain `Filter` only *tests* a name (`matches`); an `Expandable` one
    can additionally *list* the concrete names it stands for via `expand`.
    Enumerability is what *generation* needs -- producing the strings a
    pattern stands for, for example to scaffold a directory tree.
    Open-ended filters (`Glob`, `Regex`, ...) match but never enumerate,
    so they are deliberately not `Expandable`.
    """

    @abstractmethod
    def expand(self) -> Iterator[str]:
        """Yield the concrete names this pattern stands for."""
        raise NotImplementedError


@register_filter("literal")
@dataclass(frozen=True)
class Literal(Expandable):
    """A filter matching exactly one `name`, and expanding to it.

    Matching is case-sensitive, so -- unlike `Equals`, which can be
    case-insensitive and thus match several spellings -- a `Literal`
    always stands for exactly one concrete name, making it
    unconditionally `Expandable`.
    """

    name: str

    def matches(self, target: str) -> bool:
        return target == self.name

    def expand(self) -> Iterator[str]:
        yield self.name

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "literal", "name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(name=data["name"])


@register_filter("one_of")
@dataclass(frozen=True)
class OneOf(Expandable):
    """A filter matching and enumerating an explicit set of `names`.

    The `Expandable` counterpart of `EqualsAny`: it matches a name that is
    one of `names`, and expands to each -- `OneOf(["train", "val",
    "test"])`. `names` is materialized to a tuple at construction and
    deduplicated (first occurrence wins); matching is case-sensitive, so
    `OneOf` is unconditionally `Expandable`.

    Raises:
        ValueError: If `names` is empty.
    """

    names: Iterable[str]

    def __post_init__(self) -> None:
        names = tuple(dict.fromkeys(self.names))
        if not names:
            msg = "OneOf requires at least one name."
            raise ValueError(msg)
        object.__setattr__(self, "names", names)

    def matches(self, target: str) -> bool:
        return target in self.names

    def expand(self) -> Iterator[str]:
        yield from self.names

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "one_of", "names": list(self.names)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(names=data["names"])


@register_filter("template")
class Template(Expandable):
    """A filter enumerating `template.format(*combo)` over value `axes`.

    A single axis condenses a run of regularly-named siblings --
    `Template("shard_{:03d}", range(8))` stands for `shard_000` through
    `shard_007`. Multiple axes vary independently and combine as a
    cartesian product -- `Template("{}_{}.png", ["real", "fake"],
    range(1, 4))` enumerates `real_1.png`, `real_2.png`, `real_3.png`,
    `fake_1.png`, ... . Each axis is materialized to a tuple at
    construction; a name matches when it is one of the enumerated results.

    The template uses positional `str.format` fields, one per axis (so a
    two-axis template needs two fields, e.g. `"{}_{}"`). Formatting is
    lazy, so a template whose field count does not match the axes surfaces
    the error from `expand`, not at construction.

    Args:
        template: A `str.format` string with one positional field per axis.
        *axes: One or more iterables of values; names are drawn from their
            cartesian product, in row-major (last axis varies fastest)
            order.

    Raises:
        ValueError: If no axes are given.
    """

    _template: str
    _axes: tuple[tuple[object, ...], ...]

    def __init__(self, template: str, *axes: Iterable[object]) -> None:
        if not axes:
            msg = "Template requires at least one axis of values."
            raise ValueError(msg)
        object.__setattr__(self, "_template", template)
        object.__setattr__(self, "_axes", tuple(tuple(axis) for axis in axes))

    @property
    def template(self) -> str:
        """The format string applied to each combination of values."""
        return self._template

    @property
    def axes(self) -> tuple[tuple[object, ...], ...]:
        """The value axes, each frozen to a tuple, combined as a product."""
        return self._axes

    def matches(self, target: str) -> bool:
        names = getattr(self, "_matchable", None)
        if names is None:
            names = frozenset(self.expand())
            object.__setattr__(self, "_matchable", names)
        return target in names

    def expand(self) -> Iterator[str]:
        for combo in product(*self._axes):
            yield self._template.format(*combo)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "template",
            "template": self._template,
            "axes": [list(axis) for axis in self._axes],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(data["template"], *data["axes"])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Template):
            return (self._template, self._axes) == (other._template, other._axes)
        return NotImplemented

    def __hash__(self) -> int:
        return hash((Template, self._template, self._axes))

    def __repr__(self) -> str:
        axes = "".join(f", {axis!r}" for axis in self._axes)
        return f"Template({self._template!r}{axes})"


def _as_filter(value: str | Filter) -> Filter:
    """Coerce a bare name into a `Literal`; pass a filter through."""
    return Literal(value) if isinstance(value, str) else value


@register_filter("without")
class Without(Expandable):
    """`base` minus every name matching any of `excluded`.

    The `Expandable` form of `And(base, Not(...))`: it both *matches* and
    *enumerates* `base`'s names with the excluded ones removed -- use it to
    punch holes in an enumerable set. For example
    `Without(Template("cam_{:02d}", range(4)), "cam_02")` yields `cam_00`,
    `cam_01`, `cam_03`.

    `base` must be enumerable (`Literal`, `OneOf`, `Template`, or another
    `Without`); each excluded entry is any `Filter` (a bare `str` is sugar
    for `Literal`), removed by `matches`, so it may itself be open-ended
    (`Without(Template("img_{:04d}", range(1000)), Glob("*_999"))`).

    Raises:
        ValueError: If no exclusions are given.
    """

    _base: Expandable
    _excluded: tuple[Filter, ...]

    def __init__(self, base: Expandable, *excluded: str | Filter) -> None:
        if not excluded:
            msg = "Without requires at least one exclusion."
            raise ValueError(msg)
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_excluded", tuple(_as_filter(e) for e in excluded))

    @property
    def base(self) -> Expandable:
        """The enumerable filter being reduced."""
        return self._base

    @property
    def excluded(self) -> tuple[Filter, ...]:
        """The filters whose matches are removed from `base`."""
        return self._excluded

    def matches(self, target: str) -> bool:
        return self._base.matches(target) and not any(
            e.matches(target) for e in self._excluded
        )

    def expand(self) -> Iterator[str]:
        for name in self._base.expand():
            if not any(e.matches(name) for e in self._excluded):
                yield name

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "without",
            "base": self._base.to_dict(),
            "excluded": [e.to_dict() for e in self._excluded],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        base = cast("Expandable", Filter.from_dict(data["base"]))
        return cls(base, *[Filter.from_dict(e) for e in data["excluded"]])

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Without):
            return (self._base, self._excluded) == (other._base, other._excluded)
        return NotImplemented

    def __hash__(self) -> int:
        return hash((Without, self._base, self._excluded))

    def __repr__(self) -> str:
        excluded = ", ".join(repr(e) for e in self._excluded)
        return f"Without({self._base!r}, {excluded})"
