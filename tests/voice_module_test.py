#!/usr/bin/env python3
"""
Enhanced Voice Module Test Script for Sabrina AI
=======================================
This script tests the voice module components with auto-start and hidden playback.
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("voice_test")

# Ensure project directory is in Python path
script_dir = Path(__file__).parent.absolute()
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Voice Module Test")
    parser.add_argument("--no-auto-start", action="store_true", 
                      help="Disable auto-starting the voice service")
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging")
    parser.add_argument("--text", type=str, 
                      default="Hello, this is a test of the Sabrina voice system with auto-start and hidden playback.",
                      help="Text to speak for TTS test")
    parser.add_argument("--timeout", type=int, default=30,
                      help="Maximum time to wait for service to start (seconds)")
    parser.add_argument("--voices", action="store_true",
                      help="Show available voice settings")
    return parser.parse_args()

def test_voice_client(auto_start=True):
    """Test the enhanced VoiceAPIClient with auto-start"""
    try:
        from services.voice.voice_api_client import VoiceAPIClient
        
        logger.info("Creating VoiceAPIClient...")
        client = VoiceAPIClient(auto_start=auto_start)
        
        # Test connection (this will auto-start if needed and auto_start=True)
        logger.info("Testing connection...")
        connected = client.test_connection()
        
        if connected:
            logger.info("✓ VoiceAPIClient connected successfully")
        else:
            logger.error("✗ VoiceAPIClient connection test failed")
            return None
        
        return client
    except ImportError as e:
        logger.error(f"✗ Failed to import VoiceAPIClient: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"✗ Error in VoiceAPIClient test: {str(e)}")
        return None

def test_tts_with_client(client, text):
    """Test TTS using the VoiceAPIClient"""
    if not client:
        logger.error("No valid VoiceAPIClient provided")
        return False
    
    try:
        logger.info(f"Testing TTS with client using text: '{text}'")
        
        # Test speech
        result = client.speak(text)
        
        if result:
            logger.info("✓ TTS test with client successful")
            return True
        else:
            logger.error("✗ TTS test with client failed")
            return False
    except Exception as e:
        logger.error(f"✗ Error in TTS client test: {str(e)}")
        return False

def test_voice_settings(client):
    """Test different voice settings with Jenny voice"""
    if not client:
        logger.error("No valid VoiceAPIClient provided")
        return False
    
    try:
        logger.info("Testing Jenny voice settings...")
        
        # Save original settings
        original_settings = client.get_settings()
        
        # First, make sure we're using Jenny voice
        client.update_settings({"voice": "jenny"})
        client.speak("Hello, I am Jenny, the voice of Sabrina AI.")
        time.sleep(2)
        
        # Test different speeds
        logger.info("Testing different speeds with Jenny voice...")
        client.set_speed(1.5)
        client.speak("This is Jenny speaking at 1.5x speed.")
        time.sleep(2)
        
        client.set_speed(0.8)
        client.speak("This is Jenny speaking at 0.8x speed.")
        time.sleep(2)
        
        # Test different pitch
        logger.info("Testing different pitch settings with Jenny voice...")
        client.set_pitch(1.3)
        client.speak("This is Jenny with a higher pitch.")
        time.sleep(2)
        
        client.set_pitch(0.7)
        client.speak("This is Jenny with a lower pitch.")
        time.sleep(2)
        
        # Test different emotions with Jenny voice
        logger.info("Testing different emotions with Jenny voice...")
        emotions = ["happy", "sad", "angry", "excited", "calm"]
        for emotion in emotions:
            logger.info(f"Testing Jenny voice with {emotion} emotion...")
            client.set_emotion(emotion)
            client.speak(f"This is Jenny speaking with {emotion} emotion. How does it sound?")
            time.sleep(3)  # Give a bit more time to hear the emotions
        
        # Restore original settings
        logger.info("Restoring original voice settings...")
        client.update_settings(original_settings)
        client.speak("This is Jenny again with the original voice settings.")
        
        return True
    except Exception as e:
        logger.error(f"✗ Error testing Jenny voice settings: {str(e)}")
        # Try to restore original settings
        if 'original_settings' in locals():
            try:
                client.update_settings(original_settings)
            except:
                pass
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n===== Sabrina AI Voice Module Test =====\n")
    print("Testing enhanced voice module with auto-start and hidden playback")
    
    # Create voice client with auto-start (unless disabled)
    print("\nStep 1: Initializing Voice API Client (will auto-start if needed)...")
    client = test_voice_client(auto_start=not args.no_auto_start)
    
    if client:
        # Display current voice settings
        if args.voices:
            print("\nCurrent voice settings:")
            settings = client.get_settings()
            for key, value in settings.items():
                print(f"  {key}: {value}")
                
            # Try to get available voices from API
            try:
                import requests
                response = requests.get(f"{client.api_url}/status", timeout=5)
                if response.status_code == 200:
                    voices_info = response.json().get("available_voices", {})
                    if voices_info:
                        print("\nAvailable voices:")
                        for category, voices in voices_info.items():
                            print(f"  {category}:")
                            for voice in voices:
                                print(f"    - {voice}")
            except Exception as e:
                print(f"Could not retrieve voice information: {e}")
                
        # Test basic TTS
        print("\nStep 2: Testing text-to-speech...")
        tts_ok = test_tts_with_client(client, args.text)
        
        # Test voice settings variations if requested
        if args.voices and tts_ok:
            print("\nStep 3: Testing voice setting variations...")
            test_voice_settings(client)
        
        # Print summary
        print("\n===== Test Results =====")
        print(f"Voice API: {'✓ Running' if client.connected else '✗ Not Running'}")
        print(f"TTS Client Test: {'✓ OK' if tts_ok else '✗ Issues Found'}")
        
        # Final result
        if client.connected and tts_ok:
            print("\n✓ Voice module is working correctly with auto-start and hidden playback!")
            return 0
        else:
            print("\n✗ Issues were found with the voice module.")
            
            # Provide troubleshooting tips
            print("\nTroubleshooting Tips:")
            if not client.connected:
                print("- Check if the Voice API is running on: http://localhost:8100")
                print("- Look for errors in the Voice API logs")
            if not tts_ok:
                print("- Verify TTS engine installation")
                print("- Check if audio playback is working on your system")
            
            return 1
    else:
        print("\n✗ Cannot proceed with tests because Voice API client initialization failed.")
        print("\nTroubleshooting Tips:")
        print("- Make sure the voice_api_client.py module is present in services/voice/")
        print("- Try running the Voice API manually: python services/voice/voice_api.py")
        print("- Check for any Python import errors or missing dependencies")
        return 1

if __name__ == "__main__":
    sys.exit(main())