"""Global hotkey that *arms* the next voice turn for vision.

When the user presses the bound combo (default Ctrl+Shift+V), this
listener flips an internal `armed` flag. The voice loop checks and
consumes that flag at turn start — press, then PTT-speak your question,
and Sabrina treats that turn as a vision turn.

We don't capture audio or take a screenshot on the hotkey itself. Arming
the next turn keeps the UX simple (same PTT flow) and avoids any
"screenshot without context" weirdness.
"""

from __future__ import annotations

import threading

from sabrina.logging import get_logger

log = get_logger(__name__)


class VisionHotkey:
    """Arm-the-next-turn global hotkey wrapper around pynput.GlobalHotKeys."""

    def __init__(self, hotkey: str = "<ctrl>+<shift>+v") -> None:
        self._hotkey = hotkey
        self._armed = threading.Event()
        self._listener = None  # set in start()

    def start(self) -> None:
        # Local import so headless tests / non-vision runs don't load pynput.
        from pynput import keyboard

        def _on_trigger() -> None:
            self._armed.set()
            log.info("vision.hotkey.armed", hotkey=self._hotkey)

        self._listener = keyboard.GlobalHotKeys({self._hotkey: _on_trigger})
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:  # noqa: BLE001 - best effort on shutdown
                pass
            self._listener = None

    # --- armed-flag interface ---

    @property
    def armed(self) -> bool:
        return self._armed.is_set()

    def consume(self) -> bool:
        """Atomically: read-and-clear. Returns True if armed before the call."""
        if self._armed.is_set():
            self._armed.clear()
            return True
        return False

    def arm(self) -> None:
        """Manually arm — useful for tests and CLI triggers."""
        self._armed.set()
