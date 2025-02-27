#!/usr/bin/env python3
"""
Vision Module Test Script for Sabrina AI
=======================================
This script tests the vision module components independently to identify issues.
"""

import os
import sys
import time
import logging
import argparse
import subprocess
import traceback
from pathlib import Path
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vision_test")

# Ensure project directory is in Python path
script_dir = Path(__file__).parent.absolute()
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Vision Module Test")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--save-dir", type=str, default=None, 
                       help="Directory to save captured images (default: data/captures)")
    parser.add_argument("--display-images", action="store_true",
                       help="Display captured images (requires cv2.imshow)")
    parser.add_argument("--test-active-window", action="store_true",
                       help="Test active window detection")
    return parser.parse_args()

def check_directories():
    """Ensure required directories exist"""
    dirs = ["logs", "data", "data/captures", "config"]
    for d in dirs:
        os.makedirs(project_dir / d, exist_ok=True)
    logger.info("Required directories exist")
    return project_dir / "data" / "captures"

def check_python_dependencies():
    """Check if required Python packages are installed"""
    required_packages = [
        "opencv-python", "numpy", "pytesseract", "pillow", "mss", "pygetwindow"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            if package == "opencv-python":
                import cv2
                logger.info(f"✓ {package} is installed")
            elif package == "pytesseract":
                import pytesseract
                logger.info(f"✓ {package} is installed")
            else:
                __import__(package.replace("-", "_"))
                logger.info(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"✗ {package} is not installed")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.error("Install them using: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_system_dependencies():
    """Check if required system dependencies are installed"""
    system_deps = {
        "tesseract": "tesseract --version"
    }
    
    all_installed = True
    for name, command in system_deps.items():
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✓ {name} is installed")
            else:
                logger.warning(f"✗ {name} is not installed or not in PATH")
                all_installed = False
        except Exception as e:
            logger.error(f"Error checking {name}: {str(e)}")
            all_installed = False
    
    return all_installed

def test_screen_capture(save_dir, display_images=False):
    """Test the screen capture functionality"""
    try:
        from services.vision.vision_core import VisionCore
        
        logger.info("Creating VisionCore instance...")
        vision_core = VisionCore()
        
        # Override capture directory if needed
        if save_dir:
            vision_core.capture_directory = str(save_dir)
            logger.info(f"Set capture directory to: {save_dir}")
        
        # Test screen capture
        logger.info("Capturing screen...")
        capture_result = vision_core.capture_screen()
        
        if capture_result and os.path.exists(capture_result):
            logger.info(f"✓ Screen captured successfully: {capture_result}")
            
            # Display the captured image if requested
            if display_images:
                try:
                    import cv2
                    img = cv2.imread(capture_result)
                    cv2.imshow("Captured Screen", img)
                    cv2.waitKey(3000)  # Display for 3 seconds
                    cv2.destroyAllWindows()
                except Exception as e:
                    logger.error(f"Failed to display image: {str(e)}")
            
            return capture_result, vision_core
        else:
            logger.error("✗ Screen capture failed")
            return None, vision_core
    except ImportError as e:
        logger.error(f"✗ Failed to import VisionCore: {str(e)}")
        return None, None
    except Exception as e:
        logger.error(f"✗ Error in screen capture test: {str(e)}")
        traceback.print_exc()
        return None, None

def test_ocr(image_path, vision_core=None):
    """Test OCR functionality with a captured image"""
    if not image_path or not os.path.exists(image_path):
        logger.error("No valid image provided for OCR test")
        return False
    
    try:
        # Create VisionCore if not provided
        if vision_core is None:
            from services.vision.vision_core import VisionCore
            vision_core = VisionCore()
        
        # Check if vision_ocr is available
        if not hasattr(vision_core, 'vision_ocr') or not hasattr(vision_core.vision_ocr, 'run_ocr'):
            logger.error("VisionCore does not have OCR capability")
            return False
        
        # Run OCR
        logger.info(f"Running OCR on image: {image_path}")
        ocr_text = vision_core.vision_ocr.run_ocr(image_path)
        
        if ocr_text:
            logger.info("✓ OCR extracted text successfully")
            logger.info(f"Extracted text sample: {ocr_text[:200]}{'...' if len(ocr_text) > 200 else ''}")
            return True
        else:
            logger.warning("OCR returned no text - either no text in image or OCR not working")
            return False
    except Exception as e:
        logger.error(f"✗ Error in OCR test: {str(e)}")
        traceback.print_exc()
        return False

def test_active_window(vision_core=None):
    """Test active window detection"""
    try:
        # Create VisionCore if not provided
        if vision_core is None:
            from services.vision.vision_core import VisionCore
            vision_core = VisionCore()
        
        # Check if get_active_window_info is available
        if not hasattr(vision_core, 'get_active_window_info'):
            logger.error("VisionCore does not have active window detection capability")
            return False
        
        # Get active window info
        logger.info("Getting active window information...")
        window_info = vision_core.get_active_window_info()
        
        if window_info:
            logger.info("✓ Active window detected successfully")
            for key, value in window_info.items():
                logger.info(f"  {key}: {value}")
            return True
        else:
            logger.warning("Could not detect active window")
            return False
    except Exception as e:
        logger.error(f"✗ Error in active window detection test: {str(e)}")
        traceback.print_exc()
        return False

def test_vision_analysis(image_path, vision_core=None):
    """Test full vision analysis on a captured image"""
    if not image_path or not os.path.exists(image_path):
        logger.error("No valid image provided for vision analysis test")
        return False
    
    try:
        # Create VisionCore if not provided
        if vision_core is None:
            from services.vision.vision_core import VisionCore
            vision_core = VisionCore()
        
        # Check if analyze_screen is available
        if not hasattr(vision_core, 'analyze_screen'):
            logger.error("VisionCore does not have screen analysis capability")
            return False
        
        # Run analysis
        logger.info(f"Running full vision analysis on image: {image_path}")
        analysis = vision_core.analyze_screen(image_path)
        
        if analysis:
            logger.info("✓ Screen analysis completed successfully")
            # Print a summary of the analysis
            for key, value in analysis.items():
                if key == "ocr_text":
                    logger.info(f"  {key}: {value[:100]}{'...' if len(value) > 100 else ''}")
                elif isinstance(value, dict):
                    logger.info(f"  {key}: {type(value).__name__} with {len(value)} items")
                else:
                    logger.info(f"  {key}: {value}")
            return True
        else:
            logger.warning("Screen analysis returned no results")
            return False
    except Exception as e:
        logger.error(f"✗ Error in vision analysis test: {str(e)}")
        traceback.print_exc()
        return False

def test_ui_element_detection(image_path, vision_core=None):
    """Test UI element detection if available"""
    if not image_path or not os.path.exists(image_path):
        logger.error("No valid image provided for UI element detection test")
        return False
    
    try:
        # Create VisionCore if not provided
        if vision_core is None:
            from services.vision.vision_core import VisionCore
            vision_core = VisionCore()
        
        # Check if detect_ui_elements is available
        if not hasattr(vision_core, 'detect_ui_elements'):
            logger.warning("UI element detection not available in VisionCore")
            return False
        
        # Run UI element detection
        logger.info(f"Detecting UI elements in image: {image_path}")
        ui_elements = vision_core.detect_ui_elements(image_path)
        
        if ui_elements and len(ui_elements) > 0:
            logger.info(f"✓ Detected {len(ui_elements)} UI elements")
            # Print summary of detected elements
            for i, element in enumerate(ui_elements[:5]):  # Show first 5 elements
                element_type = element.get("type", "unknown")
                coordinates = element.get("coordinates", [])
                text = element.get("text", "")
                logger.info(f"  Element {i+1}: {element_type}, text: {text[:30]}{'...' if len(text) > 30 else ''}")
            return True
        else:
            logger.warning("No UI elements detected in the image")
            return False
    except Exception as e:
        logger.error(f"✗ Error in UI element detection test: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n===== Sabrina AI Vision Module Test =====\n")
    
    # Check environment
    print("Step 1: Checking environment...")
    captures_dir = check_directories()
    # Use specified save directory if provided
    if args.save_dir:
        captures_dir = Path(args.save_dir)
        os.makedirs(captures_dir, exist_ok=True)
        
    print("\nStep 2: Checking Python dependencies...")
    python_deps_ok = check_python_dependencies()
    
    print("\nStep 3: Checking system dependencies...")
    system_deps_ok = check_system_dependencies()
    
    # Only continue with tests if dependencies are ok
    if python_deps_ok:
        print("\nStep 4: Testing screen capture...")
        captured_image, vision_core = test_screen_capture(captures_dir, args.display_images)
        screen_capture_ok = captured_image is not None
        
        if screen_capture_ok and vision_core:
            print("\nStep 5: Testing OCR functionality...")
            ocr_ok = test_ocr(captured_image, vision_core)
            
            if args.test_active_window or args.debug:
                print("\nStep 6: Testing active window detection...")
                active_window_ok = test_active_window(vision_core)
            else:
                active_window_ok = None
                logger.info("Skipping active window detection test (use --test-active-window to enable)")
            
            print("\nStep 7: Testing vision analysis...")
            analysis_ok = test_vision_analysis(captured_image, vision_core)
            
            print("\nStep 8: Testing UI element detection (if available)...")
            ui_detection_ok = test_ui_element_detection(captured_image, vision_core)
            
            # Print summary
            print("\n===== Test Results =====")
            print(f"Python Dependencies: {'✓ OK' if python_deps_ok else '✗ Issues Found'}")
            print(f"System Dependencies: {'✓ OK' if system_deps_ok else '✗ Issues Found'}")
            print(f"Screen Capture: {'✓ OK' if screen_capture_ok else '✗ Failed'}")
            print(f"OCR Functionality: {'✓ OK' if ocr_ok else '✗ Issues Found'}")
            
            if active_window_ok is not None:
                print(f"Active Window Detection: {'✓ OK' if active_window_ok else '✗ Issues Found'}")
            
            print(f"Vision Analysis: {'✓ OK' if analysis_ok else '✗ Issues Found'}")
            
            if ui_detection_ok is not None:
                print(f"UI Element Detection: {'✓ OK' if ui_detection_ok else '✗ Not Available or Issues Found'}")
            
            # Final result
            tests_required = [screen_capture_ok, ocr_ok, analysis_ok]
            tests_passed = sum(1 for test in tests_required if test)
            
            if all(tests_required):
                print("\n✓ Vision module is working correctly!")
                return 0
            else:
                print(f"\n⚠ Vision module tests: {tests_passed}/{len(tests_required)} tests passed.")
                
                # Provide troubleshooting tips
                print("\nTroubleshooting Tips:")
                if not screen_capture_ok:
                    print("- Check if screen capture libraries (mss, PIL) are installed and working")
                    print("- Try different capture methods if available")
                if not ocr_ok:
                    print("- Verify Tesseract OCR is installed and in your PATH")
                    print("- Check Tesseract path in vision_ocr.py")
                if not analysis_ok:
                    print("- Check for errors in the analyze_screen method")
                if active_window_ok is not None and not active_window_ok:
                    print("- Install pygetwindow for active window detection")
                if ui_detection_ok is not None and not ui_detection_ok:
                    print("- UI element detection requires additional models")
                    print("- Check if YOLO models are installed and properly configured")
                
                return 1
        else:
            print("\n✗ Cannot proceed with tests because screen capture failed.")
            print("\nTroubleshooting Tips:")
            print("- Check if screen capture libraries (mss, PIL) are installed")
            print("- Verify screen capture permissions are granted to the application")
            return 1
    else:
        print("\n✗ Cannot proceed with tests due to missing Python dependencies.")
        return 1

if __name__ == "__main__":
    sys.exit(main())