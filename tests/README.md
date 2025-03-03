# Sabrina AI Test Framework

This directory contains the test framework and tests for the Sabrina AI project. The framework provides utilities for testing components in isolation (unit tests), testing interactions between components (integration tests), and testing the system as a whole (end-to-end tests).

## Test Structure

The test suite is organized as follows:

```
tests/
├── unit/               # Unit tests for individual components
├── integration/        # Integration tests for component interactions
├── e2e/                # End-to-end tests for the full system
├── data/               # Test data and resources
│   ├── configs/        # Test configuration files
│   └── resources/      # Test resource files
├── temp/               # Temporary files created during tests
├── test_utils/         # Test utilities and helpers
│   ├── paths.py        # Path utilities for consistent path handling
│   ├── helpers.py      # Helper functions and mocks
│   └── test_template.py # Template for new test files
├── conftest.py         # Pytest configuration and fixtures
├── pytest.ini          # Pytest settings
└── README.md           # This file
```

## Running Tests

### Using Pytest

The recommended way to run tests is using pytest:

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/

# Run a specific test file
pytest tests/unit/test_core.py

# Run a specific test class
pytest tests/unit/test_core.py::TestCore

# Run a specific test method
pytest tests/unit/test_core.py::TestCore::test_initialization
```

### Test Categories

You can run specific categories of tests using markers:

```bash
# Run unit tests only
pytest -m unit

# Run integration tests only
pytest -m integration

# Run voice component tests
pytest -m voice

# Run core component tests
pytest -m core

# Run tests that don't require external dependencies
pytest -m "not dependency"

# Run tests that don't require GPU
pytest -m "not requires_gpu"
```

## Writing Tests

When writing tests for Sabrina AI, follow these guidelines:

### Test File Template

Start by copying the test template:

```bash
cp tests/test_utils/test_template.py tests/unit/test_your_component.py
```

### Using Path Utilities

Always use the path utilities to ensure consistent path handling:

```python
from tests.test_utils.paths import (
    get_project_root,
    ensure_project_root_in_sys_path,
)

# Ensure project root is in path
ensure_project_root_in_sys_path()

# Now you can import project modules
from module.to.test import ClassToTest
```

### Using Test Fixtures

Pytest fixtures are available in `conftest.py`:

```python
def test_something(temp_dir, mock_event_bus, mock_state_machine):
    # temp_dir is a temporary directory for the test
    # mock_event_bus is a mock event bus
    # mock_state_machine is a mock state machine

    # Create a file in the temporary directory
    file_path = temp_dir / "test_file.txt"
    with open(file_path, "w") as f:
        f.write("Test content")
```

### Mocking Components

Use the mock components provided in `test_utils/helpers.py`:

```python
from tests.test_utils.helpers import (
    MockVoiceService,
    MockVisionService,
    MockAutomationService,
)

def test_integration(mock_voice_service, mock_vision_service):
    # Use mock components
    result = mock_voice_service.speak("Hello, world!")
    self.assertTrue(result)
    self.assertEqual(mock_voice_service.last_text, "Hello, world!")
```

### Using the Base Test Case

Use the `SabrinaTestCase` base class for common utilities:

```python
from tests.test_utils.helpers import SabrinaTestCase

class TestYourComponent(SabrinaTestCase):
    def test_something(self):
        # Create a temporary file
        config_path = self.create_temp_config({
            "section": {"key": "value"}
        })

        # Get a test resource
        resource_path = self.get_test_resource("resource.txt")
```

## Test Utilities

### Path Utilities (`paths.py`)

The `paths.py` module provides functions for consistent path handling:

- `get_project_root()`: Get the absolute path to the project root
- `get_test_dir()`: Get the absolute path to the tests directory
- `get_component_path(component_name)`: Get the path to a component
- `get_config_path([config_name])`: Get the path to a config file
- `ensure_project_root_in_sys_path()`: Ensure project root is in `sys.path`

### Helper Functions (`helpers.py`)

The `helpers.py` module provides functions and classes for testing:

- `create_test_config(config_data, format)`: Create a test configuration file
- `wait_for_condition(condition_func, timeout)`: Wait for a condition
- `MockComponent`: Base class for mock components
- `MockVoiceService`: Mock voice service
- `MockVisionService`: Mock vision service
- `MockAutomationService`: Mock automation service
- `create_mock_event_bus()`: Create a mock event bus
- `create_mock_state_machine()`: Create a mock state machine
- `setup_component_test_environment()`: Set up a test environment
- `SabrinaTestCase`: Base test case class

## Test Configuration

The test framework uses pytest for running tests. Configuration is in `pytest.ini`:

- Custom markers for categorizing tests
- Default settings for test discovery
- Configuration for test output formatting
- Path configuration for tests

## Best Practices

For detailed guidance on path handling, testing strategies, and best practices, see:

- [Path Handling Best Practices](../docs/Path%20Handling%20Best%20Practices.md)
- [Testing Guidelines](../docs/Testing%20Guidelines.md)

## Troubleshooting

### Import Errors

If you're seeing import errors:

1. Make sure you're using the path utilities:
   ```python
   from tests.test_utils.paths import ensure_project_root_in_sys_path
   ensure_project_root_in_sys_path()
   ```

2. Check that the module you're importing exists and is spelled correctly.

3. Try running the test with pytest: `pytest path/to/test_file.py`

### Path-Related Errors

If you're seeing path-related errors:

1. Use `pathlib.Path` for all path operations.

2. Don't use hardcoded separators (`/` or `\\`).

3. Use the path utilities for accessing project files.

### Test Failures on Different Platforms

If tests fail on different platforms:

1. Use the `SabrinaTestCase` base class.

2. Use the path utilities for all file operations.

3. Be careful with case sensitivity (Windows is case-insensitive).

4. Use `tempfile.TemporaryDirectory()` for temporary files.

## Contributing

When adding new tests:

1. Use the test template as a starting point.

2. Follow the standard structure for imports and path handling.

3. Add appropriate pytest markers for test categorization.

4. Include unit tests for new functionality.

5. Include integration tests for component interactions.

6. Run the path handling regression tests to ensure your changes don't break path handling.
