from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from kaparoo.filesystem.hierarchy.conditions import (
    And,
    CheckContext,
    ChildCount,
    Condition,
    Content,
    Empty,
    NonEmpty,
    Not,
    Or,
    Size,
    TreeSize,
    register_condition,
)

if TYPE_CHECKING:
    from pathlib import Path


def make_file(path: Path, size: int = 0) -> Path:
    path.write_bytes(b"x" * size)
    return path


class TestSize:
    def test_min_and_max_bounds(self, tmp_path: Path) -> None:
        f = make_file(tmp_path / "f", size=5)
        assert Size(min=5).check(f)
        assert Size(min=6).check(f) is False
        assert Size(max=5).check(f)
        assert Size(max=4).check(f) is False
        assert Size(min=3, max=7).check(f)

    def test_requires_a_bound(self) -> None:
        with pytest.raises(ValueError, match="at least one of min / max"):
            Size()

    def test_rejects_max_below_min(self) -> None:
        with pytest.raises(ValueError, match="below min"):
            Size(min=10, max=5)

    def test_round_trips(self) -> None:
        size = Size(min=1, max=100)
        assert size.to_dict() == {"kind": "size", "min": 1, "max": 100}
        assert Condition.from_dict(size.to_dict()) == size
        # each bound is omitted when unset
        assert Size(min=1).to_dict() == {"kind": "size", "min": 1}
        assert Size(max=9).to_dict() == {"kind": "size", "max": 9}


