#!/usr/bin/env python3
"""
Update Voice Settings Script
===========================
This script updates the voice_settings.json file to use the preferred voices
"""

import os
import json
import glob


def update_settings():
    """Update voice settings to use preferred voices"""
    print("Voice Settings Update Script")
    print("===========================")

    # Define preferred voices in order of preference
    preferred_voices = [
        "en_US-amy-medium",  # Confident female voice
        "en_US-kathleen-medium",  # Alternative female voice
        "en_US-jenny-medium",  # Another female voice option
    ]

    # Possible locations for settings file
    settings_paths = [
        "./voice_settings.json",
        "./services/voice/voice_settings.json",
        "./config/voice_settings.json",
    ]

    # Find the settings file
    settings_file = None
    for path in settings_paths:
        if os.path.exists(path):
            settings_file = path
            print(f"Found settings at: {path}")
            break

    if not settings_file:
        # Create a settings file if none exists
        settings_file = "./services/voice/voice_settings.json"
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        print(f"No settings found, creating new file: {settings_file}")

    # Create or load settings
    settings = {
        "speed": 1.0,
        "pitch": 1.05,
        "emotion": "normal",
        "volume": 0.85,
        "voice": None,
    }

    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                current_settings = json.load(f)
                # Preserve existing settings
                for key, value in current_settings.items():
                    if key in settings:
                        settings[key] = value
        except Exception as e:
            print(f"Error reading settings file: {str(e)}")

    # Look for model files to find which voices are available
    models_paths = ["./models/piper", "./services/voice/models/piper"]

    available_voices = []
    for models_dir in models_paths:
        if os.path.exists(models_dir):
            print(f"Checking for models in: {models_dir}")
            # Look for .onnx files
            for file_path in glob.glob(f"{models_dir}/*.onnx"):
                voice_name = os.path.basename(file_path)[:-5]  # Remove .onnx extension
                available_voices.append(voice_name)
                print(f"Found voice model: {voice_name}")

    # Find best voice to use
    selected_voice = None

    # First try to use a preferred voice that's available
    for voice in preferred_voices:
        if voice in available_voices:
            selected_voice = voice
            print(f"Selected preferred voice: {voice}")
            break

    # If no preferred voices are available, use first available or fallback
    if not selected_voice:
        if available_voices:
            selected_voice = available_voices[0]
            print(f"Using available voice: {selected_voice}")
        else:
            # Fallback to a preferred voice even if we didn't find the model file
            selected_voice = preferred_voices[0]
            print(f"No voices found, using fallback: {selected_voice}")

    # Update the settings
    settings["voice"] = selected_voice

    # Save the updated settings
    try:
        with open(settings_file, "w") as f:
            json.dump(settings, f, indent=2)
        print(f"Updated settings saved to: {settings_file}")
        print(f"Voice set to: {selected_voice}")
    except Exception as e:
        print(f"Error saving settings: {str(e)}")
        return False

    return True


if __name__ == "__main__":
    update_settings()
