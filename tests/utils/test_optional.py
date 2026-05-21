from __future__ import annotations

from kaparoo.utils.optional import (
    factory_if_none,
    replace_if_none,
    unwrap_or_default,
    unwrap_or_defaults,
    unwrap_or_factories,
    unwrap_or_factory,
)


def test_replace_if_none():
    assert replace_if_none(None, 42) == 42
    assert replace_if_none("value", 42) == "value"


def test_unwrap_or_default():
    assert unwrap_or_default(None, "default") == "default"
    assert unwrap_or_default("value", "default") == "value"
    assert unwrap_or_default(None, "default", str.upper) == "DEFAULT"
    assert unwrap_or_default("value", "default", str.upper) == "VALUE"


def test_unwrap_or_defaults():
    optionals = [None, "value1", None, "value2"]

    result1 = unwrap_or_defaults(optionals, "default")
    assert result1 == ["default", "value1", "default", "value2"]

    result2 = unwrap_or_defaults(optionals, "default", str.upper)
    assert result2 == ["DEFAULT", "VALUE1", "DEFAULT", "VALUE2"]


def test_factory_if_none():
    assert factory_if_none(None, lambda: 42) == 42
    assert factory_if_none("value", lambda: 42) == "value"


def test_unwrap_or_factory():
    assert unwrap_or_factory(None, lambda: "factory") == "factory"
    assert unwrap_or_factory("value", lambda: "factory") == "value"
    assert unwrap_or_factory(None, lambda: "factory", str.upper) == "FACTORY"
    assert unwrap_or_factory("value", lambda: "factory", str.upper) == "VALUE"


def test_unwrap_or_factories():
    optionals = [None, "value1", None, "value2"]

    result1 = unwrap_or_factories(optionals, lambda: "factory")
    assert result1 == ["factory", "value1", "factory", "value2"]

    result2 = unwrap_or_factories(optionals, lambda: "factory", str.upper)
    assert result2 == ["FACTORY", "VALUE1", "FACTORY", "VALUE2"]
