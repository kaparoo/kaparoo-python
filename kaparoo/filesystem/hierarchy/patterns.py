from __future__ import annotations

__all__ = (
    "Expandable",
    "Literal",
    "OneOf",
    "Template",
)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaparoo.filters import Filter, register_filter

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from typing import Any, Self


class Expandable(ABC):
    """A capability for patterns that can enumerate their names.

    A plain `Filter` only *tests* names (`matches`); an `Expandable`
    filter can additionally *list* the concrete names it stands for via
    `expand`. Enumerability is what scaffolding needs -- code that creates
    a tree on disk requires every name to be `Expandable`. Open-ended
    filters (`Glob`, `Regex`, ...) can match but never enumerate, so they
    are deliberately not `Expandable`.
    """

    __slots__ = ()

    @abstractmethod
    def expand(self) -> Iterator[str]:
        """Yield the concrete names this pattern stands for."""
        raise NotImplementedError


@register_filter("literal")
@dataclass(frozen=True)
class Literal(Filter, Expandable):
    """A filter matching exactly one `name`, and expanding to it.

    The bare-`str` form accepted by node constructors (`File("a.txt")`)
    is sugar for `Literal("a.txt")`. Matching is case-sensitive.
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
class OneOf(Filter, Expandable):
    """A filter matching and enumerating an explicit set of `names`.

    The `Expandable` counterpart of `kaparoo.filters.EqualsAny`: it
    matches a name that is one of `names`, and expands to each. Use it for
    a fixed run of literally-named siblings that share a structure --
    `OneOf(["train", "val", "test"])`. The bare-`list[str]` form accepted
    by node constructors (`Directory(["train", "val"], ...)`) is sugar for
    `OneOf(["train", "val"])`.

    `names` is materialized to a tuple at construction and deduplicated
    (first occurrence wins); matching is case-sensitive.

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
@dataclass(frozen=True)
class Template(Filter, Expandable):
    """A filter enumerating `template.format(value)` over `values`.

    Condenses a run of regularly-named siblings into one object --
    `Template("shard_{:03d}", range(8))` stands for `shard_000` through
    `shard_007`. `values` is materialized to a tuple at construction and
    each is substituted into `template` via `str.format` with a single
    positional field; a name matches when it is one of the enumerated
    results. Formatting is lazy, so a `template` that cannot accept a
    value surfaces the error from `expand`, not at construction.
    """

    template: str
    values: Iterable[object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))

    def matches(self, target: str) -> bool:
        return any(target == name for name in self.expand())

    def expand(self) -> Iterator[str]:
        for value in self.values:
            yield self.template.format(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "template",
            "template": self.template,
            "values": list(self.values),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(template=data["template"], values=data["values"])
