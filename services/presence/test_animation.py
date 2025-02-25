import sys
import time
from PyQt5.QtWidgets import QApplication
from animation_handler import AnimationHandler

def run_animation_test():
    """Test function for animation queue and priority system."""
    app = QApplication(sys.argv)
    window = AnimationHandler()
    window.show()

    # Test animation switching with delays
    time.sleep(1)
    window.queue_animation("listening")
    time.sleep(2)
    window.queue_animation("talking")
    time.sleep(3)
    window.queue_animation("working")
    time.sleep(2)
    window.queue_animation("idle")

    sys.exit(app.exec_())

if __name__ == "__main__":
    run_animation_test()
