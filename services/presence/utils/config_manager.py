"""
Enhanced configuration management for Sabrina's Presence System

Provides a robust configuration system with environment support, validation,
schema enforcement, and efficient merging of configuration values
"""
# Standard imports
import os
import json
import copy
import time
from typing import Any, Dict, List, Optional, Union, Callable

# Local imports
from .error_handling import ErrorHandler, logger

class ConfigSchema:
    """Configuration schema definition and validation"""
    
    def __init__(self, schema: Dict[str, Any]):
        """Initialize configuration schema
        
        Args:
            schema: Schema definition dictionary
        """
        self.schema = schema
        
    def validate(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration against schema
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required sections
        for section, section_schema in self.schema.items():
            if section_schema.get("required", False) and section not in config:
                errors.append(f"Required section '{section}' is missing")
                continue
                
            if section not in config:
                continue
                
            # Check required keys
            for key, key_schema in section_schema.get("keys", {}).items():
                if key_schema.get("required", False) and key not in config[section]:
                    errors.append(f"Required key '{section}.{key}' is missing")
                
                if key not in config[section]:
                    continue
                    
                # Check value type
                expected_type = key_schema.get("type")
                if expected_type:
                    value = config[section][key]
                    if expected_type == "string" and not isinstance(value, str):
                        errors.append(f"Key '{section}.{key}' should be a string, not {type(value).__name__}")
                    elif expected_type == "number" and not isinstance(value, (int, float)):
                        errors.append(f"Key '{section}.{key}' should be a number, not {type(value).__name__}")
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        errors.append(f"Key '{section}.{key}' should be a boolean, not {type(value).__name__}")
                    elif expected_type == "array" and not isinstance(value, list):
                        errors.append(f"Key '{section}.{key}' should be an array, not {type(value).__name__}")
                    elif expected_type == "object" and not isinstance(value, dict):
                        errors.append(f"Key '{section}.{key}' should be an object, not {type(value).__name__}")
                
                # Check value range
                if isinstance(config[section][key], (int, float)):
                    min_value = key_schema.get("min")
                    max_value = key_schema.get("max")
                    
                    if min_value is not None and config[section][key] < min_value:
                        errors.append(f"Key '{section}.{key}' value {config[section][key]} is less than minimum {min_value}")
                    
                    if max_value is not None and config[section][key] > max_value:
                        errors.append(f"Key '{section}.{key}' value {config[section][key]} is greater than maximum {max_value}")
                
                # Check enum values
                enum_values = key_schema.get("enum")
                if enum_values and config[section][key] not in enum_values:
                    errors.append(f"Key '{section}.{key}' value {config[section][key]} is not one of {enum_values}")
        
        return errors
    
    def apply_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default values from schema to configuration
        
        Args:
            config: Configuration to update
            
        Returns:
            Updated configuration with defaults applied
        """
        result = copy.deepcopy(config)
        
        for section, section_schema in self.schema.items():
            if section not in result:
                result[section] = {}
                
            for key, key_schema in section_schema.get("keys", {}).items():
                if "default" in key_schema and key not in result[section]:
                    result[section][key] = key_schema["default"]
        
        return result

class ConfigManager:
    """Enhanced configuration manager with environment support and validation"""
    
    DEFAULT_CONFIG = {
        "window": {
            "width": 500,
            "height": 500,
            "padding_right": 20,
            "transparency_level": 0.85,
            "enable_dragging": True,
            "lock_position": False
        },
        "animations": {
            "default_animation": "idle",
            "transition_duration": 300,
            "enable_transitions": True,
            "priorities": {
                "talking": 5,
                "error": 4,
                "success": 3,
                "listening": 3,
                "working": 2,
                "thinking": 2,
                "waiting": 2,
                "idle": 1
            }
        },
        "system_tray": {
            "minimize_to_tray": True,
            "show_notifications": True
        },
        "themes": {
            "default_theme": "default"
        },
        "debug": {
            "debug_mode": False,
            "log_animations": False,
            "performance_stats": False
        },
        "interaction": {
            "click_through_mode": False,
            "context_menu_enabled": True,
            "auto_respond_to_click": True
        },
        "advanced": {
            "resource_cleanup_threshold": 10,
            "inactive_resource_timeout": 60,
            "max_history_entries": 20
        },
        "voice": {
            "volume": 0.8,
            "speed": 1.0,
            "pitch": 1.0,
            "emotion": "normal"
        },
    }
    
    # Configuration schema for validation
    CONFIG_SCHEMA = {
        "window": {
            "required": True,
            "keys": {
                "width": {"type": "number", "required": True, "min": 100, "max": 2000, "default": 500},
                "height": {"type": "number", "required": True, "min": 100, "max": 2000, "default": 500},
                "padding_right": {"type": "number", "required": False, "min": 0, "max": 500, "default": 20},
                "transparency_level": {"type": "number", "required": True, "min": 0.1, "max": 1.0, "default": 0.85},
                "enable_dragging": {"type": "boolean", "required": False, "default": True},
                "lock_position": {"type": "boolean", "required": False, "default": False}
            }
        },
        "animations": {
            "required": True,
            "keys": {
                "default_animation": {"type": "string", "required": True, "default": "idle"},
                "transition_duration": {"type": "number", "required": False, "min": 0, "max": 2000, "default": 300},
                "enable_transitions": {"type": "boolean", "required": False, "default": True},
                "priorities": {"type": "object", "required": False}
            }
        },
        # Add more schema definitions as needed
    }
    
    def __init__(self, 
                config_dir: str = "config", 
                config_filename: str = "presence_config.json",
                env_override: bool = True):
        """Initialize configuration manager with enhanced features
        
        Args:
            config_dir: Directory for configuration files (default: "config")
            config_filename: Name of the configuration file (default: "presence_config.json")
            env_override: Allow environment variables to override config (default: True)
        """
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, config_filename)
        self.config = None
        self.env_override = env_override
        self.last_save_time = 0
        self.modified_since_save = False
        self.schema = ConfigSchema(self.CONFIG_SCHEMA)
        self.change_callbacks = {}  # Callbacks for config changes
        
        # Make sure config directory exists
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir)
                logger.info(f"Created configuration directory: {config_dir}")
            except Exception as e:
                ErrorHandler.log_error(e, "ConfigManager.__init__")
        
        # Load or create configuration
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from file or create default
        
        Returns:
            bool: True if successful, False otherwise
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # Merge with default config to ensure all keys exist
                self.config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
                
                # Validate configuration
                validation_errors = self.schema.validate(self.config)
                if validation_errors:
                    for error in validation_errors:
                        logger.warning(f"Configuration validation error: {error}")
                    
                    # Apply defaults to fix validation errors
                    self.config = self.schema.apply_defaults(self.config)
                
                # Apply environment overrides if enabled
                if self.env_override:
                    self._apply_env_overrides()
                
                logger.info("Configuration loaded successfully")
                return True
                
            except Exception as e:
                ErrorHandler.log_error(e, "ConfigManager.load_config")
                self.config = copy.deepcopy(self.DEFAULT_CONFIG)
                self.save_config()  # Save default config
                return False
        else:
            logger.info("No configuration file found, creating default")
            self.config = copy.deepcopy(self.DEFAULT_CONFIG)
            self.save_config()  # Save default config
            return True
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration"""
        # Environment variables should be in format SABRINA_SECTION_KEY=value
        env_prefix = "SABRINA_"
        override_count = 0
        
        for env_name, env_value in os.environ.items():
            if env_name.startswith(env_prefix):
                # Split environment variable name into config path
                parts = env_name[len(env_prefix):].lower().split('_')
                if len(parts) < 2:
                    continue
                    
                section = parts[0]
                key = '_'.join(parts[1:])  # Join remaining parts as key
                
                if section in self.config:
                    # Convert value to appropriate type
                    if env_value.lower() in ("true", "yes", "1"):
                        typed_value = True
                    elif env_value.lower() in ("false", "no", "0"):
                        typed_value = False
                    elif env_value.replace(".", "").isdigit():
                        # Handle numeric values (int or float)
                        typed_value = float(env_value) if "." in env_value else int(env_value)
                    else:
                        # Keep as string
                        typed_value = env_value
                    
                    # Apply override
                    if key in self.config[section]:
                        logger.info(f"Environment override: {section}.{key}={typed_value}")
                        self.config[section][key] = typed_value
                        override_count += 1
        
        if override_count > 0:
            logger.info(f"Applied {override_count} environment overrides")
    
    def save_config(self, force=False) -> bool:
        """Save current configuration to file
        
        Args:
            force: Force save even if not modified (default: False)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not force and not self.modified_since_save:
            # Skip save if no changes and not forced
            return True
            
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
                
            self.last_save_time = time.time()
            self.modified_since_save = False
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            ErrorHandler.log_error(e, "ConfigManager.save_config")
            return False
    
    def save_config_as(self, file_path: str) -> bool:
        """Save current configuration to a specific file
        
        Args:
            file_path: Path to save the configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
                
            logger.info(f"Configuration saved to {file_path}")
            return True
        except Exception as e:
            ErrorHandler.log_error(e, f"ConfigManager.save_config_as({file_path})")
            return False
    
    def get_config(self, section: Optional[str] = None, key: Optional[str] = None, default: Any = None) -> Any:
        """Get configuration value with enhanced error checking
        
        Args:
            section: Optional section name
            key: Optional key within section
            default: Default value if section/key not found
            
        Returns:
            Config value, section dict, or entire config
        """
        if not self.config:
            logger.warning("Configuration not loaded, returning default")
            return default
            
        if section is None:
            return self.config
        
        if section not in self.config:
            logger.debug(f"Config section '{section}' not found, returning default")
            return default
            
        if key is None:
            return self.config[section]
            
        if key not in self.config[section]:
            logger.debug(f"Config key '{key}' not found in section '{section}', returning default")
            return default
            
        return self.config[section][key]
    
    def set_config(self, section: str, key: str, value: Any) -> bool:
        """Set configuration value with validation
        
        Args:
            section: Section name
            key: Key within section
            value: Value to set
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not section or not key:
            logger.warning("Invalid section or key name")
            return False
            
        # Create section if it doesn't exist
        if section not in self.config:
            logger.info(f"Creating new config section: '{section}'")
            self.config[section] = {}
        
        # Validate value if schema exists for this key
        schema_key = self.schema.schema.get(section, {}).get("keys", {}).get(key, {})
        if schema_key:
            key_type = schema_key.get("type")
            if key_type and not self._validate_type(value, key_type):
                logger.warning(f"Invalid type for {section}.{key}: expected {key_type}, got {type(value).__name__}")
                return False
                
            if key_type == "number":
                min_val = schema_key.get("min")
                max_val = schema_key.get("max")
                
                if min_val is not None and value < min_val:
                    logger.warning(f"Value {value} for {section}.{key} is less than minimum {min_val}")
                    return False
                    
                if max_val is not None and value > max_val:
                    logger.warning(f"Value {value} for {section}.{key} is greater than maximum {max_val}")
                    return False
            
            enum_vals = schema_key.get("enum")
            if enum_vals and value not in enum_vals:
                logger.warning(f"Value {value} for {section}.{key} is not one of {enum_vals}")
                return False
        
        # Save old value for logging
        old_value = self.config[section].get(key, None)
        
        # Only update if value changed
        if old_value != value:
            self.config[section][key] = value
            self.modified_since_save = True
            
            logger.info(f"Config changed: {section}.{key}: {old_value} -> {value}")
            
            # Notify callbacks
            self._notify_change_callbacks(section, key, old_value, value)
            
            return True
        
        return False
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type
        
        Args:
            value: Value to validate
            expected_type: Expected type string
            
        Returns:
            bool: True if valid, False otherwise
        """
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "number":
            return isinstance(value, (int, float))
        elif expected_type == "boolean":
            return isinstance(value, bool)
        elif expected_type == "array":
            return isinstance(value, list)
        elif expected_type == "object":
            return isinstance(value, dict)
        return True  # Unknown type, assume valid
    
    def reset_section(self, section: str) -> bool:
        """Reset a section to default values
        
        Args:
            section: Section name to reset
            
        Returns:
            bool: True if successful, False otherwise
        """
        if section not in self.DEFAULT_CONFIG:
            logger.warning(f"No default config for section '{section}'")
            return False
        
        # Keep track of old values for callbacks
        old_values = self.config.get(section, {}).copy()
        
        # Reset to default
        self.config[section] = copy.deepcopy(self.DEFAULT_CONFIG[section])
        self.modified_since_save = True
        
        logger.info(f"Reset section '{section}' to defaults")
        
        # Notify callbacks for each changed key
        for key, new_value in self.config[section].items():
            old_value = old_values.get(key, None)
            if old_value != new_value:
                self._notify_change_callbacks(section, key, old_value, new_value)
        
        return True
    
    def reset_all(self) -> bool:
        """Reset entire configuration to defaults
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Keep track of old config for callbacks
        old_config = copy.deepcopy(self.config)
        
        # Reset to default
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        self.modified_since_save = True
        
        logger.info("Reset entire configuration to defaults")
        
        # Notify callbacks for each changed key
        for section, section_data in self.config.items():
            for key, new_value in section_data.items():
                old_value = old_config.get(section, {}).get(key, None)
                if old_value != new_value:
                    self._notify_change_callbacks(section, key, old_value, new_value)
        
        return self.save_config()
    
    def _merge_configs(self, default_config: Dict[str, Any], user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge user config with default config
        
        This ensures all default keys exist in the final config,
        while preserving user customizations.
        
        Args:
            default_config: Default configuration (template)
            user_config: User configuration (overrides)
            
        Returns:
            Dict[str, Any]: Merged configuration dictionary
        """
        result = copy.deepcopy(default_config)
        
        for key, value in user_config.items():
            # If both configs have dict at this key, merge recursively
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                # Otherwise take the user value
                result[key] = value
                
        return result
        
    def load_config_from_file(self, file_path: str) -> bool:
        """Load configuration from a specific file path
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.warning(f"Configuration file not found: {file_path}")
            return False
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                
            # Store old config for change detection
            old_config = copy.deepcopy(self.config)
                
            # Merge with default config to ensure all keys exist
            self.config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
            self.modified_since_save = True
            
            logger.info(f"Configuration loaded successfully from {file_path}")
            
            # Detect changes and notify callbacks
            self._detect_changes_and_notify(old_config, self.config)
            
            return True
        except Exception as e:
            ErrorHandler.log_error(e, f"ConfigManager.load_config_from_file({file_path})")
            return False
    
    def _detect_changes_and_notify(self, old_config: Dict[str, Any], new_config: Dict[str, Any]):
        """Detect changes between configurations and notify callbacks
        
        Args:
            old_config: Old configuration
            new_config: New configuration
        """
        for section, section_data in new_config.items():
            if isinstance(section_data, dict):
                for key, new_value in section_data.items():
                    old_value = old_config.get(section, {}).get(key, None)
                    if old_value != new_value:
                        self._notify_change_callbacks(section, key, old_value, new_value)
    
    def register_change_callback(self, section: str, key: str, callback: Callable[[str, str, Any, Any], None]) -> str:
        """Register a callback for configuration changes
        
        Args:
            section: Section to monitor
            key: Key to monitor
            callback: Function to call when value changes
            
        Returns:
            str: Callback ID for unregistering
        """
        callback_id = f"{section}.{key}.{id(callback)}"
        
        if section not in self.change_callbacks:
            self.change_callbacks[section] = {}
            
        if key not in self.change_callbacks[section]:
            self.change_callbacks[section][key] = {}
            
        self.change_callbacks[section][key][callback_id] = callback
        
        return callback_id
    
    def unregister_change_callback(self, callback_id: str) -> bool:
        """Unregister a configuration change callback
        
        Args:
            callback_id: Callback ID from register_change_callback
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not callback_id or "." not in callback_id:
            return False
            
        section, key, _ = callback_id.split(".", 2)
        
        if (section in self.change_callbacks and 
            key in self.change_callbacks[section] and 
            callback_id in self.change_callbacks[section][key]):
            del self.change_callbacks[section][key][callback_id]
            return True
            
        return False
    
    def _notify_change_callbacks(self, section: str, key: str, old_value: Any, new_value: Any):
        """Notify callbacks about configuration changes
        
        Args:
            section: Changed section
            key: Changed key
            old_value: Previous value
            new_value: New value
        """
        # Skip if no callbacks registered
        if section not in self.change_callbacks:
            return
            
        # Notify key-specific callbacks
        if key in self.change_callbacks[section]:
            for callback in self.change_callbacks[section][key].values():
                try:
                    callback(section, key, old_value, new_value)
                except Exception as e:
                    ErrorHandler.log_error(e, f"Config change callback for {section}.{key}")
        
        # Notify wildcard callbacks for this section
        if "*" in self.change_callbacks[section]:
            for callback in self.change_callbacks[section]["*"].values():
                try:
                    callback(section, key, old_value, new_value)
                except Exception as e:
                    ErrorHandler.log_error(e, f"Config wildcard callback for {section}")
    
    def load_environment_config(self) -> bool:
        """Load environment-specific configuration
        
        Loads a configuration file based on SABRINA_ENV environment variable.
        
        Returns:
            bool: True if successful, False otherwise
        """
        env = os.environ.get("SABRINA_ENV", "development")
        env_config_path = os.path.join(self.config_dir, f"config.{env}.json")
        
        if os.path.exists(env_config_path):
            logger.info(f"Loading environment config for: {env}")
            return self.load_config_from_file(env_config_path)
        else:
            logger.info(f"No environment config found for: {env}")
            return False
    
    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes
        
        Returns:
            bool: True if there are unsaved changes, False otherwise
        """
        return self.modified_since_save