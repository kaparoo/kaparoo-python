from __future__ import annotations

from pathlib import Path

pytest_plugins = [
    ".".join(path.with_suffix("").parts)
    for path in Path("tests/fixtures").glob("[!__]*.py")
]
