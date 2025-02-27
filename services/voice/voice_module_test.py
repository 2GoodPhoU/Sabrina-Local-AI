#!/usr/bin/env python3
"""
Voice Module Test Script for Sabrina AI
=======================================
This script tests the voice module components independently to identify issues.
"""

import os
import sys
import time
import json
import logging
import argparse
import requests
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
    parser = argparse.ArgumentParser(description="Sabrina AI Voice Module Test")
    parser.add_argument("--start-service", action="store_true", 
                      help="Start the voice service if not running")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--text", type=str, default="Hello, this is a test of the Sabrina voice system.",
                      help="Text to speak for TTS test")
    return parser.parse_args()

def check_directories():
    """Ensure required directories exist"""
    dirs = ["logs", "data", "config"]
    for d in dirs:
        os.makedirs(project_dir / d, exist_ok=True)
    logger.info("Required directories exist")

def check_python_dependencies():
    """Check if required Python packages are installed"""
    required_packages = [
        "fastapi", "uvicorn", "requests", "TTS", "pydub"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"✗ {package} is not installed")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.error("Install them using: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_system_dependencies():
    """Check if required system dependencies are installed"""
    system_deps = {
        "ffmpeg": "ffmpeg -version",
        "aplay": "which aplay" if sys.platform != "win32" else "echo aplay not needed on Windows"
    }
    
    all_installed = True
    for name, command in system_deps.items():
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✓ {name} is installed")
            else:
                logger.warning(f"✗ {name} is not installed or not in PATH")
                all_installed = False
        except Exception as e:
            logger.error(f"Error checking {name}: {str(e)}")
            all_installed = False
    
    return all_installed

def check_voice_service():
    """Check if the voice service is running"""
    try:
        response = requests.get("http://localhost:8100/status", timeout=1.0)
        if response.status_code == 200:
            logger.info("✓ Voice service is running")
            try:
                info = response.json()
                logger.info(f"Service info: {info}")
                return True
            except json.JSONDecodeError:
                logger.warning("Voice service response is not valid JSON")
                return True
        else:
            logger.warning(f"✗ Voice service returned status code {response.status_code}")
            return False
    except requests.RequestException as e:
        logger.error(f"✗ Voice service is not running: {str(e)}")
        return False

def start_voice_service():
    """Start the voice service"""
    voice_api_path = project_dir / "voice" / "voice_api.py"
    
    if not voice_api_path.exists():
        logger.error(f"Voice API script not found at {voice_api_path}")
        return False
    
    try:
        # Start the service as a background process
        logger.info("Starting voice service...")
        
        if sys.platform == "win32":
            # Windows
            process = subprocess.Popen(
                ["start", "python", str(voice_api_path)],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            # Linux/Mac
            process = subprocess.Popen(
                ["python", str(voice_api_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        
        # Give it time to start
        logger.info("Waiting for voice service to start (10 seconds)...")
        for i in range(10):
            time.sleep(1)
            print(".", end="", flush=True)
            
            # Check if it's running
            try:
                if check_voice_service():
                    print()
                    logger.info("Voice service started successfully")
                    return True
            except:
                pass
        
        print()
        logger.warning("Voice service did not start properly in the allotted time")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start voice service: {str(e)}")
        return False

def test_voice_client():
    """Test the VoiceAPIClient"""
    try:
        from services.voice.voice_api_client import VoiceAPIClient
        
        logger.info("Creating VoiceAPIClient...")
        client = VoiceAPIClient()
        
        # Test connection
        logger.info("Testing connection...")
        connected = client.test_connection()
        
        if connected:
            logger.info("✓ VoiceAPIClient connected successfully")
        else:
            logger.error("✗ VoiceAPIClient connection test failed")
            return False
        
        return True
    except ImportError as e:
        logger.error(f"✗ Failed to import VoiceAPIClient: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ Error in VoiceAPIClient test: {str(e)}")
        return False

def test_direct_api(text):
    """Test the voice API directly with requests"""
    try:
        logger.info(f"Testing direct API call with text: '{text}'")
        
        # Encode the text for URL
        import urllib.parse
        encoded_text = urllib.parse.quote(text)
        
        # Make the API call
        response = requests.get(
            f"http://localhost:8100/speak?text={encoded_text}&speed=1.0&pitch=1.0&emotion=normal",
            timeout=20.0
        )
        
        if response.status_code == 200:
            logger.info("✓ Direct API test successful")
            
            # Check if we got audio data
            content_type = response.headers.get("Content-Type", "")
            if "audio" in content_type:
                logger.info(f"✓ Received audio data ({len(response.content)} bytes)")
                
                # Save the audio to a file
                audio_file = project_dir / "data" / "test_output.wav"
                with open(audio_file, "wb") as f:
                    f.write(response.content)
                logger.info(f"✓ Saved audio to {audio_file}")
                
                # Play the audio if possible
                try:
                    play_audio(audio_file)
                except Exception as e:
                    logger.error(f"Failed to play audio: {str(e)}")
            else:
                logger.warning(f"Unexpected content type: {content_type}")
            
            return True
        else:
            logger.error(f"✗ API request failed with status code {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"✗ Error in direct API test: {str(e)}")
        return False

def test_tts_with_client(text):
    """Test TTS using the VoiceAPIClient"""
    try:
        from services.voice.voice_api_client import VoiceAPIClient
        
        logger.info(f"Testing TTS with client using text: '{text}'")
        
        # Create client
        client = VoiceAPIClient()
        
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

def play_audio(audio_file):
    """Play an audio file using the appropriate method for the platform"""
    if not os.path.exists(audio_file):
        logger.error(f"Audio file not found: {audio_file}")
        return False
    
    logger.info(f"Playing audio file: {audio_file}")
    
    try:
        if sys.platform == "win32":
            # Windows
            os.startfile(audio_file)
        elif sys.platform == "darwin":
            # macOS
            subprocess.call(["afplay", audio_file])
        else:
            # Linux
            subprocess.call(["aplay", audio_file])
        
        logger.info("✓ Audio playback started")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to play audio: {str(e)}")
        return False

def main():
    """Main function"""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n===== Sabrina AI Voice Module Test =====\n")
    
    # Check environment
    print("Step 1: Checking environment...")
    check_directories()
    
    print("\nStep 2: Checking Python dependencies...")
    python_deps_ok = check_python_dependencies()
    
    print("\nStep 3: Checking system dependencies...")
    system_deps_ok = check_system_dependencies()
    
    print("\nStep 4: Checking if voice service is running...")
    service_running = check_voice_service()
    
    # Start the service if requested and not already running
    if not service_running and args.start_service:
        print("\nStep 5: Starting voice service...")
        service_running = start_voice_service()
    elif not service_running and not args.start_service:
        print("\nVoice service not running. Run with --start-service to attempt to start it.")
        print("Alternatively, run the following command in another terminal:")
        print(f"python {project_dir}/services/voice/voice_api.py")
        return 1
    
    # Only continue with tests if service is running
    if service_running:
        print("\nStep 6: Testing VoiceAPIClient...")
        client_ok = test_voice_client()
        
        print("\nStep 7: Testing direct API call...")
        api_ok = test_direct_api(args.text)
        
        print("\nStep 8: Testing TTS with client...")
        tts_ok = test_tts_with_client(args.text)
        
        # Print summary
        print("\n===== Test Results =====")
        print(f"Python Dependencies: {'✓ OK' if python_deps_ok else '✗ Issues Found'}")
        print(f"System Dependencies: {'✓ OK' if system_deps_ok else '✗ Issues Found'}")
        print(f"Voice Service: {'✓ Running' if service_running else '✗ Not Running'}")
        print(f"VoiceAPIClient: {'✓ OK' if client_ok else '✗ Issues Found'}")
        print(f"Direct API Test: {'✓ OK' if api_ok else '✗ Issues Found'}")
        print(f"TTS Client Test: {'✓ OK' if tts_ok else '✗ Issues Found'}")
        
        # Final result
        if all([python_deps_ok, system_deps_ok, service_running, client_ok, api_ok, tts_ok]):
            print("\n✓ Voice module is working correctly!")
            return 0
        else:
            print("\n✗ Issues were found with the voice module.")
            
            # Provide troubleshooting tips
            print("\nTroubleshooting Tips:")
            if not python_deps_ok:
                print("- Install missing Python dependencies with pip")
            if not system_deps_ok:
                print("- Install required system tools (ffmpeg, etc.)")
            if not service_running:
                print("- Start the voice service with: python services/voice/voice_api.py")
            if not client_ok:
                print("- Check voice_api_client.py for errors")
            if not api_ok:
                print("- Check if voice_api.py is properly configured")
            if not tts_ok:
                print("- Verify TTS engine installation")
            
            return 1
    else:
        print("\n✗ Cannot proceed with tests because voice service is not running.")
        return 1

if __name__ == "__main__":
    sys.exit(main())