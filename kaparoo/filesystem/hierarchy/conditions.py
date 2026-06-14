from __future__ import annotations

__all__ = (
    "And",
    "CheckContext",
    "ChildCount",
    "Condition",
    "Content",
    "Empty",
    "NonEmpty",
    "Not",
    "Or",
    "Size",
    "register_condition",
)

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from typing import Any, Literal, Self


_CONDITION_REGISTRY: dict[str, type[Condition]] = {}


def register_condition[C: Condition](kind: str) -> Callable[[type[C]], type[C]]:
    """Register a `Condition` subclass under `kind` (decorator).

    Mirrors `register_filter`: makes the class discoverable by
    `Condition.from_dict` and stamps `kind` onto `_kind` for `to_dict`.

    Raises:
        ValueError: If `kind` is already registered to another class.
    """

    def decorator(cls: type[C]) -> type[C]:
        existing = _CONDITION_REGISTRY.get(kind)
        if existing is not None and existing is not cls:
            msg = (
                f"condition kind {kind!r} already registered to "
                f"{existing.__name__}; cannot reassign to {cls.__name__}."
            )
            raise ValueError(msg)
        _CONDITION_REGISTRY[kind] = cls
        cls._kind = kind
        return cls

    return decorator


@dataclass(frozen=True)
class CheckContext:
    """Runtime context threaded through `Condition.check`.

    `checks` maps a `Content` name to its callable (supplied at `validate`
    time); `on_missing` decides what happens when a `Content` name is absent
    from `checks` -- `"error"` raises, `"skip"` treats it as satisfied.
    """

    checks: Mapping[str, Callable[[Path], bool]] = field(default_factory=dict)
    on_missing: Literal["error", "skip"] = "error"


_NO_CHECKS = CheckContext()


@dataclass(frozen=True)
class Condition(ABC):
    """A declarative, serializable condition on a matched filesystem path.

    The `Path`-level counterpart of a `kaparoo.filters.Filter` (which tests a
    name `str`): a frozen value object whose `check` inspects the actual
    filesystem object behind a matched node -- size, child count, emptiness,
    or a named content hook. Round-trips through `to_dict` /
    `Condition.from_dict`.

    A condition is a *validation* concern: `match` still maps paths by name /
    type / depth alone, while `validate` checks the matched path's
    conditions and reports the failures.
    """

    _kind: ClassVar[str]

    @abstractmethod
    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:
        """Whether `path` satisfies this condition (`ctx` carries `Content`)."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a `"kind"`-discriminated dict (round-trips)."""
        return {"kind": self._kind, **self._payload()}

    @abstractmethod
    def _payload(self) -> dict[str, Any]:
        """The kind-specific fields of `to_dict` (everything but `"kind"`)."""
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Condition:
        """Construct a `Condition` from a dict produced by `to_dict`.

        On the base, dispatches by `data["kind"]` to the registered class.

        Raises:
            TypeError: If `data` is not a mapping.
            ValueError: If `data` lacks `"kind"`, or the kind is unknown.
            NotImplementedError: If called on a subclass that did not
                override `from_dict`.
        """
        if cls is not Condition:
            msg = f"{cls.__name__}.from_dict() must be overridden by subclasses."
            raise NotImplementedError(msg)

        if not isinstance(data, Mapping):
            msg = f"expected a condition dict, got {type(data).__name__}"
            raise TypeError(msg)

        if (kind := data.get("kind")) is None:
            msg = "condition dict missing 'kind' discriminator."
            raise ValueError(msg)

        if (target := _CONDITION_REGISTRY.get(kind)) is None:
            msg = f"unknown condition kind: {kind!r}"
            raise ValueError(msg)

        return target.from_dict(data)


@dataclass(frozen=True)
class Bound(Condition, ABC):
    """A condition on an integer measurement within an inclusive range.

    The shared base of `Size` (a file's bytes) and `ChildCount` (a
    directory's entries); subclasses supply only `_measure`.

    Raises:
        ValueError: If neither bound is given, or `max` is below `min`.
    """

    min: int | None = field(default=None, kw_only=True)
    max: int | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.min is None and self.max is None:
            msg = f"{type(self).__name__} requires at least one of min / max."
            raise ValueError(msg)
        if self.min is not None and self.max is not None and self.max < self.min:
            msg = f"{type(self).__name__} max {self.max} is below min {self.min}."
            raise ValueError(msg)

    @abstractmethod
    def _measure(self, path: Path) -> int:
        """The integer being bounded (e.g. byte count, child count)."""
        raise NotImplementedError

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:  # noqa: ARG002
        value = self._measure(path)
        return (self.min is None or value >= self.min) and (
            self.max is None or value <= self.max
        )

    def _payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(min=data.get("min"), max=data.get("max"))


