#!/usr/bin/env python3
"""
Integration tests for Sabrina AI Automation Service
Tests the integration between the automation service and other components
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
from core.component_service_wrappers import AutomationService
from utilities.event_system import Event, EventBus, EventType, EventPriority
from core.state_machine import StateMachine, SabrinaState

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("automation_integration_test")


class TestAutomationServiceIntegration(unittest.TestCase):
    """Integration tests for the Automation Service component"""

    def setUp(self):
        """Set up test fixtures"""
        # Create event bus
        self.event_bus = EventBus()
        self.event_bus.start()

        # Create state machine
        self.state_machine = StateMachine(self.event_bus)
        self.state_machine.transition_to(SabrinaState.READY)

        # Create test config
        self.config = {
            "enabled": True,
            "mouse_move_duration": 0.1,
            "typing_interval": 0.05,
            "failsafe": True,
        }

        # Mock Actions client
        self.setup_actions_mock()

        # Create automation service
        self.automation_service = AutomationService(
            name="automation",
            event_bus=self.event_bus,
            state_machine=self.state_machine,
            config=self.config,
        )

        # Initialize the service
        self.automation_service.initialize()

    def tearDown(self):
        """Clean up test fixtures"""
        # Shutdown automation service
        self.automation_service.shutdown()

        # Stop event bus
        self.event_bus.stop()

        # Stop patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def setup_actions_mock(self):
        """Set up mocks for automation actions"""
        self._patchers = []

        # Patch Actions class
        actions_patcher = patch("services.automation.automation.Actions")
        self.mock_actions_class = actions_patcher.start()
        self._patchers.append(actions_patcher)

        # Create mock instance
        self.mock_actions = MagicMock()

        # Configure mock behavior
        self.mock_actions.move_mouse_to.return_value = True
        self.mock_actions.click.return_value = True
        self.mock_actions.click_at.return_value = True
        self.mock_actions.type_text.return_value = True
        self.mock_actions.press_key.return_value = True
        self.mock_actions.drag_mouse.return_value = True
        self.mock_actions.scroll.return_value = True
        self.mock_actions.hotkey.return_value = True
        self.mock_actions.get_mouse_position.return_value = (500, 500)
        self.mock_actions.run_shortcut.return_value = True
        self.mock_actions.get_available_shortcuts.return_value = [
            "copy",
            "paste",
            "save",
        ]
        self.mock_actions.run_common_task.return_value = True

        # Mock pyautogui availability
        self.mock_actions.pyautogui_available = True
        self.mock_actions.screen_width = 1920
        self.mock_actions.screen_height = 1080

        # Set the mock instance as the return value
        self.mock_actions_class.return_value = self.mock_actions

    def test_automation_service_initialization(self):
        """Test automation service initialization"""
        # Check that service was initialized
        self.assertEqual(self.automation_service.status.name, "READY")
        self.assertIsNotNone(self.automation_service.actions)

        # Check config values were passed correctly
        self.assertEqual(self.automation_service.mouse_move_duration, 0.1)
        self.assertEqual(self.automation_service.typing_interval, 0.05)
        self.assertTrue(self.automation_service.failsafe)

        # Verify Actions was initialized
        self.mock_actions_class.assert_called_once()

        # Verify configure was called with correct parameters
        self.mock_actions.configure.assert_called_once_with(
            mouse_move_duration=0.1, typing_interval=0.05, failsafe=True
        )

    def test_move_mouse_functionality(self):
        """Test move mouse functionality"""
        # Call move_mouse_to method
        self.automation_service.execute_task("move_mouse_to", x=500, y=300)

        # Check that the service transitioned to the EXECUTING_TASK state
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Wait for event processing
        time.sleep(0.1)

        # Verify that the action was called (indirectly via the post_event mechanism)
        # Since we can't easily check if the thread was called, we'll verify the last_action was set
        self.assertEqual(self.automation_service.last_action, "move_mouse_to")

    def test_automation_event_handling(self):
        """Test handling of automation events"""
        # Create result collectors
        automation_started_events = []
        automation_completed_events = []

        # Create handlers for automation events
        def started_handler(event):
            if event.event_type == EventType.AUTOMATION_STARTED:
                automation_started_events.append(event)

        def completed_handler(event):
            if event.event_type == EventType.AUTOMATION_COMPLETED:
                automation_completed_events.append(event)

        # Register handlers
        started_handler_obj = self.event_bus.create_handler(
            callback=started_handler, event_types=[EventType.AUTOMATION_STARTED]
        )
        completed_handler_obj = self.event_bus.create_handler(
            callback=completed_handler, event_types=[EventType.AUTOMATION_COMPLETED]
        )

        started_handler_id = self.event_bus.register_handler(started_handler_obj)
        completed_handler_id = self.event_bus.register_handler(completed_handler_obj)
        automation_completed_events.clear()

        # Create and post an automation event directly
        started_event = Event(
            event_type=EventType.AUTOMATION_STARTED,
            data={"action": "click_at", "parameters": {"x": 100, "y": 200}},
            priority=EventPriority.HIGH,
            source="test",
        )

        # Post the event
        self.event_bus.post_event_immediate(started_event)

        # Wait for event processing
        time.sleep(0.1)

        # Check that handler received the event
        self.assertEqual(len(automation_started_events), 1)
        self.assertEqual(automation_started_events[0].get("action"), "click_at")

        # The action execution would have begun in a thread, but we can't easily check its completion
        # For testing purposes, create and post a completion event manually
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "click_at", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Check that handler received the event
        self.assertEqual(len(automation_completed_events), 1)

        # Clean up
        self.event_bus.unregister_handler(started_handler_id)
        self.event_bus.unregister_handler(completed_handler_id)

    def test_click_functionality(self):
        """Test click functionality"""
        # Call click method with test coordinates
        result = self.automation_service.execute_task(
            "click_at", x=100, y=200, button="left", clicks=1
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "click_at", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify state transition back to READY
        self.assertEqual(self.state_machine.current_state, SabrinaState.READY)

    def test_type_text_functionality(self):
        """Test type text functionality"""
        test_text = "Hello, this is a test."

        # Call type_text method with test text
        result = self.automation_service.execute_task(
            "type_text", text=test_text, interval=0.01
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "type_text", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "type_text")

    def test_drag_mouse_functionality(self):
        """Test drag mouse functionality"""
        # Call drag_mouse method
        result = self.automation_service.execute_task(
            "drag_mouse", start_x=100, start_y=100, end_x=200, end_y=200, duration=0.1
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "drag_mouse", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "drag_mouse")

    def test_scroll_functionality(self):
        """Test scroll functionality"""
        # Call scroll method
        result = self.automation_service.execute_task(
            "scroll", amount=5, direction="down"
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "scroll", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "scroll")

    def test_hotkey_functionality(self):
        """Test hotkey functionality"""
        # Call hotkey method
        result = self.automation_service.execute_task("hotkey", keys=["ctrl", "c"])

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "hotkey", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "hotkey")

    def test_run_shortcut_functionality(self):
        """Test run shortcut functionality"""
        # Call run_shortcut method
        result = self.automation_service.execute_task(
            "run_shortcut", shortcut_name="copy"
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "run_shortcut", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "run_shortcut")

    def test_run_common_task_functionality(self):
        """Test run common task functionality"""
        # Call run_common_task method
        result = self.automation_service.execute_task(
            "run_common_task", task_name="copy_paste", target_x=100, target_y=100
        )

        # Check result
        self.assertTrue(result)

        # Verify state transition to EXECUTING_TASK
        self.assertEqual(self.state_machine.current_state, SabrinaState.EXECUTING_TASK)

        # Manually post completion event to simulate action completion
        completed_event = Event(
            event_type=EventType.AUTOMATION_COMPLETED,
            data={"action": "run_common_task", "result": True},
            priority=EventPriority.NORMAL,
            source="automation_service",
        )

        # Post the event
        self.event_bus.post_event_immediate(completed_event)

        # Verify the service's last_action was updated
        self.assertEqual(self.automation_service.last_action, "run_common_task")

    def test_error_handling(self):
        """Test error handling in automation service"""
        # Create a result collector
        error_events = []

        # Create a handler for error events
        def error_handler(event):
            if event.event_type == EventType.AUTOMATION_ERROR:
                error_events.append(event)

        # Register the handler
        handler = self.event_bus.create_handler(
            callback=error_handler, event_types=[EventType.AUTOMATION_ERROR]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Configure mock to raise an exception
        self.mock_actions.move_mouse_to.side_effect = Exception("Test error")

        # Create and post an event that will trigger an error
        error_event = Event(
            event_type=EventType.AUTOMATION_STARTED,
            data={"action": "move_mouse_to", "parameters": {"x": 100, "y": 200}},
            priority=EventPriority.NORMAL,
            source="test",
        )

        # Post the event
        self.event_bus.post_event_immediate(error_event)

        # Wait for event processing
        time.sleep(0.1)

        # Verify an error event was posted
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0].get("action"), "move_mouse_to")

        # Clean up
        self.event_bus.unregister_handler(handler_id)

    def test_status_reporting(self):
        """Test status reporting"""
        # Set some state for testing
        self.automation_service.last_action = "test_action"

        # Get status
        status = self.automation_service.get_status()

        # Check status content
        self.assertEqual(status["name"], "automation")
        self.assertEqual(status["status"], "READY")
        self.assertEqual(status["last_action"], "test_action")
        self.assertEqual(status["mouse_move_duration"], 0.1)
        self.assertEqual(status["typing_interval"], 0.05)
        self.assertTrue(status["failsafe"])
        self.assertTrue(status["pyautogui_available"])

    def test_shutdown_behavior(self):
        """Test behavior during shutdown"""
        # Call shutdown
        result = self.automation_service.shutdown()

        # Check result
        self.assertTrue(result)

        # Verify status is updated
        self.assertEqual(self.automation_service.status.name, "SHUTDOWN")

        # Ensure all handlers are unregistered
        for handler_id in list(self.automation_service.handler_ids):
            self.event_bus.unregister_handler(handler_id)

        # Verify handlers were unregistered
        self.assertEqual(len(self.automation_service.handler_ids), 0)


if __name__ == "__main__":
    unittest.main()
