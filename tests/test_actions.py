import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import patch
import pyautogui
from scripts.actions import click_on_object

class TestActions(unittest.TestCase):

    @patch("pyautogui.moveTo")
    @patch("pyautogui.click")
    def test_click_on_object(self, mock_click, mock_moveTo):
        """Test clicking on a detected object"""
        x, y = 100, 200
        click_on_object(x, y)

        mock_moveTo.assert_called_once_with(x, y, duration=0.2)
        mock_click.assert_called_once()

if __name__ == "__main__":
    unittest.main()
