"""Byte-size multipliers for readable file-size values.

Decimal (SI, powers of 1000) and binary (IEC, powers of 1024) units --
`Size(max=5 * MB)`, `TreeSize(max=2 * GIB)`. Each is a plain `int` count of
bytes, so a unit multiplies and serializes like any integer; pick the name
for the convention you mean (`MB` is 1,000,000, `MIB` is 1,048,576).
"""

from __future__ import annotations

__all__ = ("GB", "GIB", "KB", "KIB", "MB", "MIB", "TB", "TIB")

# Decimal (SI) -- powers of 1000.
KB = 10**3
MB = 10**6
GB = 10**9
TB = 10**12

# Binary (IEC) -- powers of 1024.
KIB = 2**10
MIB = 2**20
GIB = 2**30
TIB = 2**40
