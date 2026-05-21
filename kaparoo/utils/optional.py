from __future__ import annotations

__all__ = (
    "factory_if_none",
    "replace_if_none",
    "unwrap_or_default",
    "unwrap_or_defaults",
    "unwrap_or_factories",
    "unwrap_or_factory",
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


# ========================== #
#          Replace           #
# ========================== #


def replace_if_none[T](optional: T | None, surrogate: T) -> T:
    """Replace the value if it is None.

    Args:
        optional: The optional value to be checked.
        surrogate: The value to be returned if `optional` is None.

    Returns:
        The `optional` value if it is not None, otherwise the `surrogate` value.
    """
    return surrogate if optional is None else optional


def unwrap_or_default[T](
    optional: T | None,
    default: T,
    callback: Callable[[T], T] | None = None,
) -> T:
    """Unwrap the optional value or replace it with a default if it is None.

    Args:
        optional: The optional value to be checked.
        default: The value to be returned if `optional` is None.
        callback: An optional callable to be applied to the result. If provided,
            it is applied to the result before returning. Defaults to None.

    Returns:
        The `optional` value if it is not None, otherwise the `default` value.
    """
    result = replace_if_none(optional, default)
    return callback(result) if callable(callback) else result


def unwrap_or_defaults[T](
    optionals: Sequence[T | None],
    default: T,
    callback: Callable[[T], T] | None = None,
) -> Sequence[T]:
    """Unwrap a sequence of optional values or replace them with default values if they are None.

    Args:
        optionals: The sequence of optional values to be checked.
        default: The value to be used for elements that are None.
        callback: An optional callable to be applied to the result. If provided,
            it is applied to the result before returning. Defaults to None.

    Returns:
        A sequence containing the unwrapped values from `optionals` or their defaults.
    """
    return [unwrap_or_default(optional, default, callback) for optional in optionals]


# ========================== #
#          Factory           #
# ========================== #


def factory_if_none[T](optional: T | None, factory: Callable[[], T]) -> T:
    """Replace the value using the factory if it is None.

    Args:
        optional: The optional value to be checked.
        factory: A callable that creates a value if `optional` is None.

    Returns:
        The `optional` value if it is not None, otherwise the value created by `factory`.
    """
    return factory() if optional is None else optional


def unwrap_or_factory[T](
    optional: T | None,
    factory: Callable[[], T],
    callback: Callable[[T], T] | None = None,
) -> T:
    """Unwrap the optional value or replace it using the factory if it is None.

    Args:
        optional: The optional value to be checked.
        factory: A callable that creates a value if `optional` is None.
        callback: An optional callable to be applied to the result. If provided,
            it is applied to the result before returning. Defaults to None.

    Returns:
        The `optional` value if it is not None, otherwise the value created by `factory`.
    """
    result = factory_if_none(optional, factory)
    return callback(result) if callable(callback) else result


def unwrap_or_factories[T](
    optionals: Sequence[T | None],
    factory: Callable[[], T],
    callback: Callable[[T], T] | None = None,
) -> Sequence[T]:
    """Unwrap a sequence of optional values or replace them using a factory if they are None.

    Args:
        optionals: The sequence of optional values to be checked.
        factory: A callable that creates a value for elements that are None.
        callback: An optional callable to be applied to the result. If provided,
            it is applied to the result before returning. Defaults to None.

    Returns:
        A sequence containing the unwrapped values from `optionals` or values created by `factory`.
    """
    return [unwrap_or_factory(optional, factory, callback) for optional in optionals]
