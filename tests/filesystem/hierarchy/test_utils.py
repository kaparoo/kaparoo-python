from __future__ import annotations

import pytest

from kaparoo.filesystem.hierarchy import Directory, File
from kaparoo.filesystem.hierarchy.utils import register_node


def test_register_node_rejects_duplicate_kind_for_different_class() -> None:
    # "file" is already registered to File; re-registering to Directory must raise.
    with pytest.raises(ValueError, match="already registered"):
        register_node("file")(Directory)


def test_register_node_same_class_is_idempotent() -> None:
    # Re-registering the SAME class under the SAME kind is a no-op (no raise).
    register_node("file")(File)
