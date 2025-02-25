from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtGui import QMovie, QPixmap
import sys
import time
import threading

class AnimationHandler(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Create a label to display the animation
        self.label = QLabel(self)
        self.label.setGeometry(50, 50, 500, 500)  # Adjust the position/size as needed
        self.setFixedSize(600, 600)

        # Dictionary to store animations (GIFs, PNGs)
        self.animations = {
            "idle": "assets/idle.gif",
            "listening": "assets/listening.gif",
            "talking": "assets/talking.gif",
            "working": "assets/working.gif",
            "static": "assets/static.png"  # Example of a static image
        }

        # Current state
        self.current_state = "idle"
        self.queue = []  # Queue for animation events
        self.priority = {"talking": 3, "listening": 2, "working": 2, "idle": 1}

        self.set_animation("idle")  # Default animation
        self.start_event_listener()  # Start queue processor

    def set_animation(self, state):
        """Change the displayed animation based on state."""
        if state in self.animations:
            if state.endswith(".png"):
                pixmap = QPixmap(self.animations[state])
                self.label.setPixmap(pixmap)
            else:
                movie = QMovie(self.animations[state])
                self.label.setMovie(movie)
                movie.start()
            self.current_state = state
            print(f"[AnimationHandler] Playing {state} animation.")

    def queue_animation(self, state):
        """Queue animations and ensure priority-based execution."""
        if state in self.animations:
            if not self.queue or self.priority[state] >= self.priority[self.queue[-1]]:
                self.queue.append(state)

    def process_queue(self):
        """Continuously process queued animations."""
        while True:
            if self.queue:
                next_animation = self.queue.pop(0)
                if next_animation != self.current_state:  # Prevent unnecessary reloads
                    self.set_animation(next_animation)
            time.sleep(0.1)

    def start_event_listener(self):
        """Start queue processing in a separate thread."""
        thread = threading.Thread(target=self.process_queue, daemon=True)
        thread.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnimationHandler()
    window.show()
    sys.exit(app.exec_())
