#!/usr/bin/env python3
"""
Path Management Utilities for Sabrina AI Tests
=============================================
Standardizes path handling across test files to ensure consistent behavior
across different environments and test types.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union, List, Dict


# Get absolute path to project root
def get_project_root() -> Path:
    """
    Get the absolute path to the project root directory.
    This function works regardless of where it's imported from.

    Returns:
        Path: Absolute path to the project root
    """
    # Start from this file's directory
    current_file = Path(os.path.abspath(__file__))

    # Go up one level from test_utils to tests, then one more to project root
    project_root = current_file.parent.parent.parent

    # Verify this is actually the project root by checking for key files/directories
    key_indicators = ["core", "utilities", "services", "README.md"]

    # Check at least some of these exist
    found_indicators = [
        indicator for indicator in key_indicators if (project_root / indicator).exists()
    ]

    if not found_indicators:
        raise RuntimeError(
            f"Failed to locate project root from {current_file}. "
            f"None of the expected directories/files {key_indicators} were found."
        )

    return project_root


# Get path to the test directory
def get_test_dir() -> Path:
    """
    Get the absolute path to the test directory.

    Returns:
        Path: Absolute path to the test directory
    """
    return get_project_root() / "tests"


# Get paths to various test subdirectories
def get_test_unit_dir() -> Path:
    """Get path to unit test directory"""
    return get_test_dir() / "unit"


def get_test_integration_dir() -> Path:
    """Get path to integration test directory"""
    return get_test_dir() / "integration"


def get_test_e2e_dir() -> Path:
    """Get path to end-to-end test directory"""
    return get_test_dir() / "e2e"


def get_test_utils_dir() -> Path:
    """Get path to test utilities directory"""
    return get_test_dir() / "test_utils"


def get_test_data_dir() -> Path:
    """
    Get path to test data directory. Creates it if it doesn't exist.

    Returns:
        Path: Absolute path to test data directory
    """
    data_dir = get_test_dir() / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_test_temp_dir() -> Path:
    """
    Get path to temporary test directory. Creates it if it doesn't exist.
    This directory is meant for temporary files created during tests.

    Returns:
        Path: Absolute path to temporary test directory
    """
    temp_dir = get_test_dir() / "temp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir


def get_component_path(component_name: str) -> Path:
    """
    Get the absolute path to a component directory.

    Args:
        component_name: Name of the component (e.g., 'core', 'voice', 'vision')

    Returns:
        Path: Absolute path to the component directory
    """
    # Handle special cases
    if component_name in ["core", "utilities"]:
        return get_project_root() / component_name

    # Regular services component
    return get_project_root() / "services" / component_name


def get_config_path(config_name: Optional[str] = None) -> Path:
    """
    Get the absolute path to a configuration file or directory.

    Args:
        config_name: Optional filename within the config directory

    Returns:
        Path: Absolute path to the config file or directory
    """
    config_dir = get_project_root() / "config"

    if config_name:
        return config_dir / config_name

    return config_dir


def get_test_config_path(config_name: str) -> Path:
    """
    Get the absolute path to a test configuration file.

    Args:
        config_name: Configuration filename for testing

    Returns:
        Path: Absolute path to the test config file
    """
    return get_test_data_dir() / "configs" / config_name


def ensure_path_in_sys_path(path: Union[str, Path]):
    """
    Ensure a path is in sys.path for imports.

    Args:
        path: Path to add to sys.path if not already present
    """
    path_str = str(path) if isinstance(path, Path) else path
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def ensure_project_root_in_sys_path():
    """
    Ensure the project root is in sys.path for imports.
    This should be called at the beginning of each test file.
    """
    ensure_path_in_sys_path(get_project_root())


def create_test_path_context():
    """
    Create a context with all paths needed for testing.

    Returns:
        Dict: Dictionary containing all relevant test paths
    """
    return {
        "project_root": get_project_root(),
        "test_dir": get_test_dir(),
        "unit_dir": get_test_unit_dir(),
        "integration_dir": get_test_integration_dir(),
        "e2e_dir": get_test_e2e_dir(),
        "utils_dir": get_test_utils_dir(),
        "data_dir": get_test_data_dir(),
        "temp_dir": get_test_temp_dir(),
        "config_dir": get_config_path(),
    }


def create_test_file(dir_path: Path, filename: str, content: str = "") -> Path:
    """
    Create a test file with optional content.

    Args:
        dir_path: Directory to create the file in
        filename: Name of the file
        content: Optional content to write to the file

    Returns:
        Path: Path to the created file
    """
    # Ensure directory exists
    dir_path.mkdir(exist_ok=True, parents=True)

    # Create file path
    file_path = dir_path / filename

    # Write content
    with open(file_path, "w") as f:
        f.write(content)

    return file_path


def get_test_resource_path(
    resource_name: str, component_name: Optional[str] = None
) -> Path:
    """
    Get path to a test resource file.

    Args:
        resource_name: Name of the resource file
        component_name: Optional component name to namespace the resources

    Returns:
        Path: Path to the test resource
    """
    resources_dir = get_test_data_dir() / "resources"

    if component_name:
        resources_dir = resources_dir / component_name

    resources_dir.mkdir(exist_ok=True, parents=True)
    return resources_dir / resource_name


# Standard path setup for all test files
PROJECT_ROOT = get_project_root()
TEST_DIR = get_test_dir()
ensure_project_root_in_sys_path()


if __name__ == "__main__":
    # Print out paths when run directly for debugging
    for name, path in create_test_path_context().items():
        print(f"{name}: {path}")
        print(f"  exists: {path.exists()}")
