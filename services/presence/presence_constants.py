# presence_constants.py - Configuration constants for Sabrina AI's presence system
import os
from config_manager import ConfigManager

# Initialize config manager
config = ConfigManager()

# Load configuration values with defaults
def get_config(section, key, default):
    """Get configuration value with default fallback"""
    return config.get_config(section, key, default)

### WINDOW POSITION & SIZE ###
WINDOW_WIDTH = get_config("window", "width", 500)  # Width of AI Presence window
WINDOW_HEIGHT = get_config("window", "height", 500)  # Height of AI Presence window
PADDING_RIGHT = get_config("window", "padding_right", 20)  # Padding from the right screen edge

### TRANSPARENCY & INTERACTIVITY ###
ENABLE_TRANSPARENCY = get_config("window", "enable_transparency", True)  # Enable transparent background
TRANSPARENCY_LEVEL = get_config("window", "transparency_level", 0.85)  # Opacity level (0.0 = fully transparent, 1.0 = fully opaque)
CLICK_THROUGH_MODE = get_config("interaction", "click_through_mode", False)  # Allow interactions behind the AI overlay
ENABLE_DRAGGING = get_config("window", "enable_dragging", True)  # Allow clicking and dragging the window
LOCK_POSITION = get_config("window", "lock_position", False)  # Prevent movement if locked

### ANIMATION SETTINGS ###
ASSETS_FOLDER = os.path.join(os.path.dirname(__file__), "assets")  # Path to animation assets
DEFAULT_ANIMATION = get_config("animations", "default_animation", "idle")  # Default animation on startup

# Animation priority levels (higher numbers = higher priority)
ANIMATION_PRIORITY = get_config("animations", "priorities", {
    "talking": 5,     # Highest priority - override almost everything
    "error": 4,       # High priority - errors should be visible
    "success": 3,     # Medium-high priority
    "listening": 3,   # Medium-high priority
    "working": 2,     # Medium priority
    "thinking": 2,    # Medium priority
    "waiting": 2,     # Medium priority
    "idle": 1         # Lowest priority - default state
})

### ANIMATION TRANSITION SETTINGS ###
ENABLE_TRANSITIONS = get_config("animations", "enable_transitions", True)  # Enable smooth transitions between animations
TRANSITION_DURATION = get_config("animations", "transition_duration", 300)  # Transition duration in milliseconds (300ms = 0.3s)

### SYSTEM TRAY SETTINGS ###
MINIMIZE_TO_TRAY = get_config("system_tray", "minimize_to_tray", True)  # Minimize to system tray instead of taskbar
SHOW_TRAY_NOTIFICATIONS = get_config("system_tray", "show_notifications", True)  # Show system tray notifications
TRAY_ICON_PATH = os.path.join(ASSETS_FOLDER, "static.png")  # System tray icon

### THEME SETTINGS ###
DEFAULT_THEME = get_config("themes", "default_theme", "default")  # Default theme name
THEMES_JSON_PATH = os.path.join(ASSETS_FOLDER, "themes.json")  # Path to themes JSON file

### DEBUGGING SETTINGS ###
DEBUG_MODE = get_config("debug", "debug_mode", False)  # Enable debug logging
LOG_ANIMATIONS = get_config("debug", "log_animations", False)  # Log animation changes
PERFORMANCE_STATS = get_config("debug", "performance_stats", False)  # Track performance statistics

### ANIMATION STATES ###
# Complete list of all animation states for state machine
ANIMATION_STATES = [
    "idle",       # Default inactive state
    "listening",  # Actively listening to user
    "talking",    # Speaking or responding
    "working",    # Processing a task
    "thinking",   # Analyzing information
    "error",      # Encountered an issue
    "success",    # Successfully completed a task
    "waiting"     # Waiting for external input
]

### DEFAULT THEME DEFINITION ###
# This serves as a fallback if no themes.json exists
DEFAULT_THEME_MAPPING = {
    "default": {
        "idle": "idle.gif",
        "listening": "listening.gif",
        "talking": "talking.gif",
        "working": "working.gif",
        "thinking": "idle.gif",
        "error": "static.png",
        "success": "talking.gif",
        "waiting": "idle.gif",
        "static": "static.png"
    }
}

# Function to get absolute paths for assets
def get_asset_path(filename):
    """Get absolute path for an asset file."""
    return os.path.join(ASSETS_FOLDER, filename)

# Save configuration to ensure all defaults are saved
config.save_config()