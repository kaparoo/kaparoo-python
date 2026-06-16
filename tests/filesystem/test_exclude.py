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
    with pytest.raises(ValueError, match="not under the root"):
        excluder(tmp_path / "other" / "a" / "b")  # absolute, outside root


def test_absolute_rule_under_root_matches(tmp_path: Path) -> None:
    # An absolute rule under root is normalized like the candidate, so both
    # collapse to the same root-relative key and match.
    root = tmp_path / "data"
    excluder = build_excluder([root / "a" / "b"], root)
    assert excluder is not None
    assert excluder(root / "a" / "b")
    assert not excluder(root / "a" / "c")


def test_absolute_rule_outside_root_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not under the root"):
        build_excluder([tmp_path / "other" / "x"], tmp_path / "data")


def test_callable_rule_receives_the_real_candidate_path(tmp_path: Path) -> None:
    # A callable gets the candidate's own (filesystem-valid) path, not the
    # root-relative form -- so `stat` / `iterdir` resolve correctly.
    root = tmp_path / "data"
    seen: list[Path] = []
    excluder = build_excluder([lambda p: bool(seen.append(p))], root)
    assert excluder is not None
    candidate = root / "sub" / "x"
    excluder(candidate)
    assert seen == [candidate]  # the real path, not Path("sub/x")
