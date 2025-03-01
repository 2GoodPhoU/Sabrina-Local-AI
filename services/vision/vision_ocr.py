import cv2
import pytesseract
import os
from services.vision.constants import CAPTURE_DIRECTORY


class VisionOCR:
    def __init__(self):
        """Initialize the VisionOCR module for text extraction using OCR."""
        self.capture_directory = CAPTURE_DIRECTORY  # Uses constant path

    def preprocess_image(self, image_path):
        """Preprocess image for better OCR accuracy."""
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        return img

    def run_ocr(self, image_path):
        """Extracts text from an image using OCR."""
        if not image_path or not os.path.exists(image_path):
            print("[VisionOCR] No valid image found for OCR.")
            return ""
        img = self.preprocess_image(image_path)
        return pytesseract.image_to_string(img).strip()
