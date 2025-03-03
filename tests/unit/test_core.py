#!/usr/bin/env python3
"""
Integration tests for Sabrina AI Core System
Tests the integration between core and service components
"""

import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch
import tempfile
import yaml
import logging

# Import core components
from core.core import SabrinaCore
from core.state_machine import SabrinaState
from utilities.event_system import Event, EventType, EventPriority

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("integration_test")


class TestCoreIntegration(unittest.TestCase):
    """Integration tests for the Sabrina Core system"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Create a temporary directory for test configuration
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.config_path = os.path.join(cls.temp_dir.name, "test_config.yaml")

        # Create a test configuration
        cls.test_config = {
            "core": {
                "debug_mode": True,
                "log_level": "DEBUG",
                "enabled_components": ["voice", "automation"],
            },
            "voice": {
                "enabled": True,
                "api_url": "http://localhost:8100",
                "volume": 0.5,
            },
            "automation": {
                "enabled": True,
                "mouse_move_duration": 0.1,
                "typing_interval": 0.05,
            },
        }

        # Write the test configuration
        with open(cls.config_path, "w") as f:
            yaml.dump(cls.test_config, f)

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures"""
        cls.temp_dir.cleanup()

    def setUp(self):
        """Set up test fixtures"""
        # Initialize the core system with test configuration
        self.core = SabrinaCore(self.config_path)

        # Mock the component classes to avoid external dependencies
        self._setup_component_mocks()

        # Initialize components
        self.core.initialize_components()

    def tearDown(self):
        """Clean up test fixtures"""
        # Shut down the core system
        self.core.shutdown()

    def _setup_component_mocks(self):
        """Set up mock components for testing"""
        # Create patchers for the component classes
        voice_patcher = patch("core.component_service_wrappers.VoiceService")
        automation_patcher = patch("core.component_service_wrappers.AutomationService")

        # Start the patchers
        self.mock_voice_class = voice_patcher.start()
        self.mock_automation_class = automation_patcher.start()

        # Create mock instances
        self.mock_voice = MagicMock()
        self.mock_automation = MagicMock()

        # Set up successful initialization
        self.mock_voice.initialize.return_value = True
        self.mock_automation.initialize.return_value = True

        # Set the status attribute
        self.mock_voice.status = "READY"
        self.mock_automation.status = "READY"

        # Configure the mock classes to return the mock instances
        self.mock_voice_class.return_value = self.mock_voice
        self.mock_automation_class.return_value = self.mock_automation

        # Add the patchers to the cleanup list
        self.addCleanup(voice_patcher.stop)
        self.addCleanup(automation_patcher.stop)

    def test_core_initialization(self):
        """Test core system initialization"""
        # Check that core is running
        self.assertTrue(hasattr(self.core, "running"))
        self.assertTrue(hasattr(self.core, "initialized"))

        # Check that event bus is started
        self.assertTrue(self.core.event_bus.running)

        # Check that state machine is initialized
        self.assertIsNotNone(self.core.state_machine)
        self.assertEqual(self.core.state_machine.current_state, SabrinaState.READY)

        # Check components were initialized
        self.assertIn("voice", self.core.components)
        self.assertIn("automation", self.core.components)
        self.assertIn("core", self.core.components)  # Core registers itself

        # Check initialization was called on components
        self.mock_voice.initialize.assert_called_once()
        self.mock_automation.initialize.assert_called_once()

    def test_event_propagation(self):
        """Test event propagation between components through the core"""
        # Create a test event
        test_event = Event(
            event_type=EventType.SPEECH_STARTED,
            data={"text": "Test speech"},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Create a handler to capture the event
        handler_called = {"value": False}
        received_event = {"value": None}

        def test_handler(event):
            handler_called["value"] = True
            received_event["value"] = event

        # Register the handler
        handler = self.core.event_bus.create_handler(
            callback=test_handler, event_types=[EventType.SPEECH_STARTED]
        )
        handler_id = self.core.event_bus.register_handler(handler)

        # Post the event
        self.core.event_bus.post_event(test_event)

        # Wait for event processing
        time.sleep(0.1)

        # Check the handler was called
        self.assertTrue(handler_called["value"])
        self.assertEqual(received_event["value"].event_type, EventType.SPEECH_STARTED)
        self.assertEqual(received_event["value"].data["text"], "Test speech")

        # Clean up
        self.core.event_bus.unregister_handler(handler_id)

    def test_state_transitions(self):
        """Test state transitions propagate to components"""
        # Test the transition to LISTENING state
        self.core.state_machine.transition_to(SabrinaState.LISTENING)

        # Verify state change
        self.assertEqual(self.core.state_machine.current_state, SabrinaState.LISTENING)

        # Create an event that results from this state transition
        wakeword_event = Event(
            event_type=EventType.WAKE_WORD_DETECTED,
            priority=EventPriority.HIGH,
            source="test",
        )
        self.core.event_bus.post_event(wakeword_event)

        # Wait for event processing
        time.sleep(0.1)

        # In a real system, the hearing component would start listening
        # We can verify that the state machine is in the correct state
        self.assertEqual(self.core.state_machine.current_state, SabrinaState.LISTENING)

    def test_voice_command_processing(self):
        """Test processing of voice commands"""
        # Create a voice command event
        command_event = Event(
            event_type=EventType.USER_VOICE_COMMAND,
            data={"command": "test command"},
            priority=EventPriority.HIGH,
            source="test",
        )

        # Post the event
        self.core.event_bus.post_event(command_event)

        # Wait for event processing
        time.sleep(0.1)

        # Verify state transitions
        # Should go to PROCESSING state first
        self.assertEqual(self.core.state_machine.current_state, SabrinaState.PROCESSING)

        # Let processing complete
        time.sleep(0.2)

        # Should now be in RESPONDING or READY state
        self.assertIn(
            self.core.state_machine.current_state,
            [SabrinaState.RESPONDING, SabrinaState.READY],
        )

    def test_core_shutdown(self):
        """Test core system shutdown"""
        # Run the core for a moment
        # (Normally this would be the core.run() method, but we're not using that in tests)
        time.sleep(0.1)

        # Verify core is running
        self.assertTrue(self.core.running)

        # Shut down the core
        self.core.shutdown()

        # Verify it's not running
        self.assertFalse(self.core.running)

        # Check that components were shut down
        self.mock_voice.shutdown.assert_called_once()
        self.mock_automation.shutdown.assert_called_once()

        # Event bus should be stopped
        self.assertFalse(self.core.event_bus.running)

    def test_component_error_handling(self):
        """Test error handling for component failures"""
        # Configure mock component to fail
        self.mock_voice.initialize.return_value = False
        self.mock_voice.error_message = "Test initialization error"

        # Create a new core instance
        test_core = SabrinaCore(self.config_path)

        # Initialize components (should handle the failure)
        test_core.initialize_components()

        # Verify error handling
        self.assertIn("voice", test_core.components)
        self.assertEqual(
            test_core.components["voice"].error_message, "Test initialization error"
        )

        # Clean up
        test_core.shutdown()

    def test_event_handler_registration(self):
        """Test registration of event handlers through the core system"""
        # Define a test handler
        test_callback = MagicMock()

        # Create a handler
        handler = self.core.event_bus.create_handler(
            callback=test_callback,
            event_types=[EventType.SYSTEM_ERROR, EventType.SYSTEM],
        )

        # Register the handler
        handler_id = self.core.event_bus.register_handler(handler)

        # Verify registration
        handler_count = self.core.event_bus.get_stats()["handler_count"]
        self.assertGreaterEqual(handler_count, 1)

        # Test that handlers receive events
        test_event = Event(
            event_type=EventType.SYSTEM, data={"test": "data"}, source="test"
        )

        # Post event
        self.core.event_bus.post_event(test_event)

        # Wait for processing
        time.sleep(0.1)

        # Verify callback was called
        test_callback.assert_called_once()

        # Check argument
        event_arg = test_callback.call_args[0][0]
        self.assertEqual(event_arg.event_type, EventType.SYSTEM)
        self.assertEqual(event_arg.data["test"], "data")

        # Unregister handler
        self.core.event_bus.unregister_handler(handler_id)

        # Verify unregistration
        new_handler_count = self.core.event_bus.get_stats()["handler_count"]
        self.assertEqual(new_handler_count, handler_count - 1)

    def test_voice_integration(self):
        """Test integration with voice service"""
        # Set up mock voice service behavior
        self.mock_voice.speak.return_value = True

        # Create a speech request event
        speech_event = Event(
            event_type=EventType.SPEECH_STARTED,
            data={"text": "Test speech text"},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post event
        self.core.event_bus.post_event(speech_event)

        # Wait for processing
        time.sleep(0.1)

        # Verify that voice service was called
        self.mock_voice.speak.assert_called_once()
        self.assertEqual(self.mock_voice.speak.call_args[0][0], "Test speech text")

    def test_automation_integration(self):
        """Test integration with automation service"""
        # Set up mock automation service behavior
        self.mock_automation.execute_task.return_value = True

        # Create an automation request event
        automation_event = Event(
            event_type=EventType.AUTOMATION_STARTED,
            data={"action": "click_at", "parameters": {"x": 100, "y": 200}},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post event
        self.core.event_bus.post_event(automation_event)

        # Wait for processing
        time.sleep(0.1)

        # In a real system, this would be routed to the automation service
        # We would verify the automation service methods were called correctly

        # For testing component delegation:
        # Create a delegated task event
        delegated_event = Event(
            event_type=EventType.DELEGATED_TASK,
            data={
                "component": "automation",
                "method": "click_at",
                "args": {"x": 150, "y": 250},
            },
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post the event
        self.core.event_bus.post_event(delegated_event)

        # Wait for processing
        time.sleep(0.1)

    def test_llm_integration(self):
        """Test integration with LLM framework"""
        # This would normally use the LLMInputHandler
        # For testing, we'll check if the core has the required components

        # Import LLM components
        from core.llm_input_framework import LLMInputHandler, LLMInput, InputType

        # Create an LLM input handler with our core
        input_handler = LLMInputHandler(self.core)

        # Test a simple function call
        llm_input = LLMInput(type=InputType.ACTION, action="get_system_status")

        # Process the input
        result = input_handler.process_input(llm_input)

        # Check result
        self.assertEqual(result.status, "success")
        self.assertIsNotNone(result.data)

        # Test core status information
        system_status = result.data
        self.assertIn("name", system_status)
        self.assertIn("uptime", system_status)
        self.assertIn("state", system_status)
        self.assertIn("components", system_status)

    def test_cross_component_interaction(self):
        """Test interaction between multiple components through the core"""
        # Set up a scenario that involves multiple components
        # For example, a voice command that triggers automation

        # First, set up the mock responses
        self.mock_voice.speak.return_value = True
        self.mock_automation.execute_task.return_value = True

        # Simulate a voice command that should trigger automation
        command_event = Event(
            event_type=EventType.USER_VOICE_COMMAND,
            data={"command": "click at position 100 200"},
            priority=EventPriority.HIGH,
            source="test",
        )

        # Post the command
        self.core.event_bus.post_event(command_event)

        # Wait for processing
        time.sleep(0.2)

        # In a full system, this would be parsed by an LLM, then turned into
        # automation commands. Since we're mocking, we can simulate the completion
        # with a direct automation command

        # Simulate the resulting automation command
        automation_event = Event(
            event_type=EventType.AUTOMATION_STARTED,
            data={"action": "click_at", "parameters": {"x": 100, "y": 200}},
            priority=EventPriority.NORMAL,
            source="llm_handler",
        )

        # Post the automation event
        self.core.event_bus.post_event(automation_event)

        # Wait for processing
        time.sleep(0.1)

        # Simulate the response after completion
        response_event = Event(
            event_type=EventType.SPEECH_STARTED,
            data={"text": "I clicked at position 100, 200"},
            priority=EventPriority.NORMAL,
            source="llm_handler",
        )

        # Post the response event
        self.core.event_bus.post_event(response_event)

        # Wait for processing
        time.sleep(0.1)

        # Voice service should have been called to speak the response
        self.assertTrue(self.mock_voice.speak.called)

    def test_component_dependency_ordering(self):
        """Test component initialization respects dependencies"""
        # Create a temporary configuration with component dependencies
        dependency_config = {
            "core": {
                "debug_mode": True,
                "enabled_components": ["component_a", "component_b", "component_c"],
            },
            "component_a": {"enabled": True},
            "component_b": {"enabled": True},
            "component_c": {"enabled": True},
        }

        # Create temp config file
        config_path = os.path.join(self.temp_dir.name, "dependency_config.yaml")
        with open(config_path, "w") as f:
            yaml.dump(dependency_config, f)

        # Mock the dependency relationships
        # component_c depends on component_b, which depends on component_a
        with patch.dict(
            self.core._component_dependencies,
            {
                "component_b": ["event_bus", "config", "core", "component_a"],
                "component_c": [
                    "event_bus",
                    "config",
                    "core",
                    "component_a",
                    "component_b",
                ],
            },
        ):
            # We would also need to mock the component classes
            # But for simplicity, we'll just check the initialization order method

            # Create a new core with our config
            test_core = SabrinaCore(config_path)

            # Use a spy on the _create_component_instances method
            with patch.object(test_core, "_create_component_instances") as mock_create:
                # Force the components dict to include our test components
                print(mock_create)
                test_core.components = {
                    "core": test_core,
                    "component_a": MagicMock(),
                    "component_b": MagicMock(),
                    "component_c": MagicMock(),
                }

                # Get initialization order
                init_order = test_core._get_initialization_order()

                # Check order respects dependencies
                component_a_idx = init_order.index("component_a")
                component_b_idx = init_order.index("component_b")
                component_c_idx = init_order.index("component_c")

                self.assertLess(component_a_idx, component_b_idx)
                self.assertLess(component_b_idx, component_c_idx)

            # Clean up
            test_core.shutdown()


if __name__ == "__main__":
    unittest.main()
