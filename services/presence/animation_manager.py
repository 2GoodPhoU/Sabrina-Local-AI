# animation_manager.py - Enhanced animation handler for Sabrina AI
import os
import json
from PyQt5.QtGui import QMovie, QPixmap
from services.presence.constants import ANIMATION_PRIORITY

class AnimationManager:
    def __init__(self, assets_folder):
        """Handles loading, queueing, and playing animations with enhanced features."""
        self.assets_folder = assets_folder
        self.animations = self.load_animations()
        self.current_state = None
        self.queue = []
        self.active_animation = None
        self.animation_history = []  # Track recent animations
        
        # Create assets folder if it doesn't exist
        if not os.path.exists(self.assets_folder):
            os.makedirs(self.assets_folder)
            print(f"Created assets folder: {self.assets_folder}")

    def load_animations(self):
        """Dynamically load all GIF and PNG animations from the assets folder."""
        animations = {}
        if not os.path.exists(self.assets_folder):
            print(f"Warning: Assets folder not found: {self.assets_folder}")
            return animations

        for file in os.listdir(self.assets_folder):
            if file.endswith((".gif", ".png")):
                key = os.path.splitext(file)[0]  
                animations[key] = os.path.join(self.assets_folder, file)
                
        if not animations:
            print(f"Warning: No animations found in {self.assets_folder}")
            
        return animations

    def get_animation_path(self, state, theme="default"):
        """Get the full path to an animation based on state and theme."""
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
            print(f"Animation '{state}' not found, using static instead")
            return self.animations["static"]
            
        print(f"Error: No animation found for '{state}' and no static fallback")
        return None

    def queue_animation(self, state, priority=None):
        """Queue animations with priority-based insertion."""
        if state not in self.animations and not state.startswith("theme_"):
            print(f"Warning: Animation '{state}' not found in available animations")
            return False
            
        # Get priority for this animation
        state_priority = priority or ANIMATION_PRIORITY.get(state, 1)
        
        # Check if this is higher priority than current
        if self.current_state:
            current_priority = ANIMATION_PRIORITY.get(self.current_state, 1)
            if state_priority > current_priority:
                # Higher priority - insert at front of queue
                self.queue.insert(0, state)
                return True
        
        # Normal priority - add to queue
        self.queue.append(state)
        return True

    def get_animation_info(self):
        """Return information about the current animation state."""
        return {
            "current_state": self.current_state,
            "queue_length": len(self.queue),
            "queue_contents": list(self.queue),
            "animation_history": self.animation_history[-5:],  # Last 5 animations
            "available_animations": list(self.animations.keys())
        }
        
    def save_animation_mapping(self, filename="animation_mapping.json"):
        """Save the current animation mapping to a JSON file."""
        mapping = {}
        for key, path in self.animations.items():
            mapping[key] = os.path.basename(path)
            
        filepath = os.path.join(self.assets_folder, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(mapping, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving animation mapping: {e}")
            return False
            
    def load_animation_mapping(self, filename="animation_mapping.json"):
        """Load animation mapping from a JSON file."""
        filepath = os.path.join(self.assets_folder, filename)
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, 'r') as f:
                mapping = json.load(f)
                
            # Update animations with loaded mapping
            new_animations = {}
            for key, filename in mapping.items():
                full_path = os.path.join(self.assets_folder, filename)
                if os.path.exists(full_path):
                    new_animations[key] = full_path
                    
            self.animations.update(new_animations)
            return True
        except Exception as e:
            print(f"Error loading animation mapping: {e}")
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
            print(f"Error: Animation file not found: {file_path}")
            return False
            
        # Check if animation already exists
        if state in self.animations and not overwrite:
            print(f"Animation '{state}' already exists and overwrite is False")
            return False
            
        # Copy file to assets folder
        filename = os.path.basename(file_path)
        target_path = os.path.join(self.assets_folder, filename)
        
        try:
            # Copy file if it's not already in the assets folder
            if file_path != target_path:
                with open(file_path, 'rb') as src, open(target_path, 'wb') as dst:
                    dst.write(src.read())
                    
            # Add to animations dictionary
            self.animations[state] = target_path
            
            # Save updated mapping
            self.save_animation_mapping()
            
            print(f"Added custom animation: {state} -> {target_path}")
            return True
        except Exception as e:
            print(f"Error adding custom animation: {e}")
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
            
        return next_animation
        
    def set_animation_on_label(self, state, label):
        """Set animation on a QLabel (legacy support method).
        
        Args:
            state: Animation state to set
            label: QLabel to update
        """
        if state not in self.animations:
            print(f"Animation not found: {state}")
            return False
            
        animation_path = self.animations[state]
        
        # Set image or movie based on file type
        if animation_path.endswith(".png"):
            label.setPixmap(QPixmap(animation_path))
            # Stop any existing movie
            if hasattr(label, 'movie') and label.movie():
                label.movie().stop()
        else:
            movie = QMovie(animation_path)
            movie.setCacheMode(QMovie.CacheAll)
            movie.loopCount = -1  # Infinite loop
            label.setMovie(movie)
            movie.start()
            
        return True
        
    def clear_queue(self):
        """Clear the animation queue."""
        self.queue = []
        
    def get_available_states(self):
        """Get list of available animation states."""
        return list(self.animations.keys())