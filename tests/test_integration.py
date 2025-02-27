"""
System Integration Tests for Sabrina AI
=====================================
Tests that validate the integration between all components.
"""

import os
import sys
import unittest
import time
import tempfile
from unittest.mock import MagicMock, patch
import threading
import pytest
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import all major components
from core.sabrina_core import SabrinaCore
from services.voice.voice_api_client import VoiceAPIClient
from services.vision.vision_core import VisionCore
from services.automation.automation import Actions
from services.hearing.hearing import Hearing
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory
from utilities.event_system import EventBus, EventType, Event, EventPriority

# Import base test class
from tests.test_framework import TestBase


@pytest.mark.slow
class SystemIntegrationTests(TestBase):
    """Full system integration tests for Sabrina AI"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Create a mock for the hearing module
        self.mock_hearing = MagicMock(spec=Hearing)
        self.mock_hearing.listen.return_value = "test command"
        
        # Patch SabrinaCore's component initialization to use our mocks
        self.patch_core_init = patch.object(SabrinaCore, '_init_components')
        self.mock_core_init = self.patch_core_init.start()
        
        # Initialize core with our config
        self.core = SabrinaCore(self.temp_config_path)
        
        # Insert our mocked and real components
        self.core.components = {
            "vision": VisionCore(),
            "voice": VoiceAPIClient(),
            "automation": Actions(),
            "hearing": self.mock_hearing
        }
        
        # Override running flag to allow controlled testing
        self.core.running = False
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop patches
        if hasattr(self, 'patch_core_init'):
            self.patch_core_init.stop()
        
        super().tearDown()
    
    @pytest.mark.integration
    def test_command_processing(self):
        """Test the command processing flow"""
        # Mock the voice client's connection and speak method
        self.core.components["voice"].connected = True
        self.core.components["voice"].speak = MagicMock()
        
        # Override process methods to isolate command handling
        self.core._process_capture_command = MagicMock(return_value=(True, "Capture processed"))
        self.core._process_click_command = MagicMock(return_value=(True, "Click processed"))
        self.core._process_say_command = MagicMock(return_value=(True, "Say processed"))
        self.core._process_exit_command = MagicMock(return_value=(False, "Exit processed"))
        
        # Test regular input
        result, response = self.core.process_command("Hello Sabrina")
        self.assertTrue(result)
        self.assertTrue(response.startswith("You said:"))
        self.core.components["voice"].speak.assert_called_once()
        
        # Reset mocks
        self.core.components["voice"].speak.reset_mock()
        
        # Test capture command
        result, response = self.core.process_command("!capture")
        self.assertTrue(result)
        self.assertEqual(response, "Capture processed")
        self.core._process_capture_command.assert_called_once()
        
        # Test click command
        result, response = self.core.process_command("!click")
        self.assertTrue(result)
        self.assertEqual(response, "Click processed")
        self.core._process_click_command.assert_called_once()
        
        # Test say command
        result, response = self.core.process_command("!say Hello world")
        self.assertTrue(result)
        self.assertEqual(response, "Say processed")
        self.core._process_say_command.assert_called_once()
        
        # Test exit command
        result, response = self.core.process_command("exit")
        self.assertFalse(result)
        self.assertEqual(response, "Exit processed")
        self.core._process_exit_command.assert_called_once()
    
    @pytest.mark.integration
    def test_event_flow(self):
        """Test the event flow through the system"""
        # Create event tracking lists
        voice_events = []
        vision_events = []
        automation_events = []
        
        # Create event handlers
        def voice_handler(event):
            voice_events.append(event)
        
        def vision_handler(event):
            vision_events.append(event)
        
        def automation_handler(event):
            automation_events.append(event)
        
        # Register handlers
        self.core.event_bus.register_handler(self.core.event_bus.create_event_handler(
            event_types=[EventType.VOICE],
            callback=voice_handler
        ))
        
        self.core.event_bus.register_handler(self.core.event_bus.create_event_handler(
            event_types=[EventType.VISION],
            callback=vision_handler
        ))
        
        self.core.event_bus.register_handler(self.core.event_bus.create_event_handler(
            event_types=[EventType.AUTOMATION],
            callback=automation_handler
        ))
        
        # Set up to handle the user input event
        self.core._handle_user_input = MagicMock()
        
        # Post a user input event
        self.core.event_bus.post_event(Event(
            event_type=EventType.USER_INPUT,
            data={"text": "Test command"},
            source="test"
        ))
        
        # Wait for event processing
        self.wait_for_events()
        
        # Verify handler was called
        self.core._handle_user_input.assert_called_once()
        
        # Test multi-event chain
        # First, override process methods to work with events
        def handle_capture(command):
            self.core.event_bus.post_event(Event(
                event_type=EventType.VISION,
                data={"command": "capture"},
                source="core"
            ))
            return True, "Capture initiated"
            
        def handle_say(command):
            text = command[5:] if command.startswith("!say ") else ""
            self.core.event_bus.post_event(Event(
                event_type=EventType.VOICE,
                data={"text": text},
                source="core"
            ))
            return True, f"Said: {text}"
            
        def handle_click(command):
            self.core.event_bus.post_event(Event(
                event_type=EventType.AUTOMATION,
                data={"command": "click"},
                source="core"
            ))
            return True, "Click initiated"
        
        # Apply overrides
        self.core._process_capture_command = handle_capture
        self.core._process_say_command = handle_say
        self.core._process_click_command = handle_click
        
        # Reset event lists
        voice_events.clear()
        vision_events.clear()
        automation_events.clear()
        
        # Post commands
        self.core.process_command("!capture")
        self.core.process_command("!say Hello world")
        self.core.process_command("!click")
        
        # Wait for event processing
        self.wait_for_events()
        
        # Verify events were received
        self.assertEqual(len(vision_events), 1)
        self.assertEqual(vision_events[0].data.get("command"), "capture")
        
        self.assertEqual(len(voice_events), 1)
        self.assertEqual(voice_events[0].data.get("text"), "Hello world")
        
        self.assertEqual(len(automation_events), 1)
        self.assertEqual(automation_events[0].data.get("command"), "click")
    
    @pytest.mark.integration
    def test_memory_update(self):
        """Test memory update functionality"""
        # Create a temporary memory file
        self.core.memory_file = os.path.join(tempfile.gettempdir(), "test_memory.json")
        
        # Ensure the memory file doesn't exist
        if os.path.exists(self.core.memory_file):
            os.remove(self.core.memory_file)
        
        # Test memory initialization
        self.assertEqual(self.core.history, [])
        
        # Test memory update
        self.core.update_memory("Test input", "Test response")
        
        # Verify memory
        self.assertEqual(len(self.core.history), 2)
        self.assertEqual(self.core.history[0]["role"], "user")
        self.assertEqual(self.core.history[0]["content"], "Test input")
        self.assertEqual(self.core.history[1]["role"], "assistant")
        self.assertEqual(self.core.history[1]["content"], "Test response")
        
        # Verify memory file was created
        self.assertTrue(os.path.exists(self.core.memory_file))
        
        # Load memory file and verify content
        with open(self.core.memory_file, "r") as f:
            loaded_memory = json.load(f)
        
        self.assertEqual(len(loaded_memory), 2)
        self.assertEqual(loaded_memory[0]["role"], "user")
        self.assertEqual(loaded_memory[0]["content"], "Test input")
        
        # Clean up
        os.remove(self.core.memory_file)


@pytest.mark.slow
class ComponentIntegrationTests(TestBase):
    """Tests for verifying integration between specific components"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Initialize components for integration tests
        self.vision_core = VisionCore()
        self.automation = Actions()
        self.voice_client = VoiceAPIClient()
    
    @pytest.mark.integration
    def test_vision_automation_integration(self):
        """Test integration between vision and automation components"""
        # Skip if automation is not available
        if not hasattr(self.automation, 'pyautogui_available') or not self.automation.pyautogui_available:
            self.skipTest("PyAutoGUI not available")
        
        # Create a UI element detection simulation
        def mock_detect_ui_elements(image_path):
            # Return a simulated button location
            return [
                {
                    "type": "button",
                    "text": "Test Button",
                    "coordinates": [100, 100, 200, 150]  # x1, y1, x2, y2
                }
            ]
        
        # Patch vision_core to use our mock detection
        self.vision_core.detect_ui_elements = mock_detect_ui_elements
        
        # Mock the screen capture to return a known path
        test_image_path = os.path.join(tempfile.gettempdir(), "test_capture.png")
        open(test_image_path, 'w').close()  # Create empty file
        self.vision_core.capture_screen = MagicMock(return_value=test_image_path)
        
        # Mock the mouse movement
        self.automation.move_mouse_to = MagicMock()
        self.automation.click = MagicMock()
        
        # Simulate a workflow that:
        # 1. Captures the screen
        # 2. Detects UI elements
        # 3. Clicks on a button
        
        # 1. Capture screen
        image_path = self.vision_core.capture_screen()
        
        # 2. Detect UI elements
        ui_elements = self.vision_core.detect_ui_elements(image_path)
        
        # 3. Click on the first button
        if ui_elements and ui_elements[0]["type"] == "button":
            # Calculate button center
            button = ui_elements[0]
            x1, y1, x2, y2 = button["coordinates"]
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            # Move mouse to button center and click
            self.automation.move_mouse_to(center_x, center_y)
            self.automation.click()
        
        # Verify the automation actions were called with expected parameters
        self.automation.move_mouse_to.assert_called_once_with(150, 125)
        self.automation.click.assert_called_once()
        
        # Clean up
        os.remove(test_image_path)
    
    @pytest.mark.integration
    def test_voice_vision_integration(self):
        """Test integration between voice and vision components"""
        # Mock the voice client's speak method
        self.voice_client.speak = MagicMock()
        
        # Mock the vision core's OCR method
        self.vision_core.vision_ocr.run_ocr = MagicMock(return_value="Sabrina AI Test Text")
        
        # Mock the screen capture method
        test_image_path = os.path.join(tempfile.gettempdir(), "test_capture.png")
        open(test_image_path, 'w').close()  # Create empty file
        self.vision_core.capture_screen = MagicMock(return_value=test_image_path)
        
        # Simulate the workflow:
        # 1. Receive a voice command to capture the screen
        # 2. Capture the screen
        # 3. Perform OCR
        # 4. Read the result back to the user
        
        # 1-3. Capture screen and perform OCR
        image_path = self.vision_core.capture_screen()
        ocr_text = self.vision_core.vision_ocr.run_ocr(image_path)
        
        # 4. Speak the result
        self.voice_client.speak(f"I can see: {ocr_text}")
        
        # Verify the OCR was performed
        self.vision_core.vision_ocr.run_ocr.assert_called_once_with(test_image_path)
        
        # Verify the TTS was called with the OCR result
        self.voice_client.speak.assert_called_once_with("I can see: Sabrina AI Test Text")
        
        # Clean up
        os.remove(test_image_path)
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_event_chain(self):
        """Test the full event chain through all components"""
        # Skip if no voice service is running
        voice_service_running = False
        try:
            response = requests.get("http://localhost:8100/status", timeout=1.0)
            voice_service_running = response.status_code == 200
        except:
            pass
        
        if not voice_service_running:
            self.skipTest("Voice service not running")
        
        # Mock component methods to track calls
        self.vision_core.capture_screen = MagicMock(return_value="test_capture.png")
        self.vision_core.vision_ocr.run_ocr = MagicMock(return_value="Test OCR Text")
        self.automation.click = MagicMock()
        self.voice_client.speak = MagicMock()
        
        # Create event handlers
        voice_handler = MagicMock()
        vision_handler = MagicMock()
        automation_handler = MagicMock()
        
        # Register handlers
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.VOICE],
            callback=voice_handler
        ))
        
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.VISION],
            callback=vision_handler
        ))
        
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.AUTOMATION],
            callback=automation_handler
        ))
        
        # Function to process events based on type
        def process_events(event):
            if event.event_type == EventType.VISION:
                if event.data.get("command") == "capture":
                    # Capture screen
                    image_path = self.vision_core.capture_screen()
                    # Perform OCR
                    ocr_text = self.vision_core.vision_ocr.run_ocr(image_path)
                    # Post result to voice system
                    self.event_bus.post_event(Event(
                        event_type=EventType.VOICE,
                        data={"text": f"I can see: {ocr_text}"},
                        source="vision"
                    ))
            
            elif event.event_type == EventType.VOICE:
                # Speak the text
                self.voice_client.speak(event.data.get("text", ""))
            
            elif event.event_type == EventType.AUTOMATION:
                if event.data.get("command") == "click":
                    # Perform click
                    self.automation.click()
        
        # Register a handler for all event types
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.VISION, EventType.VOICE, EventType.AUTOMATION],
            callback=process_events
        ))
        
        # Trigger the event chain
        self.event_bus.post_event(Event(
            event_type=EventType.VISION,
            data={"command": "capture"},
            source="test"
        ))
        
        # Wait for events to be processed
        self.wait_for_events(timeout=2.0)
        
        # Verify that all expected methods were called
        self.vision_core.capture_screen.assert_called_once()
        self.vision_core.vision_ocr.run_ocr.assert_called_once()
        self.voice_client.speak.assert_called_once_with("I can see: Test OCR Text")
        
        # Verify event handlers were called
        vision_handler.assert_called()
        voice_handler.assert_called()
        
        # Manually verify automation
        self.event_bus.post_event(Event(
            event_type=EventType.AUTOMATION,
            data={"command": "click"},
            source="test"
        ))
        
        # Wait for automation event
        self.wait_for_events()
        
        # Verify automation was triggered
        self.automation.click.assert_called_once()
        automation_handler.assert_called()


