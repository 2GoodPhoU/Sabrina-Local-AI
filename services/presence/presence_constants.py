# Updating presence_constants.py to include transparency and lock settings

import os

### WINDOW POSITION & SIZE ###
WINDOW_WIDTH = 500  # Width of AI Presence window
WINDOW_HEIGHT = 500  # Height of AI Presence window
PADDING_RIGHT = 20  # Padding from the right screen edge

### TRANSPARENCY & INTERACTIVITY ###
ENABLE_TRANSPARENCY = False  # Enable transparent background
TRANSPARENCY_LEVEL = 0.85  # Opacity level (0.0 = fully transparent, 1.0 = fully opaque)
CLICK_THROUGH_MODE = False  # Allow interactions behind the AI overlay
ENABLE_DRAGGING = True  # Allow clicking and dragging the window
LOCK_POSITION = False  # Prevent movement if locked

### ANIMATION SETTINGS ###
ASSETS_FOLDER = os.path.join(os.path.dirname(__file__), "assets")  # Path to animation assets
DEFAULT_ANIMATION = "idle"  # Default animation on startup
ANIMATION_PRIORITY = {
    "talking": 3,  # Highest priority
    "listening": 2,
    "working": 2,
    "idle": 1   # Lowest priority
}