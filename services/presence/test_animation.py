import sys
import os
from PyQt5.QtWidgets import QApplication
from animation_handler import AnimationHandler

def run_animation_test():
    """Test function for animation queue with user input."""
    app = QApplication(sys.argv)
    window = AnimationHandler()
    window.show()

    # Dynamically load available animations
    animation_map = {str(i + 1): anim for i, anim in enumerate(window.animations.keys())}

    # Display instructions dynamically
    instructions = "\nInstructions:\nEnter a number or an animation state to queue an animation:\n"
    for num, anim in animation_map.items():
        instructions += f"{num} - {anim}\n"
    instructions += "Type 'exit' to quit.\n"
    
    print(instructions)

    while True:
        user_input = input("Animation (number or state name): ").strip().lower()
        if user_input == "exit":
            break
        elif user_input in animation_map:
            window.queue_animation(animation_map[user_input])
        elif user_input in window.animations:
            window.queue_animation(user_input)
        else:
            print("Invalid input. Try again.")

    sys.exit(app.exec_())

if __name__ == "__main__":
    run_animation_test()
