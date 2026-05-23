"""Clipboard tool handlers — `write_clipboard` (and future `read_clipboard`).

Per the toolspec research doc (`rebuild/drafts/research/2026-04-26-toolspec
-first-three.md`), `write_clipboard` is the first write-side tool because
it's reversible (the user can copy something else over it), needs no auth,
no network, and adds zero new framework machinery beyond the registry.

Implementation order of preference for the backend:

  1. `pyperclip` — pure-Python, MIT-licensed, ~150 LOC wheel, supports
     Windows / macOS / Linux. Tiny enough to be a default dep.
  2. Native subprocess fallback — `clip` on Windows, `pbcopy` on macOS,
     `xclip`/`xsel` on Linux. Used only if `pyperclip` import fails so a
     broken install still lets the tool run.

The handler is async-shaped (matches `ToolHandler`) but the underlying
clipboard call is synchronous — we wrap it in `asyncio.to_thread` to keep
the brain's event loop responsive when the OS clipboard is contended.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Any


_MAX_BYTES = 100_000  # Mirror the schema's maxLength; truncate beyond.


def _set_clipboard_pyperclip(text: str) -> None:
    """Use the pyperclip backend. Raises on import failure."""
    import pyperclip  # type: ignore[import-not-found]

    pyperclip.copy(text)


def _set_clipboard_native(text: str) -> None:
    """Native-subprocess fallback. Per-platform commands.

    Windows: `clip` reads stdin and writes to the clipboard. UTF-16 LE
    is the format Windows clipboard expects natively, but `clip.exe` does
    code-page conversion from stdin — UTF-8 in, native out. Good enough
    for ASCII; non-ASCII may garble. Pyperclip is preferred for that
    reason.

    macOS: `pbcopy` accepts UTF-8 on stdin, writes to the general
    pasteboard.

    Linux: tries `xclip -selection clipboard` first, then `xsel
    --clipboard --input`. If neither is on PATH, raises a RuntimeError.
    """
    if sys.platform == "win32":
        cmd = ["clip"]
    elif sys.platform == "darwin":
        cmd = ["pbcopy"]
    else:
        # Try xclip first; fall through to xsel.
        for candidate in (
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                proc = subprocess.run(
                    candidate,
                    input=text.encode("utf-8"),
                    check=True,
                    timeout=5.0,
                )
                if proc.returncode == 0:
                    return
            except FileNotFoundError:
                continue
        raise RuntimeError(
            "No clipboard backend on PATH. Install `xclip` or `xsel`, "
            "or `pip install pyperclip`."
        )
    subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5.0)


def _set_clipboard_sync(text: str) -> None:
    """Try pyperclip; on import-or-runtime failure, fall back to native."""
    try:
        _set_clipboard_pyperclip(text)
        return
    except Exception:  # noqa: BLE001 - fall through to native
        pass
    _set_clipboard_native(text)


async def write_clipboard(content: str = "", **_extra: Any) -> dict[str, Any]:
    """Place plain text on the user's clipboard.

    Args:
        content: text to copy. Truncated to 100 KB.

    Returns:
        ``{"success": bool, "length": int}`` — `length` is the byte
        length actually written (post-truncation).

    The brain calls this via the `ToolSpec` registry; `**_extra`
    swallows any unknown kwargs so we don't blow up on a model that
    pads the call with unexpected fields. Defensive but cheap.
    """
    if not isinstance(content, str):
        return {"success": False, "length": 0, "error": "content must be a string"}
    encoded = content.encode("utf-8")
    truncated = len(encoded) > _MAX_BYTES
    if truncated:
        # Char-level truncate by re-encoding from a slice that's
        # guaranteed shorter than the byte cap. ASCII-safe and won't
        # split a UTF-8 multibyte sequence.
        content = content[: _MAX_BYTES // 4]
        encoded = content.encode("utf-8")
    try:
        await asyncio.to_thread(_set_clipboard_sync, content)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "length": 0, "error": str(exc)}
    return {"success": True, "length": len(encoded)}
