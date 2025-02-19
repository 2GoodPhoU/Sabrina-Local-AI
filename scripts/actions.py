"""
Handles mouse/keyboard automation & PC interaction.
✅ actions.py (Handles Interactions)
move_mouse_to(object): Moves cursor to detected objects
click(): Clicks detected UI elements
press_key(key): Simulates keyboard input
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
def click_on_object(x, y):
    """Moves mouse and clicks a detected object"""
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()