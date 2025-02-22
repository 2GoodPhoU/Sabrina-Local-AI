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
import torch
import os
from datetime import datetime
from enum import Enum
from ultralytics import YOLO

class CaptureMode(Enum):
    FULL_SCREEN = "full_screen"
    SPECIFIC_REGION = "specific_region"
    ACTIVE_WINDOW = "active_window"

class ScreenRegion(Enum):
    LEFT_HALF = "left_half"
    RIGHT_HALF = "right_half"
    TOP_HALF = "top_half"
    BOTTOM_HALF = "bottom_half"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CUSTOM = "custom"

class Vision:
    def __init__(self):
        """Initialize the Vision module to handle screen capture, UI tracking, and image storage."""
        self.active_window = None
        self.previous_ui_elements = []
        self.capture_directory = "captures"
        self.max_images = 5  # Limit stored images to 5
        self.model = None
        self.model_name = "custom_yolo.pt"
        self.data_set = "custom_dataset.yaml"
        self.load_model()

    def load_model(self):
        # Load the YOLO model safely
        
        if not os.path.exists(self.model_name):
            print("Model not found. Training a new model...")
            self.create_model()
            #train_model(model_name, "custom_dataset.yaml")
        else:
            print("Model found. Loading the existing model...")
            self.model = YOLO(self.model_name)

    def train_model(self):
        # Train the YOLO model
        print("Training the YOLO model")

        if os.path.exists(self.data_set):
            print("Custom dataset found. Training the model on the custom dataset.")
            # Train the model
            self.model.train(data=self.data_set, epochs=50, device='cuda')
        else:
            print("Custom dataset not found. Training the model on the COCO8 example dataset.")
            # Train the model on the COCO8 example dataset for 100 epochs
            self.model.train(data="coco8.yaml", epochs=100, device='cuda', imgsz=640, weights="yolov8n.pt", project='runs/train', name=self.model_name, exist_ok=True)

    def create_model(self):
        # Create a new YOLO model
        self.model = YOLO("yolov8n.pt")

        if torch.cuda.is_available():
            print("Cuda is available, setting the model to use the GPU")
            # Set the model to use the GPU
            self.model.to('cuda')
        else:
            print("Cuda is not available, setting the model to use the CPU")
            # Set the model to use the CPU
            self.model.to('cpu')

        # Save the trained model
        self.model.save(self.model_name)  # Save the trained model correctly

    def detect_ui_objects(self, image_path):
        """Detect UI objects using YOLO and return structured JSON data."""
        results = self.model(image_path)
        detections = []
        for result in results:
            for box in result.boxes.xyxy:
                label = result.names[int(box[4])]
                detections.append({
                    "type": label,
                    "coordinates": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "confidence": float(box[4])
                })
        return detections

    def get_active_window(self):
        """Retrieve the currently active window title."""
        try:
            win = gw.getActiveWindow()
            if win:
                return win.title
        except Exception as e:
            print(f"[Vision] Error getting active window: {e}")
        return None
    
    def get_all_active_windows(self):
        """Retrieve a list of currently open windows."""
        try:
            return [win.title for win in gw.getAllWindows() if win.title]
        except Exception as e:
            print(f"[Vision] Error retrieving active windows: {e}")
        return []
    
    def cleanup_old_images(self):
        """Removes old captured images if exceeding max_images."""
        files = sorted(os.listdir(self.capture_directory), key=lambda x: os.path.getctime(os.path.join(self.capture_directory, x)))
        while len(files) > self.max_images:
            os.remove(os.path.join(self.capture_directory, files.pop(0)))
            print("[Vision] Removed old image to maintain limit.")
    
    def capture_screen(self, mode: CaptureMode, region=None):
        """Capture the screen based on the selected mode and save the image."""
        with mss.mss() as sct:
            if mode == CaptureMode.FULL_SCREEN:
                screenshot = sct.grab(sct.monitors[1])
            elif mode == CaptureMode.SPECIFIC_REGION and region:
                screenshot = sct.grab(region)
            elif mode == CaptureMode.ACTIVE_WINDOW:
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
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = os.path.join(self.capture_directory, f"capture_{timestamp}.png")
            cv2.imwrite(image_path, img)  # Save image for later use
            self.cleanup_old_images()
            return image_path
    
    def get_last_captured_image(self):
        """Returns the path of the last captured screen image."""
        files = sorted(os.listdir(self.capture_directory), key=lambda x: os.path.getctime(os.path.join(self.capture_directory, x)))
        return os.path.join(self.capture_directory, files[-1]) if files else None
    
    def run_ocr(self):
        """Extracts text from the last captured image using OCR."""
        last_image = self.get_last_captured_image()
        if not last_image:
            print("[Vision] No captured image found.")
            return ""
        img = cv2.imread(last_image, cv2.IMREAD_GRAYSCALE)
        text = pytesseract.image_to_string(img)
        return text.strip()
    
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
            "ocr_text": self.run_ocr().split("\n"),
            "ui_elements": self.detect_objects(self.get_last_captured_image()),
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
                print("OCR Result:", self.run_ocr())
            elif choice == "5":
                print("Active Windows:", self.get_all_active_windows())
            elif choice == "6":
                print("Screen Region (Left Half):", self.calculate_screen_region(ScreenRegion.LEFT_HALF))
            elif choice == "7":
                print("Structured Data:", json.dumps(self.structure_data(), indent=4))
            elif choice == "8":
                print("YOLO Detection on last image:", self.detect_ui_objects(self.get_last_captured_image()))
            else:
                print("Invalid choice.")

if __name__ == "__main__":
    vision = Vision()
    vision.interactive_test_flow()
