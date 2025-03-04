#!/usr/bin/env python3
"""
Unit tests for Sabrina AI Event System
"""

import unittest
from unittest.mock import MagicMock
import time

# Add test utilities import first
from tests.test_utils.paths import ensure_project_root_in_sys_path

# Import components to test
from utilities.event_system import EventBus, Event, EventType, EventPriority

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()


class TestEventSystem(unittest.TestCase):
    """Test case for EventBus and related classes"""

    def setUp(self):
        """Set up test fixtures"""
        self.event_bus = EventBus(max_queue_size=100, worker_count=1)
        self.event_bus.start()

    def tearDown(self):
        """Clean up test fixtures"""
        self.event_bus.stop()

    def test_event_creation(self):
        """Test Event object creation"""
        # Create an event
        test_data = {"test_key": "test_value"}
        event = Event(
            event_type=EventType.SYSTEM,
            data=test_data,
            source="test_source",
            priority=EventPriority.NORMAL,
        )

        # Check event properties
        self.assertEqual(event.event_type, EventType.SYSTEM)
        self.assertEqual(event.data, test_data)
        self.assertEqual(event.source, "test_source")
        self.assertEqual(event.priority, EventPriority.NORMAL)
        self.assertIsNotNone(event.id)
        self.assertIsNotNone(event.timestamp)

    def test_event_data_access(self):
        """Test Event data access methods"""
        # Create an event with data
        event = Event(
            event_type=EventType.SYSTEM,
            data={"key1": "value1", "key2": "value2"},
            source="test_source",
        )

        # Test get() method
        self.assertEqual(event.get("key1"), "value1")
        self.assertEqual(event.get("key2"), "value2")
        self.assertIsNone(event.get("nonexistent_key"))
        self.assertEqual(event.get("nonexistent_key", "default"), "default")

        # Test merge_data() method
        event.merge_data({"key3": "value3", "key1": "new_value1"})
        self.assertEqual(event.get("key3"), "value3")
        self.assertEqual(event.get("key1"), "new_value1")  # Should be overwritten

        # Test to_dict() method
        event_dict = event.to_dict()
        self.assertEqual(event_dict["type"], "SYSTEM")
        self.assertEqual(event_dict["source"], "test_source")
        self.assertEqual(event_dict["priority"], "NORMAL")
        self.assertEqual(event_dict["data"]["key1"], "new_value1")
        self.assertEqual(event_dict["data"]["key3"], "value3")

    def test_handler_creation(self):
        """Test handler creation and filtering"""
        # Create a mock callback
        callback = MagicMock()

        # Create a handler with filters
        handler = self.event_bus.create_handler(
            callback=callback,
            event_types=[
                EventType.SYSTEM,
                EventType.SYSTEM_ERROR,
            ],  # Fixed: Use valid EventType
            min_priority=EventPriority.HIGH,
            sources=["test_source"],
        )

        # Check handler properties
        self.assertEqual(handler.callback, callback)
        self.assertEqual(
            handler.event_types, [EventType.SYSTEM, EventType.SYSTEM_ERROR]
        )  # Fixed
        self.assertEqual(handler.min_priority, EventPriority.HIGH)
        self.assertEqual(handler.sources, ["test_source"])
        self.assertIsNotNone(handler.id)

        # Test can_handle method
        # Should handle matching event
        matching_event = Event(
            event_type=EventType.SYSTEM,
            priority=EventPriority.CRITICAL,
            source="test_source",
        )
        self.assertTrue(handler.can_handle(matching_event))

        # Should not handle event with wrong type
        wrong_type_event = Event(
            event_type=EventType.USER_INPUT,
            priority=EventPriority.CRITICAL,
            source="test_source",
        )
        self.assertFalse(handler.can_handle(wrong_type_event))

        # Should not handle event with too low priority
        low_priority_event = Event(
            event_type=EventType.SYSTEM,
            priority=EventPriority.NORMAL,
            source="test_source",
        )
        self.assertFalse(handler.can_handle(low_priority_event))

        # Should not handle event with wrong source
        wrong_source_event = Event(
            event_type=EventType.SYSTEM,
            priority=EventPriority.CRITICAL,
            source="other_source",
        )
        self.assertFalse(handler.can_handle(wrong_source_event))

    def test_event_posting_and_handling(self):
        """Test posting events and handling them"""
        # Create a result container for the callback
        result_container = []

        # Create a callback that stores the received event
        def test_callback(event):
            result_container.append(event)

        # Create and register a handler
        handler = self.event_bus.create_handler(
            callback=test_callback, event_types=[EventType.SYSTEM]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create an event
        test_event = Event(
            event_type=EventType.SYSTEM, data={"test": "data"}, source="test_source"
        )

        # Post the event
        self.event_bus.post_event(test_event)

        # Wait for event processing
        time.sleep(0.2)

        # Check that the event was handled
        self.assertEqual(len(result_container), 1)
        self.assertEqual(result_container[0].event_type, EventType.SYSTEM)
        self.assertEqual(result_container[0].data, {"test": "data"})

        # Unregister the handler
        self.event_bus.unregister_handler(handler_id)

        # Clear result container
        result_container.clear()

        # Post another event
        another_event = Event(
            event_type=EventType.SYSTEM,
            data={"test": "more data"},
            source="test_source",
        )
        self.event_bus.post_event(another_event)

        # Wait for event processing
        time.sleep(0.2)

        # Check that the event was not handled (handler was unregistered)
        self.assertEqual(len(result_container), 0)

    def test_immediate_event_processing(self):
        """Test immediate (synchronous) event processing"""
        # Create a result container for the callback
        result_container = []

        # Create a callback that stores the received event
        def test_callback(event):
            result_container.append(event)

        # Create and register a handler
        handler = self.event_bus.create_handler(
            callback=test_callback, event_types=[EventType.SYSTEM]
        )
        handler_id = self.event_bus.register_handler(handler)

        # Create an event
        test_event = Event(
            event_type=EventType.SYSTEM,
            data={"test": "immediate data"},
            source="test_source",
        )

        # Process the event immediately
        result = self.event_bus.post_event_immediate(test_event)

        # Check result
        self.assertTrue(result)

        # Check that the event was handled immediately
        self.assertEqual(len(result_container), 1)
        self.assertEqual(result_container[0].data["test"], "immediate data")

        # Unregister the handler
        self.event_bus.unregister_handler(handler_id)

    def test_event_priority(self):
        """Test event priority handling"""
        # Create result containers for two handlers
        high_priority_events = []
        normal_priority_events = []
        processed_order = []

        # Create event processing callbacks
        def high_priority_callback(event):
            high_priority_events.append(event)
            processed_order.append("high")

        def normal_priority_callback(event):
            normal_priority_events.append(event)
            processed_order.append("normal")

        # Register handlers with different priorities
        high_handler = self.event_bus.create_handler(
            callback=high_priority_callback,
            event_types=[EventType.SYSTEM],
            min_priority=EventPriority.HIGH,
        )
        self.event_bus.register_handler(high_handler)

        normal_handler = self.event_bus.create_handler(
            callback=normal_priority_callback, event_types=[EventType.SYSTEM]
        )
        self.event_bus.register_handler(normal_handler)

        # Create and post a critical priority event
        critical_event = Event(
            event_type=EventType.SYSTEM, priority=EventPriority.CRITICAL, source="test"
        )
        self.event_bus.post_event_immediate(critical_event)

        # Create and post a normal priority event
        normal_event = Event(
            event_type=EventType.SYSTEM, priority=EventPriority.NORMAL, source="test"
        )
        self.event_bus.post_event_immediate(normal_event)

        # Check that high priority handler received the critical event (and not normal event)
        self.assertEqual(len(high_priority_events), 1)

        # Check that normal priority handler received both events
        self.assertEqual(len(normal_priority_events), 2)

    def test_event_history(self):
        """Test event history tracking"""
        # Clear existing history
        self.event_bus.history = []

        # Create and post some events
        for i in range(5):
            event = Event(event_type=EventType.SYSTEM, data={"index": i}, source="test")
            self.event_bus.post_event_immediate(event)

        # Check history length
        self.assertEqual(len(self.event_bus.history), 5)

        # Check history content (in order)
        for i, event in enumerate(self.event_bus.history):
            self.assertEqual(event.data["index"], i)

    def test_event_stats(self):
        """Test event statistics tracking"""
        # Get initial stats
        initial_stats = self.event_bus.get_stats()
        initial_processed = initial_stats["processed_count"]

        # Post some events
        num_events = 5
        for i in range(num_events):
            # Use post_event_immediate to ensure immediate processing
            self.event_bus.post_event_immediate(
                Event(event_type=EventType.SYSTEM, data={"index": i}, source="test")
            )

        # Add a small delay to ensure processing completes
        time.sleep(0.2)

        # Get updated stats
        updated_stats = self.event_bus.get_stats()

        # Check stats were updated - adjust test to match implementation
        # Should be initial_processed + number of new events
        self.assertEqual(
            updated_stats["processed_count"] - initial_processed, num_events
        )

    def test_error_handling_in_callbacks(self):
        """Test error handling for exceptions in callbacks"""

        # Create a callback that raises an exception
        def error_callback(event):
            raise RuntimeError("Test error")

        # Create result collection for a second handler
        second_handler_events = []

        def second_callback(event):
            second_handler_events.append(event)

        # Register both handlers
        error_handler = self.event_bus.create_handler(
            callback=error_callback, event_types=[EventType.SYSTEM]
        )
        self.event_bus.register_handler(error_handler)

        second_handler = self.event_bus.create_handler(
            callback=second_callback, event_types=[EventType.SYSTEM]
        )
        self.event_bus.register_handler(second_handler)

        # Create and post an event
        test_event = Event(
            event_type=EventType.SYSTEM, data={"test": "error handling"}, source="test"
        )

        # This should not raise an exception to the caller
        result = self.event_bus.post_event_immediate(test_event)
        print(result)

        # Check that second handler still got the event
        self.assertEqual(len(second_handler_events), 1)
        self.assertEqual(second_handler_events[0].data["test"], "error handling")


if __name__ == "__main__":
    unittest.main()
