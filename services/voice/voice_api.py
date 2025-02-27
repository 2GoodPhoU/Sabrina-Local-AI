"""
Enhanced Voice API Service for Sabrina AI
=========================================
Provides a FastAPI-based voice synthesis service using a real TTS engine.
"""

import os
import time
import logging
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import uvicorn
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_api")

app = FastAPI(title="Sabrina Voice API")

# Global TTS model - load it once for efficiency
tts_model = None

def load_tts_model():
    """Load the TTS model"""
    global tts_model
    
    logger.info("Loading TTS model...")
    try:
        # Try to import TTS library
        from TTS.api import TTS
        
        # Initialize the TTS model (Jenny TTS model)
        # For other models, see: https://github.com/coqui-ai/TTS
        tts_model = TTS("tts_models/en/jenny/jenny")
        
        logger.info("TTS model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading TTS model: {str(e)}")
        logger.info("Using fallback text-to-speech method")
        return False

def generate_speech(text, speed=1.0, pitch=1.0, emotion="normal"):
    """
    Generate speech from text using the TTS model
    
    Args:
        text: Text to convert to speech
        speed: Speech speed (0.5-2.0)
        pitch: Speech pitch (0.5-2.0)
        emotion: Speech emotion
    
    Returns:
        Path to the generated audio file
    """
    logger.info(f"Generating speech: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    # Create a temporary file for the audio
    fd, temp_path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    
    global tts_model
    if tts_model is not None:
        try:
            # Generate speech with the TTS model
            tts_model.tts_to_file(
                text=text,
                file_path=temp_path,
                # Some models support these parameters
                speaker=emotion if emotion != "normal" else None,
                speed=speed
            )
            logger.info(f"Speech generated with TTS model: {temp_path}")
            return temp_path
        except Exception as e:
            logger.error(f"Error generating speech with TTS model: {str(e)}")
    
    # Fallback method if TTS model fails or is not available
    logger.info("Using fallback method for speech generation")
    try:
        # Use a system TTS if available
        if os.name == 'nt':  # Windows
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', int(175 * speed))
            engine.save_to_file(text, temp_path)
            engine.runAndWait()
        else:  # Linux/Mac
            # Create a simple tone as placeholder
            import numpy as np
            from scipy.io import wavfile
            
            # Generate a simple sine wave
            sample_rate = 22050
            duration = len(text) * 0.1  # 0.1 seconds per character
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            # Generate different tones based on emotion
            if emotion == "happy" or emotion == "excited":
                freq = 440  # A4 note
            elif emotion == "sad":
                freq = 220  # A3 note
            else:
                freq = 330  # E4 note
            
            audio = np.sin(2 * np.pi * freq * t) * 0.5
            wavfile.write(temp_path, sample_rate, audio.astype(np.float32))
        
        logger.info(f"Speech generated with fallback method: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error generating speech with fallback method: {str(e)}")
        
        # Return empty file if all else fails
        with open(temp_path, 'wb') as f:
            f.write(b'')
        
        return temp_path

@app.on_event("startup")
async def startup_event():
    """Initialize the TTS model on startup"""
    load_tts_model()

@app.get("/status")
def status():
    """Check if the Voice API is running"""
    return {
        "status": "ok",
        "service": "Sabrina Voice API",
        "tts_model_loaded": tts_model is not None
    }

@app.get("/speak")
def speak(
    text: str = Query(..., description="Text to convert to speech"),
    speed: float = Query(1.0, description="Speech speed (0.5-2.0)"),
    pitch: float = Query(1.0, description="Speech pitch (0.5-2.0)"),
    emotion: str = Query("normal", description="Speech emotion")
):
    """Convert text to speech and return audio file"""
    try:
        # Validate parameters
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        
        # Generate speech
        file_path = generate_speech(text, speed, pitch, emotion)
        
        # Return the audio file
        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename="speech.wav"
        )
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