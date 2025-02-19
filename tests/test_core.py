import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import json
import numpy as np
import core  # Import the module we're testing
from unittest.mock import patch, MagicMock


class TestCoreFunctions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Runs once before all tests"""
        cls.temp_history_file = "temp_history.json"
        cls.temp_settings_file = "temp_settings.json"

        # Mock file paths
        core.history_file = cls.temp_history_file
        core.settings_file = cls.temp_settings_file

        # Ensure clean test files
        with open(cls.temp_history_file, "w") as f:
            json.dump([], f)
        with open(cls.temp_settings_file, "w") as f:
            json.dump({"speed": 1.0, "emotion": "neutral", "pitch": 1.0}, f)

    @classmethod
    def tearDownClass(cls):
        """Runs once after all tests"""
        if os.path.exists(cls.temp_history_file):
            os.remove(cls.temp_history_file)
        if os.path.exists(cls.temp_settings_file):
            os.remove(cls.temp_settings_file)

    def test_load_save_history(self):
        """Test loading and saving history"""
        test_history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        core.save_history(test_history)

        loaded_history = core.load_history()
        self.assertEqual(loaded_history, test_history)

    def test_update_memory(self):
        """Test memory update functionality"""
        core.update_memory("What's your name?", "I'm Sabrina.")
        history = core.load_history()
        self.assertEqual(history[-2]["content"], "What's your name?")
        self.assertEqual(history[-1]["content"], "I'm Sabrina.")

    def test_load_save_settings(self):
        """Test loading and saving settings"""
        test_settings = {"speed": 1.5, "emotion": "happy", "pitch": 0.9}
        core.save_settings(test_settings)

        loaded_settings = core.load_settings()
        self.assertEqual(loaded_settings, test_settings)

    def test_process_command(self):
        """Test valid and invalid commands"""
        response = core.process_command("!speed 1.2")
        self.assertEqual(response, "Updated speed to 1.2")

        response = core.process_command("!emotion excited")
        self.assertEqual(response, "Updated emotion to excited")

        response = core.process_command("!pitch invalid")
        self.assertEqual(response, "Invalid value!")

        response = core.process_command("!reset")
        self.assertEqual(response, "Voice settings reset!")

        response = core.process_command("!unknown")
        self.assertEqual(response, "Unknown command.")

    @patch("core.gw.getActiveWindow")
    def test_get_active_window_region(self, mock_get_active_window):
        """Test active window detection"""
        mock_get_active_window.return_value = MagicMock(top=100, left=100, width=800, height=600)
        region = core.get_active_window_region()
        expected = {"top": 100, "left": 100, "width": 800, "height": 600}
        self.assertEqual(region, expected)

    @patch("core.mss.mss")
    def test_capture_screen(self, mock_mss):
        """Test screen capturing"""
        mock_mss.return_value.grab.return_value = MagicMock()
        image = core.capture_screen()
        self.assertIsInstance(image, np.ndarray)


if __name__ == "__main__":
    unittest.main()
