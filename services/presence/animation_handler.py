import os
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtGui import QMovie, QPixmap
from PyQt5.QtCore import QTimer, Qt
import sys

class AnimationHandler(QMainWindow):
    def __init__(self, assets_folder="assets/"):
        super().__init__()

        # Create a label to display the animation
        self.label = QLabel(self)
        self.label.setGeometry(50, 50, 500, 500)
        self.label.setAlignment(Qt.AlignCenter)  # Center alignment
        self.setFixedSize(600, 600)

        # Dynamically load all animations in the folder
        self.animations = self.load_animations(assets_folder)

        # Default animation state
        self.current_state = None
        self.queue = []  # Queue for animation events
        self.priority = {"talking": 3, "listening": 2, "working": 2, "idle": 1}
        self.movie = None  # Store active QMovie instance

        # Play the first available animation
        default_animation = next(iter(self.animations.keys()), None)
        if default_animation:
            self.set_animation(default_animation)

        self.start_event_listener()  # Start queue processor

    def load_animations(self, folder):
        """Dynamically load all GIF and PNG animations from the assets folder."""
        animations = {}
        if not os.path.exists(folder):
            print(f"[AnimationHandler] Warning: Folder '{folder}' does not exist.")
            return animations

        for file in os.listdir(folder):
            if file.endswith((".gif", ".png")):
                key = os.path.splitext(file)[0]  # Use filename (without extension) as the state name
                animations[key] = os.path.join(folder, file)
        
        print(f"[AnimationHandler] Loaded animations: {animations}")
        return animations

    def set_animation(self, state):
        """Change the displayed animation based on state."""
        if state in self.animations and state != self.current_state:
            if self.animations[state].endswith(".png"):
                pixmap = QPixmap(self.animations[state])
                self.label.setPixmap(pixmap)
            else:
                self.movie = QMovie(self.animations[state])  # Store reference
                self.movie.setCacheMode(QMovie.CacheAll)
                self.movie.loopCount = -1  # Set looping indefinitely
                self.label.setMovie(self.movie)
                self.movie.start()
            self.current_state = state
            print(f"[AnimationHandler] Playing '{state}' animation.")

    def queue_animation(self, state):
        """Queue animations and ensure priority-based execution."""
        if state in self.animations:
            if not self.queue or self.priority.get(state, 1) > self.priority.get(self.queue[-1], 1):
                self.queue.append(state)
                print(f"[AnimationHandler] Queued '{state}' animation.")

    def process_queue(self):
        """Continuously process queued animations in the main thread."""
        if self.queue:
            next_animation = self.queue.pop(0)
            self.set_animation(next_animation)
        QTimer.singleShot(100, self.process_queue)  # Schedule next queue check

    def start_event_listener(self):
        """Start queue processing in the main thread using QTimer."""
        QTimer.singleShot(100, self.process_queue)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnimationHandler()
    window.show()
    sys.exit(app.exec_())
