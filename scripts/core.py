"""
5️⃣ core.py – The AI Orchestration Engine
🔹 Purpose: Serves as the main entry point for running Sabrina’s AI loop.
🔹 Key Responsibilities:
✔ Initializes & integrates vision.py, voice.py, actions.py, and hearing.py.
✔ Coordinates AI decision-making by processing voice, vision, and actions in real time.
✔ Manages data flow between modules for seamless automation.
🔹 Use Cases:
✅ Runs Sabrina’s main logic loop and keeps modules in sync.
✅ Processes voice and screen inputs to execute automated actions.
✅ Handles context-aware decision-making for AI-human interaction.
"""
import os
import json
import time
from actions import Actions
from scripts.vision import Vision
from scripts.voice import Voice
from hearing import Hearing

class SabrinaCore:
    def __init__(self):
        """Initialize the AI Orchestration Engine."""
        self.vision = Vision()
        self.voice = Voice()
        self.hearing = Hearing()
        self.actions = Actions()
        self.memory_file = "memory.json"
        self.history = self.load_history()
        
    def load_history(self):
        """Load conversation history from a file."""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                return json.load(f)
        return []
    
    def save_history(self):
        """Save the conversation history to a file."""
        with open(self.memory_file, "w") as f:
            json.dump(self.history, f)
    
    def update_memory(self, user_input, ai_response):
        """Update conversation memory with user input and AI response."""
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": ai_response})
        self.history = self.history[-20:]  # Keep only the last 20 exchanges
        self.save_history()
    
    def process_command(self, command):
        """Process user commands for system control."""
        if command.lower() == "exit":
            print("Exiting...")
            return False
        elif command.startswith("!say"):
            response = command[5:]
            self.voice.speak(response)
        elif command.startswith("!click"):
            self.actions.click()
        elif command.startswith("!move"):
            try:
                _, x, y = command.split()
                self.actions.move_mouse_to(int(x), int(y))
            except ValueError:
                print("Invalid move command. Use: !move x y")
        elif command.startswith("!type"):
            text = command[6:]
            self.actions.type_text(text)
        else:
            print("Unknown command.")
        return True
    
    def run(self):
        """Main AI loop that listens, processes, and interacts."""
        print("Sabrina is ready. Say a command or type '!exit' to quit.")
        running = True
        while running:
            user_input = self.hearing.listen()
            print(f"You: {user_input}")
            response = self.vision.run_ocr()  # Assume OCR is being used for text response
            print(f"Sabrina: {response}")
            self.voice.speak(response)
            self.update_memory(user_input, response)
            running = self.process_command(user_input)
            time.sleep(1)  # Avoid excessive loop execution

if __name__ == "__main__":
    core = SabrinaCore()
    core.run()
