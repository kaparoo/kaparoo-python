from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.search import (
    SPEC_FILE_SUFFIXES,
    is_spec_file,
    resolve_selector,
    select,
)
from kaparoo.filters import Filter, Glob

if TYPE_CHECKING:
    from pathlib import Path

ITEMS = ("train/a", "train/b", "val/c")


def _name(value: str) -> str:
    return value


# --- no restriction ---------------------------------------------------------


def test_no_restriction_keeps_all():
    assert select(ITEMS, key=_name) == list(ITEMS)


def test_empty_include_list_is_no_restriction():
    assert select(ITEMS, key=_name, include=[]) == list(ITEMS)


# --- inline strings ---------------------------------------------------------


def test_include_inline_single_subpath():
    assert select(ITEMS, key=_name, include="train/a") == ["train/a"]


def test_include_inline_list():
    assert select(ITEMS, key=_name, include=["train/a", "val/c"]) == [
        "train/a",
        "val/c",
    ]


def test_exclude_inline_list():
    assert select(ITEMS, key=_name, exclude=["val/c"]) == ["train/a", "train/b"]


def test_inline_hash_is_part_of_the_name_not_a_comment():
    items = ("a#b", "c")
    assert select(items, key=_name, include=["a#b"]) == ["a#b"]


def test_inline_separators_are_normalized_to_posix():
    assert select(ITEMS, key=_name, include=["train//a"]) == ["train/a"]


# --- order, conflict, duplicates, source order ------------------------------


def test_include_then_exclude():
    got = select(
        ITEMS, key=_name, include=["train/a", "train/b", "val/c"], exclude=["train/b"]
    )
    assert got == ["train/a", "val/c"]


def test_on_conflict_exclude_wins():
    # `train/a` is named by both include and exclude -> dropped.
    got = select(ITEMS, key=_name, include=["train/a", "train/b"], exclude=["train/a"])
    assert got == ["train/b"]


def test_duplicate_entries_are_idempotent():
    assert select(ITEMS, key=_name, include=["train/a", "train/a"]) == ["train/a"]


def test_output_keeps_source_order():
    items = ("val/c", "train/a", "train/b")
    got = select(items, key=_name, include=["train/a", "val/c", "train/b"])
    assert got == ["val/c", "train/a", "train/b"]


# --- filters (dict, instance, mixed) ----------------------------------------


def test_include_filterdict_glob():
    got = select(ITEMS, key=_name, include={"kind": "glob", "pattern": "train/*"})
    assert got == ["train/a", "train/b"]


def test_include_filter_instance():
    assert select(ITEMS, key=_name, include=Glob("train/*")) == ["train/a", "train/b"]


def test_include_single_filterdict_in_list():
    got = select(ITEMS, key=_name, include=[{"kind": "glob", "pattern": "train/*"}])
    assert got == ["train/a", "train/b"]


def test_include_mixes_subpath_and_filterdict():
    got = select(
        ITEMS, key=_name, include=["val/c", {"kind": "glob", "pattern": "train/*"}]
    )
    assert got == ["train/a", "train/b", "val/c"]


def test_include_mixes_subpath_and_filter_instance():
    got = select(ITEMS, key=_name, include=["val/c", Glob("train/*")])
    assert got == ["train/a", "train/b", "val/c"]


# --- .txt listing files -----------------------------------------------------


def test_txt_listing(tmp_path: Path):
    listing = tmp_path / "keep.txt"
    listing.write_text(
        "train/a\n\n# a whole-line comment\nval/c   # trailing comment\n",
        encoding="utf-8",
    )
    assert select(ITEMS, key=_name, include=listing) == ["train/a", "val/c"]


def test_txt_listing_only_comments_is_no_restriction(tmp_path: Path):
    listing = tmp_path / "empty.txt"
    listing.write_text("# only a comment\n\n", encoding="utf-8")
    assert select(ITEMS, key=_name, include=listing) == list(ITEMS)


def test_txt_listing_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        select(ITEMS, key=_name, include=tmp_path / "nope.txt")


# --- .json filter files -----------------------------------------------------


def test_json_object(tmp_path: Path):
    spec = tmp_path / "f.json"
    spec.write_text('{"kind": "glob", "pattern": "train/*"}', encoding="utf-8")
    assert select(ITEMS, key=_name, include=spec) == ["train/a", "train/b"]


