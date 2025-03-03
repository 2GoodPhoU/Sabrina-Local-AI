#!/usr/bin/env python3
"""
Integration tests for Sabrina AI Voice Service
Tests the integration between the voice service and other components
"""

import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch
import tempfile
import json
import logging

# Import components
from core.component_service_wrappers import VoiceService
from utilities.event_system import EventBus, Event, EventType, EventPriority
from core.state_machine import StateMachine, SabrinaState

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_integration_test")


class TestVoiceServiceIntegration(unittest.TestCase):
    """Integration tests for the Voice Service component"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Create a temporary directory for test configuration
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Create voice settings file
        cls.voice_settings_path = os.path.join(cls.temp_dir.name, "voice_settings.json")
        cls.voice_settings = {
            "voice": "test_voice",
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 0.8,
            "emotion": "neutral",
            "cache_enabled": True,
        }

        with open(cls.voice_settings_path, "w") as f:
            json.dump(cls.voice_settings, f)

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures"""
        cls.temp_dir.cleanup()

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
            "api_url": "http://localhost:8100",
            "voice": "test_voice",
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 0.8,
            "emotion": "neutral",
        }

        # Mock VoiceAPIClient or EnhancedVoiceClient
        self.setup_voice_client_mock()

        # Create voice service
        self.voice_service = VoiceService(
            name="voice",
            event_bus=self.event_bus,
            state_machine=self.state_machine,
            config=self.config,
        )

        # Initialize the service
        self.voice_service.initialize()

    def tearDown(self):
        """Clean up test fixtures"""
        # Shutdown voice service
        self.voice_service.shutdown()

        # Stop event bus
        self.event_bus.stop()

        # Stop patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def setup_voice_client_mock(self):
        """Set up mocks for voice client classes"""
        self._patchers = []

        # First try to patch EnhancedVoiceClient
        try:
            enhanced_patcher = patch(
                "services.voice.enhanced_voice_client.EnhancedVoiceClient"
            )
            self.mock_voice_client_class = enhanced_patcher.start()
            self._patchers.append(enhanced_patcher)
            logger.info("Patched EnhancedVoiceClient")
        except ImportError:
            # Fall back to VoiceAPIClient
            try:
                api_patcher = patch("services.voice.voice_api_client.VoiceAPIClient")
                self.mock_voice_client_class = api_patcher.start()
                self._patchers.append(api_patcher)
                logger.info("Patched VoiceAPIClient")
            except ImportError:
                logger.warning("Could not patch either voice client class")
                # Will use placeholder client
                return

        # Create mock instance
        self.mock_voice_client = MagicMock()

        # Configure mock behavior
        self.mock_voice_client.test_connection.return_value = True
        self.mock_voice_client.speak.return_value = True
        self.mock_voice_client.get_voices.return_value = [
            "voice1",
            "voice2",
            "test_voice",
        ]
        self.mock_voice_client.get_settings.return_value = self.voice_settings
        self.mock_voice_client.update_settings.return_value = True

        # Set the mock instance as the return value
        self.mock_voice_client_class.return_value = self.mock_voice_client

    def test_voice_service_initialization(self):
        """Test voice service initialization"""
        # Check that service was initialized
        self.assertEqual(self.voice_service.status.name, "READY")
        self.assertIsNotNone(self.voice_service.voice_client)

        # Check client configuration
        if hasattr(self, "mock_voice_client"):
            # Mock client should have been configured with settings
            self.mock_voice_client.update_settings.assert_called_once()

    def test_speech_event_handling(self):
        """Test handling of speech events"""
        # Create a speech started event
        speech_event = Event(
            event_type=EventType.SPEECH_STARTED,
            data={"text": "Hello, this is a test."},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post the event
        self.event_bus.post_event(speech_event)

        # Wait for processing
        time.sleep(0.1)

        # Check that speak method was called
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.speak.assert_called_once_with(
                "Hello, this is a test."
            )

        # Voice service should update its state
        self.assertEqual(self.voice_service.last_text, "Hello, this is a test.")

    def test_direct_speech_method(self):
        """Test directly calling the speak method"""
        # Call speak method
        result = self.voice_service.speak("Direct speech test")

        # Check result
        self.assertTrue(result)

        # Check client was called
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.speak.assert_called_once_with("Direct speech test")

        # Voice service should update its state
        self.assertEqual(self.voice_service.last_text, "Direct speech test")

    def test_speech_with_parameters(self):
        """Test speech with additional parameters"""
        # Create parameters
        params = {
            "voice": "alternate_voice",
            "speed": 1.2,
            "pitch": 0.9,
            "emotion": "happy",
        }

        # Call speak with parameters
        result = self.voice_service.speak("Parameterized speech", **params)

        # Check result
        self.assertTrue(result)

        # Check client was called with parameters
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.speak.assert_called_once()
            call_args = self.mock_voice_client.speak.call_args
            self.assertEqual(call_args[0][0], "Parameterized speech")
            for key, value in params.items():
                self.assertEqual(call_args[1][key], value)

    def test_speech_error_handling(self):
        """Test handling of speech errors"""
        # Configure mock to fail
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.speak.return_value = False

        # Create result collector
        error_events = []

        # Create a handler for error events
        def error_handler(event):
            if event.event_type == EventType.SPEECH_ERROR:
                error_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=error_handler, event_types=[EventType.SPEECH_ERROR]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Call speak method (should fail)
        result = self.voice_service.speak("This should fail")

        # Check result
        self.assertFalse(result)

        # Wait for event processing
        time.sleep(0.1)

        # Check that error event was posted
        self.assertEqual(len(error_events), 1)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_get_voices(self):
        """Test getting available voices"""
        # Call get_voices
        voices = self.voice_service.get_voices()

        # Check result
        self.assertIsInstance(voices, list)
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.get_voices.assert_called_once()
            self.assertEqual(voices, ["voice1", "voice2", "test_voice"])

    def test_update_settings(self):
        """Test updating voice settings"""
        # Create new settings
        new_settings = {"voice": "new_voice", "speed": 1.5, "volume": 0.7}

        # Call update_settings
        result = self.voice_service.update_settings(new_settings)

        # Check result
        self.assertTrue(result)

        # Check client was called
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.update_settings.assert_called_with(new_settings)

    def test_state_machine_integration(self):
        """Test integration with state machine"""
        # Transition to SPEAKING state
        self.state_machine.transition_to(SabrinaState.SPEAKING)

        # Create speech event
        speech_event = Event(
            event_type=EventType.SPEECH_STARTED,
            data={"text": "State machine test"},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post the event
        self.event_bus.post_event(speech_event)

        # Wait for processing
        time.sleep(0.1)

        # Check that voice service processed the event
        if hasattr(self, "mock_voice_client"):
            self.mock_voice_client.speak.assert_called_once_with("State machine test")

        # Create a speech completed event
        completed_event = Event(
            event_type=EventType.SPEECH_COMPLETED,
            data={"text": "State machine test"},
            priority=EventPriority.NORMAL,
            source="voice_service",
        )

        # Post the event
        self.event_bus.post_event(completed_event)

        # Wait for event processing
        time.sleep(0.1)

        # State should transition back to READY
        self.assertEqual(self.state_machine.current_state, SabrinaState.READY)

    def test_status_reporting(self):
        """Test status reporting"""
        # Get status
        status = self.voice_service.get_status()

        # Check status content
        self.assertEqual(status["name"], "voice")
        self.assertEqual(status["status"], "READY")
        self.assertFalse(status["currently_speaking"])
        self.assertEqual(status["voice_api_url"], "http://localhost:8100")

        # Check settings in status
        voice_settings = status["voice_settings"]
        self.assertEqual(voice_settings["voice"], "test_voice")
        self.assertEqual(voice_settings["volume"], 0.8)
        self.assertEqual(voice_settings["speed"], 1.0)
        self.assertEqual(voice_settings["pitch"], 1.0)
        self.assertEqual(voice_settings["emotion"], "neutral")

    def test_shutdown_behavior(self):
        """Test behavior during shutdown"""
        # Set speaking state
        self.voice_service.currently_speaking = True
        self.voice_service.last_text = "Speaking during shutdown"

        # Call shutdown
        result = self.voice_service.shutdown()

        # Check result
        self.assertTrue(result)

        # Should attempt to stop speaking
        if hasattr(self, "mock_voice_client") and hasattr(
            self.mock_voice_client, "stop_speaking"
        ):
            self.mock_voice_client.stop_speaking.assert_called_once()


if __name__ == "__main__":
    unittest.main()
