from __future__ import annotations

import pytest

from kaparoo.filters import utils as _filter_utils


@pytest.fixture(autouse=True)
def _isolate_filter_registry() -> None:
    # `register_filter` mutates a module-level dict. Snapshot before each
    # test and restore after, so tests that register custom kinds cannot
    # leak entries (or kind-collisions) into other tests.
    registry = _filter_utils._FILTER_REGISTRY  # noqa: SLF001
    snapshot = dict(registry)
    yield
    registry.clear()
    registry.update(snapshot)
