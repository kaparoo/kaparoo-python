from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.hierarchy import conditions as _hierarchy_conditions
from kaparoo.filesystem.hierarchy import utils as _hierarchy_utils

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _isolate_node_registry() -> Iterator[None]:
    # `register_node` mutates a module-level dict. Snapshot before each
    # test and restore after, so tests that register custom kinds cannot
    # leak entries (or kind-collisions) into other tests.
    registry = _hierarchy_utils._NODE_REGISTRY  # noqa: SLF001
    snapshot = dict(registry)
    yield
    registry.clear()
    registry.update(snapshot)


@pytest.fixture(autouse=True)
def _isolate_condition_registry() -> Iterator[None]:
    # `register_condition` mutates a module-level dict, exactly as
    # `register_node` does. Snapshot/restore so a test that registers a
    # custom condition kind cannot leak it into another test.
    registry = _hierarchy_conditions._CONDITION_REGISTRY  # noqa: SLF001
    snapshot = dict(registry)
    yield
    registry.clear()
    registry.update(snapshot)
