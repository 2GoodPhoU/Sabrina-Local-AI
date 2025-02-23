"""
4️⃣ actions.py – PC Automation & Input Simulation
🔹 Purpose: Allows Sabrina to interact with your PC via keyboard & mouse automation.
🔹 Key Functions:
✔ move_mouse_to(object) – Moves the cursor to detected UI elements.
✔ click() – Clicks on detected objects.
✔ press_key(key) – Simulates keyboard input.
🔹 Use Cases:
✅ Enables automated UI interactions (e.g., clicking buttons, selecting text).
✅ Supports keyboard automation for hands-free control.
✅ Assists in navigating applications using AI-driven inputs.
"""
import pyautogui

class Actions:
    def __init__(self):
        """Initialize the Actions class for mouse and keyboard automation."""
        pass
    
    def move_mouse_to(self, x, y, duration=0.2):
        """Moves the cursor to a specified (x, y) coordinate."""
        pyautogui.moveTo(x, y, duration=duration)
    
    def click(self):
        """Clicks at the current cursor position."""
        pyautogui.click()
    
    def click_on_object(self, x, y):
        """Moves mouse to the detected object and clicks it."""
        self.move_mouse_to(x, y)
        self.click()
    
    def press_key(self, key):
        """Simulates a keyboard key press."""
        pyautogui.press(key)
    
    def type_text(self, text, interval=0.1):
        """Types the given text with a small delay between keystrokes."""
        pyautogui.write(text, interval=interval)
    
    def scroll(self, amount):
        """Scrolls the mouse up or down by a specified amount."""
        pyautogui.scroll(amount)