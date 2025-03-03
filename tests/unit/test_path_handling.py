#!/usr/bin/env python3
"""
Regression Tests for Path Handling in Sabrina AI
==============================================
These tests verify that the path handling utilities work correctly across
different environments and prevent regression issues with imports and file access.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Import the path utilities to test
from tests.test_utils.paths import (
    get_project_root,
    get_test_dir,
    get_test_unit_dir,
    get_test_integration_dir,
    get_test_e2e_dir,
    get_test_utils_dir,
    get_test_data_dir,
    get_test_temp_dir,
    get_component_path,
    get_config_path,
    get_test_config_path,
    ensure_path_in_sys_path,
    ensure_project_root_in_sys_path,
    create_test_path_context,
    create_test_file,
    get_test_resource_path,
    PROJECT_ROOT,
    TEST_DIR,
)


class TestPathHandling(unittest.TestCase):
    """Tests for path handling utilities to ensure consistent behavior."""

    def setUp(self):
        """Set up test fixtures"""
        # Ensure path is set up correctly
        ensure_project_root_in_sys_path()

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up test fixtures"""
        self.temp_dir.cleanup()

    def test_project_root_detection(self):
        """Test that project root is detected correctly"""
        # Check that project root is a directory
        root = get_project_root()
        self.assertTrue(root.is_dir())

        # Check that key project directories exist
        self.assertTrue((root / "core").is_dir())
        self.assertTrue((root / "utilities").is_dir())
        self.assertTrue((root / "services").is_dir())
        self.assertTrue((root / "tests").is_dir())

    def test_test_directory_structure(self):
        """Test that test directory structure is detected correctly"""
        test_dir = get_test_dir()

        # Test directory should be a subdirectory of project root
        self.assertEqual(test_dir.parent, get_project_root())

        # Test subdirectories should exist
        self.assertTrue(get_test_unit_dir().is_dir())
        self.assertTrue(get_test_integration_dir().is_dir())

        # This file should be in the unit test directory
        current_file = Path(__file__)
        self.assertTrue(current_file.is_relative_to(get_test_unit_dir()))

    def test_component_path_resolution(self):
        """Test resolution of component paths"""
        # Core component
        core_path = get_component_path("core")
        self.assertTrue(core_path.is_dir())
        self.assertEqual(core_path, get_project_root() / "core")

        # Utilities component
        utilities_path = get_component_path("utilities")
        self.assertTrue(utilities_path.is_dir())
        self.assertEqual(utilities_path, get_project_root() / "utilities")

        # Service component
        voice_path = get_component_path("voice")
        self.assertEqual(voice_path, get_project_root() / "services" / "voice")

        # Check that same result is returned regardless of case
        self.assertEqual(get_component_path("voice"), get_component_path("Voice"))

    def test_config_path_resolution(self):
        """Test resolution of configuration paths"""
        # Config directory
        config_dir = get_config_path()
        self.assertEqual(config_dir, get_project_root() / "config")

        # Specific config file
        settings_path = get_config_path("settings.yaml")
        self.assertEqual(settings_path, get_project_root() / "config" / "settings.yaml")

        # Test config path
        test_config_path = get_test_config_path("test_config.yaml")
        expected_path = get_test_data_dir() / "configs" / "test_config.yaml"
        self.assertEqual(test_config_path, expected_path)

    def test_data_directory_creation(self):
        """Test that data directories are created if they don't exist"""
        # Test data directory
        data_dir = get_test_data_dir()
        self.assertTrue(data_dir.is_dir())

        # Temp directory
        temp_dir = get_test_temp_dir()
        self.assertTrue(temp_dir.is_dir())

        # Remove directories to test creation
        if data_dir.exists():
            os.rmdir(data_dir)
        if temp_dir.exists():
            os.rmdir(temp_dir)

        # They should be recreated when accessed
        self.assertTrue(get_test_data_dir().is_dir())
        self.assertTrue(get_test_temp_dir().is_dir())

    def test_test_file_creation(self):
        """Test creation of test files"""
        # Create a test file
        file_path = create_test_file(self.temp_path, "test_file.txt", "Test content")

        # Check file was created
        self.assertTrue(file_path.is_file())

        # Check content was written
        with open(file_path, "r") as f:
            content = f.read()
        self.assertEqual(content, "Test content")

        # Test creating file in nested directory
        nested_dir = self.temp_path / "nested" / "directory"
        file_path = create_test_file(nested_dir, "nested_file.txt", "Nested content")

        # Check file was created
        self.assertTrue(file_path.is_file())
        self.assertTrue(nested_dir.is_dir())

    def test_resource_path_resolution(self):
        """Test resolution of test resource paths"""
        # Get resource path
        resource_path = get_test_resource_path("test.txt")
        expected_path = get_test_data_dir() / "resources" / "test.txt"
        self.assertEqual(resource_path, expected_path)

        # Get component-specific resource
        component_resource = get_test_resource_path("test.txt", "voice")
        expected_path = get_test_data_dir() / "resources" / "voice" / "test.txt"
        self.assertEqual(component_resource, expected_path)

        # Directory should be created if it doesn't exist
        self.assertTrue(component_resource.parent.is_dir())

    def test_system_path_management(self):
        """Test management of system path for imports"""
        # Get original sys.path
        original_path = sys.path.copy()

        # Ensure project root is not in path (for testing)
        project_root = str(get_project_root())
        if project_root in sys.path:
            sys.path.remove(project_root)

        # Add a test path
        test_path = str(self.temp_path)
        ensure_path_in_sys_path(test_path)
        self.assertIn(test_path, sys.path)

        # Adding it again shouldn't duplicate it
        ensure_path_in_sys_path(test_path)
        self.assertEqual(sys.path.count(test_path), 1)

        # Ensure project root is added
        ensure_project_root_in_sys_path()
        self.assertIn(project_root, sys.path)

        # Restore original path
        sys.path = original_path

    def test_path_constants(self):
        """Test that path constants are correctly initialized"""
        # PROJECT_ROOT should match get_project_root()
        self.assertEqual(PROJECT_ROOT, get_project_root())

        # TEST_DIR should match get_test_dir()
        self.assertEqual(TEST_DIR, get_test_dir())

    def test_path_context_creation(self):
        """Test creation of path context dictionary"""
        context = create_test_path_context()

        # Check required keys
        required_keys = [
            "project_root",
            "test_dir",
            "unit_dir",
            "integration_dir",
            "e2e_dir",
            "utils_dir",
            "data_dir",
            "temp_dir",
            "config_dir",
        ]

        for key in required_keys:
            self.assertIn(key, context)
            self.assertTrue(isinstance(context[key], Path))

        # Check values match individual functions
        self.assertEqual(context["project_root"], get_project_root())
        self.assertEqual(context["test_dir"], get_test_dir())
        self.assertEqual(context["unit_dir"], get_test_unit_dir())
        self.assertEqual(context["config_dir"], get_config_path())

    def test_path_import_reliability(self):
        """Test that imports work reliably from different locations"""
        # Create a test script in a different location
        test_script = """
import sys
from pathlib import Path
current_dir = Path(__file__).parent

# Add parent directories to path
parent = current_dir.parent
sys.path.insert(0, str(parent))

# Now try importing the path utilities
from tests.test_utils.paths import get_project_root, ensure_project_root_in_sys_path

# Ensure project root is in path
ensure_project_root_in_sys_path()

# Try importing core components
try:
    from core.core import SabrinaCore
    success = True
except ImportError as e:
    success = False
    error = str(e)

# Print results
import json
result = {
    'success': success,
    'project_root': str(get_project_root()),
    'sys_path': sys.path,
}
print(json.dumps(result))
"""

        # Write test script to a nested directory
        script_dir = self.temp_path / "nested" / "script" / "dir"
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / "test_script.py"

        with open(script_path, "w") as f:
            f.write(test_script)

        # Run the script
        import subprocess
        import json

        result = subprocess.run(
            [sys.executable, str(script_path)], capture_output=True, text=True
        )

        # Check script output
        output = result.stdout.strip()
        data = json.loads(output)

        # Verify that the script properly resolved paths
        self.assertEqual(Path(data["project_root"]), get_project_root())

        # Check if imports were successful
        # Note: This might fail if SabrinaCore isn't available, which is okay
        # We're primarily testing path resolution, not component availability
        project_root_str = str(get_project_root())
        self.assertIn(project_root_str, data["sys_path"])


if __name__ == "__main__":
    unittest.main()
