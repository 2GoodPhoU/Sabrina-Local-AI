"""
Vision Component Tests for Sabrina AI
====================================
Tests for the Vision Core and OCR functionality.
"""

import os
import sys
import unittest
import tempfile
import time
from unittest.mock import MagicMock, patch
import shutil
import pytest
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import vision components
from services.vision.vision_core import VisionCore, VisionOCR
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler
from utilities.event_system import EventBus, EventType, Event, EventPriority

# Import base test class
from tests.test_framework import TestBase


class VisionCoreTests(TestBase):
    """Tests for the Vision Core"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create test image with text
        self.test_image_dir = tempfile.mkdtemp()
        self.test_image_path = os.path.join(self.test_image_dir, "test_image.png")
        self._create_test_image_with_text(
            self.test_image_path, 
            "Sabrina AI Test Image", 
            width=800, 
            height=600
        )
        
        # Create test capture directory
        self.test_capture_dir = os.path.join(self.test_image_dir, "captures")
        os.makedirs(self.test_capture_dir, exist_ok=True)
        
        # Initialize vision components with test directories
        self.vision_core = VisionCore()
        self.vision_core.capture_directory = self.test_capture_dir
    
    def tearDown(self):
        """Clean up test environment"""
        super().tearDown()
        
        # Remove test directories
        if hasattr(self, 'test_image_dir') and os.path.exists(self.test_image_dir):
            shutil.rmtree(self.test_image_dir)
    
    def _create_test_image_with_text(self, path, text, width=800, height=600):
        """Create a test image with text for OCR testing"""
        try:
            # Create a blank image
            image = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except IOError:
                # Use default font
                font = ImageFont.load_default()
            
            # Draw text
            draw.text((width // 4, height // 2), text, fill=(0, 0, 0), font=font)
            
            # Save the image
            image.save(path)
            return True
        except Exception as e:
            print(f"Error creating test image: {str(e)}")
            return False
    
    @patch.object(VisionCore, 'capture_screen')
    def test_analyze_screen(self, mock_capture):
        """Test screen analysis functionality"""
        # Mock capture_screen to return our test image
        mock_capture.return_value = self.test_image_path
        
        # Mock OCR to return predictable text
        self.vision_core.vision_ocr.run_ocr = MagicMock(return_value="Sabrina AI Test Image")
        
        # Test analyze_screen with no image provided
        result = self.vision_core.analyze_screen()
        
        # Verify
        self.assertIsInstance(result, dict)
        self.assertEqual(result["ocr_text"], "Sabrina AI Test Image")
        self.assertEqual(result["image_path"], self.test_image_path)
        
        # Test analyze_screen with image provided
        mock_capture.reset_mock()
        result = self.vision_core.analyze_screen(image_path=self.test_image_path)
        
        # Verify
        self.assertIsInstance(result, dict)
        self.assertEqual(result["ocr_text"], "Sabrina AI Test Image")
        self.assertEqual(result["image_path"], self.test_image_path)
        mock_capture.assert_not_called()  # Should not capture screen when image is provided
    
    @patch('mss.mss')
    def test_capture_screen(self, mock_mss):
        """Test screen capture functionality"""
        # Mock MSS to simulate screen capture
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = b'\x00' * (800 * 600 * 3)  # RGB data
        mock_screenshot.size = (800, 600)
        
        mock_sct = MagicMock()
        mock_sct.__enter__.return_value = mock_sct
        mock_sct.monitors = [{"top": 0, "left": 0, "width": 800, "height": 600}]
        mock_sct.grab.return_value = mock_screenshot
        
        mock_mss.return_value = mock_sct
        
        # Mock mss.tools.to_png to save our test image instead
        def mock_to_png(rgb, size, output):
            shutil.copy(self.test_image_path, output)
            return True
        
        with patch('mss.tools.to_png', mock_to_png):
            # Test full screen capture
            result = self.vision_core.capture_screen(mode="full_screen")
            
            # Verify
            self.assertIsNotNone(result)
            self.assertTrue(os.path.exists(result))
            mock_sct.grab.assert_called_once()
    
    @patch('services.vision.vision_core.VisionCore._check_mss_available')
    @patch('PIL.ImageGrab.grab')
    def test_capture_screen_fallback(self, mock_grab, mock_check_mss):
        """Test screen capture with PIL fallback"""
        # Mock MSS as unavailable
        mock_check_mss.return_value = False
        self.vision_core.mss_available = False
        
        # Mock PIL.ImageGrab
        mock_image = Image.new('RGB', (800, 600), color=(255, 255, 255))
        mock_grab.return_value = mock_image
        
        # Test fallback capture
        with patch.object(mock_image, 'save') as mock_save:
            result = self.vision_core.capture_screen()
            
            # Verify
            self.assertIsNotNone(result)
            mock_grab.assert_called_once()
            mock_save.assert_called_once()
    
    @patch('pygetwindow.getActiveWindow')
    def test_get_active_window_info(self, mock_get_active):
        """Test getting active window information"""
        # Mock active window
        mock_window = MagicMock()
        mock_window.title = "Test Window"
        mock_window.left = 100
        mock_window.top = 100
        mock_window.width = 800
        mock_window.height = 600
        mock_get_active.return_value = mock_window
        
        # Test get_active_window_info
        result = self.vision_core.get_active_window_info()
        
        # Verify
        self.assertIsInstance(result, dict)
        self.assertEqual(result["title"], "Test Window")
        self.assertEqual(result["position"], (100, 100))
        self.assertEqual(result["size"], (800, 600))
        self.assertEqual(result["rect"], (100, 100, 800, 600))
        
        # Test with no active window
        mock_get_active.return_value = None
        result = self.vision_core.get_active_window_info()
        
        # Verify
        self.assertIsNone(result)


class VisionOCRTests(TestBase):
    """Tests for the Vision OCR functionality"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create test image with text
        self.test_image_dir = tempfile.mkdtemp()
        self.test_image_path = os.path.join(self.test_image_dir, "test_image.png")
        self._create_test_image_with_text(
            self.test_image_path, 
            "Sabrina AI Test Image", 
            width=800, 
            height=600
        )
        
        # Initialize OCR component
        self.vision_ocr = VisionOCR()
        
        # Check if Tesseract is available
        self.tesseract_available = self.vision_ocr.tesseract_available
    
    def tearDown(self):
        """Clean up test environment"""
        super().tearDown()
        
        # Remove test directories
        if hasattr(self, 'test_image_dir') and os.path.exists(self.test_image_dir):
            shutil.rmtree(self.test_image_dir)
    
    def _create_test_image_with_text(self, path, text, width=800, height=600):
        """Create a test image with text for OCR testing"""
        try:
            # Create a blank image
            image = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except IOError:
                # Use default font
                font = ImageFont.load_default()
            
            # Draw text
            draw.text((width // 4, height // 2), text, fill=(0, 0, 0), font=font)
            
            # Save the image
            image.save(path)
            return True
        except Exception as e:
            print(f"Error creating test image: {str(e)}")
            return False
    
    def test_preprocess_image(self):
        """Test image preprocessing for OCR"""
        # Skip if OpenCV is not installed
        try:
            import cv2
        except ImportError:
            self.skipTest("OpenCV not installed")
        
        # Test image preprocessing
        preprocessed = self.vision_ocr.preprocess_image(self.test_image_path)
        
        # Verify
        self.assertIsNotNone(preprocessed)
        
        # Verify image dimensions
        self.assertEqual(preprocessed.shape[:2], (600, 800))
    
    @patch('pytesseract.image_to_string')
    def test_run_ocr(self, mock_image_to_string):
        """Test OCR functionality"""
        # Mock tesseract output
        mock_image_to_string.return_value = "Sabrina AI Test Image\n"
        
        # Override tesseract_available for testing
        self.vision_ocr.tesseract_available = True
        
        # Test run_ocr
        result = self.vision_ocr.run_ocr(self.test_image_path)
        
        # Verify
        self.assertEqual(result, "Sabrina AI Test Image")
        mock_image_to_string.assert_called_once()
        
        # Test with non-existent image
        result = self.vision_ocr.run_ocr("nonexistent.png")
        
        # Verify
        self.assertEqual(result, "")
    
    def test_integration_with_real_ocr(self):
        """Test OCR with real Tesseract if available"""
        # Skip if Tesseract is not available
        if not self.tesseract_available:
            self.skipTest("Tesseract OCR not installed")
        
        # Create a new image with simple text for reliable OCR
        simple_image_path = os.path.join(self.test_image_dir, "simple.png")
        self._create_test_image_with_text(
            simple_image_path, 
            "HELLO WORLD", 
            width=400, 
            height=200
        )
        
        # Test OCR on simple image
        result = self.vision_ocr.run_ocr(simple_image_path)
        
        # Verify - allow for some OCR variability
        self.assertTrue(
            "HELLO" in result.upper() or "WORLD" in result.upper(), 
            f"OCR result '{result}' doesn't contain expected text"
        )


class VisionIntegrationTests(TestBase):
    """Integration tests for the Vision system"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create vision components
        self.vision_core = VisionCore()
        
        # Create test image with text
        self.test_image_dir = tempfile.mkdtemp()
        self.test_image_path = os.path.join(self.test_image_dir, "test_image.png")
        self._create_test_image_with_text(
            self.test_image_path, 
            "Sabrina AI Test Image", 
            width=800, 
            height=600
        )
    
    def tearDown(self):
        """Clean up test environment"""
        super().tearDown()
        
        # Remove test directories
        if hasattr(self, 'test_image_dir') and os.path.exists(self.test_image_dir):
            shutil.rmtree(self.test_image_dir)
    
    def _create_test_image_with_text(self, path, text, width=800, height=600):
        """Create a test image with text for OCR testing"""
        try:
            # Create a blank image
            image = Image.new('RGB', (width, height), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # Try to load a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except IOError:
                # Use default font
                font = ImageFont.load_default()
            
            # Draw text
            draw.text((width // 4, height // 2), text, fill=(0, 0, 0), font=font)
            
            # Save the image
            image.save(path)
            return True
        except Exception as e:
            print(f"Error creating test image: {str(e)}")
            return False
    
    @pytest.mark.integration
    def test_vision_event_integration(self):
        """Test integration between Vision system and event system"""
        # Create event handler to track vision events
        vision_events = []
        
        def vision_event_handler(event):
            vision_events.append(event)
        
        # Register handler
        handler = self.event_bus.create_event_handler(
            event_types=[EventType.VISION],
            callback=vision_event_handler
        )
        self.event_bus.register_handler(handler)
        
        # Mock vision_core.capture_screen to return our test image
        self.vision_core.capture_screen = MagicMock(return_value=self.test_image_path)
        
        # Post vision event
        self.event_bus.post_event(Event(
            event_type=EventType.VISION,
            data={"command": "capture"},
            source="test"
        ))
        
        # Wait for event to be processed
        self.wait_for_events()
        
        # Verify event was received
        self.assertGreaterEqual(len(vision_events), 1)
        self.assertEqual(vision_events[0].data.get("command"), "capture")


if __name__ == "__main__":
    unittest.main()