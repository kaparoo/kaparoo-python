from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from kaparoo.filters import Filter, register_filter

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any, Self


# --- register_filter -------------------------------------------------------


def test_register_filter_makes_custom_kind_discoverable():
    @register_filter("test_length_above")
    @dataclass(frozen=True)
    class LengthAboveFilter(Filter):
        """Match strings longer than `threshold`."""

        threshold: int

        def matches(self, target: str) -> bool:
            return len(target) > self.threshold

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_length_above", "threshold": self.threshold}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls(threshold=data["threshold"])

    f = LengthAboveFilter(5)
    restored = Filter.from_dict(f.to_dict())
    assert restored == f


def test_register_filter_rejects_duplicate_kind_for_different_class():
    @register_filter("test_dup_kind_a")
    @dataclass(frozen=True)
    class FilterA(Filter):
        def matches(self, target: str) -> bool:
            return False

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_dup_kind_a"}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls()

    with pytest.raises(ValueError, match="already registered"):

        @register_filter("test_dup_kind_a")  # collision
        @dataclass(frozen=True)
        class FilterB(Filter):
            def matches(self, target: str) -> bool:
                return False

            def to_dict(self) -> dict[str, Any]:
                return {"kind": "test_dup_kind_a"}

            @classmethod
            def from_dict(cls, data: Mapping[str, Any]) -> Self:
                return cls()


def test_register_filter_same_class_is_idempotent():
    # Re-registering the SAME class under the SAME kind is a no-op (no raise).
    @register_filter("test_idempotent")
    @dataclass(frozen=True)
    class IdempotentFilter(Filter):
        def matches(self, target: str) -> bool:
            return False

        def to_dict(self) -> dict[str, Any]:
            return {"kind": "test_idempotent"}

        @classmethod
        def from_dict(cls, data: Mapping[str, Any]) -> Self:
            return cls()

    # Re-registration must succeed (idempotent).
    register_filter("test_idempotent")(IdempotentFilter)
