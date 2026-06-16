from __future__ import annotations

from pathlib import Path

import pytest

from kaparoo.filesystem.exclude import build_excluder


def test_none_and_empty_excluders_return_none() -> None:
    assert build_excluder(None, Path("/data")) is None
    assert build_excluder([], Path("/data")) is None


def test_candidate_under_root_is_stripped() -> None:
    excluder = build_excluder(["a/b"], Path("data"))
    assert excluder is not None
    assert excluder(Path("data/a/b"))  # under root -> stripped to "a/b"
    assert not excluder(Path("data/a/c"))


def test_relative_candidate_not_under_root_is_taken_as_root_relative() -> None:
    excluder = build_excluder(["a/b"], Path("/data"))
    assert excluder is not None
    # not absolute and not under /data -> used as-is (already root-relative)
    assert excluder(Path("a/b"))
    assert not excluder(Path("a/c"))


def test_absolute_candidate_outside_root_raises(tmp_path: Path) -> None:
    # `tmp_path` is genuinely absolute on every platform (a Windows `/x` is
    # not, so it would be taken as root-relative instead).
    excluder = build_excluder(["a/b"], tmp_path / "data")
    assert excluder is not None
    with pytest.raises(ValueError, match="outside the root"):
        excluder(tmp_path / "other" / "a" / "b")  # absolute, outside root
