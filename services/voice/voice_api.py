"""
Docker-Ready Voice API Service for Sabrina AI with Piper TTS Support
=================================================================
Provides a FastAPI-based voice synthesis service that uses Piper TTS for offline,
high-quality voice synthesis.
"""

import os
import time
import logging
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Query, Response, HTTPException
from fastapi.responses import FileResponse
import uvicorn
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/voice_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("voice_api")

app = FastAPI(title="Sabrina Voice API with Piper TTS")

# Global settings
PIPER_INSTALLED = False
PIPER_BINARY_PATH = None
PIPER_MODELS_DIR = "models/piper"
DEFAULT_VOICE = "en_US-amy-medium"
AVAILABLE_VOICES = []

# Load settings
def load_settings():
    """Load voice settings from file"""
    try:
        if os.path.exists("voice_settings.json"):
            with open("voice_settings.json", "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
    
    # Default settings
    return {
        "speed": 1.0,
        "pitch": 1.0,
        "emotion": "normal",
        "volume": 0.8,
        "voice": DEFAULT_VOICE
    }

# Initialize settings
SETTINGS = load_settings()

def check_piper_installation():
    """Check if Piper is installed and locate the binary"""
    global PIPER_INSTALLED, PIPER_BINARY_PATH
    
    # Try to find piper binary in common locations
    possible_locations = [
        "/usr/bin/piper",
        "/usr/local/bin/piper",
        "piper",  # If it's in PATH
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "piper/piper")
    ]
    
    for location in possible_locations:
        try:
            logger.info(f"Checking for Piper at: {location}")
            result = subprocess.run([location, "--help"], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE, 
                                  text=True,
                                  timeout=2)
            
            if result.returncode == 0 or "piper" in result.stdout or "piper" in result.stderr:
                PIPER_BINARY_PATH = location
                PIPER_INSTALLED = True
                logger.info(f"Found Piper binary at: {location}")
                return True
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.debug(f"Piper not found at {location}: {str(e)}")
            continue
    
    logger.warning("Piper binary not found in standard locations")
    return False

def find_piper_models():
    """Find available Piper voice models"""
    global AVAILABLE_VOICES, DEFAULT_VOICE
    
    voices = []
    models_dir = Path(PIPER_MODELS_DIR)
    
    # Create models directory if it doesn't exist
    models_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Looking for voice models in: {models_dir.absolute()}")
    
    # List all files in the models directory for debugging
    try:
        all_files = list(models_dir.glob("**/*"))
        logger.info(f"Files in models directory: {[str(f) for f in all_files]}")
    except Exception as e:
        logger.error(f"Error listing model directory contents: {str(e)}")
    
    # Check for model files (*.onnx)
    try:
        for file in models_dir.glob("**/*.onnx"):
            # Get voice name from filename (removing extension)
            voice_name = file.stem
            voices.append(voice_name)
            
            # Also check for associated JSON config
            config_file = file.with_suffix('.json')
            if config_file.exists():
                logger.info(f"Found Piper voice with config: {voice_name}")
            else:
                logger.warning(f"Found voice model without config: {voice_name}")
    except Exception as e:
        logger.error(f"Error searching for model files: {str(e)}")
    
    if voices:
        AVAILABLE_VOICES = voices
        # Set default voice to first available if current default not available
        if DEFAULT_VOICE not in voices:
            DEFAULT_VOICE = voices[0]
            logger.info(f"Set default voice to: {DEFAULT_VOICE}")
    else:
        logger.warning(f"No voice models found in {models_dir}")
        # Add placeholder for default voice
        AVAILABLE_VOICES = [DEFAULT_VOICE]
    
    return voices

