"""
Automation Component Tests for Sabrina AI
=======================================
Tests for the Automation functionality.
"""

import os
import sys
import unittest
import time
from unittest.mock import MagicMock, patch
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import automation components
from services.automation.automation import Actions
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler
from utilities.event_system import EventBus, EventType, Event, EventPriority

# Import base test class
from tests.test_framework import TestBase


class ActionsTests(TestBase):
    """Tests for the Automation Actions"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Initialize automation component
        self.actions = Actions()
    
    def test_initialization(self):
        """Test initialization of Actions class"""
        # Verify initial state
        self.assertIsInstance(self.actions, Actions)
        
        # Test PyAutoGUI availability detection
        with patch('importlib.import_module') as mock_import:
            # Force PyAutoGUI import to fail
            mock_import.side_effect = ImportError("No module named 'pyautogui'")
            
            # Create new Actions instance
            actions = Actions()
            
            # Verify
            self.assertFalse(actions.pyautogui_available)
    
    @patch('pyautogui.moveTo')
    def test_move_mouse_to(self, mock_move_to):
        """Test mouse movement"""
        # Ensure pyautogui_available is True for this test
        self.actions.pyautogui_available = True
        self.actions.pyautogui = MagicMock()
        self.actions.pyautogui.moveTo = mock_move_to
        
        # Test move_mouse_to
        self.actions.move_mouse_to(100, 200, duration=0.5)
        
        # Verify
        mock_move_to.assert_called_once_with(100, 200, duration=0.5)
        
        # Test with pyautogui not available
        mock_move_to.reset_mock()
        self.actions.pyautogui_available = False
        
        # This should use the placeholder implementation
        self.actions.move_mouse_to(100, 200, duration=0.5)
        
        # Verify
        mock_move_to.assert_not_called()
    
    @patch('pyautogui.click')
    def test_click(self, mock_click):
        """Test mouse click"""
        # Ensure pyautogui_available is True for this test
        self.actions.pyautogui_available = True
        self.actions.pyautogui = MagicMock()
        self.actions.pyautogui.click = mock_click
        
        # Test click
        self.actions.click()
        
        # Verify
        mock_click.assert_called_once()
        
        # Test with pyautogui not available
        mock_click.reset_mock()
        self.actions.pyautogui_available = False
        
        # This should use the placeholder implementation
        self.actions.click()
        
        # Verify
        mock_click.assert_not_called()
    
    @patch('pyautogui.write')
    def test_type_text(self, mock_write):
        """Test typing text"""
        # Ensure pyautogui_available is True for this test
        self.actions.pyautogui_available = True
        self.actions.pyautogui = MagicMock()
        self.actions.pyautogui.write = mock_write
        
        # Test type_text
        self.actions.type_text("Hello world", interval=0.2)
        
        # Verify
        mock_write.assert_called_once_with("Hello world", interval=0.2)
        
        # Test with pyautogui not available
        mock_write.reset_mock()
        self.actions.pyautogui_available = False
        
        # This should use the placeholder implementation
        self.actions.type_text("Hello world", interval=0.2)
        
        # Verify
        mock_write.assert_not_called()
    
    @patch('pyautogui.press')
    def test_press_key(self, mock_press):
        """Test pressing a key"""
        # Ensure pyautogui_available is True for this test
        self.actions.pyautogui_available = True
        self.actions.pyautogui = MagicMock()
        self.actions.pyautogui.press = mock_press
        
        # Test press_key
        self.actions.press_key("enter")
        
        # Verify
        mock_press.assert_called_once_with("enter")
        
        # Test with pyautogui not available
        mock_press.reset_mock()
        self.actions.pyautogui_available = False
        
        # This should use the placeholder implementation
        self.actions.press_key("enter")
        
        # Verify
        mock_press.assert_not_called()


class AutomationIntegrationTests(TestBase):
    """Integration tests for the Automation system"""
    
    def setUp(self):
        """Set up test environment"""
        super().setUp()
        
        # Initialize automation component
        self.actions = Actions()
    
    @pytest.mark.integration
    def test_automation_event_integration(self):
        """Test integration between Automation system and event system"""
        # Create event handler to track automation events
        automation_events = []
        
        def automation_event_handler(event):
            automation_events.append(event)
        
        # Register handler
        handler = self.event_bus.create_event_handler(
            event_types=[EventType.AUTOMATION],
            callback=automation_event_handler
        )
        self.event_bus.register_handler(handler)
        
        # Mock automation methods
        self.actions.click = MagicMock()
        self.actions.move_mouse_to = MagicMock()
        self.actions.type_text = MagicMock()
        
        # Post automation events
        self.event_bus.post_event(Event(
            event_type=EventType.AUTOMATION,
            data={"command": "click"},
            source="test"
        ))
        
        self.event_bus.post_event(Event(
            event_type=EventType.AUTOMATION,
            data={"command": "move", "x": 100, "y": 200},
            source="test"
        ))
        
        self.event_bus.post_event(Event(
            event_type=EventType.AUTOMATION,
            data={"command": "type", "text": "Test text"},
            source="test"
        ))
        
        # Wait for events to be processed
        self.wait_for_events()
        
        # Verify events were received
        self.assertEqual(len(automation_events), 3)
        self.assertEqual(automation_events[0].data.get("command"), "click")
        self.assertEqual(automation_events[1].data.get("command"), "move")
        self.assertEqual(automation_events[2].data.get("command"), "type")
    
    @pytest.mark.integration
    @pytest.mark.skipif(not hasattr(Actions(), 'pyautogui_available') or not Actions().pyautogui_available, 
                       reason="PyAutoGUI not available")
    def test_real_mouse_movement(self):
        """Test real mouse movement (only in controlled environments)"""
        # Check for environment variable to enable real mouse tests
        if not os.environ.get("ENABLE_REAL_MOUSE_TESTS"):
            self.skipTest("Real mouse tests not enabled")
        
        # Save current mouse position
        current_x, current_y = self.actions.pyautogui.position()
        
        try:
            # Move mouse to a specific position
            self.actions.move_mouse_to(current_x + 10, current_y + 10, duration=0.1)
            
            # Verify (approximately)
            new_x, new_y = self.actions.pyautogui.position()
            self.assertAlmostEqual(new_x, current_x + 10, delta=2)
            self.assertAlmostEqual(new_y, current_y + 10, delta=2)
            
        finally:
            # Move mouse back to original position
            self.actions.move_mouse_to(current_x, current_y, duration=0.1)


if __name__ == "__main__":
    unittest.main()