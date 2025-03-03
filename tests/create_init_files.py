#!/usr/bin/env python3
"""
Script to create missing __init__.py files in test directories
This script ensures all test directories are properly importable Python packages.
"""

import os
import sys
from pathlib import Path


def create_init_files():
    """Create __init__.py files in all test directories"""
    # Get project root and test directory
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    project_root = script_dir.parent  # Go up one level to get project root
    tests_dir = project_root / "tests"

    # Check if tests directory exists
    if not tests_dir.exists():
        print(f"Tests directory not found: {tests_dir}")
        return False

    # Create __init__.py in tests directory
    tests_init = tests_dir / "__init__.py"
    if not tests_init.exists():
        with open(tests_init, "w") as f:
            f.write(
                """\"\"\"
Sabrina AI Test Suite
==================
This package contains tests for the Sabrina AI project.

Test structure:
- unit/: Unit tests for individual components
- integration/: Integration tests between components
- e2e/: End-to-end tests for the full system
- test_utils/: Utilities for testing
\"\"\"

# Import path utilities to ensure correct path configuration
from tests.test_utils.paths import ensure_project_root_in_sys_path

# Ensure project root
ensure_project_root_in_sys_path()
"""
            )
        print(f"Created: {tests_init}")

    # List of test subdirectories
    test_subdirs = ["unit", "integration", "e2e", "test_utils"]

    # Create __init__.py in each subdirectory
    for subdir in test_subdirs:
        subdir_path = tests_dir / subdir

        # Create directory if it doesn't exist
        if not subdir_path.exists():
            subdir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {subdir_path}")

        init_file = subdir_path / "__init__.py"
        if not init_file.exists():
            with open(init_file, "w") as f:
                f.write(f"# {subdir.capitalize()} tests package\n")
            print(f"Created: {init_file}")

    print("\nAll __init__.py files have been created successfully!")
    return True


if __name__ == "__main__":
    create_init_files()
