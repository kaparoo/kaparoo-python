from __future__ import annotations

__all__ = ("Filter",)

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Filter(ABC):
    """Abstract base for any filter (pattern-based or logical composition).

    Two subclass families live under this base:
        - `PatternFilter` and its concretes: leaf rules that compare an
          input string against a single `pattern`.
        - `LogicalFilter` and its concretes: composite rules that combine
          the results of one or more child filters.
    """

    @abstractmethod
    def matches(self, target: str) -> bool:
        """Test whether `target` satisfies this filter."""
