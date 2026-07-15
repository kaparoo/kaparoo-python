from __future__ import annotations

from kaparoo.utils.optional import (
    factory_if_none,
    fold_optional,
    fold_optionals,
    replace_if_none,
    unwrap_or_default,
    unwrap_or_defaults,
    unwrap_or_factories,
    unwrap_or_factory,
)


def test_replace_if_none():
    assert replace_if_none(None, 42) == 42
    assert replace_if_none("value", 42) == "value"


def test_factory_if_none():
    assert factory_if_none(None, lambda: 42) == 42
    assert factory_if_none("value", lambda: 42) == "value"


def test_unwrap_or_default():
    # `transform` is applied to both the wrapped value and the default.
    assert unwrap_or_default(None, "default") == "default"
    assert unwrap_or_default("value", "default") == "value"
    assert unwrap_or_default(None, "default", str.upper) == "DEFAULT"
    assert unwrap_or_default("value", "default", str.upper) == "VALUE"


def test_unwrap_or_factory():
    assert unwrap_or_factory(None, lambda: "factory") == "factory"
    assert unwrap_or_factory("value", lambda: "factory") == "value"
    assert unwrap_or_factory(None, lambda: "factory", str.upper) == "FACTORY"
    assert unwrap_or_factory("value", lambda: "factory", str.upper) == "VALUE"


def test_unwrap_or_defaults():
    optionals = [None, "value1", None, "value2"]
    assert unwrap_or_defaults(optionals, "default") == [
        "default",
        "value1",
        "default",
        "value2",
    ]
    assert unwrap_or_defaults(optionals, "default", str.upper) == [
        "DEFAULT",
        "VALUE1",
        "DEFAULT",
        "VALUE2",
    ]


def test_unwrap_or_factories():
    optionals = [None, "value1", None, "value2"]
    assert unwrap_or_factories(optionals, lambda: "factory") == [
        "factory",
        "value1",
        "factory",
        "value2",
    ]
    assert unwrap_or_factories(optionals, lambda: "factory", str.upper) == [
        "FACTORY",
        "VALUE1",
        "FACTORY",
        "VALUE2",
    ]


def test_factory_not_called_on_present_value():
    # Lazy-factory contract: a present value short-circuits, so the factory --
    # and any side effect it carries -- never runs.
    calls = 0

    def factory() -> str:
        nonlocal calls
        calls += 1
        return "fallback"

    assert factory_if_none("value", factory) == "value"
    assert unwrap_or_factory("value", factory) == "value"
    assert unwrap_or_factories(["a", "b"], factory) == ["a", "b"]
    assert calls == 0

    # The factory still fires, once per None, when a fallback is actually needed.
    assert unwrap_or_factories([None, "b", None], factory) == [
        "fallback",
        "b",
        "fallback",
    ]
    assert calls == 2


def test_fold_optional_branches_on_presence():
    assert fold_optional(None, lambda index: f"{index=}", "global") == "global"
    assert fold_optional(3, lambda index: f"{index=}", "global") == "index=3"


def test_fold_optional_changes_type():
    # int | None -> str, and the present branch transforms the value.
    assert fold_optional(0, str, "none") == "0"
    assert fold_optional(None, str, "none") == "none"


def test_fold_optional_transform_not_called_for_none():
    # The present-branch transform (and any side effect) never runs on None.
    calls = 0

    def transform(value: int) -> int:
        nonlocal calls
        calls += 1
        return value + 1

    assert fold_optional(None, transform, -1) == -1
    assert calls == 0

    assert fold_optional(41, transform, -1) == 42
    assert calls == 1


def test_fold_optional_falsy_present_value_takes_transform_branch():
    # `is not None`, not truthiness: 0 / "" / [] are present, so `transform` runs.
    assert fold_optional(0, lambda _: "some", "none") == "some"
    assert fold_optional("", lambda _: "some", "none") == "some"
    assert fold_optional([], lambda _: "some", "none") == "some"


def test_fold_optionals_maps_element_wise():
    assert fold_optionals([1, None, 2], str, "-") == ["1", "-", "2"]
    assert fold_optionals([], str, "-") == []
    assert fold_optionals([None, None], lambda i: f"{i}", "none") == ["none", "none"]


def test_fold_optionals_transform_only_for_present():
    calls = 0

    def transform(value: int) -> int:
        nonlocal calls
        calls += 1
        return value + 1

    assert fold_optionals([None, 1, None, 2], transform, -1) == [-1, 2, -1, 3]
    assert calls == 2  # once per present element, never for a None


def test_optional_helpers_reexported_from_package():
    from kaparoo import utils

    assert utils.factory_if_none is factory_if_none
    assert utils.fold_optional is fold_optional
    assert utils.fold_optionals is fold_optionals
    assert utils.replace_if_none is replace_if_none
    assert utils.unwrap_or_default is unwrap_or_default
    assert utils.unwrap_or_defaults is unwrap_or_defaults
    assert utils.unwrap_or_factories is unwrap_or_factories
    assert utils.unwrap_or_factory is unwrap_or_factory
