#!/usr/bin/env python3
"""
Integration tests for Sabrina AI Hearing Service
Tests the integration between the hearing service and other components
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
from core.component_service_wrappers import HearingService
from utilities.event_system import Event, EventBus, EventType, EventPriority
from core.state_machine import StateMachine, SabrinaState

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hearing_integration_test")


class TestHearingServiceIntegration(unittest.TestCase):
    """Integration tests for the Hearing Service component"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Create a temporary directory for test files
        cls.temp_dir = tempfile.TemporaryDirectory()

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
            "wake_word": "hey sabrina",
            "silence_threshold": 0.03,
            "model_path": os.path.join(self.temp_dir.name, "test_model"),
            "hotkey": "ctrl+shift+s",
        }

        # Mock Hearing client
        self.setup_hearing_client_mock()

        # Create hearing service
        self.hearing_service = HearingService(
            name="hearing",
            event_bus=self.event_bus,
            state_machine=self.state_machine,
            config=self.config,
        )

        # Initialize the service
        self.hearing_service.initialize()

    def tearDown(self):
        """Clean up test fixtures"""
        # Shutdown hearing service
        self.hearing_service.shutdown()

        # Stop event bus
        self.event_bus.stop()

        # Stop patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def setup_hearing_client_mock(self):
        """Set up mocks for hearing client classes"""
        self._patchers = []

        # Patch Hearing class
        hearing_patcher = patch("services.hearing.hearing.Hearing")
        self.mock_hearing_class = hearing_patcher.start()
        self._patchers.append(hearing_patcher)

        # Create mock instance
        self.mock_hearing_client = MagicMock()

        # Configure mock behavior for wake word detection
        self.mock_hearing_client.listen_for_wake_word.return_value = True

        # Configure mock behavior for speech transcription
        self.mock_hearing_client.listen.return_value = "test transcription"

        # Mock hotkey attribute
        self.mock_hearing_client.hotkey = "ctrl+shift+s"

        # Set the mock instance as the return value
        self.mock_hearing_class.return_value = self.mock_hearing_client

    def test_hearing_service_initialization(self):
        """Test hearing service initialization"""
        # Check that service was initialized
        self.assertEqual(self.hearing_service.status.name, "READY")
        self.assertIsNotNone(self.hearing_service.hearing_client)

        # Check config values were passed correctly
        self.assertEqual(self.hearing_service.wake_word, "hey sabrina")
        self.assertEqual(self.hearing_service.hotkey, "ctrl+shift+s")

        # Verify Hearing was initialized with correct parameters
        self.mock_hearing_class.assert_called_once()
        args, kwargs = self.mock_hearing_class.call_args
        self.assertEqual(kwargs["wake_word"], "hey sabrina")
        self.assertEqual(
            kwargs["model_path"], os.path.join(self.temp_dir.name, "test_model")
        )

    def test_wake_word_detection(self):
        """Test wake word detection"""
        # Mock the event bus post_event method to track events
        self.event_bus.post_event = MagicMock(return_value=True)

        # Call listen_for_wake_word
        result = self.hearing_service.listen_for_wake_word()

        # Check that wake word detection was successful
        self.assertTrue(result)

        # Check that hearing_client.listen_for_wake_word was called
        self.mock_hearing_client.listen_for_wake_word.assert_called_once()

    def test_listening_event_handling(self):
        """Test handling of listening events"""
        # Create a result collector
        listening_events = []

        # Create a handler for listening events
        def listening_handler(event):
            if event.event_type in [
                EventType.LISTENING_STARTED,
                EventType.LISTENING_COMPLETED,
            ]:
                listening_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=listening_handler,
            event_types=[EventType.LISTENING_STARTED, EventType.LISTENING_COMPLETED],
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post a listening started event
        listening_started_event = Event(
            event_type=EventType.LISTENING_STARTED,
            priority=EventPriority.HIGH,
            source="test",
        )

        # Post the event directly
        self.event_bus.post_event_immediate(listening_started_event)

        # Check that start_listening was called
        self.assertTrue(self.mock_hearing_client.listen.called)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_listening_functionality(self):
        """Test the start_listening method"""
        # Call start_listening
        result = self.hearing_service.start_listening()

        # Check result
        self.assertTrue(result)

        # Check that currently_listening was set to True
        self.assertTrue(self.hearing_service.currently_listening)

        # The actual listen method would be called in a thread, but we can verify it was set up correctly
        self.mock_hearing_client.listen.assert_not_called()  # Not called immediately

    def test_wake_word_event_handling(self):
        """Test handling of wake word detection events"""
        # Create a result collector
        wake_word_events = []

        # Create a handler for wake word events
        def wake_word_handler(event):
            if event.event_type == EventType.WAKE_WORD_DETECTED:
                wake_word_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=wake_word_handler, event_types=[EventType.WAKE_WORD_DETECTED]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post a wake word event
        wake_word_event = Event(
            event_type=EventType.WAKE_WORD_DETECTED,
            priority=EventPriority.HIGH,
            source="test",
        )

        # Set the state machine to READY
        self.state_machine.current_state = SabrinaState.READY

        # Post the event directly
        self.event_bus.post_event_immediate(wake_word_event)

        # Wait for any event processing (if needed)
        time.sleep(0.1)

        # Check that state changed to LISTENING
        self.assertEqual(self.state_machine.current_state, SabrinaState.LISTENING)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_transcription_event_handling(self):
        """Test handling of transcription completed events"""
        # Reset the state machine
        self.state_machine.current_state = SabrinaState.LISTENING

        # Create a result collector for user commands
        command_events = []

        # Create a handler for user commands
        def command_handler(event):
            if event.event_type == EventType.USER_VOICE_COMMAND:
                command_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=command_handler, event_types=[EventType.USER_VOICE_COMMAND]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create and post a listening completed event
        completed_event = Event(
            event_type=EventType.LISTENING_COMPLETED,
            data={"transcription": "Hello Sabrina"},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post the event directly
        self.event_bus.post_event_immediate(completed_event)

        # Check that it generated a user command event
        self.assertEqual(len(command_events), 1)
        self.assertEqual(command_events[0].get("command"), "Hello Sabrina")

        # Check that state changed to PROCESSING
        self.assertEqual(self.state_machine.current_state, SabrinaState.PROCESSING)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_error_handling(self):
        """Test error handling in hearing service"""
        # Configure mock to raise an exception
        self.mock_hearing_client.listen_for_wake_word.side_effect = Exception(
            "Test error"
        )

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
        result = self.hearing_service.listen_for_wake_word()

        # Check result
        self.assertFalse(result)

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_status_reporting(self):
        """Test status reporting"""
        # Set some state for testing
        self.hearing_service.currently_listening = True
        self.hearing_service.last_transcription = "Test transcription"

        # Get status
        status = self.hearing_service.get_status()

        # Check status content
        self.assertEqual(status["name"], "hearing")
        self.assertEqual(status["status"], "READY")
        self.assertTrue(status["currently_listening"])
        self.assertEqual(status["last_transcription"], "Test transcription")
        self.assertEqual(status["wake_word"], "hey sabrina")
        self.assertEqual(status["hotkey"], "ctrl+shift+s")

    def test_shutdown_behavior(self):
        """Test behavior during shutdown"""
        # Call shutdown
        result = self.hearing_service.shutdown()

        # Check result
        self.assertTrue(result)

        # Should call close on the client if available
        self.mock_hearing_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
