# Fixing animation_main.py to correctly reference AnimationManager for animations
import sys
from PyQt5.QtWidgets import QApplication
from presence_gui import PresenceGUI

def run_animation_test():
    """Test function for animation queue with user input."""
    app = QApplication(sys.argv)
    window = PresenceGUI()
    window.show()

    # Retrieve animations from the animation manager
    animation_manager = window.animation_manager  # Get the animation manager instance
    animation_map = {str(i + 1): anim for i, anim in enumerate(animation_manager.animations.keys())}

    # Display instructions dynamically
    instructions = "\\nInstructions:\\nEnter a number or an animation state to queue an animation:\\n"
    for num, anim in animation_map.items():
        instructions += f"{num} - {anim}\\n"
    instructions += "Type 'exit' to quit.\\n"
    
    print(instructions)

    while True:
        user_input = input("Animation (number or state name): ").strip().lower()
        if user_input == "exit":
            break
        elif user_input in animation_map:
            animation_manager.queue_animation(animation_map[user_input])  # Use animation_manager for queueing
        elif user_input in animation_manager.animations:
            animation_manager.queue_animation(user_input)  # Use animation_manager for queueing
        else:
            print("Invalid input. Try again.")

    sys.exit(app.exec_())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    run_animation_test()
    sys.exit(app.exec_())
