from __future__ import annotations

__all__ = ("Filter",)

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from kaparoo.filters.utils import _FILTER_REGISTRY

if TYPE_CHECKING:
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

    Subclasses implement `matches`, `_payload`, and `from_dict` (the last
    constructs from a dict with no further dispatch). Polymorphic
    deserialization goes through `Filter.from_dict`, which dispatches on
    `data["kind"]` via the `register_filter` registry.
    """

    _kind: ClassVar[str]

    @abstractmethod
    def matches(self, target: str) -> bool:
        """Test whether `target` satisfies this filter."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a `"kind"`-discriminated dict, round-trippable via
        `Filter.from_dict`."""
        return {"kind": self._kind, **self._payload()}

    @abstractmethod
    def _payload(self) -> dict[str, Any]:
        """Return this filter's serialized fields, excluding `"kind"`.

        Default-valued fields may be omitted for compactness; `from_dict`
        supplies them via `data.get(..., DEFAULT)`.
        """

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Filter:
        """Construct a `Filter` from a dict produced by `to_dict`.

        When called on the base (`Filter.from_dict(data)`), dispatches
        by `data["kind"]` to the registered target class. Concrete
        subclasses override this to construct themselves from `data`'s
        fields without dispatch.

        Raises:
            TypeError: If `data` is not a mapping.
            ValueError: If `data` lacks `"kind"`, or the kind is not
                registered.
            NotImplementedError: If called on a subclass that did not
                override `from_dict`.
        """
        if cls is not Filter:
            msg = f"{cls.__name__}.from_dict() must be overridden by subclasses."
            raise NotImplementedError(msg)

        if not isinstance(data, Mapping):
            msg = f"expected a filter dict, got {type(data).__name__}"
            raise TypeError(msg)

        if "kind" not in data:
            msg = "filter dict missing 'kind' discriminator."
            raise ValueError(msg)

        kind = data["kind"]
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
            TypeError: If `value` is neither a `Filter` nor a mapping.
            ValueError: If `value` is a dict but lacks `"kind"` or the
                kind is not registered.
        """
        return value if isinstance(value, Filter) else cls.from_dict(value)
