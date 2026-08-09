"""Small text helpers."""

from __future__ import annotations

__all__ = ("quantify",)


def quantify(count: int, noun: str, plural: str | None = None) -> str:
    """Return `count` followed by `noun`, pluralized for every count but one.

    Args:
        count: How many there are.
        noun: The singular form.
        plural: The form for every count but one, or `None` to append `"s"` to
            `noun`. Since it is the whole word, it also covers an irregular
            plural a suffix cannot (a stem change or a replacement).
    """
    if count == 1:
        return f"{count} {noun}"

    word = plural if plural is not None else f"{noun}s"
    return f"{count} {word}"
