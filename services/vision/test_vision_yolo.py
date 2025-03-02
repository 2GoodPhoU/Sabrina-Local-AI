#!/usr/bin/env python3
"""
Test Script for Enhanced Vision Module with YOLOv8
=================================================
This script demonstrates and tests the enhanced vision module with YOLOv8 integration.

Usage:
    python test_vision_yolo.py --display --annotate
    python test_vision_yolo.py --use-existing path/to/image.png --annotate
"""

import os
import sys
import logging
import argparse
import time
import cv2
from pathlib import Path

# Ensure the project root is in the Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("vision_test")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Enhanced Vision Module Test")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--save-dir", type=str, default=None, help="Directory to save captured images"
    )
    parser.add_argument(
        "--display", action="store_true", help="Display captured images and detections"
    )
    parser.add_argument(
        "--use-existing",
        type=str,
        default=None,
        help="Use an existing image instead of capturing",
    )
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="Create annotated images with detections",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Automatically close windows after this many seconds (0 = wait for key)",
    )
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR testing")
    return parser.parse_args()


def setup_environment(args):
    """Ensure required directories exist and set up environment"""
    # Create necessary directories
    for directory in ["data", "data/captures", "logs", "models"]:
        os.makedirs(os.path.join(project_root, directory), exist_ok=True)

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    logger.info("Environment setup complete")


def initialize_vision_module():
    """Initialize the vision module"""
    try:
        from services.vision.vision_core import VisionCore

        logger.info("Creating VisionCore instance...")
        vision_core = VisionCore()

        # Check if Vision AI is available
        has_vision_ai = (
            hasattr(vision_core, "vision_ai") and vision_core.vision_ai is not None
        )
        logger.info(f"Vision AI available: {has_vision_ai}")

        # If Vision AI is not available, try to initialize it
        if not has_vision_ai:
            try:
                logger.info("Attempting to initialize Vision AI manually...")
                from services.vision.vision_ai import VisionAI

                vision_core.vision_ai = VisionAI()
                has_vision_ai = True
                logger.info("Vision AI initialized manually")
            except Exception as e:
                logger.warning(f"Failed to initialize Vision AI manually: {str(e)}")

        return vision_core, has_vision_ai
    except ImportError as e:
        logger.error(f"Failed to import VisionCore: {str(e)}")
        return None, False
    except Exception as e:
        logger.error(f"Error initializing vision module: {str(e)}")
        return None, False


def capture_or_load_image(vision_core, args):
    """Capture a new image or load an existing one"""
    if args.use_existing:
        if os.path.exists(args.use_existing):
            logger.info(f"Using existing image: {args.use_existing}")
            return args.use_existing
        else:
            logger.error(f"Specified image not found: {args.use_existing}")
            return None

    # Set capture directory if specified
    if args.save_dir:
        vision_core.capture_directory = args.save_dir
        os.makedirs(args.save_dir, exist_ok=True)
        logger.info(f"Set capture directory to: {args.save_dir}")

    # Capture screen
    logger.info("Capturing screen...")
    print("Capturing screen in 3 seconds...")
    time.sleep(3)  # Give user time to prepare

    image_path = vision_core.capture_screen(mode="full_screen")

    if image_path and os.path.exists(image_path):
        logger.info(f"Screen captured successfully: {image_path}")
        return image_path
    else:
        logger.error("Failed to capture screen")
        return None


def test_ocr(vision_core, image_path):
    """Test OCR functionality"""
    if not image_path or not os.path.exists(image_path):
        logger.error("No valid image provided for OCR test")
        return None

    logger.info(f"Running OCR on image: {image_path}")
    ocr_text = vision_core.vision_ocr.run_ocr(image_path)

    if ocr_text:
        logger.info("✓ OCR extracted text successfully")
        logger.info(
            f"Extracted text sample: {ocr_text[:200]}{'...' if len(ocr_text) > 200 else ''}"
        )
        return ocr_text
    else:
        logger.warning(
            "OCR returned no text - either no text in image or OCR not working"
        )
        return None


def test_ui_detection(vision_core, image_path):
    """Test UI element detection"""
    if not image_path or not os.path.exists(image_path):
        logger.error("No valid image provided for UI detection test")
        return None

    logger.info(f"Detecting UI elements in image: {image_path}")
    ui_elements = vision_core.detect_ui_elements(image_path)

    if ui_elements and len(ui_elements) > 0:
        logger.info(f"✓ Detected {len(ui_elements)} UI elements")

        # Log detected elements
        for i, element in enumerate(ui_elements[:10]):  # Show first 10 elements
            element_type = element.get("type", "unknown")
            confidence = element.get("confidence", 0.0)
            coords = element.get("coordinates", [0, 0, 0, 0])
            text = element.get("text", "")

            logger.info(f"  Element {i+1}: {element_type} (conf: {confidence:.2f})")
            logger.info(f"    Coords: {coords}")
            if text:
                logger.info(f"    Text: {text[:50]}{'...' if len(text) > 50 else ''}")

        return ui_elements
    else:
        logger.warning("No UI elements detected")
        return []


