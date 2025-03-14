"""
Sabrina AI Voice API Service
===========================
FastAPI-based voice service providing text-to-speech capabilities
for the Sabrina AI Assistant system with simplified implementation.
"""

import os
import uuid
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("logs/voice_api.log"), logging.StreamHandler()],
)
logger = logging.getLogger("voice_api")

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("data/audio_cache", exist_ok=True)
os.makedirs("config", exist_ok=True)

# ================== Models ==================


class SpeakRequest(BaseModel):
    text: str = Field(..., description="Text to convert to speech")
    voice: Optional[str] = Field(None, description="Voice model name")
    speed: Optional[float] = Field(None, description="Speech speed (0.5-2.0)")
    pitch: Optional[float] = Field(None, description="Voice pitch (0.5-2.0)")
    volume: Optional[float] = Field(None, description="Audio volume (0.0-1.0)")
    emotion: Optional[str] = Field(
        None, description="Emotion style (neutral, happy, sad)"
    )
    cache: Optional[bool] = Field(None, description="Use caching if available")


class VoiceSettings(BaseModel):
    voice: str = Field("en_US-jenny-medium", description="Default voice model")
    speed: float = Field(1.0, description="Default speech speed", ge=0.5, le=2.0)
    pitch: float = Field(1.0, description="Default voice pitch", ge=0.5, le=2.0)
    volume: float = Field(0.8, description="Default audio volume", ge=0.0, le=1.0)
    emotion: str = Field("neutral", description="Default emotion style")
    cache_enabled: bool = Field(True, description="Enable audio caching")


class UpdateSettingsRequest(BaseModel):
    voice: Optional[str] = None
    speed: Optional[float] = None
    pitch: Optional[float] = None
    volume: Optional[float] = None
    emotion: Optional[str] = None
    cache_enabled: Optional[bool] = None


# ================== Settings Manager ==================


class VoiceSettingsManager:
    """Handles voice configuration persistence and retrieval"""

    def __init__(self, settings_file="config/voice_settings.json"):
        self.settings_file = settings_file
        self.settings = self._load_settings()

    def _load_settings(self) -> VoiceSettings:
        """Load settings from file or create default settings"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    data = json.load(f)
                return VoiceSettings(**data)
            else:
                # Create default settings
                default_settings = VoiceSettings()
                self._save_settings(default_settings)
                return default_settings
        except Exception as e:
            logger.error(f"Error loading voice settings: {str(e)}")
            return VoiceSettings()  # Return defaults on error

    def _save_settings(self, settings: VoiceSettings) -> bool:
        """Save settings to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)

            with open(self.settings_file, "w") as f:
                json.dump(settings.model_dump(), f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving voice settings: {str(e)}")
            return False

    def get_settings(self) -> VoiceSettings:
        """Get current voice settings"""
        return self.settings

    def update_settings(self, updates: UpdateSettingsRequest) -> VoiceSettings:
        """Update voice settings with new values"""
        # Get current settings as dict
        current_settings = self.settings.model_dump()

        # Update with new values, ignoring None values
        updates_dict = updates.model_dump(exclude_unset=True)
        current_settings.update(updates_dict)

        # Create new settings object
        new_settings = VoiceSettings(**current_settings)

        # Save and update current settings
        if self._save_settings(new_settings):
            self.settings = new_settings

        return self.settings


# ================== Import TTS Engine ==================

try:
    # Import TTS engine
    from tts_implementation import TTSEngine

    logger.info("Imported TTS engine")
except ImportError:
    logger.error(
        "Failed to import TTS implementation. Voice API will not function correctly."
    )
    raise


# ================== Setup App ==================

# Setup FastAPI app
app = FastAPI(
    title="Sabrina AI Voice API",
    description="Voice synthesis API for Sabrina AI Assistant",
    version="1.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Setup API key security
API_KEY = os.getenv("VOICE_API_KEY", "sabrina-dev-key")  # Default dev key
api_key_header = APIKeyHeader(name="X-API-Key")

# Initialize settings manager
settings_manager = VoiceSettingsManager()

# Initialize TTS engine
tts_engine = TTSEngine(settings_manager)


# Verify API key middleware
async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for protected endpoints"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key


# Exception middleware
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)},
        )


# ================== API Endpoints ==================


@app.get("/status")
async def status():
    """Check if the voice service is running"""
    return {
        "status": "online",
        "tts_initialized": tts_engine.tts_initialized,
        "version": "1.1.0",
    }


@app.post("/speak")
async def speak(request: SpeakRequest, api_key: str = Depends(verify_api_key)):
    """Convert text to speech and return audio file URL"""
    try:
        # Check if text is provided
        if not request.text:
            raise HTTPException(status_code=400, detail="Text is required")

        # Convert text to speech
        audio_path = await tts_engine.speak(
            text=request.text,
            voice_settings={
                "voice": request.voice,
                "speed": request.speed,
                "pitch": request.pitch,
                "volume": request.volume,
                "emotion": request.emotion,
                "cache": request.cache,
            },
        )

        # Get relative path for URL
        audio_filename = os.path.basename(audio_path)

        return {
            "status": "success",
            "message": "Text converted to speech",
            "audio_url": f"/audio/{audio_filename}",
            "text": request.text,
        }

    except Exception as e:
        logger.error(f"Error in speak endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate speech: {str(e)}",
        )


@app.get("/get_file_audio")
async def get_file_audio(text: str, api_key: str = Depends(verify_api_key)):
    """Convert text to speech and return audio file directly"""
    try:
        # Check if text is provided
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required"
            )

        # Convert text to speech
        audio_path = await tts_engine.speak(text=text)

        # Return the audio file
        return FileResponse(
            audio_path,
            media_type="audio/wav",
            filename=f"sabrina_speech_{uuid.uuid4().hex[:8]}.wav",
        )

    except Exception as e:
        logger.error(f"Error in get_file_audio endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate speech: {str(e)}",
        )


@app.get("/voices")
async def get_voices(api_key: str = Depends(verify_api_key)):
    """Get list of available voice models"""
    return {
        "voices": tts_engine.voice_models,
        "default_voice": settings_manager.get_settings().voice,
    }


@app.get("/settings")
async def get_settings(api_key: str = Depends(verify_api_key)):
    """Get current voice settings"""
    return settings_manager.get_settings()


@app.post("/settings")
async def update_settings(
    request: UpdateSettingsRequest, api_key: str = Depends(verify_api_key)
):
    """Update voice settings"""
    updated_settings = settings_manager.update_settings(request)
    return {
        "status": "success",
        "message": "Settings updated successfully",
        "settings": updated_settings,
    }


@app.post("/speak_simple")
async def speak_simple(text: str):
    """Simple endpoint to convert text to speech without API key"""
    try:
        # Check if text is provided
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required"
            )

        # Convert text to speech using default settings
        audio_path = await tts_engine.speak(text=text)

        # Get relative path for URL
        audio_filename = os.path.basename(audio_path)

        return {
            "status": "success",
            "message": "Text converted to speech",
            "audio_url": f"/audio/{audio_filename}",
            "text": text,
        }

    except Exception as e:
        logger.error(f"Error in speak_simple endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate speech: {str(e)}",
        )


# ================== Main ==================

# Serve static files
app.mount("/audio", StaticFiles(directory="data/audio_cache"), name="audio")

# Run the server if this file is executed directly
if __name__ == "__main__":
    # Get configuration from environment
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    port = int(os.getenv("VOICE_API_PORT", "8100"))

    # Start the server
    uvicorn.run(
        app, host="0.0.0.0", port=port, log_level="debug" if debug_mode else "info"
    )