@register_condition("size")
@dataclass(frozen=True)
class Size(Bound):
    """An inclusive bound, in bytes, on a file's size (`min` / `max`)."""

    def _measure(self, path: Path) -> int:
        return path.stat().st_size


@register_condition("child_count")
@dataclass(frozen=True)
class ChildCount(Bound):
    """An inclusive bound on a directory's number of entries (`min` / `max`)."""

    def _measure(self, path: Path) -> int:
        return sum(1 for _ in path.iterdir())


@register_condition("empty")
@dataclass(frozen=True)
class Empty(Condition):
    """A file with no bytes, or a directory with no entries."""

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:  # noqa: ARG002
        if path.is_dir():
            return not any(path.iterdir())
        return path.stat().st_size == 0

    def _payload(self) -> dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:  # noqa: ARG003
        return cls()


@register_condition("non_empty")
@dataclass(frozen=True)
class NonEmpty(Condition):
    """A file with at least one byte, or a directory with at least one entry."""

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:  # noqa: ARG002
        if path.is_dir():
            return any(path.iterdir())
        return path.stat().st_size > 0

    def _payload(self) -> dict[str, Any]:
        return {}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:  # noqa: ARG003
        return cls()


@register_condition("content")
@dataclass(frozen=True)
class Content(Condition):
    """A named content hook resolved at `validate` time.

    Only the `name` is stored (and serialized), so the spec stays
    serializable and value-comparable; the actual callable -- which may
    inspect arbitrary file content -- is supplied to `validate` as
    `checks={name: callable}`. When `name` is absent from `checks`,
    `CheckContext.on_missing` decides: `"error"` raises, `"skip"` passes.

    The callable receives the matched *absolute* `Path` (a live filesystem
    handle, not just a name), so it may navigate to siblings and ancestors
    -- `path.parent`, `iterdir()`, `glob(...)` -- to relate its node to
    others at the same or a higher level (e.g. comparing this file's line
    count to the entry count of a sibling directory). Navigation is relative
    to the matched path, not the validation root.
    """

    name: str

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:
        fn = ctx.checks.get(self.name)
        if fn is None:
            if ctx.on_missing == "skip":
                return True
            msg = f"no check supplied for content condition {self.name!r}"
            raise ValueError(msg)
        return fn(path)

    def _payload(self) -> dict[str, Any]:
        return {"name": self.name}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(name=data["name"])


@dataclass(frozen=True)
class Variadic(Condition, ABC):
    """A condition over a non-empty tuple of `conditions`.

    The shared base of `And` / `Or`; subclasses supply only the `check`
    quantifier (`all` / `any`). Field, validation, and serialization are
    shared.

    Raises:
        ValueError: If `conditions` is empty.
    """

    conditions: tuple[Condition, ...]

    def __post_init__(self) -> None:
        if not self.conditions:
            msg = f"{type(self).__name__} requires at least one condition."
            raise ValueError(msg)

    def _payload(self) -> dict[str, Any]:
        return {"conditions": [condition.to_dict() for condition in self.conditions]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(tuple(Condition.from_dict(c) for c in data["conditions"]))


@register_condition("all")
@dataclass(frozen=True)
class And(Variadic):
    """Satisfied when ALL of `conditions` are (conjunction)."""

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:
        return all(condition.check(path, ctx) for condition in self.conditions)


@register_condition("any")
@dataclass(frozen=True)
class Or(Variadic):
    """Satisfied when AT LEAST ONE of `conditions` is (disjunction)."""

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:
        return any(condition.check(path, ctx) for condition in self.conditions)


@register_condition("not")
@dataclass(frozen=True)
class Not(Condition):
    """Satisfied when `condition` is not (negation)."""

    condition: Condition

    def check(self, path: Path, ctx: CheckContext = _NO_CHECKS) -> bool:
        return not self.condition.check(path, ctx)

    def _payload(self) -> dict[str, Any]:
        return {"condition": self.condition.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(Condition.from_dict(data["condition"]))
