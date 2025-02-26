# presence_constants.py - Configuration constants for Sabrina AI's presence system
import os

### WINDOW POSITION & SIZE ###
WINDOW_WIDTH = 500  # Width of AI Presence window
WINDOW_HEIGHT = 500  # Height of AI Presence window
PADDING_RIGHT = 20  # Padding from the right screen edge

### TRANSPARENCY & INTERACTIVITY ###
ENABLE_TRANSPARENCY = True  # Enable transparent background
TRANSPARENCY_LEVEL = 0.85  # Opacity level (0.0 = fully transparent, 1.0 = fully opaque)
CLICK_THROUGH_MODE = False  # Allow interactions behind the AI overlay
ENABLE_DRAGGING = True  # Allow clicking and dragging the window
LOCK_POSITION = False  # Prevent movement if locked

### ANIMATION SETTINGS ###
ASSETS_FOLDER = os.path.join(os.path.dirname(__file__), "assets")  # Path to animation assets
DEFAULT_ANIMATION = "idle"  # Default animation on startup

# Animation priority levels (higher numbers = higher priority)
ANIMATION_PRIORITY = {
    "talking": 5,     # Highest priority - override almost everything
    "error": 4,       # High priority - errors should be visible
    "success": 3,     # Medium-high priority
    "listening": 3,   # Medium-high priority
    "working": 2,     # Medium priority
    "thinking": 2,    # Medium priority
    "waiting": 2,     # Medium priority
    "idle": 1         # Lowest priority - default state
}

### ANIMATION TRANSITION SETTINGS ###
ENABLE_TRANSITIONS = True  # Enable smooth transitions between animations
TRANSITION_DURATION = 300  # Transition duration in milliseconds (300ms = 0.3s)

### SYSTEM TRAY SETTINGS ###
MINIMIZE_TO_TRAY = True  # Minimize to system tray instead of taskbar
SHOW_TRAY_NOTIFICATIONS = True  # Show system tray notifications
TRAY_ICON_PATH = os.path.join(ASSETS_FOLDER, "static.png")  # System tray icon

### THEME SETTINGS ###
DEFAULT_THEME = "default"  # Default theme name
THEMES_JSON_PATH = os.path.join(ASSETS_FOLDER, "themes.json")  # Path to themes JSON file

### DEBUGGING SETTINGS ###
DEBUG_MODE = False  # Enable debug logging
LOG_ANIMATIONS = False  # Log animation changes
PERFORMANCE_STATS = False  # Track performance statistics

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