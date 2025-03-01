"""
Animation manager for Sabrina's Presence System

Handles loading, tracking, and managing animations with improved performance and error handling
"""
# Standard imports
import os
import json
import time

# Third-party imports
from PyQt5.QtGui import QMovie, QPixmap

# Local imports
from ..utils.error_handling import ErrorHandler, logger
from ..constants import ANIMATION_PRIORITY, ASSETS_FOLDER


class AnimationManager:
    """Handles loading, queueing, and playing animations with enhanced features."""

    def __init__(self, assets_folder=None):
        """Initialize the animation manager.

        Args:
            assets_folder: Path to animation assets (default: from constants.ASSETS_FOLDER)
        """
        self.assets_folder = assets_folder or ASSETS_FOLDER
        self.animations = {}
        self.current_state = None
        self.queue = []
        self.active_animation = None
        self.animation_history = []  # Track recent animations
        self.last_load_time = 0

        # Create assets folder if it doesn't exist
        if not os.path.exists(self.assets_folder):
            try:
                os.makedirs(self.assets_folder)
                logger.info(f"Created assets folder: {self.assets_folder}")
            except Exception as e:
                ErrorHandler.log_error(e, f"{self.__class__.__name__}.__init__")

        # Load animations
        self.load_animations()

        logger.info(
            f"Animation manager initialized with {len(self.animations)} animations"
        )

    def load_animations(self):
        """Dynamically load all GIF and PNG animations from the assets folder.

        Returns:
            dict: Loaded animations mapping state names to file paths
        """
        start_time = time.time()
        self.animations = {}

        if not os.path.exists(self.assets_folder):
            logger.warning(f"Assets folder not found: {self.assets_folder}")
            return self.animations

        try:
            for file in os.listdir(self.assets_folder):
                if file.lower().endswith((".gif", ".png")):
                    key = os.path.splitext(file)[0]
                    self.animations[key] = os.path.join(self.assets_folder, file)
        except Exception as e:
            ErrorHandler.log_error(e, f"{self.__class__.__name__}.load_animations")

        if not self.animations:
            logger.warning(f"No animations found in {self.assets_folder}")

        self.last_load_time = time.time()
        load_duration = (self.last_load_time - start_time) * 1000  # ms
        logger.debug(
            f"Loaded {len(self.animations)} animations in {load_duration:.2f}ms"
        )

        return self.animations

    def get_animation_path(self, state, theme="default"):
        """Get the full path to an animation based on state and theme.

        Args:
            state: Animation state name
            theme: Theme name (default: "default")

        Returns:
            str: Path to the animation file, or None if not found
        """
        # First try theme-specific animation
        if theme != "default":
            theme_file = f"{theme}_{state}"
            if theme_file in self.animations:
                return self.animations[theme_file]

        # Then fall back to standard animation
        if state in self.animations:
            return self.animations[state]

        # Fall back to static image if no animation exists
        if "static" in self.animations:
            logger.warning(f"Animation '{state}' not found, using static instead")
            return self.animations["static"]

        logger.error(f"No animation found for '{state}' and no static fallback")
        return None

    def queue_animation(self, state, priority=None):
        """Queue animations with priority-based insertion.

        Args:
            state: Animation state to queue
            priority: Priority level (higher = more important)

        Returns:
            bool: Success or failure
        """
        # Validate animation exists
        if state not in self.animations and not state.startswith("theme_"):
            logger.warning(f"Animation '{state}' not found in available animations")
            return False

        # Get priority for this animation
        state_priority = priority or ANIMATION_PRIORITY.get(state, 1)

        # Check if this is higher priority than current
        if self.current_state:
            current_priority = ANIMATION_PRIORITY.get(self.current_state, 1)
            if state_priority > current_priority:
                # Higher priority - insert at front of queue
                self.queue.insert(0, state)
                logger.debug(
                    f"Queued high-priority animation: {state} (priority {state_priority})"
                )
                return True

        # Normal priority - add to queue
        self.queue.append(state)
        logger.debug(f"Queued animation: {state} (priority {state_priority})")
        return True

    def get_animation_info(self):
        """Return information about the current animation state.

        Returns:
            dict: Animation status information
        """
        return {
            "current_state": self.current_state,
            "queue_length": len(self.queue),
            "queue_contents": list(self.queue),
            "animation_history": self.animation_history[-5:],  # Last 5 animations
            "available_animations": list(self.animations.keys()),
        }

    def save_animation_mapping(self, filename="animation_mapping.json"):
        """Save the current animation mapping to a JSON file.

        Args:
            filename: Name of the mapping file (default: "animation_mapping.json")

        Returns:
            bool: Success or failure
        """
        mapping = {}
        for key, path in self.animations.items():
            mapping[key] = os.path.basename(path)

        filepath = os.path.join(self.assets_folder, filename)
        try:
            with open(filepath, "w") as f:
                json.dump(mapping, f, indent=4)
            logger.info(f"Saved animation mapping to {filepath}")
            return True
        except Exception as e:
            ErrorHandler.log_error(
                e, f"{self.__class__.__name__}.save_animation_mapping"
            )
            return False

    def load_animation_mapping(self, filename="animation_mapping.json"):
        """Load animation mapping from a JSON file.

        Args:
            filename: Name of the mapping file (default: "animation_mapping.json")

        Returns:
            bool: Success or failure
        """
        filepath = os.path.join(self.assets_folder, filename)
        if not os.path.exists(filepath):
            logger.warning(f"Animation mapping file not found: {filepath}")
            return False

        try:
            with open(filepath, "r") as f:
                mapping = json.load(f)

            # Update animations with loaded mapping
            load_count = 0
            for key, filename in mapping.items():
                full_path = os.path.join(self.assets_folder, filename)
                if os.path.exists(full_path):
                    self.animations[key] = full_path
                    load_count += 1

            logger.info(f"Loaded {load_count} animations from mapping file")
            return True
        except Exception as e:
            ErrorHandler.log_error(
                e, f"{self.__class__.__name__}.load_animation_mapping"
            )
            return False

    def add_custom_animation(self, state, file_path, overwrite=False):
        """Add a custom animation to the manager.

        Args:
            state: The animation state name
            file_path: Path to the animation file (.gif or .png)
            overwrite: Whether to overwrite existing animation

        Returns:
            bool: Success or failure
        """
        if not os.path.exists(file_path):
            logger.error(f"Animation file not found: {file_path}")
            return False

        # Check if animation already exists
        if state in self.animations and not overwrite:
            logger.warning(f"Animation '{state}' already exists and overwrite is False")
            return False

        # Copy file to assets folder
        filename = os.path.basename(file_path)
        target_path = os.path.join(self.assets_folder, filename)

        try:
            # Copy file if it's not already in the assets folder
            if file_path != target_path:
                with open(file_path, "rb") as src, open(target_path, "wb") as dst:
                    dst.write(src.read())

            # Add to animations dictionary
            self.animations[state] = target_path

            # Save updated mapping
            self.save_animation_mapping()

            logger.info(f"Added custom animation: {state} -> {target_path}")
            return True
        except Exception as e:
            ErrorHandler.log_error(e, f"{self.__class__.__name__}.add_custom_animation")
            return False

    def process_queue(self, label=None):
        """Process the next animation in the queue.

        Args:
            label: Optional QLabel to update directly (legacy support)

        Returns:
            str: The animation state that was processed, or None
        """
        if not self.queue:
            return None

        # Get next animation from queue
        next_animation = self.queue.pop(0)

        # Update current state
        self.current_state = next_animation

        # Add to history
        self.animation_history.append(next_animation)
        if len(self.animation_history) > 20:  # Limit history size
            self.animation_history.pop(0)

        # If a label is provided (legacy mode), set the animation directly
        if label:
            self.set_animation_on_label(next_animation, label)

        logger.debug(f"Processed animation: {next_animation}")
        return next_animation

    def set_animation_on_label(self, state, label):
        """Set animation on a QLabel (legacy support method).

        Args:
            state: Animation state to set
            label: QLabel to update

        Returns:
            bool: Success or failure
        """
        if state not in self.animations:
            logger.warning(f"Animation not found: {state}")
            return False

        animation_path = self.animations[state]

        try:
            # Set image or movie based on file type
            if animation_path.endswith(".png"):
                # Static image
                label.setPixmap(QPixmap(animation_path))
                # Stop any existing movie
                if hasattr(label, "movie") and label.movie():
                    label.movie().stop()
            else:
                # Animated GIF
                movie = QMovie(animation_path)
                movie.setCacheMode(QMovie.CacheAll)
                movie.loopCount = -1  # Infinite loop
                label.setMovie(movie)
                movie.start()

            return True
        except Exception as e:
            ErrorHandler.log_error(
                e, f"{self.__class__.__name__}.set_animation_on_label"
            )
            return False

    def clear_queue(self):
        """Clear the animation queue."""
        queue_size = len(self.queue)
        self.queue = []
        logger.debug(f"Cleared animation queue ({queue_size} items)")

    def get_available_states(self):
        """Get list of available animation states.

        Returns:
            list: Available animation state names
        """
        return list(self.animations.keys())
