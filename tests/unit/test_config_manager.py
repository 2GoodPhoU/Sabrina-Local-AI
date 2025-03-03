#!/usr/bin/env python3
"""
Unit tests for Sabrina AI Configuration Manager
Tests the functionality for loading, saving, and manipulating configuration settings
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
from unittest.mock import patch

# Import the component to test
from utilities.config_manager import ConfigManager

# Ensure the project root is in the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../.."))
sys.path.insert(0, project_root)


class TestConfigManager(unittest.TestCase):
    """Test case for ConfigManager class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for test configuration files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.yaml_config_path = os.path.join(self.temp_dir.name, "config.yaml")
        self.json_config_path = os.path.join(self.temp_dir.name, "config.json")

        # Create test configuration data
        self.test_config = {
            "core": {"debug_mode": True, "log_level": "DEBUG"},
            "voice": {
                "api_url": "http://test.example.com",
                "volume": 0.5,
                "speed": 1.2,
            },
            "test_section": {
                "test_key": "test_value",
                "nested": {"key1": "value1", "key2": "value2"},
            },
        }

        # Create YAML config file
        with open(self.yaml_config_path, "w") as f:
            yaml.dump(self.test_config, f)

        # Create JSON config file
        with open(self.json_config_path, "w") as f:
            json.dump(self.test_config, f, indent=2)

    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        self.temp_dir.cleanup()

    def test_initialization_without_file(self):
        """Test initialization without a configuration file"""
        # Initialize with no config path
        config_manager = ConfigManager()

        # Should have default config
        self.assertIn("core", config_manager.config)
        self.assertIn("voice", config_manager.config)
        self.assertIn("hearing", config_manager.config)

        # Default values should be present
        self.assertFalse(config_manager.config["core"]["debug_mode"])
        self.assertEqual(config_manager.config["core"]["log_level"], "INFO")
        self.assertEqual(
            config_manager.config["voice"]["api_url"], "http://localhost:8100"
        )

    def test_default_config_structure(self):
        """Test the default configuration structure"""
        # Initialize without a config path to get defaults
        config_manager = ConfigManager()

        # Check all required sections exist
        for section in [
            "core",
            "voice",
            "vision",
            "hearing",
            "automation",
            "memory",
            "smart_home",
            "presence",
        ]:
            self.assertIn(section, config_manager.config)

        # Check specific default values across sections
        self.assertEqual(config_manager.config["core"]["log_level"], "INFO")
        self.assertEqual(config_manager.config["voice"]["volume"], 0.8)
        self.assertEqual(config_manager.config["hearing"]["wake_word"], "hey sabrina")
        self.assertEqual(
            config_manager.config["automation"]["mouse_move_duration"], 0.2
        )
        self.assertEqual(config_manager.config["vision"]["capture_method"], "auto")

    def test_load_yaml_config(self):
        """Test loading configuration from YAML file"""
        # Initialize with YAML config path
        config_manager = ConfigManager(self.yaml_config_path)

        # Test loaded values
        self.assertTrue(config_manager.config["core"]["debug_mode"])
        self.assertEqual(config_manager.config["core"]["log_level"], "DEBUG")
        self.assertEqual(
            config_manager.config["voice"]["api_url"], "http://test.example.com"
        )
        self.assertEqual(config_manager.config["voice"]["volume"], 0.5)
        self.assertEqual(config_manager.config["voice"]["speed"], 1.2)
        self.assertEqual(
            config_manager.config["test_section"]["test_key"], "test_value"
        )

        # Test nested values
        self.assertEqual(
            config_manager.config["test_section"]["nested"]["key1"], "value1"
        )
        self.assertEqual(
            config_manager.config["test_section"]["nested"]["key2"], "value2"
        )

    def test_load_json_config(self):
        """Test loading configuration from JSON file"""
        # Initialize with JSON config path
        config_manager = ConfigManager(self.json_config_path)

        # Test loaded values
        self.assertTrue(config_manager.config["core"]["debug_mode"])
        self.assertEqual(config_manager.config["core"]["log_level"], "DEBUG")
        self.assertEqual(
            config_manager.config["voice"]["api_url"], "http://test.example.com"
        )
        self.assertEqual(config_manager.config["voice"]["volume"], 0.5)
        self.assertEqual(config_manager.config["voice"]["speed"], 1.2)
        self.assertEqual(
            config_manager.config["test_section"]["test_key"], "test_value"
        )

    def test_load_nonexistent_file(self):
        """Test loading from a nonexistent file"""
        # Create config manager with nonexistent file
        nonexistent_path = os.path.join(self.temp_dir.name, "nonexistent.yaml")
        config_manager = ConfigManager(nonexistent_path)

        # Should have default config
        self.assertFalse(config_manager.config["core"]["debug_mode"])
        self.assertEqual(config_manager.config["core"]["log_level"], "INFO")

        # File should be created with defaults
        self.assertTrue(os.path.exists(nonexistent_path))

    def test_load_invalid_file_format(self):
        """Test loading from a file with invalid format"""
        # Create a file with invalid format
        invalid_path = os.path.join(self.temp_dir.name, "invalid.txt")
        with open(invalid_path, "w") as f:
            f.write("This is not a valid config file.")

        # Initialize with invalid file
        config_manager = ConfigManager(invalid_path)

        # Should have default config
        self.assertFalse(config_manager.config["core"]["debug_mode"])
        self.assertEqual(config_manager.config["core"]["log_level"], "INFO")

    def test_get_config(self):
        """Test getting configuration values"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Test get_config for existing values
        self.assertTrue(config_manager.get_config("core", "debug_mode"))
        self.assertEqual(config_manager.get_config("core", "log_level"), "DEBUG")
        self.assertEqual(
            config_manager.get_config("voice", "api_url"), "http://test.example.com"
        )

        # Test get_config with default value for non-existent keys
        self.assertEqual(
            config_manager.get_config("nonexistent", "key", "default"), "default"
        )
        self.assertEqual(config_manager.get_config("core", "nonexistent", 42), 42)

        # Test get_config for entire section
        core_section = config_manager.get_config("core")
        self.assertIsInstance(core_section, dict)
        self.assertIn("debug_mode", core_section)
        self.assertIn("log_level", core_section)

        # Test get_config for non-existent section
        self.assertIsNone(config_manager.get_config("nonexistent_section"))
        self.assertEqual(
            config_manager.get_config("nonexistent_section", default={}), {}
        )

    def test_set_config(self):
        """Test setting configuration values"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Test setting simple values
        result = config_manager.set_config("core", "log_level", "INFO")
        self.assertTrue(result)
        self.assertEqual(config_manager.get_config("core", "log_level"), "INFO")

        # Test setting new keys
        result = config_manager.set_config("core", "new_key", "new_value")
        self.assertTrue(result)
        self.assertEqual(config_manager.get_config("core", "new_key"), "new_value")

        # Test setting new sections
        result = config_manager.set_config("new_section", "key", "value")
        self.assertTrue(result)
        self.assertEqual(config_manager.get_config("new_section", "key"), "value")

        # Test the modified flag
        self.assertTrue(config_manager.modified_since_load)

        # Test setting with complex values
        complex_value = {"nested1": {"nested2": ["array", "values"]}}
        result = config_manager.set_config("complex", "structure", complex_value)
        self.assertTrue(result)
        self.assertEqual(
            config_manager.get_config("complex", "structure"), complex_value
        )

        # Test setting identical value (should not mark as modified)
        config_manager.modified_since_load = False
        result = config_manager.set_config("core", "log_level", "INFO")
        self.assertTrue(result)
        self.assertFalse(config_manager.modified_since_load)

    def test_save_config(self):
        """Test saving configuration to file"""
        # Create new config manager with a new file path
        save_path = os.path.join(self.temp_dir.name, "saved_config.yaml")
        config_manager = ConfigManager()

        # Set some values
        config_manager.set_config("test", "key1", "value1")
        config_manager.set_config("test", "key2", 123)

        # Save to file
        result = config_manager.save_config(save_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(save_path))

        # Load the saved file and verify
        new_config = ConfigManager(save_path)
        self.assertEqual(new_config.get_config("test", "key1"), "value1")
        self.assertEqual(new_config.get_config("test", "key2"), 123)

        # Test JSON saving
        json_save_path = os.path.join(self.temp_dir.name, "saved_config.json")
        result = config_manager.save_config(json_save_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(json_save_path))

        # Verify JSON content
        with open(json_save_path, "r") as f:
            json_data = json.load(f)
        self.assertEqual(json_data["test"]["key1"], "value1")
        self.assertEqual(json_data["test"]["key2"], 123)

        # Check if modified flag is reset
        self.assertFalse(config_manager.modified_since_load)

        # Test saving to a directory that doesn't exist
        deep_path = os.path.join(
            self.temp_dir.name, "nonexistent", "dir", "config.yaml"
        )
        result = config_manager.save_config(deep_path)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(deep_path))

    def test_save_config_error_handling(self):
        """Test error handling when saving configuration"""
        config_manager = ConfigManager()

        # Test saving to invalid path
        with patch("builtins.open", side_effect=IOError("Simulated IO error")):
            result = config_manager.save_config("invalid_path.yaml")
            self.assertFalse(result)

        # Test saving with invalid format
        invalid_format_path = os.path.join(self.temp_dir.name, "invalid.format")
        result = config_manager.save_config(invalid_format_path)
        self.assertFalse(result)

    def test_reset_to_defaults(self):
        """Test resetting configuration to defaults"""
        # Initialize with config that modifies defaults
        config_manager = ConfigManager(self.yaml_config_path)

        # Verify test values are loaded
        self.assertTrue(config_manager.get_config("core", "debug_mode"))
        self.assertEqual(config_manager.get_config("core", "log_level"), "DEBUG")

        # Reset to defaults
        result = config_manager.reset_to_defaults()
        self.assertTrue(result)

        # Verify defaults are restored
        self.assertFalse(config_manager.get_config("core", "debug_mode"))
        self.assertEqual(config_manager.get_config("core", "log_level"), "INFO")

        # Test section-specific reset
        config_manager = ConfigManager(self.yaml_config_path)
        result = config_manager.reset_to_defaults("core")
        self.assertTrue(result)

        # Verify only core section was reset
        self.assertFalse(config_manager.get_config("core", "debug_mode"))
        self.assertEqual(config_manager.get_config("core", "log_level"), "INFO")
        self.assertEqual(
            config_manager.get_config("voice", "api_url"), "http://test.example.com"
        )

        # Test resetting nonexistent section
        result = config_manager.reset_to_defaults("nonexistent_section")
        self.assertFalse(result)

    def test_merge_configs(self):
        """Test merging of configuration dictionaries"""
        config_manager = ConfigManager()

        # Test merging with private method
        base_config = {
            "section1": {"key1": "base_value1", "key2": "base_value2"},
            "section2": {"nested": {"key1": "nested_base"}},
        }

        override_config = {
            "section1": {"key1": "override_value1"},
            "section2": {"nested": {"key1": "nested_override", "key2": "new_nested"}},
            "section3": {"new_key": "new_value"},
        }

        merged = config_manager._merge_configs(base_config, override_config)

        # Check merging results
        self.assertEqual(merged["section1"]["key1"], "override_value1")
        self.assertEqual(merged["section1"]["key2"], "base_value2")
        self.assertEqual(merged["section2"]["nested"]["key1"], "nested_override")
        self.assertEqual(merged["section2"]["nested"]["key2"], "new_nested")
        self.assertEqual(merged["section3"]["new_key"], "new_value")

    def test_apply_environment_overrides(self):
        """Test applying environment variable overrides"""
        # Set test environment variables
        os.environ["SABRINA_CORE_DEBUG_MODE"] = "true"
        os.environ["SABRINA_VOICE_VOLUME"] = "0.8"
        os.environ["SABRINA_TEST_NEW_VALUE"] = "123"

        try:
            # Initialize config manager
            config_manager = ConfigManager()

            # Apply environment overrides
            override_count = config_manager.apply_environment_overrides()

            # Check that overrides were applied
            self.assertGreaterEqual(override_count, 3)
            self.assertTrue(config_manager.get_config("core", "debug_mode"))
            self.assertEqual(config_manager.get_config("voice", "volume"), 0.8)
            self.assertEqual(config_manager.get_config("test", "new_value"), 123)

            # Test different value types
            os.environ["SABRINA_TYPES_STRING"] = "string_value"
            os.environ["SABRINA_TYPES_INT"] = "42"
            os.environ["SABRINA_TYPES_FLOAT"] = "3.14"
            os.environ["SABRINA_TYPES_BOOL_TRUE"] = "true"
            os.environ["SABRINA_TYPES_BOOL_FALSE"] = "false"

            # Apply new overrides
            config_manager.apply_environment_overrides()

            # Check type conversion
            self.assertEqual(
                config_manager.get_config("types", "string"), "string_value"
            )
            self.assertEqual(config_manager.get_config("types", "int"), 42)
            self.assertEqual(config_manager.get_config("types", "float"), 3.14)
            self.assertEqual(config_manager.get_config("types", "bool_true"), True)
            self.assertEqual(config_manager.get_config("types", "bool_false"), False)

        finally:
            # Clean up environment variables
            for var in [
                "SABRINA_CORE_DEBUG_MODE",
                "SABRINA_VOICE_VOLUME",
                "SABRINA_TEST_NEW_VALUE",
                "SABRINA_TYPES_STRING",
                "SABRINA_TYPES_INT",
                "SABRINA_TYPES_FLOAT",
                "SABRINA_TYPES_BOOL_TRUE",
                "SABRINA_TYPES_BOOL_FALSE",
            ]:
                if var in os.environ:
                    del os.environ[var]

    def test_check_for_updates(self):
        """Test checking for configuration file updates"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Initially, no updates expected
        self.assertFalse(config_manager.check_for_updates())

        # Modify the file to simulate an update
        with open(self.yaml_config_path, "w") as f:
            modified_config = self.test_config.copy()
            modified_config["core"]["log_level"] = "WARNING"
            yaml.dump(modified_config, f)

        # Now should detect an update
        self.assertTrue(config_manager.check_for_updates())

        # Test reload
        result = config_manager.reload_if_changed()
        self.assertTrue(result)
        self.assertEqual(config_manager.get_config("core", "log_level"), "WARNING")

        # Test with nonexistent file
        config_manager.config_path = "nonexistent.yaml"
        self.assertFalse(config_manager.check_for_updates())
        self.assertFalse(config_manager.reload_if_changed())

    def test_export_config(self):
        """Test exporting configuration in different formats"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Test dict export
        dict_export = config_manager.export_config("dict")
        self.assertIsInstance(dict_export, dict)
        self.assertEqual(dict_export["core"]["log_level"], "DEBUG")

        # Test JSON export
        json_export = config_manager.export_config("json")
        self.assertIsInstance(json_export, str)
        json_dict = json.loads(json_export)
        self.assertEqual(json_dict["core"]["log_level"], "DEBUG")

        # Test YAML export
        yaml_export = config_manager.export_config("yaml")
        self.assertIsInstance(yaml_export, str)
        yaml_dict = yaml.safe_load(yaml_export)
        self.assertEqual(yaml_dict["core"]["log_level"], "DEBUG")

        # Test invalid format
        invalid_export = config_manager.export_config("invalid_format")
        self.assertIsInstance(invalid_export, dict)  # Should return dict by default

    def test_has_section(self):
        """Test checking if a section exists"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Test existing and non-existing sections
        self.assertTrue(config_manager.has_section("core"))
        self.assertTrue(config_manager.has_section("voice"))
        self.assertTrue(config_manager.has_section("test_section"))
        self.assertFalse(config_manager.has_section("nonexistent"))

    def test_has_changed(self):
        """Test checking if configuration has changed"""
        config_manager = ConfigManager(self.yaml_config_path)

        # Initially not changed
        self.assertFalse(config_manager.has_changed())

        # Make a change
        config_manager.set_config("core", "new_setting", "new_value")
        self.assertTrue(config_manager.has_changed())

        # Save changes
        config_manager.save_config()
        self.assertFalse(config_manager.has_changed())

    def test_list_sections(self):
        """Test listing available sections"""
        # Initialize with config
        config_manager = ConfigManager(self.yaml_config_path)

        # Get sections
        sections = config_manager.list_sections()

        # Check results
        self.assertIsInstance(sections, list)
        self.assertIn("core", sections)
        self.assertIn("voice", sections)
        self.assertIn("test_section", sections)

        # Check added default sections
        for section in ["hearing", "vision", "automation"]:
            self.assertIn(section, sections)


if __name__ == "__main__":
    unittest.main()
