#!/usr/bin/env python3
"""
Enhanced Voice Module Test Script for Sabrina AI with Piper TTS
=======================================
This script tests the voice module components with Piper TTS integration.
"""

import os
import sys
import time
import logging
import argparse
import requests
import json
import subprocess
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
    parser = argparse.ArgumentParser(description="Sabrina AI Voice Module Test with Piper TTS")
    parser.add_argument("--no-auto-start", action="store_true", 
                      help="Disable auto-starting the voice service")
    parser.add_argument("--debug", action="store_true", 
                      help="Enable debug logging")
    parser.add_argument("--text", type=str, 
                      default="Hello, this is a test of Sabrina's voice system using Piper TTS. How does it sound?",
                      help="Text to speak for TTS test")
    parser.add_argument("--timeout", type=int, default=30,
                      help="Maximum time to wait for service to start (seconds)")
    parser.add_argument("--download-voices", action="store_true",
                      help="Download additional voice models")
    parser.add_argument("--test-all-voices", action="store_true",
                      help="Test all available voices")
    return parser.parse_args()

def test_voice_client(auto_start=True):
    """Test the enhanced VoiceAPIClient with Piper TTS"""
    try:
        from services.voice.voice_api_client import VoiceAPIClient
        
        logger.info("Creating VoiceAPIClient...")
        client = VoiceAPIClient(auto_start=auto_start)
        
        # Test connection (this will auto-start if needed and auto_start=True)
        logger.info("Testing connection...")
        connected = client.test_connection()
        
        if connected:
            logger.info("✓ VoiceAPIClient connected successfully")
            
            # Fetch available voices
            available_voices = client.get_available_voices()
            logger.info(f"Found {len(available_voices)} available voices")
            
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
    """Test TTS using the VoiceAPIClient with Piper TTS"""
    if not client:
        logger.error("No valid VoiceAPIClient provided")
        return False
    
    try:
        logger.info(f"Testing TTS with Piper using text: '{text}'")
        
        # Test speech
        result = client.speak(text)
        
        if result:
            logger.info("✓ TTS test with Piper successful")
            return True
        else:
            logger.error("✗ TTS test with Piper failed")
            return False
    except Exception as e:
        logger.error(f"✗ Error in TTS client test: {str(e)}")
        return False

def test_all_voices(client, sample_text="This is a test of the Piper text to speech system."):
    """Test all available voices with a sample text"""
    if not client or not client.connected:
        logger.error("Cannot test voices - client not connected")
        return False
    
    try:
        # Get available voices
        voices = client.get_available_voices()
        if not voices:
            logger.error("No voices available to test")
            return False
        
        logger.info(f"Testing {len(voices)} voices with sample text: '{sample_text}'")
        
        # Save original voice setting
        original_voice = client.settings.get("voice")
        
        # Test each voice
        for voice in voices:
            logger.info(f"Testing voice: {voice}")
            client.set_voice(voice)
            result = client.speak(f"This is the {voice} voice in Piper. {sample_text}")
            
            if result:
                logger.info(f"✓ Voice test successful: {voice}")
                # Wait for audio to complete to avoid overlapping
                time.sleep(2)
            else:
                logger.error(f"✗ Voice test failed: {voice}")
                
        # Restore original voice
        if original_voice:
            client.set_voice(original_voice)
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing voices: {str(e)}")
        return False

