from __future__ import annotations

import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _stringify(path: Path) -> str:
    """Stringify a path for computing expected values in tests.

    Re-implemented independently of `kaparoo.filesystem.stringify_path` so
    tests do not validate that function against itself. The leading
    underscore keeps it distinct from `stringify`, a local variable name
    used in several tests.
    """
    text = str(path)
    if platform.system() == "Windows":
        text = text.replace("\\", "/")
    return text
