"""
5️⃣ core.py – The AI Orchestration Engine
🔹 Purpose: Serves as the main entry point for running Sabrina’s AI loop.
🔹 Key Responsibilities:
✔ Initializes & integrates vision.py, automation.py, and hearing.py.
✔ Communicates with the voice API instead of directly accessing the voice module.
✔ Coordinates AI decision-making by processing voice, vision, and actions in real time.
✔ Manages data flow between modules for seamless automation.
✔ Implements logging and debugging for real-time monitoring.
🔹 Use Cases:
✅ Runs Sabrina’s main logic loop and keeps modules in sync.
✅ Processes voice and screen inputs to execute automated actions.
✅ Handles context-aware decision-making for AI-human interaction.
"""
import os
import json
import time
import logging
import requests
from services.automation.automation import Actions
from services.vision.vision_core import VisionCore
from services.hearing.hearing import Hearing

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

VOICE_API_URL = "http://localhost:8100/get_file_audio"  # URL of the voice API service

class SabrinaCore:
    def __init__(self):
        """Initialize the AI Orchestration Engine."""
        self.vision_core = VisionCore()
        self.hearing = Hearing()
        self.actions = Actions()
        self.memory_file = "memory.json"
        self.history = self.load_history()
        logging.info("Sabrina AI Core initialized.")
    
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
    
    def speak(self, text):
        """Send text to the voice API for TTS processing."""
        logging.info(f"Sending text to voice API: {text}")
        try:
            response = requests.get(VOICE_API_URL, params={"text": text})
            if response.status_code == 200:
                logging.info("Voice API successfully processed the request.")
            else:
                logging.error(f"Voice API error: {response.status_code}, {response.text}")
        except requests.RequestException as e:
            logging.error(f"Failed to reach Voice API: {e}")
    
    def process_command(self, command):
        """Process user commands for system control."""
        logging.info(f"Processing command: {command}")
        if command.lower() == "exit":
            logging.info("Exiting AI system.")
            return False
        elif command.startswith("!say"):
            response = command[5:]
            self.speak(response)
        elif command.startswith("!click"):
            self.actions.click()
        elif command.startswith("!move"):
            try:
                _, x, y = command.split()
                self.actions.move_mouse_to(int(x), int(y))
            except ValueError:
                logging.error("Invalid move command. Use: !move x y")
        elif command.startswith("!type"):
            text = command[6:]
            self.actions.type_text(text)
        else:
            logging.warning("Unknown command.")
        return True
    
    def run(self):
        """Main AI loop that listens, processes, and interacts."""
        logging.info("Sabrina is ready. Say a command or type '!exit' to quit.")
        running = True
        while running:
            user_input = self.hearing.listen()
            logging.info(f"User Input: {user_input}")
            print(f"You: {user_input}")
            
            screen_text = self.vision_ocr.run_ocr()  # Screen analysis
            logging.info(f"Screen OCR Detected: {screen_text}")
            print(f"Sabrina: {screen_text}")
            
            self.speak(screen_text)  # Send text to voice API
            self.update_memory(user_input, screen_text)
            running = self.process_command(user_input)
            
            time.sleep(1)  # Avoid excessive loop execution

if __name__ == "__main__":
    core = SabrinaCore()
    core.run()