def test_json_array(tmp_path: Path):
    spec = tmp_path / "f.json"
    spec.write_text('["train/a", "val/c"]', encoding="utf-8")
    assert select(ITEMS, key=_name, include=spec) == ["train/a", "val/c"]


def test_json_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        select(ITEMS, key=_name, include=tmp_path / "nope.json")


def test_json_scalar_raises(tmp_path: Path):
    spec = tmp_path / "f.json"
    spec.write_text("42", encoding="utf-8")
    with pytest.raises(ValueError, match="object or array"):
        select(ITEMS, key=_name, include=spec)


# --- validation of exact names ----------------------------------------------


def test_unmatched_include_name_raises():
    with pytest.raises(ValueError, match="no such item"):
        select(ITEMS, key=_name, include=["train/a", "nope"])


def test_unmatched_exclude_name_raises():
    with pytest.raises(ValueError, match="no such item"):
        select(ITEMS, key=_name, exclude=["nope"])


def test_unmatched_message_lists_every_missing_name_sorted():
    with pytest.raises(ValueError, match="include names no such item: aaa, zzz"):
        select(ITEMS, key=_name, include=["zzz", "aaa"])


def test_open_pattern_matching_nothing_does_not_raise():
    assert select(ITEMS, key=_name, include=Glob("zzz/*")) == []


def test_malformed_filterdict_raises():
    with pytest.raises(ValueError, match="unknown filter kind"):
        select(ITEMS, key=_name, include={"kind": "nope"})


# --- key ---------------------------------------------------------------------


def test_key_names_each_item():
    items = ({"name": "train/a"}, {"name": "val/c"})
    got = select(items, key=lambda item: item["name"], include=["train/a"])
    assert got == [{"name": "train/a"}]


# --- resolve_selector (public front end) ------------------------------------


def test_resolve_none_is_none():
    assert resolve_selector(None) is None


def test_resolve_empty_sequence_is_none():
    assert resolve_selector([]) is None


def test_resolve_returns_a_matching_filter():
    resolved = resolve_selector(["train/a", "val/c"])
    assert isinstance(resolved, Filter)
    assert resolved.matches("train/a")
    assert not resolved.matches("train/b")


def test_resolve_filterdict():
    resolved = resolve_selector({"kind": "glob", "pattern": "train/*"})
    assert resolved is not None
    assert resolved.matches("train/a")
    assert not resolved.matches("val/c")


def test_resolve_txt_file(tmp_path: Path):
    listing = tmp_path / "keep.txt"
    listing.write_text("train/a\n# comment\n", encoding="utf-8")
    resolved = resolve_selector(listing)
    assert resolved is not None
    assert resolved.matches("train/a")


def test_resolve_lets_include_and_exclude_apply_independently():
    include = resolve_selector(["train/a", "train/b"])
    exclude = resolve_selector("train/b")  # single inline subpath
    assert include is not None
    assert exclude is not None

    names = ["train/a", "train/b", "val/c"]
    kept = [n for n in names if include.matches(n) and not exclude.matches(n)]
    assert kept == ["train/a"]


# --- is_spec_file / SPEC_FILE_SUFFIXES --------------------------------------


@pytest.mark.parametrize("suffix", SPEC_FILE_SUFFIXES)
def test_listed_suffix_is_read_as_a_file(suffix: str):
    # `is_spec_file` agrees with `_load`: a listed suffix is read (raises on a
    # missing file), not treated as an inline name.
    assert is_spec_file(f"missing{suffix}")
    with pytest.raises(FileNotFoundError):
        resolve_selector(f"missing{suffix}")


def test_suffix_match_is_case_insensitive():
    assert is_spec_file("KEEP.JSON")
    assert is_spec_file("keep.TXT")


def test_non_spec_suffix_and_inline_name_are_not_spec_files():
    assert not is_spec_file("train/a")
    assert not is_spec_file("data.yaml")


def test_dotfile_only_name_is_an_inline_name_not_a_file():
    # a leading-dot name has no suffix, so it is inline, matching `_load`
    assert not is_spec_file(".json")
    resolved = resolve_selector(".json")
    assert resolved is not None
    assert resolved.matches(".json")  # a literal name, not a file read


def test_is_spec_file_accepts_pathlike(tmp_path: Path):
    assert is_spec_file(tmp_path / "x.json")
    assert not is_spec_file(tmp_path / "x")
