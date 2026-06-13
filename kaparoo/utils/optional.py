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
    """Return `optional`, or `surrogate` when `optional` is None."""
    return surrogate if optional is None else optional


def unwrap_or_default[T](
    optional: T | None,
    default: T,
    callback: Callable[[T], T] | None = None,
) -> T:
    """Unwrap `optional`, falling back to `default` when it is None.

    Args:
        optional: The value to unwrap; `None` triggers the fallback.
        default: The fallback returned when `optional` is None.
        callback: If given, applied to the chosen value before returning --
            including a substituted `default`, not only an unwrapped
            `optional`.
    """
    result = replace_if_none(optional, default)
    return callback(result) if callback is not None else result


def unwrap_or_defaults[T](
    optionals: Sequence[T | None],
    default: T,
    callback: Callable[[T], T] | None = None,
) -> list[T]:
    """Unwrap each value in `optionals`, substituting `default` for None.

    Args:
        optionals: The values to unwrap; each `None` triggers the fallback.
        default: The fallback used for every None element.
        callback: If given, applied to each result element -- substituted
            defaults included.
    """
    if callback is None:
        return [default if o is None else o for o in optionals]
    return [callback(default if o is None else o) for o in optionals]


# ========================== #
#          Factory           #
# ========================== #


def factory_if_none[T](optional: T | None, factory: Callable[[], T]) -> T:
    """Return `optional`, or `factory()` when `optional` is None."""
    return factory() if optional is None else optional


def unwrap_or_factory[T](
    optional: T | None,
    factory: Callable[[], T],
    callback: Callable[[T], T] | None = None,
) -> T:
    """Unwrap `optional`, calling `factory` for the fallback when it is None.

    Args:
        optional: The value to unwrap; `None` triggers the fallback.
        factory: Called to produce the fallback when `optional` is None.
        callback: If given, applied to the chosen value before returning --
            including the `factory()` result, not only an unwrapped
            `optional`.
    """
    result = factory_if_none(optional, factory)
    return callback(result) if callback is not None else result


def unwrap_or_factories[T](
    optionals: Sequence[T | None],
    factory: Callable[[], T],
    callback: Callable[[T], T] | None = None,
) -> list[T]:
    """Unwrap each value in `optionals`, calling `factory` for None.

    Args:
        optionals: The values to unwrap; each `None` triggers the fallback.
        factory: Called to produce the fallback for every None element.
        callback: If given, applied to each result element -- factory
            results included.
    """
    if callback is None:
        return [o if o is not None else factory() for o in optionals]
    return [callback(o if o is not None else factory()) for o in optionals]
