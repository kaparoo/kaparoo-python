from __future__ import annotations

__all__ = ("Filter",)

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from kaparoo.filters.utils import _FILTER_REGISTRY

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from kaparoo.filters.types import FilterDict


@dataclass(frozen=True)
class Filter(ABC):
    """Abstract base for any filter (pattern-based or logical composition).

    Two subclass families live under this base:
        - `PatternFilter` and its concretes: leaf rules that compare an
          input string against a single `pattern`.
        - `LogicalFilter` and its concretes: composite rules that combine
          the results of one or more child filters.

    Subclasses must implement `matches` and `_payload`, and override
    `from_dict` to construct themselves from a dict (with no further
    dispatch). Polymorphic deserialization is provided by
    `Filter.from_dict(data)`, which reads `data["kind"]`, looks up the
    target class in the registry (populated by `register_filter`), and
    delegates. `register_filter` stamps each concrete class's discriminator
    onto `_kind`, which `to_dict` injects automatically -- so a subclass
    never repeats (or mistypes) its own kind.
    """

    _kind: ClassVar[str]

    @abstractmethod
    def matches(self, target: str) -> bool:
        """Test whether `target` satisfies this filter."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a `"kind"`-discriminated dict.

        The `"kind"` discriminator is injected from `_kind`; subclasses
        supply only their own fields via `_payload`. Round-trippable via
        `Filter.from_dict`.
        """
        return {"kind": self._kind, **self._payload()}

    @abstractmethod
    def _payload(self) -> dict[str, Any]:
        """Return this filter's serialized fields, excluding `"kind"`.

        Default-valued fields may be omitted for compactness; `from_dict`
        supplies them via `data.get(..., DEFAULT)`.
        """
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Filter:
        """Construct a `Filter` from a dict produced by `to_dict`.

        When called on the base (`Filter.from_dict(data)`), dispatches
        by `data["kind"]` to the registered target class. Concrete
        subclasses override this to construct themselves from `data`'s
        fields without dispatch.

        Raises:
            ValueError: If `data` lacks `"kind"`, or the kind is not
                registered.
            NotImplementedError: If called on a subclass that did not
                override `from_dict`.
        """
        if cls is not Filter:
            msg = f"{cls.__name__}.from_dict() must be overridden by subclasses."
            raise NotImplementedError(msg)

        if (kind := data.get("kind")) is None:
            msg = "filter dict missing 'kind' discriminator."
            raise ValueError(msg)

        if (target := _FILTER_REGISTRY.get(kind)) is None:
            msg = f"unknown filter kind: {kind!r}"
            raise ValueError(msg)

        return target.from_dict(data)

    @classmethod
    def parse(cls, value: Filter | FilterDict) -> Filter:
        """Normalize `value` into a `Filter`.

        Passes through a `Filter` instance, or deserializes a
        `FilterDict` via `Filter.from_dict`. Callers needing to accept
        optional input should guard `None` themselves.

        Raises:
            ValueError: If `value` is a dict but lacks `"kind"` or the
                kind is not registered.
        """
        return value if isinstance(value, Filter) else cls.from_dict(value)