class TestChildCount:
    def test_counts_entries(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        (d / "a").touch()
        (d / "b").touch()
        assert ChildCount(min=2).check(d)
        assert ChildCount(min=3).check(d) is False
        assert ChildCount(max=2).check(d)

    def test_only_counts_the_selected_kind(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        (d / "a").touch()
        (d / "b").touch()
        (d / "sub").mkdir()
        assert ChildCount(min=3, max=3).check(d)  # default: 2 files + 1 dir
        assert ChildCount(min=2, max=2, only="files").check(d)
        assert ChildCount(min=1, max=1, only="dirs").check(d)
        assert ChildCount(min=2, only="dirs").check(d) is False

    def test_rejects_invalid_only(self) -> None:
        with pytest.raises(ValueError, match="`only` must be"):
            ChildCount(min=1, only="links")

    def test_round_trips(self) -> None:
        cc = ChildCount(min=8)
        assert cc.to_dict() == {"kind": "child_count", "min": 8}
        assert Condition.from_dict(cc.to_dict()) == cc
        # `only` is serialized only when set (None default is omitted)
        only_files = ChildCount(min=1, only="files")
        assert only_files.to_dict() == {
            "kind": "child_count",
            "min": 1,
            "only": "files",
        }
        assert Condition.from_dict(only_files.to_dict()) == only_files


class TestTreeSize:
    def test_sums_file_sizes_recursively(self, tmp_path: Path) -> None:
        make_file(tmp_path / "a", size=5)
        sub = tmp_path / "sub"
        sub.mkdir()
        make_file(sub / "b", size=3)
        assert TreeSize(min=8, max=8).check(tmp_path)
        assert TreeSize(max=7).check(tmp_path) is False

    def test_empty_directory_totals_zero(self, tmp_path: Path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        assert TreeSize(max=0).check(d)

    def test_round_trips(self) -> None:
        ts = TreeSize(max=1000)
        assert ts.to_dict() == {"kind": "tree_size", "max": 1000}
        assert Condition.from_dict(ts.to_dict()) == ts


class TestApplicability:
    def test_size_is_file_only(self) -> None:
        assert Size(min=1).applies_to("file")
        assert Size(min=1).applies_to("dir") is False

    def test_child_count_and_tree_size_are_dir_only(self) -> None:
        for cond in (ChildCount(min=1), TreeSize(min=1)):
            assert cond.applies_to("file") is False
            assert cond.applies_to("dir")

    def test_kind_agnostic_conditions_apply_to_both(self) -> None:
        for cond in (Empty(), NonEmpty(), Content("x")):
            assert cond.applies_to("file")
            assert cond.applies_to("dir")

    def test_composite_is_the_intersection_of_children(self) -> None:
        both = And((Empty(), Content("x")))
        assert both.applies_to("file")
        assert both.applies_to("dir")

        file_only = And((Size(min=1), Empty()))
        assert file_only.applies_to("file")
        assert file_only.applies_to("dir") is False

        neither = Or((Size(min=1), ChildCount(min=1)))  # file ∩ dir
        assert neither.applies_to("file") is False
        assert neither.applies_to("dir") is False

    def test_not_delegates_to_its_child(self) -> None:
        assert Not(ChildCount(min=1)).applies_to("file") is False
        assert Not(ChildCount(min=1)).applies_to("dir")


class TestEmptiness:
    def test_empty_file_and_dir(self, tmp_path: Path) -> None:
        empty_file = make_file(tmp_path / "f", size=0)
        full_file = make_file(tmp_path / "g", size=1)
        empty_dir = tmp_path / "d"
        empty_dir.mkdir()
        full_dir = tmp_path / "e"
        full_dir.mkdir()
        (full_dir / "x").touch()

        assert Empty().check(empty_file)
        assert Empty().check(empty_dir)
        assert Empty().check(full_file) is False
        assert Empty().check(full_dir) is False

        assert NonEmpty().check(full_file)
        assert NonEmpty().check(full_dir)
        assert NonEmpty().check(empty_file) is False
        assert NonEmpty().check(empty_dir) is False

    def test_round_trips(self) -> None:
        for condition in (Empty(), NonEmpty()):
            assert condition.to_dict() == {"kind": condition._kind}  # noqa: SLF001
            assert Condition.from_dict(condition.to_dict()) == condition


class TestContent:
    def test_runs_the_supplied_callable(self, tmp_path: Path) -> None:
        f = make_file(tmp_path / "f", size=3)
        ctx = CheckContext(checks={"big": lambda p: p.stat().st_size > 2})
        assert Content("big").check(f, ctx)
        small = make_file(tmp_path / "g", size=1)
        assert Content("big").check(small, ctx) is False

    def test_missing_check_errors_by_default(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="no check supplied"):
            Content("absent").check(tmp_path)  # default ctx: on_missing="error"

    def test_missing_check_skips_when_configured(self, tmp_path: Path) -> None:
        ctx = CheckContext(on_missing="skip")
        assert Content("absent").check(tmp_path, ctx) is True

    def test_round_trips(self) -> None:
        content = Content("valid_schema")
        assert content.to_dict() == {"kind": "content", "name": "valid_schema"}
        assert Condition.from_dict(content.to_dict()) == content


class TestLogical:
    def test_and_or_not(self, tmp_path: Path) -> None:
        f = make_file(tmp_path / "f", size=5)
        assert And((Size(min=1), Size(max=10))).check(f)
        assert And((Size(min=1), Size(max=4))).check(f) is False
        assert Or((Size(max=4), Size(min=1))).check(f)
        assert Or((Size(max=4), Size(min=9))).check(f) is False
        assert Not(Size(min=9)).check(f)
        assert Not(Size(min=1)).check(f) is False

    def test_threads_context_to_children(self, tmp_path: Path) -> None:
        # Content resolves only via `ctx`, so reaching it proves threading.
        ctx = CheckContext(checks={"ok": lambda _: True})
        empty = make_file(tmp_path / "x", size=0)
        assert And((Content("ok"), Size(max=0))).check(empty, ctx)
        nonempty = make_file(tmp_path / "y", size=3)
        assert And((Content("ok"), Size(max=0))).check(nonempty, ctx) is False

    def test_empty_conjunction_disjunction_raise(self) -> None:
        with pytest.raises(ValueError, match="And requires"):
            And(())
        with pytest.raises(ValueError, match="Or requires"):
            Or(())

    def test_round_trips_nested(self) -> None:
        nested = And((Or((Size(min=1), Empty())), Not(Content("x"))))
        assert Condition.from_dict(nested.to_dict()) == nested


class TestValueSemantics:
    def test_equal_and_hashable(self) -> None:
        assert Size(min=1) == Size(min=1)
        assert Size(min=1) != Size(min=2)
        assert hash(Content("a")) == hash(Content("a"))
        assert {Empty(), Empty()} == {Empty()}


class TestRegistryAndDispatch:
    def test_from_dict_missing_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'kind'"):
            Condition.from_dict({})

    def test_from_dict_unknown_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown condition kind"):
            Condition.from_dict({"kind": "nope"})

    def test_from_dict_null_kind_treated_as_missing(self) -> None:
        # A null discriminator is treated the same as an absent one.
        with pytest.raises(ValueError, match="missing 'kind'"):
            Condition.from_dict({"kind": None})

    def test_from_dict_non_mapping_raises_type_error(self) -> None:
        for bad in (None, 42, "x", ["a"]):
            with pytest.raises(TypeError, match="expected a condition dict"):
                Condition.from_dict(bad)  # ty: ignore[invalid-argument-type]

    def test_register_duplicate_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="already registered"):

            @register_condition("size")  # collides with `Size`
            @dataclass(frozen=True)
            class _Other(Condition):  # never instantiated; the decorator raises
                pass

    def test_subclass_from_dict_not_overridden_raises(self) -> None:
        # A subclass that inherits the base dispatcher (which only dispatches
        # when `cls is Condition`) raises rather than silently mis-constructing.
        class _Unoverridden(Condition):
            pass

        with pytest.raises(NotImplementedError, match="must be overridden"):
            _Unoverridden.from_dict({"kind": "x"})
