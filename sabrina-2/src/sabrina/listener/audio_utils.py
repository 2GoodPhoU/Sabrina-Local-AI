"""Audio device resolution helpers for the listener stack.

The legacy code (`services/hearing/hearing.py` / `rebuild/drafts/old-repo-migration-audit.md`
item #1) carried a pyaudio-based loop that enumerated devices and matched by
name when the system default was unavailable or didn't fit. The rebuild uses
`sounddevice` instead of pyaudio, but the same fallback intent still applies:
on Eric's box the default input device sometimes isn't the one you want, and a
config string like `"Logitech"` should resolve to the matching device index
without the caller having to know its number.

`select_input_device()` is the canonical entry point. It accepts the
`asr.input_device` config field's three accepted shapes — empty/None, a digit
string or int, or a name substring — and resolves to a concrete sounddevice
index (or `None`, meaning "use sounddevice's own default").

Resolution rules, in order:

1. ``None`` or empty string → return ``None``. The caller passes this through to
   sounddevice, which uses ``sd.default.device``.
2. ``int`` or all-digit string → that exact index, validated to have at least
   one input channel. ``ValueError`` if invalid.
3. Non-digit string → case-insensitive substring match against device names,
   restricted to devices with ``max_input_channels > 0``. First match wins.
4. No name match → log a warning and fall back to ``sd.default.device[0]``
   (the system default input). ``RuntimeError`` if even the default has no
   input channels.

The tests in ``sabrina-2/tests/test_audio_utils.py`` inject mock device lists
so the resolver is exercisable on Linux without a real audio backend.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sabrina.logging import get_logger

log = get_logger(__name__)


DeviceDict = Mapping[str, Any]


def _is_input_device(dev: DeviceDict) -> bool:
    """A device is usable for input if it reports at least one input channel."""
    try:
        return int(dev.get("max_input_channels", 0)) > 0
    except (TypeError, ValueError):
        return False


def _device_name(dev: DeviceDict) -> str:
    """Best-effort device name; sounddevice always sets `name`, but be defensive."""
    name = dev.get("name", "")
    return str(name) if name is not None else ""


def _query_devices() -> Sequence[DeviceDict]:
    """Wrap `sd.query_devices()` in a function so tests can monkeypatch it."""
    import sounddevice as sd

    return list(sd.query_devices())


def _query_default_input_index() -> int | None:
    """Wrap `sd.default.device[0]` so tests can monkeypatch it."""
    import sounddevice as sd

    default = sd.default.device
    # `sd.default.device` is a 2-tuple (input, output) on most platforms; on
    # some it's a single int meaning "both". Handle both.
    if isinstance(default, (list, tuple)):
        return int(default[0]) if default and default[0] is not None else None
    if isinstance(default, int):
        return int(default)
    return None


def select_input_device(
    requested: str | int | None,
    *,
    devices: Sequence[DeviceDict] | None = None,
    default_index: int | None = None,
) -> int | None:
    """Resolve an input-device specifier to a concrete sounddevice index.

    Parameters
    ----------
    requested:
        The config value: ``None``, empty string, an integer, an all-digit
        string (treated as int), or a non-digit name substring.
    devices:
        Optional device list (each entry shaped like a `sd.query_devices()`
        result dict). Tests pass this directly; production calls leave it
        ``None`` so the resolver queries sounddevice.
    default_index:
        Optional default input index. Tests pass this directly; production
        calls leave it ``None`` so the resolver queries sounddevice.

    Returns
    -------
    int | None
        The resolved device index, or ``None`` to defer to sounddevice's
        default (i.e. the caller can pass ``device=None`` to ``sd.rec`` /
        ``sd.InputStream``).

    Raises
    ------
    ValueError
        If ``requested`` is an int / digit-string and either out of range or
        has no input channels.
    RuntimeError
        If ``requested`` is a non-digit string with no name match and the
        default input device is also unusable (no input channels, or no
        default at all).
    """
    # Case 1: empty / None — defer to sounddevice's default.
    if requested is None or (isinstance(requested, str) and requested.strip() == ""):
        log.debug("audio.device.select.default", requested=str(requested))
        return None

    if devices is None:
        devices = _query_devices()

    # Case 2: explicit integer (or all-digit string) — return that index after
    # validating it has input channels.
    int_index: int | None = None
    if isinstance(requested, int) and not isinstance(requested, bool):
        int_index = requested
    elif isinstance(requested, str) and requested.strip().lstrip("-").isdigit():
        int_index = int(requested.strip())

    if int_index is not None:
        if int_index < 0 or int_index >= len(devices):
            raise ValueError(
                f"audio.device.select: requested index {int_index} is out of range "
                f"(have {len(devices)} devices)"
            )
        if not _is_input_device(devices[int_index]):
            raise ValueError(
                f"audio.device.select: device index {int_index} "
                f"({_device_name(devices[int_index])!r}) has no input channels"
            )
        log.info(
            "audio.device.select.by_index",
            index=int_index,
            name=_device_name(devices[int_index]),
        )
        return int_index

    # Case 3: name substring — find the first input-capable device whose name
    # contains the requested substring (case-insensitive).
    needle = str(requested).strip().lower()
    for index, dev in enumerate(devices):
        if not _is_input_device(dev):
            continue
        if needle in _device_name(dev).lower():
            log.info(
                "audio.device.select.by_name",
                requested=str(requested),
                index=index,
                name=_device_name(dev),
            )
            return index

    # Case 4: fall back to system default.
    if default_index is None:
        default_index = _query_default_input_index()

    if default_index is None or not (0 <= default_index < len(devices)):
        raise RuntimeError(
            f"audio.device.select: no device matches {str(requested)!r} "
            f"and no usable system default input is available"
        )
    if not _is_input_device(devices[default_index]):
        raise RuntimeError(
            f"audio.device.select: no device matches {str(requested)!r} "
            f"and the system default (index {default_index}, "
            f"{_device_name(devices[default_index])!r}) has no input channels"
        )

    log.warning(
        "audio.device.select.fallback_to_default",
        requested=str(requested),
        default_index=default_index,
        default_name=_device_name(devices[default_index]),
    )
    return default_index


__all__ = ["select_input_device"]