def download_default_model():
    """Download a default model if no models are available"""
    # Create models directory
    os.makedirs(PIPER_MODELS_DIR, exist_ok=True)
    
    # Default model URL
    model_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx"
    config_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json"
    
    model_path = os.path.join(PIPER_MODELS_DIR, "en_US-amy-medium.onnx")
    config_path = os.path.join(PIPER_MODELS_DIR, "en_US-amy-medium.onnx.json")
    
    try:
        logger.info(f"Downloading default voice model from {model_url}")
        
        # Use curl or wget if available (better progress indicators)
        if os.system("which curl > /dev/null 2>&1") == 0:
            os.system(f"curl -L '{model_url}' -o '{model_path}'")
            os.system(f"curl -L '{config_url}' -o '{config_path}'")
        elif os.system("which wget > /dev/null 2>&1") == 0:
            os.system(f"wget '{model_url}' -O '{model_path}'")
            os.system(f"wget '{config_url}' -O '{config_path}'")
        else:
            # Fall back to Python's urllib
            import urllib.request
            urllib.request.urlretrieve(model_url, model_path)
            urllib.request.urlretrieve(config_url, config_path)
            
        # Verify the download was successful
        if os.path.exists(model_path) and os.path.getsize(model_path) > 1000000:  # File should be several MB
            logger.info(f"Default model downloaded to {model_path}")
            return True
        else:
            logger.error(f"Model file exists but seems too small or corrupted: {model_path}")
            # Try to display its size
            try:
                size = os.path.getsize(model_path)
                logger.error(f"File size: {size} bytes")
            except:
                pass
            return False
    except Exception as e:
        logger.error(f"Error downloading default model: {str(e)}")
        return False

