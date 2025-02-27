#!/usr/bin/env python3
"""
Enhanced Voice Module Test Script for Sabrina AI
=======================================
This script tests the voice module components independently with improved service startup.
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

# Import the service starter if available
try:
    from utilities.service_starter import start_voice_api
    service_starter_available = True
except ImportError:
    service_starter_available = False

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sabrina AI Voice Module Test")
    parser.add_argument("--start-service", action="store_true", 
                      help="Start the voice service if not running")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--text", type=str, default="Hello, this is a test of the Sabrina voice system.",
                      help="Text to speak for TTS test")
    parser.add_argument("--timeout", type=int, default=30,
                      help="Maximum time to wait for service to start (seconds)")
    return parser.parse_args()

def start_voice_service_with_verification(timeout=30, check_interval=1.0):
    """
    Start the voice service and verify it's running properly
    
    Args:
        timeout: Maximum time to wait for service (seconds)
        check_interval: Time between status checks (seconds)
        
    Returns:
        bool: True if service started successfully, False otherwise
    """
    # Use the imported service starter if available
    if service_starter_available:
        return start_voice_api(project_dir, timeout)
    
    voice_api_path = project_dir / "services" / "voice" / "voice_api.py"
    
    if not voice_api_path.exists():
        logger.error(f"Voice API script not found at {voice_api_path}")
        return False
    
    try:
        # Check if service is already running
        logger.info("Checking if Voice API is already running...")
        try:
            response = requests.get("http://localhost:8100/status", timeout=3.0)
            if response.status_code == 200:
                logger.info("Voice API is already running")
                return True
        except requests.RequestException:
            logger.info("Voice API is not running, will start it")
        
        # Start the service
        logger.info("Starting voice service...")
        
        if sys.platform == "win32":
            # Windows
            process = subprocess.Popen(
                ["start", "python", str(voice_api_path)],
                shell=True
            )
        else:
            # Linux/Mac
            process = subprocess.Popen(
                ["python", str(voice_api_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setpgrp  # Run in a new process group
            )
        
        # Wait for service to start with progress indicator
        logger.info(f"Waiting for Voice API to start (timeout: {timeout}s)...")
        start_time = time.time()
        
        print("Starting Voice API", end="", flush=True)
        
        while time.time() - start_time < timeout:
            print(".", end="", flush=True)
            
            # Check if service is running
            try:
                response = requests.get("http://localhost:8100/status", timeout=2.0)
                if response.status_code == 200:
                    print()  # New line after dots
                    logger.info("Voice API started successfully")
                    return True
            except requests.RequestException:
                # Service not ready yet, continue waiting
                pass
            
            time.sleep(check_interval)
        
        print()  # New line after dots
        logger.warning(f"Voice API did not start within the timeout period ({timeout}s)")
        return False
        
    except Exception as e:
        logger.error(f"Failed to start voice service: {str(e)}")
        return False

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

def main():
    """Main function"""
    args = parse_arguments()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    print("\n===== Sabrina AI Voice Module Test =====\n")
    
    # Check if voice service is running
    print("Step 1: Checking if voice service is running...")
    service_running = check_voice_service()
    
    # Start the service if requested and not already running
    if not service_running and args.start_service:
        print("\nStep 2: Starting voice service...")
        service_running = start_voice_service_with_verification(timeout=args.timeout)
    elif not service_running and not args.start_service:
        print("\nVoice service not running. Run with --start-service to attempt to start it.")
        print("Alternatively, run the following command in another terminal:")
        print(f"python {project_dir}/services/voice/voice_api.py")
        return 1
    
    # Only continue with tests if service is running
    if service_running:
        print("\nStep 3: Testing VoiceAPIClient...")
        client_ok = test_voice_client()
        
        print("\nStep 4: Testing TTS with client...")
        tts_ok = test_tts_with_client(args.text)
        
        # Print summary
        print("\n===== Test Results =====")
        print(f"Voice Service: {'✓ Running' if service_running else '✗ Not Running'}")
        print(f"VoiceAPIClient: {'✓ OK' if client_ok else '✗ Issues Found'}")
        print(f"TTS Client Test: {'✓ OK' if tts_ok else '✗ Issues Found'}")
        
        # Final result
        if all([service_running, client_ok, tts_ok]):
            print("\n✓ Voice module is working correctly!")
            return 0
        else:
            print("\n✗ Issues were found with the voice module.")
            
            # Provide troubleshooting tips
            print("\nTroubleshooting Tips:")
            if not service_running:
                print("- Start the voice service with: python services/voice/voice_api.py")
                print("- Check logs for errors in the service startup")
            if not client_ok:
                print("- Check voice_api_client.py for errors")
                print("- Verify network connectivity to the service")
            if not tts_ok:
                print("- Verify TTS engine installation")
                print("- Check if audio playback is working")
            
            return 1
    else:
        print("\n✗ Cannot proceed with tests because voice service is not running.")
        return 1

if __name__ == "__main__":
    sys.exit(main())