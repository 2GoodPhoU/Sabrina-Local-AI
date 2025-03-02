"""
Enhanced Vision Core for Sabrina AI
==================================
Provides real OCR and screen analysis functionality with
YOLOv8 integration for advanced UI element detection.
"""

import os
import logging
from datetime import datetime
import cv2
import pytesseract
from PIL import Image
import mss
import mss.tools

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vision")


class VisionCore:
    """Enhanced vision core for Sabrina AI with real OCR and screen analysis"""

    def __init__(self):
        """Initialize the vision module with real functionality"""
        logger.info("Initializing enhanced vision module")

        # Create capture directory
        self.capture_directory = "data/captures"
        os.makedirs(self.capture_directory, exist_ok=True)

        # Initialize OCR
        self.vision_ocr = VisionOCR()

        # Initialize Vision AI for object detection (if available)
        self.vision_ai = self._init_vision_ai()

        # Set up screen capture
        self.mss_available = self._check_mss_available()
        if not self.mss_available:
            logger.warning("MSS not available - screen capture will be limited")

    def _init_vision_ai(self):
        """Initialize the Vision AI module for object detection"""
        try:
            from services.vision.vision_ai import VisionAI

            # Get model path from constants if possible
            model_path = None
            try:
                from services.vision.constants import MODEL_PATH

                if os.path.exists(MODEL_PATH):
                    model_path = MODEL_PATH
            except ImportError:
                logger.warning("Could not import MODEL_PATH from constants")

            # Create Vision AI instance
            vision_ai = VisionAI(model_path=model_path)
            logger.info("Vision AI initialized successfully")
            return vision_ai

        except ImportError:
            logger.warning(
                "Vision AI module not available - object detection will be limited"
            )
            return None
        except Exception as e:
            logger.error(f"Error initializing Vision AI: {str(e)}")
            return None

    def _check_mss_available(self):
        """Check if MSS screen capture is available"""
        try:
            with mss.mss() as sct:
                # Try a test capture
                sct.grab(sct.monitors[0])
            return True
        except Exception as e:
            logger.error(f"MSS screen capture not available: {str(e)}")
            return False

    def capture_screen(self, mode="full_screen", region=None):
        """
        Capture the screen with real screen capture functionality

        Args:
            mode: Capture mode (full_screen, active_window, specific_region)
            region: Screen region to capture (if mode is specific_region)

        Returns:
            Path to the captured image
        """
        logger.info(f"Capturing screen with mode: {mode}")

        # Generate filename based on timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(self.capture_directory, f"capture_{timestamp}.png")

        try:
            if self.mss_available:
                with mss.mss() as sct:
                    # Determine what to capture
                    if mode == "full_screen":
                        monitor = sct.monitors[0]  # Primary monitor
                        screenshot = sct.grab(monitor)
                    elif mode == "active_window":
                        # Get active window info
                        active_window = self.get_active_window_info()
                        if active_window and "rect" in active_window:
                            # Capture the active window region
                            monitor = {
                                "left": active_window["rect"][0],
                                "top": active_window["rect"][1],
                                "width": active_window["rect"][2],
                                "height": active_window["rect"][3],
                            }
                            screenshot = sct.grab(monitor)
                        else:
                            # Fallback to primary monitor
                            monitor = sct.monitors[0]
                            screenshot = sct.grab(monitor)
                    elif mode == "specific_region" and region:
                        screenshot = sct.grab(region)
                    else:
                        logger.warning(f"Invalid capture mode: {mode}")
                        return None

                    # Save the screenshot
                    mss.tools.to_png(screenshot.rgb, screenshot.size, output=image_path)
            else:
                # Fallback to PIL/ImageGrab if MSS is not available
                try:
                    from PIL import ImageGrab

                    if mode == "specific_region" and region:
                        screenshot = ImageGrab.grab(bbox=region)
                    elif mode == "active_window":
                        active_window = self.get_active_window_info()
                        if active_window and "rect" in active_window:
                            screenshot = ImageGrab.grab(bbox=active_window["rect"])
                        else:
                            screenshot = ImageGrab.grab()
                    else:
                        screenshot = ImageGrab.grab()

                    screenshot.save(image_path)
                except Exception as e:
                    logger.error(f"Failed to capture screen with PIL: {str(e)}")
                    return None

            logger.info(f"Screen captured to {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"Error capturing screen: {str(e)}")
            return None

    def get_active_window_info(self):
        """
        Get information about the active window

        Returns:
            Dict with active window information, or None if not available
        """
        try:
            import pygetwindow as gw

            # Get the active window
            active_window = gw.getActiveWindow()

            if active_window:
                return {
                    "title": active_window.title,
                    "position": (active_window.left, active_window.top),
                    "size": (active_window.width, active_window.height),
                    "rect": (
                        active_window.left,
                        active_window.top,
                        active_window.width,
                        active_window.height,
                    ),
                }
            else:
                logger.warning("No active window found")
                return None

        except Exception as e:
            logger.error(f"Error getting active window info: {str(e)}")
            return None

    def analyze_screen(self, image_path=None):
        """
        Analyze the screen using OCR and object detection

        Args:
            image_path: Path to the image to analyze, or None to capture a new one

        Returns:
            Dict with analysis results
        """
        # Capture screen if no image provided
        if not image_path:
            image_path = self.capture_screen()

        if not image_path or not os.path.exists(image_path):
            logger.warning("No valid image to analyze")
            return {"error": "No valid image to analyze"}

        # Perform OCR
        ocr_text = self.vision_ocr.run_ocr(image_path)

        # Detect UI elements if Vision AI is available
        ui_elements = self.detect_ui_elements(image_path)

        # Analyze the image
        analysis = {
            "ocr_text": ocr_text,
            "ui_elements": ui_elements,
            "timestamp": datetime.now().isoformat(),
            "image_path": image_path,
        }

        # Add active window info if available
        active_window = self.get_active_window_info()
        if active_window:
            analysis["active_window"] = active_window

        return analysis

    def detect_ui_elements(self, image_path):
        """
        Detect UI elements in the given image

        Args:
            image_path: Path to the image file

        Returns:
            List of detected UI elements with their coordinates and types
        """
        # Use Vision AI if available
        if self.vision_ai:
            logger.info(f"Detecting UI elements with Vision AI in {image_path}")
            elements = self.vision_ai.detect_ui_elements(image_path)

            # Extract text from detected UI elements if they have no text yet
            elements_with_text = []
            for element in elements:
                if "text" not in element or not element["text"]:
                    elements_with_text = self.vision_ai.extract_text_from_regions(
                        image_path, [element], self.vision_ocr
                    )
                else:
                    elements_with_text = elements

            return elements_with_text

        # Fallback to basic detection if Vision AI not available
        return self._fallback_detect_ui_elements(image_path)

    def _fallback_detect_ui_elements(self, image_path):
        """
        Fallback method for UI element detection when Vision AI is not available

        Args:
            image_path: Path to the image file

        Returns:
            List of detected UI elements
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Error: Could not read image: {image_path}")
                return []

            # Convert to grayscale for simple edge detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Basic edge detection to find potential UI elements
            edges = cv2.Canny(gray, 50, 150)

            # Find contours which might be UI elements
            contours, _ = cv2.findContours(
                edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # Filter contours by size (avoid small noise)
            min_area = 500  # Minimum area threshold
            valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]

            # Extract information about detected elements
            elements = []
            for i, contour in enumerate(valid_contours):
                x, y, w, h = cv2.boundingRect(contour)

                # Extract ROI for OCR
                roi = gray[y : y + h, x : x + w]
                text = ""

                # Only try OCR if ROI is large enough
                if w > 20 and h > 10:
                    try:
                        text = pytesseract.image_to_string(roi).strip()
                    except Exception as e:
                        logger.error(f"OCR error on ROI: {str(e)}")

                elements.append(
                    {
                        "type": "unknown_ui_element",
                        "coordinates": [int(x), int(y), int(x + w), int(y + h)],
                        "confidence": 0.5,  # Default confidence
                        "text": text,
                    }
                )

            return elements

        except Exception as e:
            logger.error(f"Error detecting UI elements: {str(e)}")
            return []

    def create_annotated_image(self, image_path, save_path=None):
        """
        Create an annotated image with detected UI elements

        Args:
            image_path: Path to the original image
            save_path: Path to save the annotated image (if None, auto-generated)

        Returns:
            Path to the annotated image
        """
        if not self.vision_ai:
            logger.warning("Vision AI not available - cannot create annotated image")
            return None

        # Detect UI elements
        elements = self.detect_ui_elements(image_path)

        if not elements:
            logger.warning("No UI elements detected")
            return None

        # Create annotated image
        return self.vision_ai.add_bounding_boxes(image_path, elements, save_path)


class VisionOCR:
    """Enhanced OCR module with real Tesseract functionality"""

    def __init__(self):
        """Initialize the OCR module with Tesseract"""
        logger.info("Initializing OCR module with Tesseract")

        # Check if Tesseract is available
        self.tesseract_available = self._check_tesseract_available()
        if not self.tesseract_available:
            logger.warning("Tesseract OCR not available - OCR will be limited")

    def _check_tesseract_available(self):
        """Check if Tesseract OCR is available"""
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.error(f"Tesseract OCR not available: {str(e)}")
            return False

    def preprocess_image(self, image_path):
        """
        Preprocess the image for better OCR results

        Args:
            image_path: Path to the image

        Returns:
            Preprocessed image
        """
        try:
            # Read the image
            img = cv2.imread(image_path)

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply threshold to get black and white image
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

            return thresh
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return None

    def run_ocr(self, image_path):
        """
        Extract text from an image using Tesseract OCR

        Args:
            image_path: Path to the image

        Returns:
            Extracted text
        """
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"Image not found: {image_path}")
            return ""

        logger.info(f"Running OCR on {image_path}")

        if self.tesseract_available:
            try:
                # Preprocess the image
                preprocessed_img = self.preprocess_image(image_path)

                if preprocessed_img is not None:
                    # Run OCR on preprocessed image
                    text = pytesseract.image_to_string(preprocessed_img)
                else:
                    # Run OCR on original image as fallback
                    text = pytesseract.image_to_string(Image.open(image_path))

                return text.strip()
            except Exception as e:
                logger.error(f"Error running OCR: {str(e)}")
                return "[OCR Error: Could not process image]"
        else:
            logger.warning("Tesseract OCR not available")
            return "[OCR Unavailable: Tesseract not installed]"
