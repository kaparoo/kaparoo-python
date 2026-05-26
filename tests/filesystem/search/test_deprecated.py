from __future__ import annotations

import os
from typing import TYPE_CHECKING

from kaparoo.filesystem.search import get_paths
from kaparoo.filesystem.utils import stringify_paths

if TYPE_CHECKING:
    from pathlib import Path


def test_get_paths(tmp_filesystem: list[Path]):
    root_dir, file1, file2, file3, sub_dir, sub_file = tmp_filesystem

    # default
    result1 = get_paths(root_dir)
    expected1 = [file1, file2, file3, sub_dir]
    assert sorted(result1) == sorted(expected1)

    # recursive
    result2 = get_paths(root_dir, recursive=True)
    expected2 = [file1, file2, file3, sub_dir, sub_file]
    assert sorted(result2) == sorted(expected2)

    # stringify
    result3 = get_paths(root_dir, recursive=True, stringify=True)
    expected3 = stringify_paths(expected2)
    assert sorted(result3) == sorted(expected3)

    # pattern
    result4 = get_paths(root_dir, pattern="*.txt", recursive=True)
    expected4 = [file1, file2, sub_file]
    assert sorted(result4) == sorted(expected4)

    # excludes
    result5 = get_paths(root_dir, excludes=[file2, sub_dir], recursive=True)
    expected5 = [file1, file3, sub_file]
    assert sorted(result5) == sorted(expected5)

    # condition
    result6 = get_paths(root_dir, condition=os.path.isfile, recursive=True)
    expected6 = [file1, file2, file3, sub_file]
    assert sorted(result6) == sorted(expected6)
