"""
🚀 Summary:
1️⃣ Sabrina sees your entire screen & switches to specific apps dynamically
2️⃣ She detects text (OCR) & objects (YOLOv8) in real-time
3️⃣ She clicks buttons, presses keys, or runs scripts automatically
4️⃣ She talks while performing actions, making her feel more interactive

Main orchestration file (integrates vision.py, voice.py, actions.py).
✅ core.py (Main Entry Point)
Initializes vision.py, voice.py, and actions.py
Ensures all modules work together in real-time
Runs Sabrina’s AI loop
"""
from ultralytics import YOLO
import numpy as np
import platform
import os
import pygetwindow as gw
import time
import mss
import pytesseract
import pyautogui
import cv2
from TTS.api import TTS
from pydub import AudioSegment
import json
from ollama import Client  # Connect with AI model
import subprocess
def load_defaults():
    if os.path.exists(defaults_file):
        with open(defaults_file, "r") as f:
            return json.load(f)
    return {}

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r") as f:
            settings = json.load(f)
        return {**DEFAULT_SETTINGS, **settings}  # Merge defaults with stored settings
    return DEFAULT_SETTINGS

def save_settings(settings):
    with open(settings_file, "w") as f:
        json.dump(settings, f)

def load_history():
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
        return history if history else [load_defaults()]
    return [load_defaults()]

def save_history(history):
    with open(history_file, "w") as f:
        json.dump(history, f)

def update_memory(user_input, ai_response):
    history = load_history()
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": ai_response})
    relevant_history = history[-20:]  # Keep the last 20 exchanges
    save_history(relevant_history)

def process_command(command):
    settings = load_settings()
    parts = command.split()
    if len(parts) == 2 and parts[0] in ["!speed", "!emotion", "!pitch"]:
        key = parts[0][1:]
        try:
            value = float(parts[1]) if key in ["speed", "pitch"] else parts[1]
            settings[key] = value
            save_settings(settings)
            return f"Updated {key} to {value}"
        except ValueError:
            return "Invalid value!"
    elif command == "!reset":
        save_settings(DEFAULT_SETTINGS)
        return "Voice settings reset!"
    elif command == "!forget":
        save_history([load_defaults()])
        return "Memory reset to defaults!"
    return "Unknown command."

def ask_sabrina(user_input):
    history = load_history()
    context = history[-5:] + [{"role": "system", "content": json.dumps(load_defaults())}]
    response = ollama.chat(model="mistral", messages=context + [{"role": "user", "content": user_input}])
    ai_response = response["message"]["content"]
    update_memory(user_input, ai_response)
    return ai_response

def main():
    print("Sabrina is ready. Type your message or some commands like '!speed 1.2', '!emotion happy', '!forget'. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        speak(user_input)

if __name__ == "__main__":
    main()
def get_active_window_region():
    """Gets the active application window region"""
    active_win = gw.getActiveWindow()
    if active_win:
        return {
            "top": active_win.top,
            "left": active_win.left,
            "width": active_win.width,
            "height": active_win.height
        }
    return None

def capture_screen(region=None):
    """Capture the entire screen or a specific region"""
    with mss.mss() as sct:
        screenshot = sct.grab(region if region else sct.monitors[1])
        img = np.array(screenshot)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

