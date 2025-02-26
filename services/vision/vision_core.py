"""
1️⃣ vision_core.py – AI-Powered Screen Analysis & Object Detection
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
import os
from datetime import datetime
import json
from services.vision.vision_ocr import VisionOCR
from services.vision.vision_ai import VisionAI
from services.vision.constants import CaptureMode, ScreenRegion, CAPTURE_DIRECTORY, MAX_IMAGES

class VisionCore:
    def __init__(self):
        """Initialize the VisionCore module to handle screen capture and active window tracking."""
        self.vision_ocr = VisionOCR()
        self.vision_ai = VisionAI()
        self.capture_directory = CAPTURE_DIRECTORY  # Uses constant path
        self.max_images = MAX_IMAGES  # Uses constant for max image storage
        if not os.path.exists(self.capture_directory):
            os.makedirs(self.capture_directory)

    def get_active_window(self):
        """Retrieve the currently active window title safely."""
        try:
            win = gw.getActiveWindow()
            return win.title if win else None
        except Exception as e:
            print(f"[VisionCore] Error getting active window: {e}")
            return "Unknown Window"
    
    def get_all_active_windows(self):
        """Retrieve a list of currently open windows."""
        try:
            return [win.title for win in gw.getAllWindows() if win.title]
        except Exception as e:
            print(f"[VisionCore] Error retrieving active windows: {e}")
            return []
    
    def get_last_captured_image(self):
        """Returns the path of the last captured screen image."""
        files = sorted(os.listdir(self.capture_directory), key=lambda x: os.path.getctime(os.path.join(self.capture_directory, x)))
        return os.path.join(self.capture_directory, files[-1]) if files else None

    def capture_screen(self, mode: CaptureMode, region=None):
        """Capture the screen based on the selected mode and save the image."""
        with mss.mss() as sct:
            if mode == CaptureMode.FULL_SCREEN:
                screenshot = sct.grab(sct.monitors[0]) # change to grab input on which montior to capture
            elif mode == CaptureMode.SPECIFIC_REGION and region:
                screenshot = sct.grab(region)
            elif mode == CaptureMode.ACTIVE_WINDOW:
                active_win = self.get_active_window()
                if active_win:
                    bbox = gw.getWindowsWithTitle(active_win)[0]._rect
                    screenshot = sct.grab({"left": bbox.left, "top": bbox.top, "width": bbox.width, "height": bbox.height})
                else:
                    print("[VisionCore] No active window detected. Capturing full screen.")
                    screenshot = sct.grab(sct.monitors[1])
            else:
                print("[VisionCore] Invalid capture mode. Defaulting to full screen.")
                screenshot = sct.grab(sct.monitors[1])

            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(self.capture_directory, f"capture_{timestamp}.png")
            cv2.imwrite(image_path, img)
            self.cleanup_old_images()
            return image_path

    def cleanup_old_images(self):
        """Removes old captured images if exceeding max_images."""
        files = sorted(os.listdir(self.capture_directory), key=lambda x: os.path.getctime(os.path.join(self.capture_directory, x)))
        while len(files) > self.max_images:
            file_path = os.path.join(self.capture_directory, files.pop(0))
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[VisionCore] Removed old image: {file_path}")
            else:
                print(f"[VisionCore] Image already removed: {file_path}")

    def calculate_screen_region(self, region: ScreenRegion, custom_coords=None):
        """Returns coordinates for a specified region of the active window or custom region."""
        active_win = gw.getActiveWindow()
        if not active_win and region != ScreenRegion.CUSTOM:
            return None
        bbox = active_win._rect if active_win else None
        width, height = bbox.width, bbox.height if bbox else (None, None)
        regions = {
            ScreenRegion.LEFT_HALF: (bbox.left, bbox.top, bbox.left + width // 2, bbox.top + height),
            ScreenRegion.RIGHT_HALF: (bbox.left + width // 2, bbox.top, bbox.left + width, bbox.top + height),
            ScreenRegion.TOP_HALF: (bbox.left, bbox.top, bbox.left + width, bbox.top + height // 2),
            ScreenRegion.BOTTOM_HALF: (bbox.left, bbox.top + height // 2, bbox.left + width, bbox.top + height),
            ScreenRegion.TOP_LEFT: (bbox.left, bbox.top, bbox.left + width // 2, bbox.top + height // 2),
            ScreenRegion.TOP_RIGHT: (bbox.left + width // 2, bbox.top, bbox.left + width, bbox.top + height // 2),
            ScreenRegion.BOTTOM_LEFT: (bbox.left, bbox.top + height // 2, bbox.left + width // 2, bbox.top + height),
            ScreenRegion.BOTTOM_RIGHT: (bbox.left + width // 2, bbox.top + height // 2, bbox.left + width, bbox.top + height),
            ScreenRegion.CUSTOM: custom_coords
        }
        return regions.get(region, None)

    def structure_data(self):
        """Structure vision data into a digestible format for AI."""
        return {
            "active_window": self.get_active_window(),
            "active_windows": self.get_all_active_windows(),
            "ocr_text": self.vision_ocr.run_ocr(self.get_last_captured_image()).split("\n"),
            "ui_elements": self.vision_ai.detect_objects(self.get_last_captured_image()),
            "last_capture": self.get_last_captured_image(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def interactive_test_flow(self):
        """Allows user input to determine which function flow to test."""
        print("Select a function to test:")
        print("1 - Capture Full Screen")
        print("2 - Capture Active Window")
        print("3 - Capture Specific Region (Left Half)")
        print("4 - Run OCR")
        print("5 - Get Active Windows")
        print("6 - Calculate Specific Screen Region")
        print("7 - Structure Data Output")
        print("8 - Run YOLO detection on last image")
        print("9 - Run train YOLO model")
        print("10 - Evaluate YOLO model")

        while True:
            choice = input("Enter choice: ")
            if choice == "1":
                print("Captured Image:", self.capture_screen(CaptureMode.FULL_SCREEN))
            elif choice == "2":
                print("Captured Image:", self.capture_screen(CaptureMode.ACTIVE_WINDOW))
            elif choice == "3":
                region = self.calculate_screen_region(ScreenRegion.LEFT_HALF)
                if region:
                    print("Captured Image:", self.capture_screen(CaptureMode.SPECIFIC_REGION, region))
                else:
                    print("No active window detected, region calculation failed.")
            elif choice == "4":
                print("OCR Result:", self.vision_ocr.run_ocr(self.get_last_captured_image()).split("\n"))
            elif choice == "5":
                print("Active Windows:", self.get_all_active_windows())
            elif choice == "6":
                print("Screen Region (Left Half):", self.calculate_screen_region(ScreenRegion.LEFT_HALF))
            elif choice == "7":
                print("Structured Data:", json.dumps(self.structure_data(), indent=4))
            elif choice == "8":
                print("YOLO Detection on last image:", self.vision_ai.detect_objects(self.get_last_captured_image()))
            elif choice == "9":
                self.vision_ai.train_model()
            elif choice == "10":
                if self.vision_ai:
                    print("Evaluating YOLO model...")
                    self.vision_ai.evaluate_model()
                else:
                    print("Model not loaded. Please load or create a model first.")
            else:
                print("Invalid choice.")

if __name__ == "__main__":
    """Interactive test flow for VisionCore module. Comment out if not needed."""
    
    vision = VisionCore()
    vision.interactive_test_flow()
    
