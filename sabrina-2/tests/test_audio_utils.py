"""Unit tests for `sabrina.listener.audio_utils.select_input_device`.

Mocks the sounddevice device-list shape so the resolver is exercisable on
Linux without PortAudio. Each test injects a `devices` list directly, and
where relevant a `default_index` override, so the production `_query_devices`
and `_query_default_input_index` paths are not touched.
"""

from __future__ import annotations

import pytest

from sabrina.listener.audio_utils import select_input_device


# A representative device list shaped like sounddevice's `query_devices()`
# output. Indices 0/2 are input-capable; 1/3 are output-only.
SAMPLE_DEVICES: list[dict] = [
    {"name": "Default Mic Array (Realtek)", "max_input_channels": 2, "max_output_channels": 0},
    {"name": "Speakers (Realtek)", "max_input_channels": 0, "max_output_channels": 2},
    {"name": "Logitech BRIO USB Microphone", "max_input_channels": 1, "max_output_channels": 0},
    {"name": "NVIDIA Broadcast (Output)", "max_input_channels": 0, "max_output_channels": 2},
    {"name": "Mapper - Input", "max_input_channels": 2, "max_output_channels": 0},
]


# ---------------------------------------------------------------------------
# Case 1: None / empty string defers to sounddevice's default
# ---------------------------------------------------------------------------


def test_none_returns_none() -> None:
    assert select_input_device(None, devices=SAMPLE_DEVICES, default_index=0) is None


def test_empty_string_returns_none() -> None:
    assert select_input_device("", devices=SAMPLE_DEVICES, default_index=0) is None


def test_whitespace_only_returns_none() -> None:
    assert select_input_device("   ", devices=SAMPLE_DEVICES, default_index=0) is None


# ---------------------------------------------------------------------------
# Case 2: explicit integer / digit string
# ---------------------------------------------------------------------------


def test_int_index_returns_index() -> None:
    assert select_input_device(2, devices=SAMPLE_DEVICES, default_index=0) == 2


def test_digit_string_returns_index() -> None:
    assert select_input_device("2", devices=SAMPLE_DEVICES, default_index=0) == 2


def test_digit_string_with_whitespace_returns_index() -> None:
    assert select_input_device(" 2 ", devices=SAMPLE_DEVICES, default_index=0) == 2


def test_int_index_out_of_range_raises_value_error() -> None:
    with pytest.raises(ValueError, match="out of range"):
        select_input_device(99, devices=SAMPLE_DEVICES, default_index=0)


def test_int_index_negative_raises_value_error() -> None:
    with pytest.raises(ValueError, match="out of range"):
        select_input_device(-1, devices=SAMPLE_DEVICES, default_index=0)


def test_int_index_pointing_at_output_only_raises_value_error() -> None:
    # Index 1 is "Speakers" — output-only.
    with pytest.raises(ValueError, match="no input channels"):
        select_input_device(1, devices=SAMPLE_DEVICES, default_index=0)


def test_digit_string_pointing_at_output_only_raises_value_error() -> None:
    with pytest.raises(ValueError, match="no input channels"):
        select_input_device("3", devices=SAMPLE_DEVICES, default_index=0)


# ---------------------------------------------------------------------------
# Case 3: name substring match
# ---------------------------------------------------------------------------


def test_name_substring_exact_match() -> None:
    assert (
        select_input_device("Logitech BRIO USB Microphone", devices=SAMPLE_DEVICES, default_index=0)
        == 2
    )


def test_name_substring_partial_match() -> None:
    assert select_input_device("Logitech", devices=SAMPLE_DEVICES, default_index=0) == 2


def test_name_substring_case_insensitive() -> None:
    assert select_input_device("logitech", devices=SAMPLE_DEVICES, default_index=0) == 2
    assert select_input_device("LOGITECH", devices=SAMPLE_DEVICES, default_index=0) == 2


def test_name_substring_first_match_wins() -> None:
    # Both index 0 ("Default Mic Array (Realtek)") and index 4 ("Mapper - Input")
    # contain a vowel; "Realtek" is in index 0's name only — verify first-wins.
    devices = [
        {"name": "Foo Realtek", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "Bar Realtek", "max_input_channels": 1, "max_output_channels": 0},
    ]
    assert select_input_device("Realtek", devices=devices, default_index=0) == 0


def test_name_substring_skips_output_only_devices() -> None:
    # "NVIDIA" is in index 3 — but that's output-only. Should NOT match;
    # should fall back to default with a warning.
    result = select_input_device("NVIDIA", devices=SAMPLE_DEVICES, default_index=0)
    assert result == 0  # fell back to default (index 0, an input device)


# ---------------------------------------------------------------------------
# Case 4: fallback to default when no name matches
# ---------------------------------------------------------------------------


def test_no_match_falls_back_to_default() -> None:
    assert (
        select_input_device("NonexistentDevice", devices=SAMPLE_DEVICES, default_index=0)
        == 0
    )


def test_no_match_default_index_invalid_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="no usable system default"):
        select_input_device(
            "NonexistentDevice", devices=SAMPLE_DEVICES, default_index=None
        )


def test_no_match_default_index_out_of_range_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError, match="no usable system default"):
        select_input_device(
            "NonexistentDevice", devices=SAMPLE_DEVICES, default_index=99
        )


def test_no_match_default_is_output_only_raises_runtime_error() -> None:
    # Default points at "Speakers" (output-only). Should raise rather than
    # silently return an unusable index.
    with pytest.raises(RuntimeError, match="no input channels"):
        select_input_device(
            "NonexistentDevice", devices=SAMPLE_DEVICES, default_index=1
        )


# ---------------------------------------------------------------------------
# Defensive shapes
# ---------------------------------------------------------------------------


def test_device_with_missing_max_input_channels_treated_as_non_input() -> None:
    # Some sounddevice backends omit `max_input_channels` entirely on certain
    # device kinds. The resolver should treat that as "not an input device"
    # rather than raising KeyError.
    devices = [
        {"name": "Weird Device"},  # no max_input_channels
        {"name": "Real Mic", "max_input_channels": 1, "max_output_channels": 0},
    ]
    assert select_input_device("Real Mic", devices=devices, default_index=1) == 1


def test_device_with_non_int_max_input_channels_treated_as_non_input() -> None:
    devices = [
        {"name": "Bad Channel Count", "max_input_channels": "two"},
        {"name": "Real Mic", "max_input_channels": 1, "max_output_channels": 0},
    ]
    assert select_input_device("Bad", devices=devices, default_index=1) == 1
    # Falls back to default since the only "Bad" match is a non-input device.


def test_empty_device_list_with_no_match_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        select_input_device("anything", devices=[], default_index=None)


def test_int_index_against_empty_device_list_raises_value_error() -> None:
    with pytest.raises(ValueError, match="out of range"):
        select_input_device(0, devices=[], default_index=None)
