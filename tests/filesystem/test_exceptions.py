from __future__ import annotations

import pytest

from kaparoo.filesystem.exceptions import UnsupportedExtensionError


def test_message_and_attributes():
    err = UnsupportedExtensionError("xyz", ["bin", "txt"])
    assert isinstance(err, ValueError)
    assert err.ext == "xyz"
    assert err.supported == ("bin", "txt")
    assert err.kind == ""
    assert str(err) == "unsupported extension 'xyz' (supported: 'bin', 'txt')"


def test_kind_labels_the_message():
    err = UnsupportedExtensionError("xyz", ["bin"], kind="phase")
    assert err.kind == "phase"
    assert str(err) == "unsupported extension 'xyz' for phase (supported: 'bin')"


def test_normalizes_dedups_and_drops_empties():
    err = UnsupportedExtensionError(".XYZ", [".bin", "bin", " txt ", "."])
    assert err.ext == "XYZ"  # leading dot stripped, case kept
    assert err.supported == ("bin", "txt")  # normalized, de-duplicated, "." dropped


def test_empty_expected_is_rejected():
    with pytest.raises(ValueError, match="at least one extension"):
        UnsupportedExtensionError("xyz", [])
    with pytest.raises(ValueError, match="at least one extension"):
        UnsupportedExtensionError("xyz", [".", "  "])  # all normalize to empty
