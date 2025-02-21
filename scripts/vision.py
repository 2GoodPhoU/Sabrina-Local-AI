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
import numpy as np
import mss
import cv2
import pytesseract
from ultralytics import YOLO
from scipy.io.wavfile import write
import torch
import pyautogui
import os

# Prevent pyautogui from trying to use a display
os.environ['DISPLAY'] = ':0'

class Vision:
    def __init__(self, model_path="yolov8n.pt"):
        """Initialize the Vision module with object detection and OCR capabilities."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"YOLO model file '{model_path}' not found. Download it first.")
        
        self.model = YOLO(model_path, task="detect")

    def capture_screen(self, region=None):
        """Captures a screenshot of the entire screen or a specific region."""
        with mss.mss() as sct:
            screenshot = sct.grab(region if region else sct.monitors[1])
            return np.array(screenshot)
    
    # Example: Get active window title (without GUI)
    def get_active_window():
        try:
            return pyautogui.getActiveWindowTitle()  # Might fail in a headless environment
        except Exception as e:
            print(f"Error getting window title: {e}")
            return None
    
    def run_ocr(self):
        """Runs OCR on the active screen or active application window."""
        region = self.get_active_window()
        img = self.capture_screen(region)
        text = pytesseract.image_to_string(img)
        if text.strip():
            print("OCR Result:", text)
            return text
        print("No text detected.")
        return ""
    
    def detect_objects(self):
        """Runs real-time object detection on the screen."""
        img = self.capture_screen()
        if img is None or img.size == 0:
            print("Warning: Empty image captured, skipping object detection.")
            return []
        
        results = self.model(img)
        detected_objects = []
        for result in results:
            for box in result.boxes.xyxy:
                x1, y1, x2, y2 = map(int, box)
                detected_objects.append((x1, y1, x2, y2))
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        cv2.imshow("Object Detection", img)
        cv2.waitKey(1)
        return detected_objects