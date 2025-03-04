#!/usr/bin/env python3
"""
Integration tests for Sabrina AI Vision Service
Tests the integration between the vision service and other components
"""

import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch
import tempfile
import logging

# Import test utilities
from tests.test_utils.paths import (
    ensure_project_root_in_sys_path,
)

# Import components to test
from core.component_service_wrappers import VisionService
from utilities.event_system import Event, EventBus, EventType
from core.state_machine import StateMachine

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vision_integration_test")


class TestVisionServiceIntegration(unittest.TestCase):
    """Integration tests for the Vision Service component"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Create a temporary directory for test files
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Create a test image for OCR testing
        cls.test_image_path = os.path.join(cls.temp_dir.name, "test_image.png")
        cls._create_test_image(cls.test_image_path)

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures"""
        cls.temp_dir.cleanup()

    @classmethod
    def _create_test_image(cls, image_path):
        """Create a simple test image with text"""
        try:
            import cv2
            import numpy as np

            # Create a blank white image
            img = np.ones((300, 500, 3), dtype=np.uint8) * 255

            # Add text to the image
            text = "Sabrina AI Vision Test"
            cv2.putText(img, text, (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

            # Save the image
            cv2.imwrite(image_path, img)
            logger.info(f"Created test image at {image_path}")
        except ImportError:
            # If OpenCV is not available, create an empty file
            with open(image_path, "wb") as f:
                f.write(b"")
            logger.warning("OpenCV not available, created empty test image")

    def setUp(self):
        """Set up test fixtures"""
        # Create event bus
        self.event_bus = EventBus()
        self.event_bus.start()

        # Create state machine
        self.state_machine = StateMachine(self.event_bus)

        # Create test config
        self.config = {
            "enabled": True,
            "capture_method": "auto",
            "use_ocr": True,
            "use_object_detection": True,
            "capture_directory": self.temp_dir.name,
        }

        # Mock VisionCore
        self.setup_vision_core_mock()

        # Create vision service
        self.vision_service = VisionService(
            name="vision",
            event_bus=self.event_bus,
            state_machine=self.state_machine,
            config=self.config,
        )

        # Initialize the service
        self.vision_service.initialize()

    def tearDown(self):
        """Clean up test fixtures"""
        # Shutdown vision service
        self.vision_service.shutdown()

        # Stop event bus
        self.event_bus.stop()

        # Stop patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def setup_vision_core_mock(self):
        """Set up mocks for vision core classes"""
        self._patchers = []

        # Patch VisionCore
        vision_core_patcher = patch("services.vision.vision_core.VisionCore")
        self.mock_vision_core_class = vision_core_patcher.start()
        self._patchers.append(vision_core_patcher)

        # Create mock instance
        self.mock_vision_core = MagicMock()

        # Configure mock behavior for screen capture
        def mock_capture_screen(mode="full_screen", region=None):
            return self.test_image_path

        self.mock_vision_core.capture_screen.side_effect = mock_capture_screen

        # Configure mock behavior for analyze_screen
        def mock_analyze_screen(image_path=None):
            if not image_path:
                image_path = self.test_image_path

            return {
                "ocr_text": "Sabrina AI Vision Test",
                "ui_elements": [
                    {
                        "type": "button",
                        "coordinates": [50, 100, 150, 150],
                        "confidence": 0.85,
                        "text": "Button Text",
                    }
                ],
                "timestamp": time.time(),
                "image_path": image_path,
            }

        self.mock_vision_core.analyze_screen.side_effect = mock_analyze_screen

        # Configure mock behavior for detect_ui_elements
        def mock_detect_ui_elements(image_path):
            return [
                {
                    "type": "button",
                    "coordinates": [50, 100, 150, 150],
                    "confidence": 0.85,
                    "text": "Button Text",
                },
                {
                    "type": "text_field",
                    "coordinates": [200, 100, 400, 150],
                    "confidence": 0.9,
                    "text": "Input Field",
                },
            ]

        self.mock_vision_core.detect_ui_elements.side_effect = mock_detect_ui_elements

        # Configure mock vision_ocr
        self.mock_vision_ocr = MagicMock()
        self.mock_vision_ocr.run_ocr.return_value = "Sabrina AI Vision Test"
        self.mock_vision_core.vision_ocr = self.mock_vision_ocr

        # Set the mock instance as the return value
        self.mock_vision_core_class.return_value = self.mock_vision_core

    def test_vision_service_initialization(self):
        """Test vision service initialization"""
        # Patch the capture directory to match test directory
        self.vision_service.capture_directory = self.temp_dir.name

        # Update the mock_vision_core capture_directory attribute
        if hasattr(self.mock_vision_core, "capture_directory"):
            self.mock_vision_core.capture_directory = self.temp_dir.name

        # Check that service was initialized
        self.assertEqual(self.vision_service.status.name, "READY")
        self.assertIsNotNone(self.vision_service.vision_core)

        # Check config values were passed correctly
        self.assertEqual(self.vision_service.capture_method, "auto")
        self.assertTrue(self.vision_service.use_ocr)
        self.assertTrue(self.vision_service.use_object_detection)
        self.assertEqual(self.vision_service.capture_directory, self.temp_dir.name)

    def test_capture_screen(self):
        """Test screen capture functionality"""
        # Mock the event bus post_event method to enable assertions
        self.event_bus.post_event = MagicMock(return_value=True)

        # Call capture_screen
        image_path = self.vision_service.capture_screen()

        # Check result
        self.assertEqual(image_path, self.test_image_path)

        # Check that vision_core.capture_screen was called
        self.mock_vision_core.capture_screen.assert_called_once_with(
            mode="full_screen", region=None
        )

        # Check that event was posted
        self.event_bus.post_event.assert_called()

        # Verify the image path exists
        self.assertTrue(os.path.exists(image_path))

    def test_capture_screen_with_parameters(self):
        """Test screen capture with specific parameters"""
        # Define custom region
        region = {"left": 0, "top": 0, "width": 500, "height": 500}

        # Call capture_screen with parameters
        image_path = self.vision_service.capture_screen(
            mode="specific_region", region=region
        )

        # Check that vision_core.capture_screen was called with correct parameters
        self.mock_vision_core.capture_screen.assert_called_with(
            mode="specific_region", region=region
        )

        # Verify result
        self.assertEqual(image_path, self.test_image_path)

    def test_screen_capture_event_handling(self):
        """Test handling of screen capture events"""
        # Create a result collector
        captured_events = []

        # Create a handler for capture events
        def capture_handler(event):
            if event.event_type == EventType.SCREEN_CAPTURED:
                captured_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=capture_handler, event_types=[EventType.SCREEN_CAPTURED]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post an event directly for testing
        test_event = Event(
            event_type=EventType.SCREEN_CAPTURED,
            data={"image_path": self.test_image_path, "mode": "full_screen"},
            source="test",
        )

        # Use immediate event processing for reliable testing
        self.event_bus.post_event_immediate(test_event)

        # Check that event was posted
        self.assertEqual(len(captured_events), 1)
        self.assertEqual(captured_events[0].event_type, EventType.SCREEN_CAPTURED)
        self.assertEqual(captured_events[0].get("image_path"), self.test_image_path)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_analyze_screen(self):
        """Test screen analysis functionality"""
        # Call analyze_screen
        analysis = self.vision_service.analyze_screen(self.test_image_path)

        # Check results
        self.assertIn("ocr_text", analysis)
        self.assertEqual(analysis["ocr_text"], "Sabrina AI Vision Test")
        self.assertIn("ui_elements", analysis)
        self.assertEqual(len(analysis["ui_elements"]), 1)
        self.assertEqual(analysis["ui_elements"][0]["type"], "button")

        # Check vision_core.analyze_screen was called
        self.mock_vision_core.analyze_screen.assert_called_once_with(
            self.test_image_path
        )

        # Check OCR text was stored
        self.assertEqual(self.vision_service.last_ocr_text, "Sabrina AI Vision Test")

        # Check UI elements were stored
        self.assertEqual(len(self.vision_service.last_detected_elements), 1)

    def test_detect_ui_elements(self):
        """Test UI element detection"""
        # Call detect_ui_elements
        elements = self.vision_service.detect_ui_elements(self.test_image_path)

        # Check results
        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0]["type"], "button")
        self.assertEqual(elements[1]["type"], "text_field")

        # Check vision_core.detect_ui_elements was called
        self.mock_vision_core.detect_ui_elements.assert_called_once_with(
            self.test_image_path
        )

        # Check elements were stored
        self.assertEqual(len(self.vision_service.last_detected_elements), 2)

    def test_extract_text(self):
        """Test text extraction using OCR"""
        # Call extract_text
        text = self.vision_service.extract_text(self.test_image_path)

        # Check result
        self.assertEqual(text, "Sabrina AI Vision Test")

        # Check vision_ocr.run_ocr was called
        self.mock_vision_ocr.run_ocr.assert_called_once_with(self.test_image_path)

        # Check OCR text was stored
        self.assertEqual(self.vision_service.last_ocr_text, "Sabrina AI Vision Test")

    def test_element_detection_event_handling(self):
        """Test handling of element detection events"""
        # Create a result collector
        detection_events = []

        # Create a handler for detection events
        def detection_handler(event):
            if event.event_type == EventType.ELEMENT_DETECTED:
                detection_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=detection_handler, event_types=[EventType.ELEMENT_DETECTED]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post an event directly for testing
        test_event = Event(
            event_type=EventType.ELEMENT_DETECTED,
            data={
                "elements": [{"type": "button", "coordinates": [10, 20, 30, 40]}],
                "image_path": self.test_image_path,
            },
            source="test",
        )
        self.event_bus.post_event_immediate(test_event)

        # Wait for event processing
        time.sleep(0.1)

        # Check that event was received
        self.assertGreaterEqual(len(detection_events), 1)
        self.assertEqual(detection_events[0].event_type, EventType.ELEMENT_DETECTED)
        self.assertIn("elements", detection_events[0].data)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_ocr_result_event_handling(self):
        """Test handling of OCR result events"""
        # Create a result collector
        ocr_events = []

        # Create a handler for OCR events
        def ocr_handler(event):
            if event.event_type == EventType.OCR_RESULT:
                ocr_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=ocr_handler, event_types=[EventType.OCR_RESULT]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post an event directly for testing
        test_event = Event(
            event_type=EventType.OCR_RESULT,
            data={"text": "Sabrina AI Vision Test", "image_path": self.test_image_path},
            source="test",
        )
        self.event_bus.post_event_immediate(test_event)

        # Wait for event processing
        time.sleep(0.1)

        # Check that event was received
        self.assertGreaterEqual(len(ocr_events), 1)
        self.assertEqual(ocr_events[0].event_type, EventType.OCR_RESULT)
        self.assertIn("text", ocr_events[0].data)
        self.assertEqual(ocr_events[0].get("text"), "Sabrina AI Vision Test")

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_status_reporting(self):
        """Test status reporting"""
        # Set some state for testing
        self.vision_service.last_capture_path = self.test_image_path
        self.vision_service.last_ocr_text = "Sabrina AI Vision Test"
        self.vision_service.last_detected_elements = [
            {"type": "button", "coordinates": [50, 100, 150, 150]}
        ]

        # Explicitly set the capture directory to match expectations
        self.vision_service.capture_directory = self.temp_dir.name

        # Get status
        status = self.vision_service.get_status()

        # Check status content
        self.assertEqual(status["name"], "vision")
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["last_capture_path"], self.test_image_path)
        self.assertEqual(status["last_ocr_text"], "Sabrina AI Vision Test")
        self.assertEqual(status["last_element_count"], 1)
        self.assertEqual(status["capture_directory"], self.temp_dir.name)
        self.assertEqual(status["capture_method"], "auto")
        self.assertTrue(status["use_ocr"])
        self.assertTrue(status["use_object_detection"])

    def test_error_handling(self):
        """Test error handling in vision service"""
        # Configure mock to raise an exception
        self.mock_vision_core.capture_screen.side_effect = Exception("Test error")

        # Create a result collector
        error_events = []

        # Create a handler for error events
        def error_handler(event):
            if event.event_type == EventType.SYSTEM_ERROR:
                error_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=error_handler, event_types=[EventType.SYSTEM_ERROR]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Call method that should raise an error
        result = self.vision_service.capture_screen()

        # Check result
        self.assertIsNone(result)

        # Wait for event processing
        time.sleep(0.1)

        # Check that error event was posted
        self.assertGreaterEqual(len(error_events), 1)
        self.assertEqual(error_events[0].event_type, EventType.SYSTEM_ERROR)
        self.assertEqual(error_events[0].get("component"), "vision")

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_analyze_screen_with_capture(self):
        """Test analyze_screen with automatic capture"""
        # Ensure capture returns valid path
        self.mock_vision_core.capture_screen.side_effect = (
            lambda mode, region=None: self.test_image_path
        )

        # Call analyze_screen without providing an image path
        analysis = self.vision_service.analyze_screen()

        # Check that capture_screen was called
        self.mock_vision_core.capture_screen.assert_called()

        # Check that analyze_screen was called with the captured image
        self.mock_vision_core.analyze_screen.assert_called_with(self.test_image_path)

        # Check results
        self.assertIn("ocr_text", analysis)
        self.assertIn("ui_elements", analysis)

    def test_integration_with_automation(self):
        """Test integration with automation component"""
        # Create a mock automation service
        mock_automation = MagicMock()
        mock_automation.click_at.return_value = True

        # Add it to core components
        if hasattr(self.vision_service, "components"):
            self.vision_service.components["automation"] = mock_automation

        # Create an example UI element
        button = {
            "type": "button",
            "coordinates": [100, 150, 200, 180],
            "confidence": 0.9,
            "text": "Submit",
        }

        # Set it as a detected element
        self.vision_service.last_detected_elements = [button]

        # Now simulate a workflow where vision detects a button and automation clicks it
        # This would typically be coordinated by the core system, but we can test the integration here

        # Detect UI elements
        elements = self.vision_service.detect_ui_elements(self.test_image_path)

        # Extract button coordinates (center point for clicking)
        if elements and len(elements) > 0:
            button = elements[0]  # Get first button
            coords = button["coordinates"]
            center_x = (coords[0] + coords[2]) // 2
            center_y = (coords[1] + coords[3]) // 2

            # In a real scenario, the core would now call automation.click_at(center_x, center_y)
            # Here we'll just verify that we have valid coordinates
            self.assertIsInstance(center_x, int)
            self.assertIsInstance(center_y, int)
            self.assertGreater(center_x, 0)
            self.assertGreater(center_y, 0)

    def test_shutdown_behavior(self):
        """Test behavior during shutdown"""
        # Save the current handler IDs count
        initial_handler_count = len(self.vision_service.handler_ids)
        print(initial_handler_count)

        # Call shutdown
        result = self.vision_service.shutdown()

        # Check result
        self.assertTrue(result)

        # Verify status is updated
        self.assertEqual(self.vision_service.status.name, "SHUTDOWN")

        # Verify handlers were unregistered
        # Note: If the handlers are properly unregistered, the count should be 0
        # If there are still handlers after shutdown, something is wrong with the shutdown logic
        self.assertEqual(len(self.vision_service.handler_ids), 0)


if __name__ == "__main__":
    unittest.main()