def download_additional_voices(client):
    """Download additional voice models for Piper TTS"""
    if not client or not client.connected:
        logger.error("Cannot download voices - client not connected")
        return False
    
    try:
        import requests
        
        # Check for tqdm
        try:
            from tqdm import tqdm
        except ImportError:
            print("Installing tqdm for progress bars...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
            from tqdm import tqdm
        
        # Get API status to find models directory
        response = requests.get(f"{client.api_url}/status", timeout=10)
        if response.status_code != 200:
            logger.error("Failed to get API status")
            return False
        
        models_directory = response.json().get("models_directory", "models/piper")
        
        # Voice model options
        voices_to_download = [
            # English voices
            {"lang": "en", "region": "US", "name": "ryan", "quality": "medium"},
            {"lang": "en", "region": "GB", "name": "alan", "quality": "medium"},
            # Additional voices (uncomment to download)
            # {"lang": "fr", "region": "FR", "name": "siwis", "quality": "medium"},
            # {"lang": "de", "region": "DE", "name": "thorsten", "quality": "medium"},
            # {"lang": "es", "region": "ES", "name": "mls_10246", "quality": "medium"},
        ]
        
        # Ensure the models directory exists on the host machine
        host_models_dir = os.path.join(project_dir, "services/voice/models/piper")
        os.makedirs(host_models_dir, exist_ok=True)
        
        downloaded_count = 0
        for voice in voices_to_download:
            lang = voice["lang"]
            region = voice["region"]
            name = voice["name"]
            quality = voice["quality"]
            
            # Create URL for model download
            model_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{lang}_{region}/{name}/{quality}/{lang}_{region}-{name}-{quality}.onnx"
            config_url = f"{model_url}.json"
            
            # Create paths
            model_filename = f"{lang}_{region}-{name}-{quality}.onnx"
            config_filename = f"{model_filename}.json"
            model_path = os.path.join(host_models_dir, model_filename)
            config_path = os.path.join(host_models_dir, config_filename)
            
            # Download if not exists
            if not os.path.exists(model_path):
                logger.info(f"Downloading voice model: {model_filename}")
                try:
                    # Download model file
                    response = requests.get(model_url, stream=True)
                    if response.status_code == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        with open(model_path, 'wb') as f, tqdm(
                                desc=model_filename,
                                total=total_size,
                                unit='B',
                                unit_scale=True,
                                unit_divisor=1024,
                            ) as bar:
                            for data in response.iter_content(chunk_size=1024):
                                size = f.write(data)
                                bar.update(size)
                        
                        # Download config file
                        config_response = requests.get(config_url)
                        if config_response.status_code == 200:
                            with open(config_path, 'wb') as f:
                                f.write(config_response.content)
                                
                            logger.info(f"Successfully downloaded: {model_filename}")
                            downloaded_count += 1
                        else:
                            logger.error(f"Failed to download config for {model_filename}: {config_response.status_code}")
                    else:
                        logger.error(f"Failed to download {model_filename}: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error downloading {model_filename}: {str(e)}")
            else:
                logger.info(f"Voice model already exists: {model_filename}")
                
        # Refresh available voices in the client
        if downloaded_count > 0:
            client._fetch_available_voices()
            logger.info(f"Successfully downloaded {downloaded_count} new voice models")
            return True
        else:
            logger.info("No new voice models downloaded")
            return False
            
    except Exception as e:
        logger.error(f"Error downloading voice models: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n===== Sabrina AI Voice Module Test with Piper TTS =====\n")
    print("Testing enhanced voice module with Piper TTS integration")
    
    # Create voice client with auto-start (unless disabled)
    print("\nStep 1: Initializing Voice API Client (will auto-start if needed)...")
    client = test_voice_client(auto_start=not args.no_auto_start)
    
    if client:
        # If requested, download additional voices
        if args.download_voices:
            print("\nDownloading additional voice models...")
            try:
                from tqdm import tqdm
            except ImportError:
                print("Installing tqdm for download progress bars...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
                from tqdm import tqdm
                
            download_success = download_additional_voices(client)
        
        # Display current voice settings
        print("\nCurrent voice settings:")
        settings = client.get_settings()
        for key, value in settings.items():
            print(f"  {key}: {value}")
            
        print("\nAvailable voices:")
        voices = client.get_available_voices()
        if voices:
            for voice in voices:
                print(f"  - {voice}")
        else:
            print("  No voices available")
                
        # Test basic TTS
        print("\nStep 2: Testing text-to-speech with Piper...")
        tts_ok = test_tts_with_client(client, args.text)
        
        # Test all voices if requested
        if args.test_all_voices and tts_ok:
            print("\nStep 3: Testing all available voices...")
            test_all_voices(client)
        
        # Print summary
        print("\n===== Test Results =====")
        print(f"Voice API: {'✓ Running' if client.connected else '✗ Not Running'}")
        print(f"TTS Client Test: {'✓ OK' if tts_ok else '✗ Issues Found'}")
        print(f"Voice Count: {len(client.get_available_voices())}")
        
        # Final result
        if client.connected and tts_ok:
            print("\n✓ Piper TTS voice module is working correctly!")
            return 0
        else:
            print("\n✗ Issues were found with the Piper TTS voice module.")
            
            # Provide troubleshooting tips
            print("\nTroubleshooting Tips:")
            if not client.connected:
                print("- Check if the Voice API is running on: http://localhost:8100")
                print("- Look for errors in the Voice API logs")
                print("- Verify that Piper has been installed in the container")
            if not tts_ok:
                print("- Check if piper binary is available in the container")
                print("- Make sure voice models are properly installed")
                print("- Verify that the audio system is working")
            
            return 1
    else:
        print("\n✗ Cannot proceed with tests because Voice API client initialization failed.")
        print("\nTroubleshooting Tips:")
        print("- Make sure the voice_api_client.py module is present in services/voice/")
        print("- Try running the Voice API manually: python services/voice/voice_api.py")
        print("- Check for Docker errors if using containerized deployment")
        print("- Ensure Piper TTS is installed in the container")
        return 1

if __name__ == "__main__":
    sys.exit(main())