def create_annotated_image(vision_core, image_path, ui_elements):
    """Create an image with UI element annotations"""
    if not vision_core or not image_path:
        return None

    # Check if we can use the built-in annotation function
    if hasattr(vision_core, "create_annotated_image") and vision_core.vision_ai:
        logger.info("Using built-in annotation function")
        return vision_core.create_annotated_image(image_path)

    # Otherwise create our own annotations
    logger.info("Creating custom annotated image")
    try:
        # Create output path
        base_name = os.path.basename(image_path)
        name, ext = os.path.splitext(base_name)
        output_path = os.path.join(
            os.path.dirname(image_path), f"{name}_annotated{ext}"
        )

        # Load the image
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return None

        # Define colors for different object types
        color_map = {
            "button": (0, 255, 0),  # Green
            "checkbox": (255, 0, 0),  # Blue
            "dropdown": (0, 0, 255),  # Red
            "text_field": (255, 255, 0),  # Cyan
            "link": (255, 0, 255),  # Magenta
            "icon": (0, 255, 255),  # Yellow
            "menu": (128, 0, 128),  # Purple
            "tab": (0, 128, 128),  # Teal
            "unknown_ui_element": (200, 200, 200),  # Gray
            "default": (255, 255, 255),  # White
        }

        # Draw bounding boxes
        for element in ui_elements:
            if "coordinates" in element:
                x1, y1, x2, y2 = element["coordinates"]
                obj_type = element.get("type", "default")
                confidence = element.get("confidence", 0)

                # Get color for this object type
                color = color_map.get(obj_type, color_map["default"])

                # Draw rectangle
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

                # Draw label
                label = f"{obj_type}: {confidence:.2f}"
                cv2.putText(
                    img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
                )

        # Save the image
        cv2.imwrite(output_path, img)
        logger.info(f"Saved annotated image to: {output_path}")

        return output_path

    except Exception as e:
        logger.error(f"Error creating annotated image: {str(e)}")
        return None


def display_images(original_path, annotated_path, timeout=0):
    """Display original and annotated images"""
    try:
        # Load images
        original = cv2.imread(original_path)

        if annotated_path and os.path.exists(annotated_path):
            annotated = cv2.imread(annotated_path)

            # Resize if too large
            max_height = 800
            if original.shape[0] > max_height:
                scale = max_height / original.shape[0]
                original = cv2.resize(
                    original, (int(original.shape[1] * scale), max_height)
                )
            if annotated.shape[0] > max_height:
                scale = max_height / annotated.shape[0]
                annotated = cv2.resize(
                    annotated, (int(annotated.shape[1] * scale), max_height)
                )

            # Display side-by-side
            cv2.imshow("Original Image", original)
            cv2.imshow("Detected UI Elements", annotated)
        else:
            # Just show original
            cv2.imshow("Captured Image", original)

        # Wait for key press or timeout
        if timeout > 0:
            cv2.waitKey(timeout * 1000)
        else:
            print("Press any key to close the image windows...")
            cv2.waitKey(0)

        cv2.destroyAllWindows()

    except Exception as e:
        logger.error(f"Error displaying images: {str(e)}")


def main():
    """Main function"""
    # Parse arguments
    args = parse_arguments()

    # Setup environment
    setup_environment(args)

    print("\n===== Enhanced Vision Module Test with YOLOv8 =====\n")

    # Initialize vision module
    vision_core, has_vision_ai = initialize_vision_module()

    if not vision_core:
        logger.error("Failed to initialize vision module. Exiting.")
        return 1

    print(f"Vision AI available: {'✓' if has_vision_ai else '✗'}")

    # Capture or load image
    image_path = capture_or_load_image(vision_core, args)

    if not image_path:
        logger.error("Failed to obtain an image. Exiting.")
        return 1

    print(f"Image path: {image_path}")

    # Test OCR if not disabled
    ocr_text = None
    if not args.no_ocr:
        ocr_text = test_ocr(vision_core, image_path)
        if ocr_text:
            print("OCR Test: ✓ Success")
            print(
                f"Sample text: {ocr_text[:100]}{'...' if len(ocr_text) > 100 else ''}"
            )
        else:
            print("OCR Test: ⚠ No text extracted")

    # Test UI element detection
    ui_elements = test_ui_detection(vision_core, image_path)

    if ui_elements and len(ui_elements) > 0:
        print(f"UI Detection: ✓ Found {len(ui_elements)} elements")
    else:
        print("UI Detection: ⚠ No UI elements found")

    # Create annotated image if requested
    annotated_path = None
    if args.annotate and ui_elements:
        annotated_path = create_annotated_image(vision_core, image_path, ui_elements)
        if annotated_path:
            print(f"Annotated image created: {annotated_path}")
        else:
            print("Failed to create annotated image")

    # Display images if requested
    if args.display:
        print("\nDisplaying images...")
        display_images(image_path, annotated_path, args.timeout)

    print("\n===== Vision Test Complete =====")

    # Full analysis
    print("\nSummary:")
    print(f"- YOLOv8 available: {'✓' if has_vision_ai else '✗'}")
    if not args.no_ocr:
        print(f"- OCR working: {'✓' if ocr_text else '⚠'}")
    print(
        f"- UI elements detected: {'✓' if ui_elements and len(ui_elements) > 0 else '⚠'} ({len(ui_elements) if ui_elements else 0} elements)"
    )

    if has_vision_ai:
        return 0
    else:
        print("\nRecommendation: Install YOLOv8 for better UI element detection")
        print("pip install ultralytics")
        return 0


if __name__ == "__main__":
    sys.exit(main())
