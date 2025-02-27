# Configuration management for Sabrina's Presence System
import os
import json
import copy
from .error_handling import ErrorHandler, logger  # Changed from "from error_handling" to "from .error_handling"

class ConfigManager:
    """Manages configuration settings for the Presence System"""
    
    DEFAULT_CONFIG = {
        "window": {
            "width": 500,
            "height": 500,
            "padding_right": 20,
            "enable_transparency": True,
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
        }
    }
    
    def __init__(self, config_dir="config", config_filename="presence_config.json"):
        """Initialize configuration manager
        
        Args:
            config_dir: Directory for configuration files
            config_filename: Name of the configuration file
        """
        self.config_dir = config_dir
        self.config_path = os.path.join(config_dir, config_filename)
        self.config = None
        
        # Make sure config directory exists
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        
        # Load or create configuration
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                
                # Merge with default config to ensure all keys exist
                self.config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
                logger.info("Configuration loaded successfully")
            except Exception as e:
                ErrorHandler.log_error(e, "Failed to load configuration")
                self.config = copy.deepcopy(self.DEFAULT_CONFIG)
                self.save_config()  # Save default config
        else:
            logger.info("No configuration file found, creating default")
            self.config = copy.deepcopy(self.DEFAULT_CONFIG)
            self.save_config()  # Save default config
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            ErrorHandler.log_error(e, "Failed to save configuration")
            return False
    
    def get_config(self, section=None, key=None, default=None):
        """Get configuration value
        
        Args:
            section: Optional section name
            key: Optional key within section
            default: Default value if section/key not found
            
        Returns:
            Config value, section dict, or entire config
        """
        if section is None:
            return self.config
        
        if section not in self.config:
            logger.warning(f"Config section '{section}' not found")
            return default
            
        if key is None:
            return self.config[section]
            
        if key not in self.config[section]:
            logger.warning(f"Config key '{key}' not found in section '{section}'")
            return default
            
        return self.config[section][key]
    
    def set_config(self, section, key, value):
        """Set configuration value
        
        Args:
            section: Section name
            key: Key within section
            value: Value to set
            
        Returns:
            True if successful, False otherwise
        """
        if section not in self.config:
            logger.warning(f"Creating new config section: '{section}'")
            self.config[section] = {}
        
        # Save old value for logging
        old_value = self.config[section].get(key, None)
        self.config[section][key] = value
        
        logger.info(f"Config changed: {section}.{key}: {old_value} -> {value}")
        return True
    
    def reset_section(self, section):
        """Reset a section to default values
        
        Args:
            section: Section name to reset
            
        Returns:
            True if successful, False otherwise
        """
        if section not in self.DEFAULT_CONFIG:
            logger.warning(f"No default config for section '{section}'")
            return False
        
        self.config[section] = copy.deepcopy(self.DEFAULT_CONFIG[section])
        logger.info(f"Reset section '{section}' to defaults")
        return True
    
    def reset_all(self):
        """Reset entire configuration to defaults
        
        Returns:
            True if successful, False otherwise
        """
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        logger.info("Reset entire configuration to defaults")
        return self.save_config()
    
    def _merge_configs(self, default_config, user_config):
        """Recursively merge user config with default config
        
        This ensures all default keys exist in the final config,
        while preserving user customizations.
        
        Args:
            default_config: Default configuration (template)
            user_config: User configuration (overrides)
            
        Returns:
            Merged configuration dictionary
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
        
    def load_config_from_file(self, file_path):
        """Load configuration from a specific file path
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(file_path):
            logger.warning(f"Configuration file not found: {file_path}")
            return False
            
        try:
            with open(file_path, 'r') as f:
                loaded_config = json.load(f)
                
            # Merge with default config to ensure all keys exist
            self.config = self._merge_configs(self.DEFAULT_CONFIG, loaded_config)
            logger.info(f"Configuration loaded successfully from {file_path}")
            return True
        except Exception as e:
            ErrorHandler.log_error(e, f"Failed to load configuration from {file_path}")
            return False