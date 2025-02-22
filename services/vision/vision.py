"""
1️⃣ vision.py – AI-Powered Screen Analysis & Object Detection
🔹 Purpose: Enables real-time AI vision for OCR, object detection, and UI automation.
🔹 Key Functions:
✔ Detects active application windows dynamically.
✔ Switches between full-screen vision & app-specific vision as needed.
✔ Extracts text from screen using OCR (Tesseract or PaddleOCR).
✔ Identifies UI elements & objects using YOLO (deep learning object detection).
✔ Efficient screen capturing for low-latency performance.
🔹 Use Cases:
✅ Enables Sabrina to "see" your screen & assist dynamically.
✅ Helps in navigating UI elements for automation tasks.
✅ Supports text extraction for real-time reading & command execution.
"""
import mss
import pygetwindow as gw
import cv2
import numpy as np
import pytesseract
import json
import time
import os

class Vision:
    def __init__(self):
        """Initialize the Vision module to handle screen capture and UI tracking."""
        self.active_window = None
        self.previous_ui_elements = []
        self.capture_mode = "active_window"  # Default to capturing the active window

    def get_active_window(self):
        """Retrieve the currently active window title."""
        try:
            win = gw.getActiveWindow()
            if win:
                return win.title
        except Exception as e:
            print(f"[Vision] Error getting active window: {e}")
        return None

    def capture_screen(self, mode="active_window", region=None):
        """Capture the screen based on the selected mode."""
        with mss.mss() as sct:
            if mode == "full_screen":
                screenshot = sct.grab(sct.monitors[1])
            elif mode == "specific_region" and region:
                screenshot = sct.grab(region)
            elif mode == "active_window":
                active_win = self.get_active_window()
                if active_win:
                    bbox = gw.getWindowsWithTitle(active_win)[0]._rect
                    screenshot = sct.grab({"left": bbox.left, "top": bbox.top, "width": bbox.width, "height": bbox.height})
                else:
                    print("[Vision] No active window detected. Capturing full screen.")
                    screenshot = sct.grab(sct.monitors[1])
            else:
                print("[Vision] Invalid capture mode. Defaulting to full screen.")
                screenshot = sct.grab(sct.monitors[1])
        
            img = np.array(screenshot)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def run_ocr(self, img):
        """Extracts text from an image using OCR."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray)
        return text.strip()

    def scan_ui_elements(self, img):
        """Placeholder function for UI element detection (e.g., buttons, fields)."""
        # Future YOLO or OpenCV-based element detection
        detected_elements = []
        return detected_elements

    def analyze_screen(self):
        """Capture the screen, extract text, and detect UI elements."""
        img = self.capture_screen(mode=self.capture_mode)
        ocr_text = self.run_ocr(img)
        ui_elements = self.scan_ui_elements(img)
        
        result = {
            "active_window": self.get_active_window(),
            "ocr_text": ocr_text.split("\n"),
            "ui_elements": ui_elements,
            "timestamp": time.time()
        }
        return json.dumps(result, indent=4)

if __name__ == "__main__":
    vision = Vision()
    while True:
        screen_data = vision.analyze_screen()
        print("[Vision Output]:", screen_data)
        time.sleep(5)  # Capture every 5 seconds for testing


# Change screen capture to save the screen as an image
# create a get function for the last saved image.
# create a fucntion for image and window hisotry cleanup. 
# create a get functions for the current window, display, and list of active windows.
# make sure ocr is also independent but relies on the last saved image.
# do we need a fuction that help to identify region sizes for the screen capture? or will this be soley handled by the AI?