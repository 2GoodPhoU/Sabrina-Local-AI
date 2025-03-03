"""
Pytest Configuration for Sabrina AI Tests
=======================================
This file contains global fixtures and configuration for pytest.
"""

import os
import sys
import time
import pytest
import tempfile
from pathlib import Path
from tests.test_utils.paths import (
    get_project_root,
    get_test_dir,
    get_test_data_dir,
    get_config_path,
    ensure_project_root_in_sys_path,
)

# Import path utilities
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))


# Ensure project root is in path
ensure_project_root_in_sys_path()


# Path fixtures
@pytest.fixture
def project_root():
    """Fixture providing the project root path"""
    return get_project_root()


@pytest.fixture
def test_dir():
    """Fixture providing the test directory path"""
    return get_test_dir()


@pytest.fixture
def data_dir():
    """Fixture providing the test data directory path"""
    return get_test_data_dir()


@pytest.fixture
def temp_dir():
    """Fixture providing a temporary directory for the test"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def config_dir():
    """Fixture providing the configuration directory path"""
    return get_config_path()


# Time fixtures
@pytest.fixture
def current_time():
    """Fixture providing the current time"""
    return time.time()


# Component fixtures
@pytest.fixture
def mock_event_bus():
    """Fixture providing a mock event bus"""
    from tests.test_utils.helpers import create_mock_event_bus

    return create_mock_event_bus()


@pytest.fixture
def mock_state_machine():
    """Fixture providing a mock state machine"""
    from tests.test_utils.helpers import create_mock_state_machine

    return create_mock_state_machine()


@pytest.fixture
def mock_voice_service():
    """Fixture providing a mock voice service"""
    from tests.test_utils.helpers import MockVoiceService

    return MockVoiceService()


@pytest.fixture
def mock_vision_service():
    """Fixture providing a mock vision service"""
    from tests.test_utils.helpers import MockVisionService

    return MockVisionService()


@pytest.fixture
def mock_automation_service():
    """Fixture providing a mock automation service"""
    from tests.test_utils.helpers import MockAutomationService

    return MockAutomationService()


@pytest.fixture
def mock_hearing_service():
    """Fixture providing a mock hearing service"""
    from tests.test_utils.helpers import MockHearingService

    return MockHearingService()


# Configuration fixtures
@pytest.fixture
def create_test_config():
    """
    Fixture providing a function to create test configuration files

    Usage:
        def test_something(create_test_config):
            config_path = create_test_config({
                'section': {'key': 'value'}
            }, format='yaml')
    """
    from tests.test_utils.helpers import create_test_config as create_config

    # Keep track of created files for cleanup
    created_files = []

    def _create_config(config_data, format="yaml"):
        path = create_config(config_data, format)
        created_files.append(path)
        return path

    yield _create_config

    # Clean up created files
    for file_path in created_files:
        try:
            os.remove(file_path)
        except (OSError, IOError):
            pass


# Core system fixture
@pytest.fixture
def sabrina_core():
    """
    Fixture providing a Sabrina core instance with mocked components

    This is a higher-level fixture that creates a complete environment
    for integration testing with the core system.
    """
    from unittest.mock import patch

    # Create patches for all component classes
    patches = []
    for component in [
        "VoiceService",
        "VisionService",
        "HearingService",
        "AutomationService",
        "PresenceService",
        "SmartHomeService",
    ]:
        path = f"core.component_service_wrappers.{component}"
        patches.append(patch(path))

    # Start all patches
    mocks = [p.start() for p in patches]
    print(mocks)

    # Create a temporary config
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as temp_config:
        temp_config.write(
            b"""
core:
  debug_mode: true
  log_level: DEBUG
  enabled_components: ["voice", "automation"]
voice:
  enabled: true
  api_url: http://localhost:8100
  volume: 0.5
automation:
  enabled: true
  mouse_move_duration: 0.1
  typing_interval: 0.05
"""
        )

    # Try to import the core
    try:
        from core.core import SabrinaCore

        core = SabrinaCore(temp_config.name)
        yield core
        core.shutdown()
    except ImportError as e:
        pytest.skip(f"Could not import SabrinaCore: {e}")
    finally:
        # Stop all patches
        for p in patches:
            p.stop()

        # Remove temp config
        os.unlink(temp_config.name)


def pytest_configure(config):
    """Configure pytest for Sabrina AI tests"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "requires_voice: mark tests that require voice service"
    )
    config.addinivalue_line(
        "markers", "requires_vision: mark tests that require vision service"
    )
    config.addinivalue_line(
        "markers", "requires_hearing: mark tests that require hearing service"
    )
    config.addinivalue_line(
        "markers", "requires_automation: mark tests that require automation service"
    )
    config.addinivalue_line(
        "markers", "requires_gpu: mark tests that require GPU access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test items to handle specific environment needs"""
    # Skip tests that require unavailable components
    for item in items:
        # Skip GPU tests if no GPU available
        if "requires_gpu" in item.keywords:
            try:
                import torch

                if not torch.cuda.is_available():
                    item.add_marker(pytest.mark.skip(reason="No GPU available"))
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="PyTorch not installed"))