def generate_speech_piper(text, voice=DEFAULT_VOICE, speed=1.0, pitch=1.0, volume=0.8):
    """
    Generate speech using Piper TTS
    
    Args:
        text: Text to synthesize
        voice: Voice model to use
        speed: Speed factor (0.5-2.0)
        pitch: Pitch factor (not fully supported in Piper)
        volume: Volume factor (0.0-1.0)
        
    Returns:
        Path to the output audio file
    """
    if not PIPER_INSTALLED or not PIPER_BINARY_PATH:
        logger.error("Piper TTS not available")
        return None
        
    try:
        # Create a temporary file for the output
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        
        # Create a temporary file for the input text
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as text_file:
            text_file.write(text)
            text_file_path = text_file.name
        
        # Prepare command
        # Piper uses --rate for speed control (default 16000)
        # We convert speed factor to rate by multiplying default rate by speed
        rate = int(16000 * speed)
        
        # Build the command
        model_path = os.path.join(PIPER_MODELS_DIR, f"{voice}.onnx")
        
        # Check if voice file exists
        if not os.path.exists(model_path):
            logger.error(f"Voice model file not found: {model_path}")
            # List all available models for debugging
            try:
                models_dir = Path(PIPER_MODELS_DIR)
                all_files = list(models_dir.glob("**/*"))
                logger.error(f"Available files in models directory: {[str(f) for f in all_files]}")
            except Exception as e:
                logger.error(f"Error listing model directory contents: {str(e)}")
                
            # Try to use default voice as fallback
            if voice != DEFAULT_VOICE:
                logger.info(f"Trying default voice: {DEFAULT_VOICE}")
                model_path = os.path.join(PIPER_MODELS_DIR, f"{DEFAULT_VOICE}.onnx")
                if not os.path.exists(model_path):
                    logger.error(f"Default voice model not found: {model_path}")
                    return None
            else:
                return None
                
        command = [
            PIPER_BINARY_PATH,
            "--model", model_path,
            "--output_file", output_path,
            "--rate", str(rate)
        ]
        
        logger.info(f"Running Piper command: {' '.join(command)}")
        
        # Run piper with the text file as input
        with open(text_file_path, 'r') as f:
            process = subprocess.Popen(
                command,
                stdin=f,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
        # Clean up the text file
        os.unlink(text_file_path)
            
        if process.returncode != 0:
            logger.error(f"Piper TTS error (code {process.returncode}): {stderr}")
            if stdout:
                logger.error(f"Piper stdout: {stdout}")
            return None
            
        logger.info(f"Speech generated with Piper TTS: {output_path}")
        return output_path
            
    except Exception as e:
        logger.error(f"Error generating speech with Piper TTS: {str(e)}")
        return None

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    global PIPER_INSTALLED, DEFAULT_VOICE, AVAILABLE_VOICES
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    # Check for Piper installation
    PIPER_INSTALLED = check_piper_installation()
    
    if not PIPER_INSTALLED:
        logger.warning("Piper not found - voice synthesis will be limited")
    
    # Find available voice models
    voices = find_piper_models()
    
    # If no models found, try to download a default one
    if not voices:
        logger.info("No voice models found, downloading default model...")
        download_success = download_default_model()
        if download_success:
            voices = find_piper_models()
        else:
            logger.error("Failed to download default model - voice synthesis may not work")
    
    logger.info(f"Available voices: {', '.join(AVAILABLE_VOICES)}")
    logger.info(f"Default voice: {DEFAULT_VOICE}")

@app.get("/status")
def status():
    """Check if the Voice API is running and return status information"""
    # Group voices by language prefix
    voice_by_language = {}
    for voice in AVAILABLE_VOICES:
        # Split on underscore or hyphen
        parts = voice.replace('-', '_').split('_')
        if len(parts) >= 2:
            lang_code = f"{parts[0]}_{parts[1]}"
            if lang_code not in voice_by_language:
                voice_by_language[lang_code] = []
            voice_by_language[lang_code].append(voice)
        else:
            # Fallback for voices without clear language code
            if "Other" not in voice_by_language:
                voice_by_language["Other"] = []
            voice_by_language["Other"].append(voice)
    
    # Add detailed debug info
    debug_info = {
        "piper_models_dir_absolute": str(Path(PIPER_MODELS_DIR).absolute()),
        "piper_binary_path": PIPER_BINARY_PATH,
        "current_directory": os.getcwd(),
        "voices_found": len(AVAILABLE_VOICES),
        "default_voice_file_exists": os.path.exists(os.path.join(PIPER_MODELS_DIR, f"{DEFAULT_VOICE}.onnx"))
    }
    
    try:
        # Try to list files in the models directory
        models_dir = Path(PIPER_MODELS_DIR)
        all_files = list(models_dir.glob("**/*"))
        debug_info["files_in_models_dir"] = [str(f) for f in all_files]
    except Exception as e:
        debug_info["files_list_error"] = str(e)
    
    return {
        "status": "ok",
        "service": "Sabrina Voice API with Piper TTS",
        "tts_engine": "piper",
        "tts_engine_installed": PIPER_INSTALLED,
        "piper_binary": PIPER_BINARY_PATH,
        "default_voice": DEFAULT_VOICE,
        "voice_count": len(AVAILABLE_VOICES),
        "available_voices": voice_by_language,
        "models_directory": PIPER_MODELS_DIR,
        "debug_info": debug_info
    }

@app.get("/speak")
async def speak(
    text: str = Query(..., description="Text to convert to speech"),
    speed: float = Query(1.0, description="Speech speed (0.5-2.0)"),
    pitch: float = Query(1.0, description="Speech pitch (0.5-2.0)"),
    emotion: str = Query("normal", description="Speech emotion (limited support)"),
    voice: str = Query(None, description="Voice model to use"),
    volume: float = Query(0.8, description="Volume level (0.0-1.0)")
):
    """Convert text to speech and return audio file"""
    if not PIPER_INSTALLED:
        raise HTTPException(status_code=503, detail="Piper TTS not installed or configured")
        
    try:
        # Use default voice if not specified
        if voice is None or voice not in AVAILABLE_VOICES:
            voice = DEFAULT_VOICE
            
        # Validate parameters
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        volume = max(0.0, min(1.0, volume))
        
        # Log voice being used
        logger.info(f"Using voice: {voice}")
        
        # Generate speech
        file_path = generate_speech_piper(
            text=text, 
            voice=voice,
            speed=speed, 
            pitch=pitch, 
            volume=volume
        )
        
        if file_path and os.path.exists(file_path):
            # Determine correct media type (wav for Piper)
            media_type = "audio/wav"
            filename = "speech.wav"
            
            # Log the file size
            file_size = os.path.getsize(file_path)
            logger.info(f"Sending audio file: {file_path}, size: {file_size} bytes")
            
            # Return the audio file
            return FileResponse(
                path=file_path,
                media_type=media_type,
                filename=filename
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
def list_voices():
    """List all available voices"""
    return {
        "default_voice": DEFAULT_VOICE,
        "voices": AVAILABLE_VOICES,
        "count": len(AVAILABLE_VOICES),
        "models_directory": PIPER_MODELS_DIR
    }

def main():
    """Run the Voice API server"""
    # Make sure the output directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8100)

if __name__ == "__main__":
    main()