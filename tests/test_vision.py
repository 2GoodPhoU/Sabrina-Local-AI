import sys
import os
import unittest
import numpy as np
import cv2
import time
import threading
from unittest.mock import patch, MagicMock
import pytesseract
import mss
import pyautogui
from services.vision.vision import capture_screen, get_active_window_region, detect_objects, live_screen_ocr

class TestVisionFunctions(unittest.TestCase):

    @patch("scripts.vision.pyautogui.screenshot")
    def test_capture_screen(self, mock_screenshot):
        """Test full-screen capture"""
        mock_screenshot.return_value = "mock_image"
        result = capture_screen()
        self.assertEqual(result, "mock_image")

    @patch("scripts.vision.pyautogui.screenshot")
    def test_capture_screen_with_region(self, mock_screenshot):
        """Test region-based capture"""
        mock_screenshot.return_value = "mock_image"
        result = capture_screen(region=(0, 0, 100, 100))
        self.assertEqual(result, "mock_image")

    @patch("scripts.vision.gw.getActiveWindow")
    def test_get_active_window_region(self, mock_getActiveWindow):
        """Test getting the active window region"""
        mock_getActiveWindow.return_value = type('MockWindow', (object,), {'left': 100, 'top': 100, 'width': 800, 'height': 600})()
        region = get_active_window_region()
        self.assertEqual(region, (100, 100, 800, 600))

    def simulate_exit(self):
        """Forcefully close OpenCV window after 1 second"""
        time.sleep(1)
        cv2.destroyAllWindows()

    @patch("scripts.vision.mss.mss")
    @patch("cv2.imshow")
    @patch("cv2.waitKey", side_effect=[ord('q')])  # Simulate 'q' keypress to close window
    def test_detect_objects(self, mock_waitKey, mock_imshow, mock_mss):
        """Test object detection function with automatic exit."""
        mock_sct_instance = MagicMock()
        mock_mss.return_value.__enter__.return_value = mock_sct_instance

        # Ensure a valid image with shape (480, 640, 3)
        mock_sct_instance.grab.return_value = np.zeros((480, 640, 3), dtype=np.uint8)

        # Run object detection once and exit
        detect_objects()

        mock_sct_instance.grab.assert_called_once()  # Ensure only one frame is processed
        cv2.destroyAllWindows()  # 🔹 Explicitly close OpenCV windows


    @patch("scripts.vision.mss.mss")
    @patch("scripts.vision.pytesseract.image_to_string", return_value="Detected Text")
    @patch("cv2.imshow")
    @patch("cv2.waitKey", side_effect=[ord('q')])  # Simulate 'q' keypress to close window
    def test_live_screen_ocr(self, mock_waitKey, mock_imshow, mock_ocr, mock_mss):
        """Test OCR function for screen text recognition with automatic exit."""
        mock_sct_instance = MagicMock()
        mock_mss.return_value.__enter__.return_value = mock_sct_instance

        # Mock a valid image (480x640, single channel)
        mock_sct_instance.grab.return_value = np.zeros((480, 640, 3), dtype=np.uint8)

        # Run OCR detection once and exit
        live_screen_ocr()

        mock_ocr.assert_called_once()  # Ensure OCR was called only once
        cv2.destroyAllWindows()  # 🔹 Explicitly close OpenCV windows

if __name__ == "__main__":
    unittest.main()
