"""
✅ What This Does

Detects the active application window dynamically
Switches between full-screen vision and app-specific vision
Extracts text in real-time
Uses efficient screen capture to prevent lag
🚀 This will allow Sabrina to seamlessly look at your entire screen OR specific apps.

Handles real-time OCR & object detection.

✅ vision.py (Handles AI Vision)
Captures screen
Runs OCR (Tesseract)
Runs object detection (YOLO)
Calls voice feedback (voice.speak()) when detecting objects or text
"""
from ultralytics import YOLO
import numpy as np
import platform
import os
import pygetwindow as gw
import time
import mss
import pytesseract
import pyautogui
import cv2
from TTS.api import TTS
from pydub import AudioSegment
import json
from ollama import Client  # Connect with AI model
import subprocess

def capture_screen(region=None):
    """
    Captures a screenshot of the entire screen or a specific region.
    
    :param region: Tuple (x, y, width, height) to capture a specific area.
    :return: Screenshot image (PIL Image)
    """
    if region:
        return pyautogui.screenshot(region=region)
    return pyautogui.screenshot()

def get_active_window_region():
    """Get the bounding box (x, y, width, height) of the currently active window"""
    window = gw.getActiveWindow()
    if window is None:
        return None  # No active window found
    x, y, width, height = window.left, window.top, window.width, window.height
    return (x, y, width, height)

def detect_objects():
    """Capture screen and detect objects using YOLOv8"""
    model = YOLO("yolov8n.pt")  # Load model
    with mss.mss() as sct:
        while True:
            screenshot = sct.grab(sct.monitors[1])  # Full-screen capture
            img = np.array(screenshot)

            if img is None or img.size == 0:
                print("Warning: Empty image captured, skipping frame.")
                continue  # Skip processing

            # Convert to RGB
            frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # Run object detection
            results = model(frame)

            # Draw bounding boxes
            for result in results:
                for box in result.boxes.xyxy:
                    x1, y1, x2, y2 = map(int, box)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Display detection results
            cv2.imshow("Object Detection", frame)

            # Quit with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cv2.destroyAllWindows()

# Run AI Object Vision
detect_objects()

def live_screen_ocr():
    """Real-time OCR with dynamic switching between full-screen and app capture"""
    while True:
        region = get_active_window_region()  # Get active app region
        img = capture_screen(region)  # Capture either full screen or app

        if img is None or img.size == 0:
            print("Warning: Empty screenshot captured, skipping OCR.")
            continue

        # Apply OCR
        extracted_text = pytesseract.image_to_string(img)

        # Print detected text
        print("\n=== Detected Text ===\n", extracted_text.strip())

        # Show vision window
        cv2.imshow("Live Screen Capture", np.array(img))  # Convert PIL image to OpenCV format
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        time.sleep(0.5)  # Adjust for performance

    cv2.destroyAllWindows()


# Run AI Vision
live_screen_ocr()
