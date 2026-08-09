from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from kaparoo.filesystem.search.types import SearchKwargs, WalkKwargs
from kaparoo.filesystem.search.wrappers import search_files

if TYPE_CHECKING:
    from pathlib import Path

    from tests.fixtures.filesystem import TmpFilesystem


def test_walk_kwargs_excludes_predicate():
    assert "predicate" not in WalkKwargs.__optional_keys__


def test_search_kwargs_extends_walk_kwargs():
    assert WalkKwargs.__optional_keys__ <= SearchKwargs.__optional_keys__
    assert "predicate" in SearchKwargs.__optional_keys__


def test_walk_kwargs_forwards_the_walk(tmp_filesystem: TmpFilesystem):
    fs = tmp_filesystem

    def named(root: Path, name: str, **walk: Unpack[WalkKwargs]) -> list[Path]:
        return search_files(root, predicate=lambda path: path.name == name, **walk)

    assert named(fs.root, "file1.txt", ordered=True) == [fs.file1]
    assert named(fs.root, "sub_file.txt", max_depth=1) == []
