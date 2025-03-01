#!/usr/bin/env python3
"""
Voice API Repair Test Script
============================
This script verifies the Voice API is working properly after fixes
"""

import requests
import json
import os
import sys
import tempfile
import subprocess
import time

def main():
    print("\n=== Sabrina Voice API Verification Test ===\n")
    
    # Step 1: Check API status
    print("Step 1: Checking Voice API status...")
    try:
        response = requests.get("http://localhost:8100/status", timeout=5)
        if response.status_code == 200:
            print("✅ Voice API is running")
            data = response.json()
            
            # Print key information
            print(f"TTS Engine: {data.get('tts_engine', 'unknown')}")
            print(f"Engine installed: {data.get('tts_engine_installed', False)}")
            print(f"Default voice: {data.get('default_voice', 'unknown')}")
            print(f"Voice count: {data.get('voice_count', 0)} voices")
            
            # Check models directory content
            debug_info = data.get('debug_info', {})
            model_files = debug_info.get('model_files', [])
            print(f"\nModel files found: {len(model_files)}")
            
            # Check if any model exists
            model_exists = debug_info.get('model_exists', False)
            if model_exists:
                print("✅ Voice model exists and can be loaded")
            else:
                print("❌ Voice model not found or cannot be loaded")
        else:
            print(f"❌ Error: API returned status code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error connecting to Voice API: {str(e)}")
        print("Is the Voice API running? Try restarting it with 'docker restart sabrina-voice-api'")
        return False
    
    # Step 2: Test voice synthesis
    print("\nStep 2: Testing voice synthesis...")
    try:
        test_text = "Hello, this is a test of the Sabrina voice system."
        response = requests.get(
            "http://localhost:8100/speak",
            params={"text": test_text},
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ Voice synthesis successful!")
            
            # Save to temporary file
            temp_file = os.path.join(tempfile.gettempdir(), "sabrina_test.wav")
            with open(temp_file, "wb") as f:
                f.write(response.content)
            
            print(f"Saved audio to: {temp_file}")
            audio_size = os.path.getsize(temp_file) / 1024
            print(f"Audio file size: {audio_size:.2f} KB")
            
            # Try to play the audio
            print("\nPlaying audio...")
            try:
                if sys.platform == "win32":
                    os.system(f"start {temp_file}")
                elif sys.platform == "darwin":
                    subprocess.run(["afplay", temp_file])
                else:
                    subprocess.run(["aplay", temp_file])
            except Exception as e:
                print(f"Could not play audio automatically: {e}")
            
            return True
        else:
            print(f"❌ Voice synthesis failed with status code {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Error during synthesis test: {str(e)}")
        return False

if __name__ == "__main__":
    # Wait a moment to ensure container is ready if just restarted
    time.sleep(2)
    success = main()
    sys.exit(0 if success else 1)