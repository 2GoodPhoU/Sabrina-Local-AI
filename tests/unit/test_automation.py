#!/usr/bin/env python3
"""
Unit tests for Sabrina AI Automation Actions
Tests the core functionality of the automation module
"""

import unittest
from unittest.mock import MagicMock, patch
import time
import os
import sys

# Import test utilities
from tests.test_utils.paths import ensure_project_root_in_sys_path

# Import the class to test
from services.automation.automation import Actions

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()


class TestActions(unittest.TestCase):
    """Test case for the Actions class"""

    def setUp(self):
        """Set up test fixtures"""
        # Set up mocks for external dependencies
        self._setup_patchers()

        # Create an instance of the Actions class
        self.actions = Actions()

    def tearDown(self):
        """Clean up test fixtures"""
        # Stop all patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def _setup_patchers(self):
        """Set up mock objects for external dependencies"""
        self._patchers = []

        # Mock PyAutoGUI
        pyautogui_patcher = patch("services.automation.automation.pyautogui")
        self.mock_pyautogui = pyautogui_patcher.start()
        self._patchers.append(pyautogui_patcher)

        # Configure PyAutoGUI mock
        self.mock_pyautogui.size.return_value = (1920, 1080)
        self.mock_pyautogui.position.return_value = (500, 500)
        self.mock_pyautogui.click.return_value = (
            None  # PyAutoGUI actions typically return None
        )
        self.mock_pyautogui.moveTo.return_value = None
        self.mock_pyautogui.dragTo.return_value = None
        self.mock_pyautogui.scroll.return_value = None
        self.mock_pyautogui.write.return_value = None
        self.mock_pyautogui.press.return_value = None
        self.mock_pyautogui.hotkey.return_value = None

        # Mock mouse module (optional enhancement)
        mouse_patcher = patch("services.automation.automation.mouse_module", None)
        self.mock_mouse_module = mouse_patcher.start()
        self._patchers.append(mouse_patcher)

        # Mock keyboard module (optional enhancement)
        keyboard_patcher = patch("services.automation.automation.keyboard_module", None)
        self.mock_keyboard_module = keyboard_patcher.start()
        self._patchers.append(keyboard_patcher)

    def test_initialization(self):
        """Test initialization of the Actions class"""
        # Test basic attributes
        self.assertIsNotNone(self.actions.screen_width)
        self.assertIsNotNone(self.actions.screen_height)
        self.assertTrue(hasattr(self.actions, "pyautogui_available"))
        self.assertEqual(self.actions.mouse_move_duration, 0.2)  # Default value
        self.assertEqual(self.actions.typing_interval, 0.1)  # Default value
        self.assertTrue(self.actions.failsafe_enabled)  # Default value

        # Check that PyAutoGUI was configured
        if self.actions.pyautogui_available:
            self.mock_pyautogui.FAILSAFE.assert_called()
            self.mock_pyautogui.PAUSE.assert_called()

    def test_configure(self):
        """Test configure method"""
        # Call configure with custom settings
        self.actions.configure(
            mouse_move_duration=0.5,
            typing_interval=0.3,
            failsafe=False,
            scroll_amount=5,
        )

        # Verify settings were updated
        self.assertEqual(self.actions.mouse_move_duration, 0.5)
        self.assertEqual(self.actions.typing_interval, 0.3)
        self.assertFalse(self.actions.failsafe_enabled)
        self.assertEqual(self.actions.scroll_amount, 5)

        # Check that PyAutoGUI failsafe was updated
        if self.actions.pyautogui_available:
            self.assertEqual(self.mock_pyautogui.FAILSAFE, False)

    def test_move_mouse_to(self):
        """Test move_mouse_to method"""
        # Call move_mouse_to with test coordinates
        result = self.actions.move_mouse_to(x=100, y=200)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.moveTo.assert_called_with(100, 200, duration=0.2)

        # Verify last_mouse_pos was updated
        self.assertEqual(self.actions.last_mouse_pos, (100, 200))

    def test_click(self):
        """Test click method"""
        # Call click with default parameters
        result = self.actions.click()

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.click.assert_called_with(button="left", clicks=1)

        # Test with custom parameters
        result = self.actions.click(button="right", clicks=2)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.click.assert_called_with(button="right", clicks=2)

    def test_click_at(self):
        """Test click_at method"""
        # Call click_at with test coordinates
        result = self.actions.click_at(x=300, y=400)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.click.assert_called_with(
                300, 400, button="left", clicks=1
            )

        # Verify last_mouse_pos was updated
        self.assertEqual(self.actions.last_mouse_pos, (300, 400))

        # Test with custom parameters
        result = self.actions.click_at(x=500, y=600, button="right", clicks=2)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.click.assert_called_with(
                500, 600, button="right", clicks=2
            )

    def test_drag_mouse(self):
        """Test drag_mouse method"""
        # Call drag_mouse with test coordinates
        result = self.actions.drag_mouse(
            start_x=100, start_y=200, end_x=300, end_y=400, duration=0.5
        )

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.moveTo.assert_called_with(100, 200)
            self.mock_pyautogui.dragTo.assert_called_with(
                300, 400, duration=0.5, button="left"
            )

        # Verify last_mouse_pos was updated
        self.assertEqual(self.actions.last_mouse_pos, (300, 400))

    def test_scroll(self):
        """Test scroll method"""
        # Call scroll with default parameters
        result = self.actions.scroll()

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.scroll.assert_called()

        # Test with custom amount and direction
        result = self.actions.scroll(amount=10, direction="up")

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called with negative value for upward scrolling
        if self.actions.pyautogui_available:
            self.mock_pyautogui.scroll.assert_called_with(-10)

    def test_type_text(self):
        """Test type_text method"""
        test_text = "Hello, world!"

        # Call type_text with test text
        result = self.actions.type_text(text=test_text)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.write.assert_called_with(test_text, interval=0.1)

        # Test with custom interval
        custom_interval = 0.05
        result = self.actions.type_text(text=test_text, interval=custom_interval)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called with custom interval
        if self.actions.pyautogui_available:
            self.mock_pyautogui.write.assert_called_with(
                test_text, interval=custom_interval
            )

    def test_press_key(self):
        """Test press_key method"""
        # Call press_key with test key
        result = self.actions.press_key(key="enter")

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.press.assert_called_with("enter")

    def test_hotkey(self):
        """Test hotkey method"""
        # Call hotkey with test keys
        result = self.actions.hotkey("ctrl", "c")

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.hotkey.assert_called_with("ctrl", "c")

    def test_run_shortcut(self):
        """Test run_shortcut method"""
        # Add a test shortcut
        self.actions.shortcuts["test_shortcut"] = ["ctrl", "shift", "t"]

        # Call run_shortcut with test shortcut
        result = self.actions.run_shortcut("test_shortcut")

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly (via hotkey)
        if self.actions.pyautogui_available:
            self.mock_pyautogui.hotkey.assert_called_with("ctrl", "shift", "t")

        # Test with nonexistent shortcut
        result = self.actions.run_shortcut("nonexistent_shortcut")

        # Check the result (should be False for unknown shortcut)
        self.assertFalse(result)

    def test_get_available_shortcuts(self):
        """Test get_available_shortcuts method"""
        # Call get_available_shortcuts
        shortcuts = self.actions.get_available_shortcuts()

        # Check the result
        self.assertIsInstance(shortcuts, list)
        self.assertGreater(len(shortcuts), 0)

        # Check some standard shortcuts are included
        standard_shortcuts = ["copy", "paste", "save"]
        for shortcut in standard_shortcuts:
            self.assertIn(shortcut, shortcuts)

    def test_select_region(self):
        """Test select_region method"""
        # Call select_region with test coordinates
        result = self.actions.select_region(100, 200, 300, 400)

        # Check the result
        self.assertTrue(result)

        # This should use drag_mouse internally, so we don't need to check PyAutoGUI directly

    def test_select_text(self):
        """Test select_text method"""
        # Call select_text with test coordinates
        result = self.actions.select_text(100, 200, 300, 400)

        # Check the result
        self.assertTrue(result)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.moveTo.assert_called_with(100, 200)
            self.mock_pyautogui.mouseDown.assert_called()
            self.mock_pyautogui.moveTo.assert_called_with(300, 400, duration=0.2)
            self.mock_pyautogui.mouseUp.assert_called()

    def test_add_custom_shortcut(self):
        """Test add_custom_shortcut method"""
        # Call add_custom_shortcut with test shortcut
        result = self.actions.add_custom_shortcut("test_shortcut", ["ctrl", "alt", "t"])

        # Check the result
        self.assertTrue(result)

        # Verify shortcut was added
        self.assertIn("test_shortcut", self.actions.shortcuts)
        self.assertEqual(self.actions.shortcuts["test_shortcut"], ["ctrl", "alt", "t"])

    def test_run_common_task(self):
        """Test run_common_task method"""
        # Mock the task methods
        self.actions._task_copy_selection = MagicMock(return_value=True)
        self.actions._task_paste = MagicMock(return_value=True)

        # Call run_common_task with "copy" task
        result = self.actions.run_common_task("copy")

        # Check the result
        self.assertTrue(result)

        # Verify task method was called
        self.actions._task_copy_selection.assert_called_once()

        # Call run_common_task with "paste" task
        result = self.actions.run_common_task("paste")

        # Check the result
        self.assertTrue(result)

        # Verify task method was called
        self.actions._task_paste.assert_called_once()

        # Test with nonexistent task
        result = self.actions.run_common_task("nonexistent_task")

        # Check the result (should be False for unknown task)
        self.assertFalse(result)

    def test_get_mouse_position(self):
        """Test get_mouse_position method"""
        # Call get_mouse_position
        pos = self.actions.get_mouse_position()

        # Check the result
        self.assertIsInstance(pos, tuple)
        self.assertEqual(len(pos), 2)

        # Verify PyAutoGUI was called correctly
        if self.actions.pyautogui_available:
            self.mock_pyautogui.position.assert_called()


if __name__ == "__main__":
    unittest.main()
