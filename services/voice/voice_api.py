"""
Voice API Server for Sabrina AI
Provides RESTful endpoints for TTS and voice settings management
"""

import os
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Local imports
from .voice_settings import VoiceSettings, voice_settings_manager
from .tts_engine import tts_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="Sabrina AI Voice API",
    description="Text-to-Speech and Voice Configuration API",
    version="1.0.0",
)


# Request models for API validation
class SpeakRequest(BaseModel):
    """Request model for text-to-speech generation"""

    text: str
    voice: Optional[str] = None
    volume: Optional[float] = None
    speed: Optional[float] = None
    pitch: Optional[float] = None
    emotion: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    """Request model for updating voice settings"""

    voice: Optional[str] = None
    volume: Optional[float] = None
    speed: Optional[float] = None
    pitch: Optional[float] = None
    emotion: Optional[str] = None
    cache_enabled: Optional[bool] = None
    max_cache_size: Optional[int] = None


# Health Check Endpoint
@app.get("/status")
async def health_check():
    """Check the status of the Voice API service"""
    return {
        "status": "healthy",
        "service": "Sabrina AI Voice API",
        "version": "1.0.0",
        "tts_model": tts_engine.current_model,
        "available_voices": tts_engine.list_available_voices(),
    }


# Text-to-Speech Endpoints
@app.post("/speak")
async def generate_speech(request: SpeakRequest):
    """
    Generate speech audio from text with optional voice customization

    Args:
        request: Speech generation parameters

    Returns:
        FileResponse with generated audio
    """
    try:
        # Prepare voice settings
        settings = VoiceSettings(
            voice=request.voice or voice_settings_manager.get_settings().voice,
            volume=request.volume or voice_settings_manager.get_settings().volume,
            speed=request.speed or voice_settings_manager.get_settings().speed,
            pitch=request.pitch or voice_settings_manager.get_settings().pitch,
            emotion=request.emotion or voice_settings_manager.get_settings().emotion,
        )

        # Generate speech
        audio_path = tts_engine.generate_speech(request.text, settings)

        # Return audio file
        return FileResponse(
            audio_path,
            media_type="audio/wav",
            filename=f"sabrina_tts_{os.path.basename(audio_path)}",
        )

    except Exception as e:
        logger.error(f"Speech generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Voice Settings Endpoints
@app.get("/settings")
async def get_voice_settings():
    """
    Retrieve current voice settings

    Returns:
        Current voice configuration
    """
    return voice_settings_manager.get_settings().dict()


@app.post("/settings")
async def update_voice_settings(request: SettingsUpdateRequest):
    """
    Update voice settings

    Args:
        request: Settings update parameters

    Returns:
        Updated voice settings
    """
    try:
        # Convert request to dictionary, removing None values
        update_dict = {k: v for k, v in request.dict().items() if v is not None}

        # Update settings
        updated_settings = voice_settings_manager.update_settings(update_dict)

        return updated_settings.dict()

    except Exception as e:
        logger.error(f"Settings update error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Voice List Endpoint
@app.get("/voices")
async def list_available_voices():
    """
    List all available TTS voices

    Returns:
        List of available voice models
    """
    return tts_engine.list_available_voices()


# Cached Speech Endpoints
@app.get("/cache/clear")
async def clear_speech_cache():
    """
    Clear the TTS audio cache

    Returns:
        Cache clearing status
    """
    try:
        cache_dir = tts_engine.cache_dir
        cache_files = os.listdir(cache_dir)

        for file in cache_files:
            file_path = os.path.join(cache_dir, file)
            os.unlink(file_path)

        return {
            "status": "success",
            "message": f"Cleared {len(cache_files)} cached audio files",
        }
    except Exception as e:
        logger.error(f"Cache clearing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Fallback for root endpoint
@app.get("/")
async def root():
    """
    Root endpoint with basic API information
    """
    return {
        "service": "Sabrina AI Voice API",
        "description": "Text-to-Speech and Voice Configuration Service",
        "endpoints": ["/status", "/speak", "/settings", "/voices", "/cache/clear"],
    }


# Main runner
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8100, reload=True)
