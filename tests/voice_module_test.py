#!/usr/bin/env python3
"""
Simple Voice API Test Script
===========================
Tests basic voice API functionality
"""

import os
import sys
import requests
import time
import json
import tempfile

def main():
    print("Voice API Test Script")
    print("=====================")
    
    # 1. Check if API is running
    print("\nStep 1: Testing connection to Voice API...")
    try:
        response = requests.get("http://localhost:8100/status", timeout=5)
        if response.status_code == 200:
            print("✅ Voice API is running!")
            
            # Print some debug info
            data = response.json()
            print(f"TTS Engine: {data.get('tts_engine', 'unknown')}")
            print(f"Default Voice: {data.get('default_voice', 'unknown')}")
            print(f"Available Voices: {len(data.get('available_voices', {}))} voices")
            
            # Print debug info if available
            if 'debug_info' in data:
                print("\nDebug Info:")
                for key, value in data['debug_info'].items():
                    if isinstance(value, list) and len(value) > 10:
                        print(f"  {key}: {len(value)} items")
                    else:
                        print(f"  {key}: {value}")
        else:
            print(f"❌ Error: Voice API returned status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Error: {str(e)}")
        print("\nIs the Voice API running? Start it with:")
        print("cd services/voice && docker-compose up -d")
        return False
    
    # 2. List available voices
    print("\nStep 2: Fetching available voices...")
    try:
        response = requests.get("http://localhost:8100/voices", timeout=5)
        if response.status_code == 200:
            data = response.json()
            voices = data.get("voices", [])
            if voices:
                print(f"✅ Found {len(voices)} voices:")
                for voice in voices:
                    print(f"  - {voice}")
            else:
                print("❌ No voices found!")
                return False
        else:
            print(f"❌ Error: Voice API returned status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Error: {str(e)}")
        return False
    
    # 3. Test speech synthesis
    print("\nStep 3: Testing speech synthesis...")
    try:
        voice = data.get("default_voice", voices[0] if voices else None)
        if not voice:
            print("❌ No voice available for testing")
            return False
            
        print(f"Using voice: {voice}")
        test_text = "Hello, this is a test of the Piper Text to Speech system."
        
        response = requests.get(
            "http://localhost:8100/speak", 
            params={
                "text": test_text,
                "voice": voice,
                "speed": 1.0
            },
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Speech synthesis successful!")
            
            # Create a temporary file with proper permissions
            temp_dir = tempfile.gettempdir()
            output_file = os.path.join(temp_dir, "test_output.wav")
            
            # Save audio file for inspection
            with open(output_file, "wb") as f:
                f.write(response.content)
            
            print(f"Saved audio to {output_file}")
            
            # Try to play the audio
            print("Attempting to play audio...")
            try:
                if sys.platform == "win32":
                    os.system(f"start {output_file}")
                elif sys.platform == "darwin":
                    os.system(f"afplay {output_file}")
                else:
                    os.system(f"aplay {output_file}")
            except Exception as e:
                print(f"Could not play audio automatically: {e}")
                print(f"You can play it manually at: {os.path.abspath(output_file)}")
        else:
            print(f"❌ Error: Speech synthesis failed with status code {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Response: {response.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"❌ Error: {str(e)}")
        return False
    except PermissionError as e:
        print(f"❌ Permission error: {str(e)}")
        print("Try running the script with administrator privileges or in a directory with write permissions.")
        return False
    
    print("\nAll tests completed successfully! ✅")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)