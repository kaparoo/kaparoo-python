from __future__ import annotations

from kaparoo.filesystem import GB, GIB, KB, KIB, MB, MIB, TB, TIB
from kaparoo.filesystem.hierarchy.conditions import Size, TreeSize


def test_decimal_units_are_powers_of_1000():
    assert (KB, MB, GB, TB) == (1_000, 1_000_000, 1_000_000_000, 1_000_000_000_000)


def test_binary_units_are_powers_of_1024():
    assert (KIB, MIB, GIB, TIB) == (
        1_024,
        1_048_576,
        1_073_741_824,
        1_099_511_627_776,
    )


def test_units_are_plain_int_multipliers_for_size_conditions():
    # A unit is a plain int; the stored / serialized bound is always bytes.
    assert Size(max=5 * MB).to_dict() == {"kind": "size", "max": 5_000_000}
    assert TreeSize(min=2 * GIB).to_dict() == {
        "kind": "tree_size",
        "min": 2_147_483_648,
    }
