"""
Unified Configuration Manager for Sabrina AI
===========================================
This module centralizes configuration management for all Sabrina AI components,
supporting YAML, JSON, and environment variable configurations with validation,
defaults, and hot-reloading capabilities.
"""

import os
import yaml
import json
import logging
import copy
from typing import Any, Dict, List, Union

# Setup logger
logger = logging.getLogger("config_manager")


class ConfigManager:
    """
    Unified configuration management for Sabrina AI

    Features:
    - Loads from YAML, JSON, or ENV variables
    - Supports configuration validation
    - Provides default values
    - Allows hot-reloading
    - Maintains configuration history
    """

    # Default configuration structure - serves as both default values and schema
    DEFAULT_CONFIG = {
        "core": {"debug_mode": False, "log_level": "INFO"},
        "voice": {
            "api_url": "http://localhost:8100",
            "volume": 0.8,
            "speed": 1.0,
            "pitch": 1.0,
            "emotion": "normal",
        },
        "vision": {
            "capture_method": "auto",  # auto, mss, pyautogui
            "use_ocr": True,
            "use_object_detection": True,
            "max_images": 5,
        },
        "hearing": {
            "wake_word": "hey sabrina",
            "silence_threshold": 0.03,
            "model_path": "models/vosk-model",
            "use_hotkey": True,
            "hotkey": "ctrl+shift+s",
        },
        "automation": {
            "mouse_move_duration": 0.2,
            "typing_interval": 0.1,
            "failsafe": True,
        },
        "memory": {
            "max_entries": 20,
            "use_vector_db": False,
            "vector_db_path": "data/vectordb",
        },
        "smart_home": {
            "enable": False,
            "home_assistant_url": "http://homeassistant.local:8123",
            "use_google_home": False,
        },
        "presence": {
            "enable": False,
            "theme": "default",
            "transparency": 0.85,
            "click_through": False,
        },
    }

    def __init__(self, config_path: str = None):
        """
        Initialize the configuration manager

        Args:
            config_path: Path to the main configuration file (YAML or JSON)
        """
        # Setup internal state
        self.config_path = config_path
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        self.config_history = []
        self.last_modified_time = 0
        self.modified_since_load = False

        # Load configuration if path provided
        if config_path:
            self.load_config(config_path)

        # Apply environment variables
        self.apply_environment_overrides()

        logger.info(
            f"Configuration manager initialized with {len(self.config)} sections"
        )

    def load_config(self, config_path: str = None) -> bool:
        """
        Load configuration from a file

        Args:
            config_path: Path to the configuration file (if None, uses the path from initialization)

        Returns:
            bool: True if successful, False otherwise
        """
        if config_path:
            self.config_path = config_path

        if not self.config_path:
            logger.warning("No configuration path specified")
            return False

        if not os.path.exists(self.config_path):
            logger.warning(f"Configuration file not found: {self.config_path}")
            self._save_default_config()
            return False

        try:
            # Backup current config before loading
            self.config_history.append(copy.deepcopy(self.config))

            # Determine file type from extension
            if self.config_path.endswith(".yaml") or self.config_path.endswith(".yml"):
                with open(self.config_path, "r", encoding="utf-8") as file:
                    loaded_config = yaml.safe_load(file) or {}
            elif self.config_path.endswith(".json"):
                with open(self.config_path, "r", encoding="utf-8") as file:
                    loaded_config = json.load(file)
            else:
                logger.error(
                    f"Unsupported configuration file format: {self.config_path}"
                )
                return False

            # Merge loaded config with default config to ensure all keys exist
            self.config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)

            # Update last modified time
            self.last_modified_time = os.path.getmtime(self.config_path)
            self.modified_since_load = False

            logger.info(f"Configuration loaded from {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            # Revert to last known good config if we had one
            if self.config_history:
                self.config = self.config_history.pop()
                logger.info("Reverted to previous configuration")
            return False

    def save_config(self, config_path: str = None) -> bool:
        """
        Save the current configuration to a file

        Args:
            config_path: Path to save the configuration (if None, uses the path from initialization)

        Returns:
            bool: True if successful, False otherwise
        """
        if config_path:
            save_path = config_path
        else:
            save_path = self.config_path

        if not save_path:
            logger.warning("No configuration path specified for saving")
            return False

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Determine file type from extension and save accordingly
            if save_path.endswith(".yaml") or save_path.endswith(".yml"):
                with open(save_path, "w", encoding="utf-8") as file:
                    yaml.dump(self.config, file, default_flow_style=False)
            elif save_path.endswith(".json"):
                with open(save_path, "w", encoding="utf-8") as file:
                    json.dump(self.config, file, indent=4)
            else:
                logger.error(f"Unsupported configuration file format: {save_path}")
                return False

            logger.info(f"Configuration saved to {save_path}")
            self.last_modified_time = os.path.getmtime(save_path)
            self.modified_since_load = False
            return True

        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            return False

    def _save_default_config(self) -> bool:
        """
        Save the default configuration to the config path

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.config_path:
            logger.warning("No configuration path specified for saving defaults")
            return False

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            # Reset config to defaults
            self.config = copy.deepcopy(self.DEFAULT_CONFIG)

            # Save to file
            return self.save_config()

        except Exception as e:
            logger.error(f"Error saving default configuration: {str(e)}")
            return False

    def get_config(self, section: str, key: str = None, default: Any = None) -> Any:
        """
        Get a configuration value

        Args:
            section: Configuration section
            key: Configuration key within section (if None, returns the entire section)
            default: Default value if section/key doesn't exist

        Returns:
            The configuration value, or default if not found
        """
        # Check if section exists
        if section not in self.config:
            return default

        # Return entire section if key is None
        if key is None:
            return self.config[section]

        # Check if key exists in section
        if key not in self.config[section]:
            return default

        return self.config[section][key]

    def set_config(self, section: str, key: str, value: Any) -> bool:
        """
        Set a configuration value

        Args:
            section: Configuration section
            key: Configuration key within section
            value: Value to set

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create section if it doesn't exist
            if section not in self.config:
                self.config[section] = {}

            # Check if value is different
            if (
                section in self.config
                and key in self.config[section]
                and self.config[section][key] == value
            ):
                return True  # No change needed

            # Set the value
            self.config[section][key] = value
            self.modified_since_load = True

            logger.debug(f"Configuration updated: {section}.{key} = {value}")
            return True

        except Exception as e:
            logger.error(f"Error setting configuration value: {str(e)}")
            return False

    def apply_environment_overrides(self) -> int:
        """
        Apply environment variable overrides to the configuration

        Environment variables in the format SABRINA_SECTION_KEY=value will override
        the corresponding configuration values.

        Returns:
            int: Number of overrides applied
        """
        override_count = 0
        prefix = "SABRINA_"

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            try:
                # Parse section and key from environment variable name
                parts = key[len(prefix) :].lower().split("_", 1)
                if len(parts) != 2:
                    continue

                section, config_key = parts

                # Convert value to appropriate type
                if value.lower() in ("true", "yes", "1"):
                    typed_value = True
                elif value.lower() in ("false", "no", "0"):
                    typed_value = False
                elif value.replace(".", "", 1).isdigit():
                    typed_value = float(value) if "." in value else int(value)
                else:
                    typed_value = value

                # Apply the override
                if self.set_config(section, config_key, typed_value):
                    override_count += 1
                    logger.info(
                        f"Configuration override from environment: {section}.{config_key} = {typed_value}"
                    )

            except Exception as e:
                logger.warning(
                    f"Error applying environment override for {key}: {str(e)}"
                )

        return override_count

    def reset_to_defaults(self, section: str = None) -> bool:
        """
        Reset configuration to default values

        Args:
            section: Section to reset (if None, resets all sections)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if section:
                # Reset only the specified section
                if section in self.DEFAULT_CONFIG:
                    self.config[section] = copy.deepcopy(self.DEFAULT_CONFIG[section])
                    logger.info(f"Reset configuration section {section} to defaults")
                else:
                    logger.warning(
                        f"Configuration section {section} not found in defaults"
                    )
                    return False
            else:
                # Reset all sections
                self.config = copy.deepcopy(self.DEFAULT_CONFIG)
                logger.info("Reset all configuration to defaults")

            self.modified_since_load = True
            return True

        except Exception as e:
            logger.error(f"Error resetting configuration: {str(e)}")
            return False

    def check_for_updates(self) -> bool:
        """
        Check if the configuration file has been modified since last load

        Returns:
            bool: True if the file has been modified, False otherwise
        """
        if not self.config_path or not os.path.exists(self.config_path):
            return False

        try:
            # Check file modification time
            current_mtime = os.path.getmtime(self.config_path)
            if current_mtime > self.last_modified_time:
                logger.info(f"Configuration file {self.config_path} has been modified")
                return True
            return False

        except Exception as e:
            logger.error(f"Error checking for configuration updates: {str(e)}")
            return False

    def reload_if_changed(self) -> bool:
        """
        Reload the configuration if the file has been modified

        Returns:
            bool: True if reloaded, False otherwise
        """
        if self.check_for_updates():
            return self.load_config()
        return False

    def _merge_configs(
        self, base_config: Dict[str, Any], override_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively merge two configuration dictionaries

        Args:
            base_config: Base configuration (typically defaults)
            override_config: Configuration with overrides

        Returns:
            Dict: Merged configuration
        """
        result = copy.deepcopy(base_config)

        for section, section_data in override_config.items():
            if (
                section in result
                and isinstance(result[section], dict)
                and isinstance(section_data, dict)
            ):
                # Recursively merge dictionaries
                result[section] = self._merge_configs(result[section], section_data)
            else:
                # Override with new value
                result[section] = copy.deepcopy(section_data)

        return result

    def has_section(self, section: str) -> bool:
        """
        Check if a configuration section exists

        Args:
            section: Section name to check

        Returns:
            bool: True if the section exists, False otherwise
        """
        return section in self.config

    def has_changed(self) -> bool:
        """
        Check if the configuration has been modified since last load/save

        Returns:
            bool: True if modified, False otherwise
        """
        return self.modified_since_load

    def list_sections(self) -> List[str]:
        """
        Get a list of all configuration sections

        Returns:
            List[str]: List of section names
        """
        return list(self.config.keys())

    def export_config(self, format: str = "dict") -> Union[Dict[str, Any], str]:
        """
        Export the configuration in various formats

        Args:
            format: Export format ('dict', 'json', 'yaml')

        Returns:
            The configuration in the requested format
        """
        if format == "dict":
            return copy.deepcopy(self.config)
        elif format == "json":
            return json.dumps(self.config, indent=4)
        elif format == "yaml":
            return yaml.dump(self.config, default_flow_style=False)
        else:
            logger.warning(f"Unsupported export format: {format}")
            return copy.deepcopy(self.config)
