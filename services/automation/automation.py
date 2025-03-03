"""
Enhanced Automation Module for Sabrina AI
========================================
Provides comprehensive PC automation capabilities including:
- Mouse movement, clicking, and dragging
- Scrolling functionality
- Keyboard control with shortcuts
- Window management
"""

import logging
import time
from typing import Tuple, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automation")


class Actions:
    """
    Enhanced PC automation and control for Sabrina AI

    Features:
    - Mouse control (move, click, drag, scroll)
    - Keyboard input (typing, shortcuts, hotkeys)
    - Window management
    - Predefined automation shortcuts
    """

    def __init__(self):
        """Initialize the enhanced automation module"""
        logger.info("Initializing enhanced automation module")

        # Track automation state
        self.last_mouse_pos = (0, 0)
        self.last_window = None
        self.failsafe_enabled = True
        self.failsafe_position = (0, 0)  # Top-left corner as default failsafe position

        # Load configuration
        self.mouse_move_duration = 0.2
        self.typing_interval = 0.1
        self.scroll_amount = 3  # Default scroll amount

        # Define common shortcuts for easy access
        self.shortcuts = {
            "copy": ["ctrl", "c"],
            "paste": ["ctrl", "v"],
            "cut": ["ctrl", "x"],
            "save": ["ctrl", "s"],
            "select_all": ["ctrl", "a"],
            "undo": ["ctrl", "z"],
            "redo": ["ctrl", "y"],
            "find": ["ctrl", "f"],
            "new_tab": ["ctrl", "t"],
            "close_tab": ["ctrl", "w"],
            "switch_tab": ["ctrl", "tab"],
            "screenshot": ["win", "shift", "s"],
            "task_view": ["win", "tab"],
            "file_explorer": ["win", "e"],
            "system_settings": ["win", "i"],
            "lock_screen": ["win", "l"],
            "app_search": ["win", "s"],
        }

        try:
            # Try to import PyAutoGUI - if it's not available, use placeholder methods
            import pyautogui

            # Configure PyAutoGUI
            pyautogui.FAILSAFE = self.failsafe_enabled
            pyautogui.PAUSE = 0.1  # Short pause between PyAutoGUI actions

            self.pyautogui = pyautogui
            self.pyautogui_available = True
            logger.info("PyAutoGUI available - automation enabled")

            # Try to get screen size
            self.screen_width, self.screen_height = pyautogui.size()
            logger.info(
                f"Screen size detected: {self.screen_width}x{self.screen_height}"
            )

        except ImportError:
            self.pyautogui_available = False
            logger.warning("PyAutoGUI not available - using placeholder methods")
            self.screen_width, self.screen_height = 1920, 1080  # Default assumption

        # Try to import mouse module for more precise control
        try:
            import mouse

            self.mouse_module = mouse
            self.mouse_module_available = True
            logger.info("Mouse module available - enhanced drag and scroll enabled")
        except ImportError:
            self.mouse_module = None
            self.mouse_module_available = False
            logger.info(
                "Mouse module not available - using PyAutoGUI for all mouse actions"
            )

        # Try to import keyboard module for better hotkey support
        try:
            import keyboard

            self.keyboard_module = keyboard
            self.keyboard_module_available = True
            logger.info("Keyboard module available - enhanced hotkey support enabled")
        except ImportError:
            self.keyboard_module = None
            self.keyboard_module_available = False
            logger.info(
                "Keyboard module not available - using PyAutoGUI for all keyboard actions"
            )

    def configure(
        self,
        mouse_move_duration=0.2,
        typing_interval=0.1,
        failsafe=True,
        scroll_amount=3,
        failsafe_position=(0, 0),
    ):
        """
        Configure automation settings

        Args:
            mouse_move_duration: Duration for mouse movements in seconds
            typing_interval: Delay between keystrokes in seconds
            failsafe: Enable failsafe (moving mouse to corner stops automation)
            scroll_amount: Default amount to scroll
            failsafe_position: Screen position that triggers failsafe
        """
        self.mouse_move_duration = mouse_move_duration
        self.typing_interval = typing_interval
        self.failsafe_enabled = failsafe
        self.scroll_amount = scroll_amount
        self.failsafe_position = failsafe_position

        # Update PyAutoGUI settings if available
        if self.pyautogui_available:
            self.pyautogui.FAILSAFE = self.failsafe_enabled

        logger.info(
            f"Automation settings updated: move_duration={mouse_move_duration}, "
            f"typing_interval={typing_interval}, failsafe={failsafe}"
        )

    def move_mouse_to(self, x: int, y: int, duration: float = None) -> bool:
        """
        Move mouse to the specified coordinates

        Args:
            x: X coordinate
            y: Y coordinate
            duration: Movement duration in seconds (None uses default)

        Returns:
            bool: True if successful, False otherwise
        """
        if duration is None:
            duration = self.mouse_move_duration

        logger.info(f"Moving mouse to ({x}, {y}) over {duration}s")

        try:
            if self.pyautogui_available:
                # Ensure coordinates are within screen bounds
                x = max(0, min(x, self.screen_width - 1))
                y = max(0, min(y, self.screen_height - 1))

                self.pyautogui.moveTo(x, y, duration=duration)
                self.last_mouse_pos = (x, y)
                return True
            else:
                # Placeholder - simulate the action
                time.sleep(duration)
                self.last_mouse_pos = (x, y)
                print(f"[SIMULATED] Mouse moved to ({x}, {y})")
                return True

        except Exception as e:
            logger.error(f"Error moving mouse: {str(e)}")
            return False

    def click(self, button: str = "left", clicks: int = 1) -> bool:
        """
        Click at the current cursor position

        Args:
            button: Mouse button to click ('left', 'right', 'middle')
            clicks: Number of clicks (1 for single-click, 2 for double-click)

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Clicking {button} button {clicks} times at current position")

        try:
            if self.pyautogui_available:
                self.pyautogui.click(button=button, clicks=clicks)
                return True
            else:
                # Placeholder - simulate the action
                print(
                    f"[SIMULATED] {button.capitalize()} mouse button clicked {clicks} times"
                )
                return True

        except Exception as e:
            logger.error(f"Error clicking mouse: {str(e)}")
            return False

    def click_at(self, x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
        """
        Move to coordinates and click

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button to click ('left', 'right', 'middle')
            clicks: Number of clicks (1 for single-click, 2 for double-click)

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Clicking {button} button at ({x}, {y})")

        try:
            if self.pyautogui_available:
                # Ensure coordinates are within screen bounds
                x = max(0, min(x, self.screen_width - 1))
                y = max(0, min(y, self.screen_height - 1))

                self.pyautogui.click(x, y, button=button, clicks=clicks)
                self.last_mouse_pos = (x, y)
                return True
            else:
                # Placeholder - simulate the action
                time.sleep(self.mouse_move_duration)
                self.last_mouse_pos = (x, y)
                print(
                    f"[SIMULATED] Moved to ({x}, {y}) and clicked {button} button {clicks} times"
                )
                return True

        except Exception as e:
            logger.error(f"Error clicking at position: {str(e)}")
            return False

    def drag_mouse(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = None,
        button: str = "left",
    ) -> bool:
        """
        Perform a drag operation from start point to end point

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            duration: Duration of the drag operation in seconds
            button: Mouse button to use for dragging

        Returns:
            bool: True if successful, False otherwise
        """
        if duration is None:
            duration = self.mouse_move_duration

        logger.info(
            f"Dragging from ({start_x}, {start_y}) to ({end_x}, {end_y}) over {duration}s"
        )

        try:
            if self.pyautogui_available:
                # Ensure coordinates are within screen bounds
                start_x = max(0, min(start_x, self.screen_width - 1))
                start_y = max(0, min(start_y, self.screen_height - 1))
                end_x = max(0, min(end_x, self.screen_width - 1))
                end_y = max(0, min(end_y, self.screen_height - 1))

                # Move to start position
                self.pyautogui.moveTo(start_x, start_y)

                # Perform drag operation
                self.pyautogui.dragTo(end_x, end_y, duration=duration, button=button)

                self.last_mouse_pos = (end_x, end_y)
                return True

            elif self.mouse_module_available:
                # Alternate implementation using mouse module
                self.mouse_module.move(start_x, start_y)
                self.mouse_module.press(button)
                time.sleep(0.1)  # Short delay after press

                # Calculate steps for smooth movement
                steps = int(duration * 60)  # 60 steps per second
                steps = max(10, steps)  # Minimum 10 steps for smoothness

                for i in range(1, steps + 1):
                    progress = i / steps
                    current_x = int(start_x + (end_x - start_x) * progress)
                    current_y = int(start_y + (end_y - start_y) * progress)
                    self.mouse_module.move(current_x, current_y)
                    time.sleep(duration / steps)

                self.mouse_module.release(button)
                self.last_mouse_pos = (end_x, end_y)
                return True

            else:
                # Placeholder - simulate the action
                time.sleep(duration)
                self.last_mouse_pos = (end_x, end_y)
                print(
                    f"[SIMULATED] Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"
                )
                return True

        except Exception as e:
            logger.error(f"Error dragging mouse: {str(e)}")
            return False

    def scroll(self, amount: int = None, direction: str = "down") -> bool:
        """
        Scroll the mouse wheel

        Args:
            amount: Number of "clicks" to scroll (negative for up, positive for down)
            direction: 'up' or 'down' to specify scroll direction

        Returns:
            bool: True if successful, False otherwise
        """
        # Set amount based on direction if not specified
        if amount is None:
            amount = self.scroll_amount
            if direction.lower() == "up":
                amount = -amount

        logger.info(f"Scrolling {direction} by {abs(amount)} clicks")

        try:
            if self.pyautogui_available:
                self.pyautogui.scroll(amount)
                return True

            elif self.mouse_module_available:
                # Alternate implementation using mouse module
                self.mouse_module.wheel(amount)
                return True

            else:
                # Placeholder - simulate the action
                print(f"[SIMULATED] Scrolled {direction} by {abs(amount)} clicks")
                return True

        except Exception as e:
            logger.error(f"Error scrolling: {str(e)}")
            return False

    def type_text(self, text: str, interval: float = None) -> bool:
        """
        Type text with the keyboard

        Args:
            text: Text to type
            interval: Delay between keystrokes in seconds

        Returns:
            bool: True if successful, False otherwise
        """
        if interval is None:
            interval = self.typing_interval

        logger.info(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")

        try:
            if self.pyautogui_available:
                self.pyautogui.write(text, interval=interval)
                return True

            elif self.keyboard_module_available:
                # Alternative implementation using keyboard module
                self.keyboard_module.write(text, delay=interval)
                return True

            else:
                # Placeholder - simulate the action
                time.sleep(len(text) * interval)
                print(f"[SIMULATED] Typed: {text}")
                return True

        except Exception as e:
            logger.error(f"Error typing text: {str(e)}")
            return False

    def press_key(self, key: str) -> bool:
        """
        Press a keyboard key

        Args:
            key: Key to press

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Pressing key: {key}")

        try:
            if self.pyautogui_available:
                self.pyautogui.press(key)
                return True

            elif self.keyboard_module_available:
                # Alternative implementation using keyboard module
                self.keyboard_module.press_and_release(key)
                return True

            else:
                # Placeholder - simulate the action
                print(f"[SIMULATED] Pressed key: {key}")
                return True

        except Exception as e:
            logger.error(f"Error pressing key: {str(e)}")
            return False

    def hotkey(self, *keys) -> bool:
        """
        Press multiple keys simultaneously

        Args:
            *keys: Keys to press together

        Returns:
            bool: True if successful, False otherwise
        """
        key_names = ", ".join(keys)
        logger.info(f"Pressing hotkey combination: {key_names}")

        try:
            if self.pyautogui_available:
                self.pyautogui.hotkey(*keys)
                return True

            elif self.keyboard_module_available:
                # Alternative implementation using keyboard module
                key_combo = "+".join(keys)
                self.keyboard_module.press_and_release(key_combo)
                return True

            else:
                # Placeholder - simulate the action
                print(f"[SIMULATED] Pressed hotkey: {key_names}")
                return True

        except Exception as e:
            logger.error(f"Error executing hotkey: {str(e)}")
            return False

    def run_shortcut(self, shortcut_name: str) -> bool:
        """
        Execute a predefined shortcut

        Args:
            shortcut_name: Name of the shortcut to execute

        Returns:
            bool: True if shortcut exists and was executed, False otherwise
        """
        if shortcut_name not in self.shortcuts:
            logger.warning(f"Unknown shortcut: {shortcut_name}")
            return False

        keys = self.shortcuts[shortcut_name]
        logger.info(f"Executing shortcut '{shortcut_name}': {', '.join(keys)}")

        return self.hotkey(*keys)

    def get_available_shortcuts(self) -> List[str]:
        """
        Get list of available shortcut names

        Returns:
            List of available shortcut names
        """
        return list(self.shortcuts.keys())

    def select_region(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """
        Select a rectangular region by dragging

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(
            f"Selecting region from ({start_x}, {start_y}) to ({end_x}, {end_y})"
        )

        # Perform drag operation to select region
        return self.drag_mouse(start_x, start_y, end_x, end_y)

    def select_text(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """
        Select text by dragging with triple-click option

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Selecting text from ({start_x}, {start_y}) to ({end_x}, {end_y})")

        try:
            if self.pyautogui_available:
                # Move to start position
                self.pyautogui.moveTo(start_x, start_y)

                # Hold left button
                self.pyautogui.mouseDown()

                # Move to end position
                self.pyautogui.moveTo(end_x, end_y, duration=self.mouse_move_duration)

                # Release
                self.pyautogui.mouseUp()

                self.last_mouse_pos = (end_x, end_y)
                return True

            else:
                # Use standard drag method as fallback
                return self.drag_mouse(start_x, start_y, end_x, end_y)

        except Exception as e:
            logger.error(f"Error selecting text: {str(e)}")
            return False

    def scroll_to_element(
        self, target_y: int, current_scroll_position: int = None, max_attempts: int = 10
    ) -> bool:
        """
        Scroll until a target Y position is in view

        Args:
            target_y: Target Y coordinate to scroll to
            current_scroll_position: Current scroll position if known
            max_attempts: Maximum scroll attempts

        Returns:
            bool: True if scrolled successfully, False otherwise
        """
        logger.info(f"Scrolling to target Y position: {target_y}")

        # If we don't know the current scroll position or relationship,
        # we'll have to use a trial-and-error approach

        # Simple approach: scroll in the expected direction
        try:
            if target_y < self.screen_height / 2:
                # Target is likely above the middle of the screen, scroll up
                direction = "up"
                scroll_value = -self.scroll_amount
            else:
                # Target is likely below the middle of the screen, scroll down
                direction = "down"
                scroll_value = self.scroll_amount

            # Perform scrolling
            for i in range(max_attempts):
                self.scroll(scroll_value)
                time.sleep(0.2)  # Give UI time to update

                # In a real implementation, you would check if the target is now visible
                # For this simplified version, we'll just log the attempts
                logger.info(
                    f"Scroll attempt {i+1}/{max_attempts} in direction: {direction}"
                )

            return True

        except Exception as e:
            logger.error(f"Error scrolling to element: {str(e)}")
            return False

    def add_custom_shortcut(self, name: str, keys: List[str]) -> bool:
        """
        Add or update a custom shortcut

        Args:
            name: Name for the shortcut
            keys: List of keys to press for the shortcut

        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            self.shortcuts[name.lower()] = keys
            logger.info(f"Added custom shortcut '{name}': {', '.join(keys)}")
            return True
        except Exception as e:
            logger.error(f"Error adding custom shortcut: {str(e)}")
            return False

    def run_common_task(self, task_name: str, **kwargs) -> bool:
        """
        Run a common predefined task

        Args:
            task_name: Name of the task to run
            **kwargs: Additional parameters needed for the task

        Returns:
            bool: True if task executed successfully, False otherwise
        """
        task_name = task_name.lower()

        # Mapping of task names to methods
        tasks = {
            "copy": self._task_copy_selection,
            "paste": self._task_paste,
            "copy_paste": self._task_copy_paste,
            "select_all": self._task_select_all,
            "search": self._task_search,
            "take_screenshot": self._task_take_screenshot,
            "new_document": self._task_new_document,
            "save_document": self._task_save_document,
            "close_window": self._task_close_window,
            "switch_window": self._task_switch_window,
            "open_browser": self._task_open_browser,
        }

        if task_name not in tasks:
            logger.warning(f"Unknown task: {task_name}")
            return False

        logger.info(f"Running common task: {task_name}")

        try:
            # Execute the task method
            return tasks[task_name](**kwargs)
        except Exception as e:
            logger.error(f"Error executing task '{task_name}': {str(e)}")
            return False

    # Common task implementations
    def _task_copy_selection(self, **kwargs):
        """Copy the current selection to clipboard"""
        return self.run_shortcut("copy")

    def _task_paste(self, **kwargs):
        """Paste from clipboard"""
        return self.run_shortcut("paste")

    def _task_copy_paste(self, **kwargs):
        """Copy selection and paste (with optional target coordinates)"""
        # Copy first
        if not self.run_shortcut("copy"):
            return False

        # If target coordinates provided, click there first
        target_x = kwargs.get("target_x")
        target_y = kwargs.get("target_y")
        if target_x is not None and target_y is not None:
            if not self.click_at(target_x, target_y):
                return False

        # Then paste
        return self.run_shortcut("paste")

    def _task_select_all(self, **kwargs):
        """Select all content"""
        return self.run_shortcut("select_all")

    def _task_search(self, search_text=None, **kwargs):
        """Open search and type search text if provided"""
        # Open search dialog
        if not self.run_shortcut("find"):
            return False

        # If search text provided, type it
        if search_text:
            time.sleep(0.3)  # Wait for search dialog
            return self.type_text(search_text)

        return True

    def _task_take_screenshot(self, **kwargs):
        """Take a screenshot"""
        if "win" in self.shortcuts["screenshot"]:
            # Windows screenshot shortcut
            return self.run_shortcut("screenshot")
        else:
            # Alternative for other systems
            return self.hotkey("ctrl", "shift", "3")

    def _task_new_document(self, **kwargs):
        """Create a new document/tab"""
        return self.run_shortcut("new_tab")

    def _task_save_document(self, **kwargs):
        """Save the current document"""
        return self.run_shortcut("save")

    def _task_close_window(self, **kwargs):
        """Close the current window or tab"""
        return self.run_shortcut("close_tab")

    def _task_switch_window(self, **kwargs):
        """Switch between windows or tabs"""
        # Use Alt+Tab for window switching
        return self.hotkey("alt", "tab")

    def _task_open_browser(self, url=None, **kwargs):
        """
        Open the default browser and navigate to a URL if provided

        This is a more complex task that requires multiple steps
        """
        try:
            if self.pyautogui_available:
                # Open run dialog
                self.hotkey("win", "r")
                time.sleep(0.3)

                if url:
                    # Type the URL directly to open in default browser
                    self.type_text(url)
                else:
                    # Just open the default browser
                    self.type_text("https://www.google.com")

                time.sleep(0.2)
                self.press_key("enter")
                return True
            else:
                print(
                    f"[SIMULATED] Opening browser {'with URL: ' + url if url else ''}"
                )
                return True

        except Exception as e:
            logger.error(f"Error opening browser: {str(e)}")
            return False

    # System utility methods
    def get_mouse_position(self) -> Tuple[int, int]:
        """
        Get current mouse cursor position

        Returns:
            Tuple with (x, y) coordinates
        """
        try:
            if self.pyautogui_available:
                return self.pyautogui.position()
            else:
                # Return last known position
                return self.last_mouse_pos
        except Exception as e:
            logger.error(f"Error getting mouse position: {str(e)}")
            return self.last_mouse_pos
