"""
Handles text-to-speech (TTS) & voice commands.

✅ voice.py (Handles Speech)
speak(text): Uses TTS to narrate detected text
listen(): Captures voice commands for controlling Sabrina
Handles wake word detection for hands-free control
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
def speak(text):
    if text.startswith("!"):
        print(process_command(text))
        return
    
    settings = load_settings()
    ai_response = ask_sabrina(text)
    
    timestamp = int(time.time())
    output_file = os.path.join(output_dir, f"response_{timestamp}.wav")
    
    tts = TTS("tts_models/en/jenny/jenny", gpu=True)
    
    tts.tts_to_file(
        text=ai_response,
        file_path=output_file,
        speed=settings["speed"],  
        emotion=settings["emotion"]
    )
    
    if platform.system() == "Windows":
        process = subprocess.Popen([
            "ffplay", "-nodisp", "-autoexit", output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        process = subprocess.Popen(["afplay", output_file])
    
    process.wait()
    time.sleep(0.5)
    try:
        os.remove(output_file)
    except PermissionError:
        print(f"Warning: Unable to delete {output_file}. It might still be in use.")

