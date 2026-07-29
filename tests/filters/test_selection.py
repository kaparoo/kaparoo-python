from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filters import Filter, Glob, resolve_selector, select

if TYPE_CHECKING:
    from pathlib import Path

ITEMS = ("train/a", "train/b", "val/c", "test/d")


def _name(value: str) -> str:
    return value


def _slashes(value: str) -> str:
    return value.replace("//", "/")


# --- resolve_selector (in-memory) -------------------------------------------


def test_resolve_none_is_none():
    assert resolve_selector(None) is None


def test_resolve_empty_sequence_is_none():
    assert resolve_selector([]) is None


def test_resolve_str_is_an_exact_name():
    resolved = resolve_selector("train/a")
    assert resolved is not None
    assert resolved.matches("train/a")
    assert not resolved.matches("train/b")


def test_resolve_filter_passes_through():
    glob = Glob("train/*")
    assert resolve_selector(glob) is glob


def test_resolve_filterdict():
    resolved = resolve_selector({"kind": "glob", "pattern": "train/*"})
    assert resolved is not None
    assert resolved.matches("train/a")
    assert not resolved.matches("val/c")


def test_resolve_list_is_oneof():
    resolved = resolve_selector(["train/a", "val/c"])
    assert isinstance(resolved, Filter)
    assert resolved.matches("train/a")
    assert not resolved.matches("train/b")


def test_resolve_single_filterdict_in_list():
    resolved = resolve_selector([{"kind": "glob", "pattern": "train/*"}])
    assert resolved is not None
    assert resolved.matches("train/a")


def test_resolve_mixed_list_with_filterdict():
    resolved = resolve_selector(["val/c", {"kind": "glob", "pattern": "train/*"}])
    assert resolved is not None
    assert resolved.matches("val/c")
    assert resolved.matches("train/a")


def test_resolve_mixed_list_with_filter_instance():
    resolved = resolve_selector(["val/c", Glob("train/*")])
    assert resolved is not None
    assert resolved.matches("val/c")
    assert resolved.matches("train/a")


# --- the base neither reads files nor normalizes ----------------------------


def test_base_treats_a_txt_string_as_a_literal_name(tmp_path: Path):
    listing = tmp_path / "keep.txt"
    listing.write_text("train/a\n", encoding="utf-8")
    resolved = resolve_selector(str(listing))
    assert resolved is not None
    assert resolved.matches(str(listing))  # the literal path string
    assert not resolved.matches("train/a")  # the file was not read


def test_base_does_not_normalize_by_default():
    resolved = resolve_selector(["a//b"])
    assert resolved is not None
    assert resolved.matches("a//b")  # verbatim, not collapsed to "a/b"
    assert not resolved.matches("a/b")


# --- normalize hook ----------------------------------------------------------


def test_normalize_applies_to_a_bare_name():
    resolved = resolve_selector("a//b", normalize=_slashes)
    assert resolved is not None
    assert resolved.matches("a/b")


def test_normalize_applies_to_list_names():
    resolved = resolve_selector(["a//b"], normalize=_slashes)
    assert resolved is not None
    assert resolved.matches("a/b")


def test_normalize_leaves_filterdict_patterns_untouched():
    resolved = resolve_selector(
        {"kind": "glob", "pattern": "train/*"}, normalize=str.upper
    )
    assert resolved is not None
    assert resolved.matches("train/a")  # pattern not upper-cased


# --- select ------------------------------------------------------------------


def test_select_no_restriction_keeps_all():
    assert select(ITEMS, key=_name) == list(ITEMS)


def test_select_empty_include_is_no_restriction():
    assert select(ITEMS, key=_name, include=[]) == list(ITEMS)


def test_select_applies_include_then_exclude():
    got = select(
        ITEMS, key=_name, include=["train/a", "train/b", "val/c"], exclude=["train/b"]
    )
    assert got == ["train/a", "val/c"]


def test_select_on_conflict_exclude_wins():
    assert select(ITEMS, key=_name, include=["train/a"], exclude=["train/a"]) == []


def test_select_unmatched_exact_name_raises():
    with pytest.raises(ValueError, match="no such item"):
        select(ITEMS, key=_name, include=["nope"])


def test_select_unmatched_enumerable_filterdict_raises():
    # an enumerable FilterDict (`one_of`) is typo-checked like a string list
    with pytest.raises(ValueError, match="no such item"):
        select(ITEMS, key=_name, include={"kind": "one_of", "names": ["nope"]})


def test_select_open_pattern_matching_nothing_does_not_raise():
    assert select(ITEMS, key=_name, include=Glob("zzz/*")) == []


def test_select_threads_normalize():
    got = select(["a/b"], key=_name, include=["a//b"], normalize=_slashes)
    assert got == ["a/b"]
