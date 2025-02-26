# Creating animation_manager.py to handle animations
import os
from PyQt5.QtGui import QMovie, QPixmap

class AnimationManager:
    def __init__(self, assets_folder):
        """Handles loading, queueing, and playing animations."""
        self.assets_folder = assets_folder
        self.animations = self.load_animations()
        self.current_state = None
        self.queue = []  
        self.movie = None  

    def load_animations(self):
        """Dynamically load all GIF and PNG animations from the assets folder."""
        animations = {}
        if not os.path.exists(self.assets_folder):
            return animations

        for file in os.listdir(self.assets_folder):
            if file.endswith((".gif", ".png")):
                key = os.path.splitext(file)[0]  
                animations[key] = os.path.join(self.assets_folder, file)
        
        return animations

    def set_animation(self, state, label):
        """Change the displayed animation based on state."""
        if state in self.animations and state != self.current_state:
            if self.animations[state].endswith(".png"):
                label.setPixmap(QPixmap(self.animations[state]))
            else:
                self.movie = QMovie(self.animations[state])  
                self.movie.setCacheMode(QMovie.CacheAll)
                self.movie.loopCount = -1  # this needs to stay -1 for infinite loop
                label.setMovie(self.movie)
                self.movie.start()
            self.current_state = state

    def queue_animation(self, state):
        """Queue animations and ensure priority-based execution."""
        if state in self.animations:
            self.queue.append(state)

    def process_queue(self, label):
        """Continuously process queued animations."""
        if self.queue:
            next_animation = self.queue.pop(0)
            self.set_animation(next_animation, label)