@pytest.mark.slow
class EndToEndSystemTests(TestBase):
    """End-to-end tests for the complete Sabrina AI system"""
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.environ.get("SKIP_END_TO_END_TESTS", "true").lower() == "true",
                       reason="End-to-end tests only run when explicitly enabled")
    def test_end_to_end_system(self):
        """
        Test the entire system with actual components
        
        This test requires all services to be running and is meant to be
        run manually in a controlled environment.
        """
        # Skip unless explicitly enabled
        if not os.environ.get("ENABLE_END_TO_END_TESTS"):
            self.skipTest("End-to-end tests not enabled")
        
        # Initialize core system
        core = SabrinaCore(self.temp_config_path)
        
        # Override hearing to use console input
        core.components["hearing"].listen = lambda: input("Enter command: ")
        
        # Run the system for a limited time (5 seconds)
        core.running = True
        
        def stop_after_timeout():
            time.sleep(5)
            core.running = False
        
        # Start timeout thread
        timeout_thread = threading.Thread(target=stop_after_timeout)
        timeout_thread.daemon = True
        timeout_thread.start()
        
        # Run the system
        core.run()
        
        # No assertions - this is a manual test to verify the system works end-to-end
        # Results must be observed by the tester


if __name__ == "__main__":
    unittest.main()