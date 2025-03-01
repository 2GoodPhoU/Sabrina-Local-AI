"""
Enhanced Voice API Service for Sabrina AI
=========================================
A more efficient and robust FastAPI service for voice synthesis
with improved error handling and better voice selection.
"""

import os
import time
import logging
import json
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Query, Response, HTTPException, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/voice_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("voice_api")

# Create FastAPI app
app = FastAPI(
    title="Sabrina Voice API",
    description="High-quality voice synthesis for Sabrina AI",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global settings
PIPER_INSTALLED = False
PIPER_BINARY_PATH = None
PIPER_MODELS_DIR = "models/piper"
DEFAULT_VOICE = "en_US-ryan-medium"  # Use a more confident male voice as default
AVAILABLE_VOICES = []
PREFERRED_VOICES = [
    "en_US-amy-medium",      # Confident female voice
    "en_US-kathleen-medium", # Alternative female voice
    "en_US-jenny-medium",    # Another female voice option
]

# Global settings container
class Settings:
    def __init__(self):
        self.speed = 1.0
        self.pitch = 1.0
        self.emotion = "normal"
        self.volume = 0.8
        self.voice = DEFAULT_VOICE

# Initialize settings
SETTINGS = Settings()

def find_best_voice() -> str:
    """Find the best available voice from our preferred list"""
    for voice in PREFERRED_VOICES:
        model_path = os.path.join(PIPER_MODELS_DIR, f"{voice}.onnx")
        if os.path.exists(model_path):
            return voice
    
    # If no preferred voice is found, return any available voice
    for file in os.listdir(PIPER_MODELS_DIR):
        if file.endswith(".onnx"):
            return os.path.splitext(file)[0]
    
    return DEFAULT_VOICE

def check_piper_installation() -> bool:
    """Check if Piper is installed and locate the binary"""
    global PIPER_INSTALLED, PIPER_BINARY_PATH
    
    # Try to find piper binary in common locations
    possible_locations = [
        "/usr/local/bin/piper",
        "/usr/bin/piper",
        "piper"  # If it's in PATH
    ]
    
    for location in possible_locations:
        try:
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
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    
    logger.warning("Piper binary not found in standard locations")
    return False

def find_voice_models() -> List[str]:
    """Find available Piper voice models"""
    global AVAILABLE_VOICES, DEFAULT_VOICE
    
    voices = []
    models_dir = Path(PIPER_MODELS_DIR)
    
    # Create models directory if it doesn't exist
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for model files (*.onnx)
    try:
        for file in models_dir.glob("**/*.onnx"):
            # Get voice name from filename (removing extension)
            voice_name = file.stem
            if file.stem.endswith(".onnx"):
                voice_name = file.stem[:-5]  # Remove the .onnx part if it's in the stem
            voices.append(voice_name)
    except Exception as e:
        logger.error(f"Error searching for model files: {str(e)}")
    
    if voices:
        AVAILABLE_VOICES = voices
        # Set default voice to best available
        DEFAULT_VOICE = find_best_voice()
        SETTINGS.voice = DEFAULT_VOICE
        logger.info(f"Set default voice to: {DEFAULT_VOICE}")
    else:
        logger.warning(f"No voice models found in {models_dir}")
    
    return voices

def load_settings():
    """Load voice settings from file"""
    try:
        if os.path.exists("voice_settings.json"):
            with open("voice_settings.json", "r") as f:
                data = json.load(f)
                SETTINGS.speed = data.get("speed", 1.0)
                SETTINGS.pitch = data.get("pitch", 1.0)
                SETTINGS.emotion = data.get("emotion", "normal")
                SETTINGS.volume = data.get("volume", 0.8)
                
                # Only use the voice if it exists
                voice = data.get("voice", DEFAULT_VOICE)
                if voice in AVAILABLE_VOICES:
                    SETTINGS.voice = voice
                else:
                    # Use best available voice
                    SETTINGS.voice = find_best_voice()
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")

def save_settings():
    """Save current settings to file"""
    try:
        with open("voice_settings.json", "w") as f:
            json.dump({
                "speed": SETTINGS.speed,
                "pitch": SETTINGS.pitch,
                "emotion": SETTINGS.emotion,
                "volume": SETTINGS.volume,
                "voice": SETTINGS.voice
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")

def generate_speech(
    text: str, 
    voice: Optional[str] = None,
    speed: Optional[float] = None,
    pitch: Optional[float] = None,
    volume: Optional[float] = None
) -> Optional[str]:
    """
    Generate speech using Piper TTS
    
    Args:
        text: Text to synthesize
        voice: Voice to use (or None for default)
        speed: Speed factor (or None for default)
        pitch: Pitch factor (or None for default)
        volume: Volume factor (or None for default)
        
    Returns:
        Path to the output audio file, or None on failure
    """
    # Use provided values or defaults
    voice = voice or SETTINGS.voice
    speed = speed or SETTINGS.speed
    pitch = pitch or SETTINGS.pitch
    volume = volume or SETTINGS.volume
    
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
        
        # Prepare the model path
        model_path = os.path.join(PIPER_MODELS_DIR, f"{voice}.onnx")
        if not os.path.exists(model_path):
            logger.warning(f"Voice model not found: {model_path}, using fallback")
            voice = find_best_voice()
            model_path = os.path.join(PIPER_MODELS_DIR, f"{voice}.onnx")
            if not os.path.exists(model_path):
                logger.error("No usable voice models found")
                return None
        
        # Check for config file
        config_path = os.path.join(PIPER_MODELS_DIR, f"{voice}.onnx.json")
        config_param = ["--config", config_path] if os.path.exists(config_path) else []
        
        # Piper uses length-scale for speed (inverse of speed)
        length_scale = 1.0 / float(speed)
        
        # Build the command
        command = [
            PIPER_BINARY_PATH,
            "--model", model_path,
            *config_param,
            "--output_file", output_path,
            "--length-scale", str(length_scale)
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
        
        # Check if successful
        if process.returncode != 0:
            logger.error(f"Piper TTS error (code {process.returncode}): {stderr}")
            return None
            
        # Verify the file exists and isn't empty
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            logger.error(f"Generated audio file is missing or too small: {output_path}")
            return None
            
        logger.info(f"Speech generated successfully: {output_path}")
        return output_path
            
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return None

@app.on_event("startup")
async def startup_event():
    """Initialize the API on startup"""
    global PIPER_INSTALLED, DEFAULT_VOICE
    
    logger.info("Starting Sabrina Voice API")
    
    # Check for Piper installation
    PIPER_INSTALLED = check_piper_installation()
    
    if not PIPER_INSTALLED:
        logger.warning("Piper not installed - voice synthesis will be limited")
    
    # Find voice models
    voices = find_voice_models()
    logger.info(f"Found {len(voices)} voice models: {', '.join(voices)}")
    
    # Load saved settings
    load_settings()
    logger.info(f"Using voice: {SETTINGS.voice}")

@app.get("/status")
def status():
    """Check if the Voice API is running"""
    return {
        "status": "ok",
        "service": "Sabrina Voice API",
        "tts_engine": "piper",
        "tts_engine_installed": PIPER_INSTALLED,
        "default_voice": SETTINGS.voice,
        "available_voices": AVAILABLE_VOICES,
        "voice_count": len(AVAILABLE_VOICES)
    }

@app.get("/voices")
def list_voices():
    """List all available voices"""
    return {
        "default_voice": SETTINGS.voice,
        "voices": AVAILABLE_VOICES
    }

@app.get("/speak")
async def speak(
    text: str = Query(..., description="Text to convert to speech"),
    speed: float = Query(None, description="Speech speed (0.5-2.0)"),
    pitch: float = Query(None, description="Speech pitch (0.5-2.0)"),
    voice: str = Query(None, description="Voice model to use"),
    volume: float = Query(None, description="Volume level (0.0-1.0)")
):
    """Convert text to speech and return audio file"""
    # Validate parameters
    if speed is not None:
        speed = max(0.5, min(2.0, speed))
        
    if pitch is not None:
        pitch = max(0.5, min(2.0, pitch))
        
    if volume is not None:
        volume = max(0.0, min(1.0, volume))
        
    if voice is not None and voice not in AVAILABLE_VOICES:
        logger.warning(f"Requested voice {voice} not available, using {SETTINGS.voice}")
        voice = None  # Use the default
    
    # Generate speech
    file_path = generate_speech(text, voice, speed, pitch, volume)
    
    if file_path and os.path.exists(file_path):
        try:
            return FileResponse(
                path=file_path,
                media_type="audio/wav",
                filename="speech.wav"
            )
        except Exception as e:
            logger.error(f"Error serving audio file: {str(e)}")
            raise HTTPException(status_code=500, detail="Error serving audio file")
    else:
        raise HTTPException(status_code=500, detail="Failed to generate speech")

@app.post("/update_settings")
async def update_settings(
    speed: Optional[float] = None,
    pitch: Optional[float] = None,
    voice: Optional[str] = None,
    volume: Optional[float] = None,
    emotion: Optional[str] = None
):
    """Update voice settings"""
    if speed is not None:
        SETTINGS.speed = max(0.5, min(2.0, speed))
        
    if pitch is not None:
        SETTINGS.pitch = max(0.5, min(2.0, pitch))
        
    if volume is not None:
        SETTINGS.volume = max(0.0, min(1.0, volume))
        
    if voice is not None and voice in AVAILABLE_VOICES:
        SETTINGS.voice = voice
        
    if emotion is not None:
        SETTINGS.emotion = emotion
    
    # Save updated settings
    save_settings()
    
    return {
        "status": "ok",
        "settings": {
            "speed": SETTINGS.speed,
            "pitch": SETTINGS.pitch,
            "volume": SETTINGS.volume,
            "voice": SETTINGS.voice,
            "emotion": SETTINGS.emotion
        }
    }

@app.get("/settings")
def get_settings():
    """Get current voice settings"""
    return {
        "speed": SETTINGS.speed,
        "pitch": SETTINGS.pitch,
        "volume": SETTINGS.volume,
        "voice": SETTINGS.voice,
        "emotion": SETTINGS.emotion
    }

def main():
    """Start the Voice API server"""
    uvicorn.run(app, host="0.0.0.0", port=8100)

if __name__ == "__main__":
    main()