"""
Enhanced Vision AI for Sabrina AI
================================
Provides advanced UI element detection and object recognition using YOLOv8.
"""

import os
import torch
import logging
from typing import List, Dict, Any
import cv2

# Configure logging
logger = logging.getLogger("vision_ai")


class VisionAI:
    """Enhanced vision AI using YOLOv8 for UI element detection and object recognition"""

    def __init__(self, model_path: str = None, confidence_threshold: float = 0.4):
        """
        Initialize the Vision AI module

        Args:
            model_path: Path to YOLOv8 model (if None, will download a default model)
            confidence_threshold: Minimum confidence for object detection
        """
        logger.info("Initializing Enhanced Vision AI")
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Default classes for UI elements detection
        self.ui_classes = [
            "button",
            "checkbox",
            "dropdown",
            "text_field",
            "link",
            "icon",
            "menu",
            "tab",
            "scrollbar",
            "slider",
            "toggle",
            "radio_button",
        ]

        # Load model
        self.model_path = model_path
        self.load_model()

    def load_model(self):
        """Load YOLOv8 model - download if not available"""
        try:
            from ultralytics import YOLO

            if self.model_path and os.path.exists(self.model_path):
                logger.info(f"Loading custom YOLOv8 model from: {self.model_path}")
                self.model = YOLO(self.model_path)
            else:
                # If no custom model, use a pretrained YOLOv8 model
                logger.info("No custom model found, loading YOLOv8n model")
                self.model = YOLO("yolov8n.pt")

            # Move model to appropriate device
            self.model.to(self.device)
            logger.info(f"Model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load YOLOv8 model: {str(e)}")
            raise

    def detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Detect objects in the given image using YOLOv8

        Args:
            image_path: Path to the image file

        Returns:
            List of detected objects with coordinates, class, and confidence
        """
        if not self.model:
            logger.error("Model not loaded. Call load_model() first.")
            return []

        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return []

        try:
            # Perform inference
            results = self.model(image_path, conf=self.confidence_threshold)

            detections = []
            for result in results:
                # Process all detections in this result
                for i, (box, confidence, class_id) in enumerate(
                    zip(
                        result.boxes.xyxy.cpu().numpy(),  # Convert to numpy for processing
                        result.boxes.conf.cpu().numpy(),
                        result.boxes.cls.cpu().numpy().astype(int),
                    )
                ):
                    # Extract the class name
                    class_name = (
                        result.names[class_id]
                        if class_id in result.names
                        else f"class_{class_id}"
                    )

                    # Create a detection object
                    detection = {
                        "type": class_name,
                        "coordinates": [
                            int(box[0]),
                            int(box[1]),
                            int(box[2]),
                            int(box[3]),
                        ],
                        "confidence": float(confidence),
                        "class_id": int(class_id),
                    }

                    detections.append(detection)

            logger.info(f"Detected {len(detections)} objects in {image_path}")
            return detections

        except Exception as e:
            logger.error(f"Error detecting objects: {str(e)}")
            return []

    def detect_ui_elements(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Specialized method for detecting UI elements

        Args:
            image_path: Path to the image file

        Returns:
            List of detected UI elements with type information
        """
        # For now, this uses the same detection as general objects
        # In a future version, this could be specialized with a UI-specific model
        return self.detect_objects(image_path)

    def extract_text_from_regions(
        self, image_path: str, regions: List[Dict[str, Any]], ocr_engine=None
    ) -> List[Dict[str, Any]]:
        """
        Extract text from specific regions using OCR

        Args:
            image_path: Path to the image file
            regions: List of regions to extract text from (format: [x1, y1, x2, y2])
            ocr_engine: OCR engine to use (if None, will use pytesseract)

        Returns:
            List of regions with extracted text
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return regions

        try:
            import pytesseract

            # Load the image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return regions

            # Process each region
            for region in regions:
                if "coordinates" in region:
                    coords = region["coordinates"]
                    x1, y1, x2, y2 = coords

                    # Extract the region
                    roi = image[y1:y2, x1:x2]

                    # Skip if ROI is empty
                    if roi.size == 0:
                        region["text"] = ""
                        continue

                    # Convert to grayscale for better OCR
                    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                    # Use custom OCR engine if provided, otherwise use pytesseract
                    if ocr_engine and hasattr(ocr_engine, "run_ocr"):
                        # Save ROI to a temporary file
                        temp_path = f"temp_roi_{x1}_{y1}_{x2}_{y2}.png"
                        cv2.imwrite(temp_path, gray_roi)

                        # Run OCR
                        text = ocr_engine.run_ocr(temp_path)

                        # Clean up temp file
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    else:
                        # Use pytesseract directly
                        text = pytesseract.image_to_string(gray_roi).strip()

                    # Add text to region
                    region["text"] = text

            return regions

        except Exception as e:
            logger.error(f"Error extracting text from regions: {str(e)}")
            return regions

    def fine_tune_model(self, dataset_path: str, epochs: int = 10):
        """
        Fine-tune the YOLOv8 model on a custom dataset

        Args:
            dataset_path: Path to the dataset in YOLO format
            epochs: Number of training epochs
        """
        if not self.model:
            logger.error("Model not loaded. Call load_model() first.")
            return

        try:
            logger.info(f"Fine-tuning model on dataset: {dataset_path}")

            # Ensure the dataset exists
            if not os.path.exists(dataset_path):
                logger.error(f"Dataset not found: {dataset_path}")
                return

            # Train the model
            self.model.train(
                data=dataset_path,
                epochs=epochs,
                imgsz=640,
                batch=8,
                name="fine_tuned_ui_model",
            )

            logger.info("Model fine-tuning complete")

            # Update model path to the fine-tuned model
            self.model_path = os.path.join(
                "runs", "detect", "fine_tuned_ui_model", "weights", "best.pt"
            )

            # Load the fine-tuned model
            self.load_model()

        except Exception as e:
            logger.error(f"Error fine-tuning model: {str(e)}")

    def add_bounding_boxes(
        self, image_path: str, detections: List[Dict[str, Any]], output_path: str = None
    ) -> str:
        """
        Add bounding boxes to an image based on detections

        Args:
            image_path: Path to the input image
            detections: List of detections with coordinates
            output_path: Path to save the output image (if None, will generate one)

        Returns:
            Path to the image with bounding boxes
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return None

        try:
            # Load the image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return None

            # Generate output path if not provided
            if not output_path:
                base_name = os.path.basename(image_path)
                name, ext = os.path.splitext(base_name)
                output_path = os.path.join(
                    os.path.dirname(image_path), f"{name}_detected{ext}"
                )

            # Define colors for different object types (for variety in visualization)
            color_map = {
                "button": (0, 255, 0),  # Green
                "checkbox": (255, 0, 0),  # Blue
                "dropdown": (0, 0, 255),  # Red
                "text_field": (255, 255, 0),  # Cyan
                "link": (255, 0, 255),  # Magenta
                "icon": (0, 255, 255),  # Yellow
                "menu": (128, 0, 128),  # Purple
                "tab": (0, 128, 128),  # Teal
                "default": (255, 255, 255),  # White (default)
            }

            # Draw bounding boxes
            for detection in detections:
                if "coordinates" in detection:
                    x1, y1, x2, y2 = detection["coordinates"]
                    obj_type = detection.get("type", "default")
                    confidence = detection.get("confidence", 0)

                    # Get color for this object type
                    color = color_map.get(obj_type, color_map["default"])

                    # Draw rectangle
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

                    # Draw label
                    label = f"{obj_type}: {confidence:.2f}"
                    cv2.putText(
                        image,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2,
                    )

            # Save the image
            cv2.imwrite(output_path, image)
            logger.info(f"Saved annotated image to: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Error adding bounding boxes: {str(e)}")
            return None
