"""
🔹 automation.py - PC Automation & Input Simulation
Purpose: Allows Sabrina to interact with your PC via keyboard & mouse automation.

Key Functions:
✔ move_mouse_to(x, y, duration) - Moves the cursor smoothly to the specified position.
✔ click() - Clicks at the current cursor position.
✔ click_on_object(x, y) - Moves to an object and clicks it.
✔ press_key(key) - Simulates a single keyboard press.
✔ hold_key(key, duration) - Holds a key for a set duration.
✔ type_text(text, interval) - Types text with a delay between keystrokes.
✔ copy_paste(text) - Copies and pastes text efficiently.
✔ scroll(amount) - Scrolls the mouse wheel up/down.
✔ drag_and_drop(start_x, start_y, end_x, end_y, duration) - Drags an object to a new location.

Use Cases:
✅ Enables AI-driven UI interactions (e.g., clicking buttons, filling forms).
✅ Supports keyboard automation for hands-free control.
✅ Assists in navigating applications using AI-driven inputs.
"""
import pyautogui
import logging
import time
import pyperclip

# Configure logging
logging.basicConfig(level=logging.INFO, format="[Automation] %(asctime)s - %(levelname)s - %(message)s")

class Actions:
    def __init__(self):
        """Initialize the Actions class for mouse and keyboard automation."""
        pyautogui.FAILSAFE = True  # Prevents accidental misclicks by allowing escape to corners.

    def move_mouse_to(self, x, y, duration=0.2):
        """Moves the cursor to a specified (x, y) coordinate smoothly."""
        logging.info(f"Moving mouse to ({x}, {y})")
        pyautogui.moveTo(x, y, duration=duration)

    def click(self):
        """Clicks at the current cursor position."""
        logging.info("Clicking at the current position")
        pyautogui.click()

    def click_on_object(self, x, y):
        """Moves mouse to the detected object and clicks it."""
        logging.info(f"Clicking on object at ({x}, {y})")
        self.move_mouse_to(x, y)
        self.click()

    def press_key(self, key):
        """Simulates a keyboard key press."""
        logging.info(f"Pressing key: {key}")
        pyautogui.press(key)

    def hold_key(self, key, duration=0.5):
        """Holds a key for a specified duration."""
        logging.info(f"Holding key '{key}' for {duration} seconds")
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)

    def type_text(self, text, interval=0.1):
        """Types the given text with a small delay between keystrokes."""
        logging.info(f"Typing text: {text}")
        pyautogui.write(text, interval=interval)

    def copy_paste(self, text):
        """Copies the given text to clipboard and pastes it."""
        logging.info(f"Copy-pasting text: {text}")
        pyperclip.copy(text)
        self.press_key("ctrl")  # Simulate Ctrl+V
        pyautogui.hotkey("ctrl", "v")

    def scroll(self, amount):
        """Scrolls the mouse up or down by a specified amount."""
        logging.info(f"Scrolling {amount} units")
        pyautogui.scroll(amount)

    def drag_and_drop(self, start_x, start_y, end_x, end_y, duration=0.5):
        """Drags an object from (start_x, start_y) to (end_x, end_y)."""
        logging.info(f"Dragging object from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        pyautogui.moveTo(start_x, start_y, duration=0.3)
        pyautogui.mouseDown()
        pyautogui.moveTo(end_x, end_y, duration=duration)
        pyautogui.mouseUp()
