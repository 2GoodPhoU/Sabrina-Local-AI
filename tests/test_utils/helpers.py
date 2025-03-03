#!/usr/bin/env python3
"""
Test Helper Utilities for Sabrina AI Tests
=========================================
Common utility functions and helpers for Sabrina AI tests to improve
test consistency and reduce duplication across test files.
"""

import os
import sys
import time
import yaml
import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
from unittest.mock import MagicMock, patch

# Import the path utilities
from tests.test_utils.paths import (
    get_project_root,
    get_test_dir,
    ensure_project_root_in_sys_path,
)

# Ensure project root is in path
ensure_project_root_in_sys_path()


def create_test_config(config_data: Dict[str, Any], format: str = "yaml") -> str:
    """
    Create a test configuration file with the specified format.

    Args:
        config_data: Dictionary containing configuration data
        format: Format to save in ('yaml' or 'json')

    Returns:
        str: Path to the created config file
    """
    # Create temporary file
    fd, temp_path = tempfile.mkstemp(suffix=f".{format}")
    os.close(fd)

    # Write data in the specified format
    with open(temp_path, "w") as f:
        if format == "yaml":
            yaml.dump(config_data, f)
        elif format == "json":
            json.dump(config_data, f, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

    return temp_path


def wait_for_condition(
    condition_func: Callable[[], bool],
    timeout: float = 5.0,
    check_interval: float = 0.1,
    message: str = "Condition not met within timeout",
) -> bool:
    """
    Wait for a condition to be true within a timeout period.

    Args:
        condition_func: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        check_interval: Time between condition checks in seconds
        message: Error message if timeout is reached

    Returns:
        bool: True if condition was met, False if timeout was reached
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(check_interval)

    return False


class MockComponent:
    """Base class for mocked components used in testing"""

    def __init__(self, name: str, **kwargs):
        self.name = name
        self.initialize_called = False
        self.shutdown_called = False
        self.status = "READY"

        # Store additional attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    def initialize(self) -> bool:
        """Mock initialize method"""
        self.initialize_called = True
        return True

    def shutdown(self) -> bool:
        """Mock shutdown method"""
        self.shutdown_called = True
        return True

    def get_status(self) -> Dict[str, Any]:
        """Mock get_status method"""
        return {
            "name": self.name,
            "status": self.status,
            "initialize_called": self.initialize_called,
            "shutdown_called": self.shutdown_called,
        }


class MockVoiceService(MockComponent):
    """Mock voice service for testing"""

    def __init__(self, **kwargs):
        super().__init__(name="voice", **kwargs)
        self.last_text = ""
        self.currently_speaking = False

    def speak(self, text: str, **kwargs) -> bool:
        """Mock speak method"""
        self.last_text = text
        self.currently_speaking = True
        return True


class MockVisionService(MockComponent):
    """Mock vision service for testing"""

    def __init__(self, **kwargs):
        super().__init__(name="vision", **kwargs)
        self.last_capture_path = None
        self.last_ocr_text = ""

    def capture_screen(
        self, mode: str = "full_screen", region: Dict[str, int] = None
    ) -> str:
        """Mock capture_screen method"""
        self.last_capture_path = f"mock_capture_{time.time()}.png"
        return self.last_capture_path

    def extract_text(self, image_path: str = None) -> str:
        """Mock extract_text method"""
        self.last_ocr_text = "Mock OCR text for testing"
        return self.last_ocr_text


class MockAutomationService(MockComponent):
    """Mock automation service for testing"""

    def __init__(self, **kwargs):
        super().__init__(name="automation", **kwargs)
        self.last_action = None

    def execute_task(self, action: str, **kwargs) -> bool:
        """Mock execute_task method"""
        self.last_action = (action, kwargs)
        return True

    def click_at(self, x: int, y: int, **kwargs) -> bool:
        """Mock click_at method"""
        self.last_action = ("click_at", {"x": x, "y": y, **kwargs})
        return True

    def type_text(self, text: str, **kwargs) -> bool:
        """Mock type_text method"""
        self.last_action = ("type_text", {"text": text, **kwargs})
        return True


class MockHearingService(MockComponent):
    """Mock hearing service for testing"""

    def __init__(self, **kwargs):
        super().__init__(name="hearing", **kwargs)
        self.last_transcription = ""
        self.currently_listening = False

    def listen_for_wake_word(self) -> bool:
        """Mock listen_for_wake_word method"""
        return True

    def start_listening(self) -> bool:
        """Mock start_listening method"""
        self.currently_listening = True
        return True


def create_mock_event_bus() -> MagicMock:
    """
    Create a mock event bus for testing.

    Returns:
        MagicMock: Mock event bus
    """
    mock_event_bus = MagicMock()
    mock_event_bus.running = True
    mock_event_bus.post_event.return_value = True
    mock_event_bus.post_event_immediate.return_value = True

    # Add handler registration methods
    mock_event_bus.create_handler.return_value = MagicMock()
    mock_event_bus.register_handler.return_value = "mock_handler_id"
    mock_event_bus.unregister_handler.return_value = True

    return mock_event_bus


def create_mock_state_machine() -> MagicMock:
    """
    Create a mock state machine for testing.

    Returns:
        MagicMock: Mock state machine
    """
    # Try to import the real state machine
    try:
        from core.state_machine import SabrinaState

        state_enum = SabrinaState
    except ImportError:
        # Create a mock enum if the real one isn't available
        from enum import Enum, auto

        class MockState(Enum):
            READY = auto()
            LISTENING = auto()
            PROCESSING = auto()
            RESPONDING = auto()
            SPEAKING = auto()
            ERROR = auto()

        state_enum = MockState

    mock_state_machine = MagicMock()
    mock_state_machine.current_state = state_enum.READY
    mock_state_machine.SabrinaState = state_enum
    mock_state_machine.transition_to.return_value = True

    return mock_state_machine


def setup_component_test_environment(
    component_class,
    config: Dict[str, Any] = None,
    mock_event_bus: bool = True,
    mock_state_machine: bool = True,
) -> Dict[str, Any]:
    """
    Set up a test environment for testing a component.

    Args:
        component_class: The component class to test
        config: Optional configuration for the component
        mock_event_bus: Whether to create a mock event bus
        mock_state_machine: Whether to create a mock state machine

    Returns:
        Dict: Environment with all required objects for testing
    """
    env = {}

    # Create mocks
    if mock_event_bus:
        env["event_bus"] = create_mock_event_bus()
    else:
        from utilities.event_system import EventBus

        env["event_bus"] = EventBus()
        env["event_bus"].start()

    if mock_state_machine:
        env["state_machine"] = create_mock_state_machine()
    else:
        from core.state_machine import StateMachine

        env["state_machine"] = StateMachine(event_bus=env["event_bus"])

    # Create default config if none provided
    if config is None:
        config = {"enabled": True}

    env["config"] = config

    # Create component instance
    env["component"] = component_class(
        name=component_class.__name__.lower().replace("service", ""),
        event_bus=env["event_bus"],
        state_machine=env["state_machine"],
        config=config,
    )

    return env


def teardown_component_test_environment(env: Dict[str, Any]):
    """
    Clean up a component test environment.

    Args:
        env: Environment dictionary from setup_component_test_environment
    """
    # Shut down component
    if "component" in env:
        env["component"].shutdown()

    # Stop event bus if it's a real one
    if (
        "event_bus" in env
        and hasattr(env["event_bus"], "stop")
        and callable(env["event_bus"].stop)
    ):
        env["event_bus"].stop()


class SabrinaTestCase(unittest.TestCase):
    """Base test case class for Sabrina AI tests with common utilities"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Ensure project root is in sys.path
        ensure_project_root_in_sys_path()

        # Create a temporary directory for test files
        cls.temp_dir = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures"""
        cls.temp_dir.cleanup()

    def create_temp_file(self, filename: str, content: str = "") -> str:
        """Create a temporary file in the test case's temp directory"""
        filepath = os.path.join(self.temp_dir.name, filename)
        with open(filepath, "w") as f:
            f.write(content)
        return filepath

    def create_temp_config(
        self, config_data: Dict[str, Any], format: str = "yaml"
    ) -> str:
        """Create a temporary config file with the given data"""
        filename = f"test_config.{format}"
        filepath = os.path.join(self.temp_dir.name, filename)

        with open(filepath, "w") as f:
            if format == "yaml":
                yaml.dump(config_data, f)
            elif format == "json":
                json.dump(config_data, f, indent=2)

        return filepath

    def get_test_resource(
        self, resource_name: str, resource_dir: str = "resources"
    ) -> str:
        """Get the path to a test resource file"""
        test_dir = get_test_dir()
        resource_path = test_dir / resource_dir / resource_name

        if not resource_path.exists():
            raise FileNotFoundError(f"Test resource not found: {resource_path}")

        return str(resource_path)
