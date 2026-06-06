from __future__ import annotations

import pytest

from kaparoo.filesystem.hierarchy import utils as _hierarchy_utils


@pytest.fixture(autouse=True)
def _isolate_node_registry() -> None:
    # `register_node` mutates a module-level dict. Snapshot before each
    # test and restore after, so tests that register custom kinds cannot
    # leak entries (or kind-collisions) into other tests.
    registry = _hierarchy_utils._NODE_REGISTRY  # noqa: SLF001
    snapshot = dict(registry)
    yield
    registry.clear()
    registry.update(snapshot)
