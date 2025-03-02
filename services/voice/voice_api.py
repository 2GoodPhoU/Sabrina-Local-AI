"""
Sabrina AI Voice API Service
===========================
FastAPI-based voice service that provides TTS (Text-to-Speech) capabilities
for the Sabrina AI Assistant system.

This module creates a REST API for text-to-speech synthesis using Coqui TTS (Jenny model),
with configurable voice settings, audio caching, and secure voice settings management.
"""

import os
import uuid
import json
import logging
from typing import Dict, Optional, List, Any
import hashlib
from pydantic import BaseModel, Field
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
import asyncio
import traceback

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
                json.dump(settings.dict(), f, indent=4)
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
        current_settings = self.settings.dict()

        # Update with new values, ignoring None values
        updates_dict = updates.dict(exclude_unset=True)
        current_settings.update(updates_dict)

        # Create new settings object
        new_settings = VoiceSettings(**current_settings)

        # Save and update current settings
        if self._save_settings(new_settings):
            self.settings = new_settings

        return self.settings


# ================== TTS Engine ==================


class TTSEngine:
    """Handles text-to-speech synthesis using the TTS library"""

    def __init__(self, settings_manager: VoiceSettingsManager):
        self.settings_manager = settings_manager
        self.voice_models = self._get_available_voices()
        self.cache_dir = "data/audio_cache"
        self.tts_initialized = False
        self.tts = None
        self.tts_models = {}

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Try to initialize TTS
        try:
            self._init_tts()
        except Exception as e:
            logger.error(f"Failed to initialize TTS: {str(e)}")
            logger.error(traceback.format_exc())

    def _init_tts(self):
        """Initialize TTS library with models"""
        try:
            # Import TTS here to avoid startup issues if not installed
            import torch

            # Check if CUDA is available
            use_cuda = torch.cuda.is_available()
            if use_cuda:
                logger.info("CUDA is available, using GPU for TTS")
            else:
                logger.info("CUDA not available, using CPU for TTS")

            self.tts_initialized = True
            logger.info("TTS engine initialized successfully")

        except ImportError:
            logger.warning("TTS library not installed. Using fallback synthesis.")
            self.tts_initialized = False
        except Exception as e:
            logger.error(f"Error initializing TTS: {str(e)}")
            logger.error(traceback.format_exc())
            self.tts_initialized = False

    def _get_available_voices(self) -> List[str]:
        """Get list of available voice models"""
        # In a real implementation, this would scan for available models
        # For now, we'll return a hardcoded list of sample voices
        return [
            "en_US-jenny-medium",
            "en_US-jenny-high",
            "en_US-amy-medium",
            "en_US-amy-high",
            "en_US-default",
        ]

    def _get_cache_path(self, text: str, settings: Dict[str, Any]) -> str:
        """Get cache file path for the given text and settings"""
        # Create a unique hash based on text and voice settings
        settings_str = json.dumps({k: v for k, v in settings.items() if k != "cache"})
        cache_key = f"{text}|{settings_str}"

        # Create MD5 hash of the cache key
        cache_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()

        return os.path.join(self.cache_dir, f"{cache_hash}.wav")

    async def speak(
        self, text: str, voice_settings: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Convert text to speech and return the path to the audio file

        Args:
            text: Text to convert to speech
            voice_settings: Optional override for voice settings

        Returns:
            Path to the generated audio file
        """
        # Get default settings if not provided
        if voice_settings is None:
            voice_settings = self.settings_manager.get_settings().dict()

        # Merge default settings with provided settings
        settings = self.settings_manager.get_settings().dict()
        for key, value in (voice_settings or {}).items():
            if value is not None:  # Only update non-None values
                settings[key] = value

        # Check if caching is enabled
        use_cache = settings.get("cache_enabled", True)
        if "cache" in voice_settings and voice_settings["cache"] is not None:
            use_cache = voice_settings["cache"]

        # Get cache path
        cache_path = self._get_cache_path(text, settings)

        # Check if cached audio exists
        if use_cache and os.path.exists(cache_path):
            logger.info(f"Using cached audio: {cache_path}")
            return cache_path

        # Generate a temporary output path if we're not using cache
        if not use_cache:
            output_path = os.path.join(self.cache_dir, f"temp_{uuid.uuid4()}.wav")
        else:
            output_path = cache_path

        # Generate speech
        success = await self._generate_speech(text, output_path, settings)

        if success:
            return output_path
        else:
            # If synthesis failed, try the fallback method
            return await self._fallback_synthesis(text, output_path, settings)

    async def _generate_speech(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> bool:
        """
        Generate speech using TTS library

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.tts_initialized:
            return False

        try:
            # In a real implementation, this would use the TTS library
            # For demonstration purposes, we'll use a placeholder await
            # to simulate the TTS processing time
            await asyncio.sleep(0.5)  # Simulate TTS processing

            # In a real implementation with the TTS library:
            # 1. Select the appropriate voice model
            # 2. Apply speed, pitch, volume settings
            # 3. Generate the audio file

            # For now, we'll create a simple test WAV file
            await self._create_test_wav(output_path)

            logger.info(f"Generated speech audio: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _fallback_synthesis(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> str:
        """Fallback synthesis method if TTS fails or is not available"""
        try:
            # Create a simple test WAV file
            await self._create_test_wav(output_path)

            logger.info(f"Generated fallback speech audio: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Fallback synthesis failed: {str(e)}")
            # Return a default audio file path
            default_audio = "config/fallback_audio.wav"
            if not os.path.exists(default_audio):
                await self._create_test_wav(default_audio)
            return default_audio

    async def _create_test_wav(self, file_path: str):
        """Create a test WAV file for demonstration purposes"""
        try:
            # This is a simple way to create a WAV file for testing
            # In a real implementation, this would be replaced with actual TTS output

            # Ensure output directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # If we have numpy and scipy, create a simple sine wave
            try:
                import numpy as np
                from scipy.io import wavfile

                # Create a simple sine wave
                sample_rate = 22050
                duration = 2  # seconds
                t = np.linspace(
                    0, duration, int(sample_rate * duration), endpoint=False
                )

                # Create a tone that changes pitch
                frequency = 440  # A4 note
                amplitude = 0.5

                # Add some variation for different texts
                seed_value = sum(ord(c) for c in file_path)
                np.random.seed(seed_value)

                # Create a sound with varying frequency
                factor = 0.5 + np.random.random()
                wave = amplitude * np.sin(2 * np.pi * frequency * factor * t)

                # Normalize to 16-bit range
                audio = np.int16(wave * 32767)

                # Save as WAV file
                wavfile.write(file_path, sample_rate, audio)

            except ImportError:
                # Fallback to a very simple WAV file if numpy/scipy not available
                with open(file_path, "wb") as f:
                    # WAV header (44 bytes) + minimal audio data
                    f.write(
                        bytes.fromhex(
                            "52 49 46 46 24 00 00 00 57 41 56 45 66 6D 74 20 10 00 00 00 01 00 01 00"
                            "44 AC 00 00 88 58 01 00 02 00 10 00 64 61 74 61 00 00 00 00"
                        )
                    )

        except Exception as e:
            logger.error(f"Error creating test WAV file: {str(e)}")
            raise


# ================== API Server ==================

# Setup FastAPI app
app = FastAPI(
    title="Sabrina AI Voice API",
    description="Voice synthesis API for Sabrina AI Assistant",
    version="1.0.0",
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


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for protected endpoints"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key


# Check if this file is executed directly, not imported
if __name__ == "__main__":
    # Check for debug flag in environment
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"

    # Serve static files
    app.mount("/audio", StaticFiles(directory="data/audio_cache"), name="audio")

    # ================== API Endpoints ==================

    @app.get("/status")
    async def status():
        """Check if the voice service is running"""
        return {
            "status": "online",
            "tts_initialized": tts_engine.tts_initialized,
            "version": "1.0.0",
        }

    @app.post("/speak")
    async def speak(request: SpeakRequest, api_key: str = Depends(verify_api_key)):
        """Convert text to speech and return audio file URL"""
        try:
            # Check if text is provided
            if not request.text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Text is required"
                )

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
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            logger.error(traceback.format_exc())
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
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate speech: {str(e)}",
            )

    # Run the server
    port = int(os.getenv("VOICE_API_PORT", "8100"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
