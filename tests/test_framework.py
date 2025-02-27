"""
Sabrina AI Testing Framework
===========================
This module provides a comprehensive testing framework for Sabrina AI components.
"""

import os
import sys
import time
import logging
import unittest
import pytest
from unittest.mock import MagicMock, patch
import threading
import tempfile

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import core modules
from utilities.config_manager import ConfigManager
from utilities.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory
from utilities.event_system import EventBus, EventType, Event, EventPriority

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger("sabrina_test")

class TestBase(unittest.TestCase):
    """
    Base class for all Sabrina AI tests providing common utilities and setup
    """
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary config file
        self.temp_config_fd, self.temp_config_path = tempfile.mkstemp(suffix='.yaml')
        os.close(self.temp_config_fd)
        
        # Write default config to temp file
        with open(self.temp_config_path, 'w') as f:
            f.write("""
core:
  debug_mode: true
  log_level: DEBUG

voice:
  enabled: true
  api_url: http://localhost:8100
  volume: 0.8
  speed: 1.0
  pitch: 1.0
  emotion: normal

vision:
  enabled: true
  capture_method: auto
  use_ocr: true
  use_object_detection: false
  max_images: 5

hearing:
  enabled: true
  wake_word: hey sabrina
  silence_threshold: 0.03
  model_path: models/vosk-model
  use_hotkey: true
  hotkey: ctrl+shift+s

automation:
  mouse_move_duration: 0.2
  typing_interval: 0.1
  failsafe: true

memory:
  max_entries: 20
  use_vector_db: false
  vector_db_path: data/vectordb
            """)
        
        # Initialize core components for testing
        self.config_manager = ConfigManager(self.temp_config_path)
        self.error_handler = ErrorHandler(self.config_manager)
        self.event_bus = EventBus()
        self.event_bus.start()
        
        # Create test directories if they don't exist
        os.makedirs("logs", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/captures", exist_ok=True)
        
        logger.info(f"Test setup complete using config at {self.temp_config_path}")
    
    def tearDown(self):
        """Clean up test environment"""
        # Stop event bus
        if hasattr(self, 'event_bus'):
            self.event_bus.stop()
        
        # Clean up temp file
        if hasattr(self, 'temp_config_path') and os.path.exists(self.temp_config_path):
            os.unlink(self.temp_config_path)
        
        logger.info("Test teardown complete")
    
    def wait_for_events(self, timeout=1.0):
        """Wait for events to be processed"""
        time.sleep(timeout)
    
    def create_test_event(self, event_type=EventType.SYSTEM, data=None, 
                        priority=EventPriority.NORMAL, source="test"):
        """
        Create a test event
        
        Args:
            event_type: Event type
            data: Event data
            priority: Event priority
            source: Event source
            
        Returns:
            Event object
        """
        if data is None:
            data = {"test": True, "timestamp": time.time()}
            
        return Event(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source
        )
    
    def count_events_of_type(self, events, event_type):
        """
        Count events of a specific type
        
        Args:
            events: List of events
            event_type: Event type to count
            
        Returns:
            Count of events with the specified type
        """
        return sum(1 for event in events if event.event_type == event_type)


class ConfigManagerTests(TestBase):
    """Tests for the ConfigManager"""
    
    def test_load_config(self):
        """Test loading configuration"""
        # Configuration should have been loaded in setUp
        self.assertIsNotNone(self.config_manager.config)
        self.assertTrue(self.config_manager.has_section("core"))
        self.assertTrue(self.config_manager.has_section("voice"))
    
    def test_get_config(self):
        """Test retrieving configuration values"""
        # Test getting a value that exists
        debug_mode = self.config_manager.get_config("core", "debug_mode")
        self.assertEqual(debug_mode, True)
        
        # Test getting a value with a default
        test_value = self.config_manager.get_config("core", "nonexistent", "default_value")
        self.assertEqual(test_value, "default_value")
        
        # Test getting an entire section
        voice_section = self.config_manager.get_config("voice")
        self.assertIsInstance(voice_section, dict)
        self.assertIn("api_url", voice_section)
    
    def test_set_config(self):
        """Test setting configuration values"""
        # Set a new value
        self.config_manager.set_config("core", "test_key", "test_value")
        
        # Verify the value was set
        value = self.config_manager.get_config("core", "test_key")
        self.assertEqual(value, "test_value")
        
        # Set a value in a new section
        self.config_manager.set_config("test_section", "test_key", "test_value")
        
        # Verify the section and value were created
        value = self.config_manager.get_config("test_section", "test_key")
        self.assertEqual(value, "test_value")
    
    def test_save_and_load(self):
        """Test saving and loading configuration"""
        # Set a test value
        self.config_manager.set_config("test_section", "test_key", "test_value")
        
        # Save the configuration
        save_path = os.path.join(tempfile.gettempdir(), "test_config.yaml")
        self.config_manager.save_config(save_path)
        
        # Create a new config manager and load the saved config
        new_config = ConfigManager(save_path)
        
        # Verify the value was loaded
        value = new_config.get_config("test_section", "test_key")
        self.assertEqual(value, "test_value")
        
        # Clean up
        os.unlink(save_path)


class ErrorHandlerTests(TestBase):
    """Tests for the ErrorHandler"""
    
    def test_log_error(self):
        """Test logging errors"""
        # Create a test error
        test_error = ValueError("Test error")
        
        # Log the error
        error_info = self.error_handler.log_error(
            test_error, 
            context="test_log_error", 
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.PROCESSING
        )
        
        # Verify error info
        self.assertIsInstance(error_info, dict)
        self.assertEqual(error_info["error_type"], "ValueError")
        self.assertEqual(error_info["message"], "Test error")
        self.assertEqual(error_info["severity"], "WARNING")
        self.assertEqual(error_info["category"], "PROCESSING")
    
    def test_error_stats(self):
        """Test error statistics"""
        # Log multiple errors
        for i in range(3):
            self.error_handler.log_error(
                ValueError(f"Test error {i}"), 
                context=f"test_{i}", 
                severity=ErrorSeverity.WARNING,
                category=ErrorCategory.PROCESSING
            )
        
        # Get error stats
        stats = self.error_handler.get_error_stats()
        
        # Verify stats
        self.assertEqual(stats["total_errors"], 3)
        self.assertEqual(stats["by_severity"]["WARNING"], 3)
        self.assertGreaterEqual(len(stats["recent_errors"]), 1)
    
    def test_recovery_function(self):
        """Test error recovery function"""
        # Create a recovery function
        def recovery_func(error, context):
            return "recovered"
        
        # Register the recovery function
        self.error_handler.register_recovery_function(
            "ValueError", 
            ErrorCategory.PROCESSING, 
            recovery_func
        )
        
        # Create a test that uses try_with_recovery
        def operation():
            raise ValueError("Test error")
        
        result = self.error_handler.try_with_recovery(
            operation,
            recovery_func=lambda e: "fallback",
            context="test_recovery",
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.PROCESSING
        )
        
        # Verify result
        self.assertEqual(result, "fallback")


class EventBusTests(TestBase):
    """Tests for the EventBus"""
    
    def test_post_event(self):
        """Test posting events"""
        # Create event handler mock
        handler_mock = MagicMock()
        
        # Register event handler
        handler = self.event_bus.create_event_handler(
            event_types=[EventType.SYSTEM],
            callback=handler_mock,
            min_priority=EventPriority.LOW
        )
        self.event_bus.register_handler(handler)
        
        # Post event
        event = self.create_test_event()
        result = self.event_bus.post_event(event)
        
        # Wait for event to be processed
        self.wait_for_events()
        
        # Verify result and handler called
        self.assertTrue(result)
        handler_mock.assert_called_once()
    
    def test_event_filtering(self):
        """Test event filtering by type and priority"""
        # Create event handler mocks
        system_handler = MagicMock()
        voice_handler = MagicMock()
        high_priority_handler = MagicMock()
        
        # Register event handlers
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.SYSTEM],
            callback=system_handler,
            min_priority=EventPriority.LOW
        ))
        
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.VOICE],
            callback=voice_handler,
            min_priority=EventPriority.LOW
        ))
        
        self.event_bus.register_handler(self.event_bus.create_event_handler(
            event_types=[EventType.SYSTEM, EventType.VOICE],
            callback=high_priority_handler,
            min_priority=EventPriority.HIGH
        ))
        
        # Post events
        system_event = self.create_test_event(event_type=EventType.SYSTEM)
        voice_event = self.create_test_event(event_type=EventType.VOICE)
        low_priority_event = self.create_test_event(
            event_type=EventType.SYSTEM, 
            priority=EventPriority.LOW
        )
        high_priority_event = self.create_test_event(
            event_type=EventType.SYSTEM, 
            priority=EventPriority.HIGH
        )
        
        self.event_bus.post_event(system_event)
        self.event_bus.post_event(voice_event)
        self.event_bus.post_event(low_priority_event)
        self.event_bus.post_event(high_priority_event)
        
        # Wait for events to be processed
        self.wait_for_events()
        
        # Verify handlers called correctly
        self.assertEqual(system_handler.call_count, 3)  # system + low + high
        self.assertEqual(voice_handler.call_count, 1)   # voice
        self.assertEqual(high_priority_handler.call_count, 1)  # high only
    
    def test_event_history(self):
        """Test event history tracking"""
        # Post multiple events
        for i in range(5):
            event = self.create_test_event(data={"index": i})
            self.event_bus.post_event(event)
        
        # Wait for events to be processed
        self.wait_for_events()
        
        # Verify history
        self.assertGreaterEqual(len(self.event_bus.history), 5)
        
        # Verify event data preserved in history
        indices = [event.data.get("index") for event in self.event_bus.history[-5:]]
        self.assertEqual(set(indices), set(range(5)))


# Run tests if module is executed directly
if __name__ == "__main__":
    unittest.main()