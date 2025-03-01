#!/usr/bin/env python3
"""
Voice Models Debug Script
========================
This script inspects the voice models directory and prints what's actually available
"""

import os
import glob

import subprocess
import json


def check_voice_files():
    """Check what voice model files exist in the expected locations"""
    print("Voice Models Debug Script")
    print("========================")

    # Check models in Docker container
    print("\nChecking if Docker container is running...")
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=sabrina-voice-api",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
        )
        if "sabrina-voice-api" in result.stdout:
            print("Voice API container is running")

            # Get list of files in the container
            print("\nFiles in container's models directory:")
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "sabrina-voice-api",
                    "ls",
                    "-la",
                    "/app/models/piper/",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"Error listing files in container: {result.stderr}")
        else:
            print("Voice API container is not running")
    except Exception as e:
        print(f"Error checking Docker: {str(e)}")

    # Check local models directory
    print("\nChecking local model files...")

    # Try multiple possible locations
    possible_paths = [
        "./models/piper",
        "./services/voice/models/piper",
        "../models/piper",
        "../services/voice/models/piper",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found models directory at: {path}")

            # List all files
            print("\nFiles in local models directory:")
            for file in os.listdir(path):
                file_path = os.path.join(path, file)
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
                print(f"  {file} ({file_size:.2f} MB)")

            # Check specifically for .onnx files
            print("\nONNX model files:")
            onnx_files = glob.glob(f"{path}/*.onnx")
            if onnx_files:
                for file in onnx_files:
                    print(f"  {os.path.basename(file)}")
            else:
                print("  No ONNX model files found")

            # Check for JSON config files
            print("\nJSON config files:")
            json_files = glob.glob(f"{path}/*.json")
            if json_files:
                for file in json_files:
                    print(f"  {os.path.basename(file)}")

                    # Try to read the JSON to see what voice it's for
                    try:
                        with open(file, "r") as f:
                            config = json.load(f)
                            if "name" in config:
                                print(f"    Voice name in config: {config['name']}")
                    except Exception as e:
                        print(f"Error: {str(e)}")
                        pass
            else:
                print("  No JSON config files found")

            # Found a valid directory, no need to check others
            break
    else:
        print("No models directory found in expected locations")

    # Check current voice settings
    print("\nChecking current voice settings...")
    settings_paths = [
        "./voice_settings.json",
        "./services/voice/voice_settings.json",
        "../voice_settings.json",
        "../services/voice/voice_settings.json",
        "./config/voice_settings.json",
        "../config/voice_settings.json",
    ]

    for path in settings_paths:
        if os.path.exists(path):
            print(f"Found voice settings at: {path}")
            try:
                with open(path, "r") as f:
                    settings = json.load(f)
                    print(f"Current voice settings: {json.dumps(settings, indent=2)}")
            except Exception as e:
                print(f"Error reading settings file: {str(e)}")
            break
    else:
        print("No voice settings file found")

    # Get status from API if it's running
    print("\nChecking Voice API status...")
    try:
        import requests

        response = requests.get("http://localhost:8100/status", timeout=2)
        if response.status_code == 200:
            print("Voice API response:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"API returned status code: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Voice API: {str(e)}")


if __name__ == "__main__":
    check_voice_files()
