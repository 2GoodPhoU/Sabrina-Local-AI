"""
Docker-Ready Voice API Service for Sabrina AI
============================================
Provides a FastAPI-based voice synthesis service that works well in Docker.
"""

import os
import time
import logging
import json
from fastapi import FastAPI, Query
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

app = FastAPI(title="Sabrina Voice API")

# Global TTS engine
tts_engine = None
tts_type = "edge-tts"  # Options: "edge-tts", "coqui-tts", "pyttsx3"

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
        "voice": "en-US-JennyNeural"  # Default Edge TTS voice
    }

# Initialize settings
SETTINGS = load_settings()

def init_tts_engine():
    """Initialize the TTS engine based on configuration"""
    global tts_engine, tts_type
    
    # Try Edge TTS first (Microsoft's TTS service, works offline)
    if tts_type == "edge-tts" or tts_engine is None:
        try:
            logger.info("Initializing Edge TTS engine...")
            import edge_tts
            tts_engine = edge_tts
            tts_type = "edge-tts"
            logger.info("Edge TTS engine initialized successfully")
            return True
        except ImportError:
            logger.warning("Edge TTS not available, trying Coqui TTS...")
    
    # Try Coqui TTS if Edge TTS fails
    if tts_type == "coqui-tts" or tts_engine is None:
        try:
            logger.info("Initializing Coqui TTS engine...")
            from TTS.api import TTS
            tts_engine = TTS("tts_models/en/ljspeech/tacotron2-DDC")
            tts_type = "coqui-tts"
            logger.info("Coqui TTS engine initialized successfully")
            return True
        except Exception as e:
            logger.warning(f"Coqui TTS not available: {str(e)}, trying pyttsx3...")
    
    # Use pyttsx3 as last resort (works on almost all platforms)
    if tts_type == "pyttsx3" or tts_engine is None:
        try:
            logger.info("Initializing pyttsx3 engine...")
            import pyttsx3
            tts_engine = pyttsx3.init()
            tts_type = "pyttsx3"
            logger.info("pyttsx3 engine initialized successfully")
            return True
        except Exception as e:
            logger.error(f"All TTS engines failed to initialize: {str(e)}")
            return False

async def generate_speech_edge_tts(text, voice, speed, volume):
    """Generate speech using Edge TTS"""
    # Create a temporary file for the audio
    fd, temp_path = tempfile.mkstemp(suffix='.mp3')
    os.close(fd)
    
    try:
        # Configure Edge TTS
        communicate = tts_engine.Communicate(
            text, 
            voice=voice,
            rate=f"{int((speed-1)*50):+d}%",  # Convert speed to rate format
            volume=f"{int(volume*100)}%"
        )
        
        # Generate speech
        await communicate.save(temp_path)
        logger.info(f"Speech generated with Edge TTS: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error generating speech with Edge TTS: {str(e)}")
        return None

def generate_speech_coqui(text, speed):
    """Generate speech using Coqui TTS"""
    # Create a temporary file for the audio
    fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    
    try:
        # Generate speech
        tts_engine.tts_to_file(text=text, file_path=temp_path, speed=speed)
        logger.info(f"Speech generated with Coqui TTS: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error generating speech with Coqui TTS: {str(e)}")
        return None

def generate_speech_pyttsx3(text, speed, volume):
    """Generate speech using pyttsx3"""
    # Create a temporary file for the audio
    fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    
    try:
        # Configure pyttsx3
        tts_engine.setProperty('rate', int(175 * speed))
        tts_engine.setProperty('volume', volume)
        
        # Generate speech
        tts_engine.save_to_file(text, temp_path)
        tts_engine.runAndWait()
        
        logger.info(f"Speech generated with pyttsx3: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error generating speech with pyttsx3: {str(e)}")
        return None

async def generate_speech(text, voice="en-US-JennyNeural", speed=1.0, pitch=1.0, 
                    emotion="normal", volume=0.8):
    """
    Generate speech from text using the available TTS engine
    
    Args:
        text: Text to convert to speech
        voice: Voice to use
        speed: Speech speed (0.5-2.0)
        pitch: Speech pitch (0.5-2.0) - not all engines support this
        emotion: Speech emotion - not all engines support this
        volume: Volume level (0.0-1.0)
    
    Returns:
        Path to the generated audio file
    """
    logger.info(f"Generating speech: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    # Use appropriate speech generator based on available engine
    if tts_type == "edge-tts":
        # Apply emotion to voice selection for Edge TTS
        if emotion == "happy" or emotion == "excited":
            # Add cheerful style to text if using JennyNeural
            if "Jenny" in voice:
                text = f'<mstts:express-as style="cheerful">{text}</mstts:express-as>'
        elif emotion == "sad":
            if "Jenny" in voice:
                text = f'<mstts:express-as style="sad">{text}</mstts:express-as>'
        
        return await generate_speech_edge_tts(text, voice, speed, volume)
    
    elif tts_type == "coqui-tts":
        return generate_speech_coqui(text, speed)
    
    elif tts_type == "pyttsx3":
        return generate_speech_pyttsx3(text, speed, volume)
    
    else:
        logger.error("No TTS engine available")
        return None

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    init_tts_engine()

@app.get("/status")
def status():
    """Check if the Voice API is running"""
    return {
        "status": "ok",
        "service": "Sabrina Voice API",
        "tts_engine": tts_type,
        "tts_engine_loaded": tts_engine is not None,
        "default_voice": SETTINGS.get("voice", "en-US-JennyNeural"),
        "available_voices": ["en-US-JennyNeural", "en-US-AriaNeural", "en-US-GuyNeural"]
    }

@app.get("/speak")
async def speak(
    text: str = Query(..., description="Text to convert to speech"),
    speed: float = Query(1.0, description="Speech speed (0.5-2.0)"),
    pitch: float = Query(1.0, description="Speech pitch (0.5-2.0)"),
    emotion: str = Query("normal", description="Speech emotion"),
    voice: str = Query(None, description="Voice to use"),
    volume: float = Query(0.8, description="Volume level (0.0-1.0)")
):
    """Convert text to speech and return audio file"""
    try:
        # Use default voice if not specified
        if voice is None:
            voice = SETTINGS.get("voice", "en-US-JennyNeural")
            
        # Validate parameters
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        volume = max(0.0, min(1.0, volume))
        
        # Generate speech
        file_path = await generate_speech(
            text=text, 
            voice=voice,
            speed=speed, 
            pitch=pitch, 
            emotion=emotion,
            volume=volume
        )
        
        if file_path and os.path.exists(file_path):
            # Return the audio file
            return FileResponse(
                path=file_path,
                media_type="audio/mpeg" if file_path.endswith(".mp3") else "audio/wav",
                filename="speech.mp3" if file_path.endswith(".mp3") else "speech.wav"
            )
        else:
            return {"error": "Failed to generate speech"}
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return {"error": str(e)}

def main():
    """Run the Voice API server"""
    # Make sure the output directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8100)

if __name__ == "__main__":
    main()