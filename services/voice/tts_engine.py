"""
Text-to-Speech Engine for Sabrina AI Voice Module
Uses Coqui TTS for high-quality speech synthesis with advanced features
"""

import os
import hashlib
import logging
import threading
from typing import Optional, Dict, Any

import torch
import sounddevice as sd
import soundfile as sf
from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer

from .voice_settings import VoiceSettings, voice_settings_manager

logger = logging.getLogger(__name__)


class TTSEngine:
    """Advanced Text-to-Speech engine with caching and emotion modulation"""

    def __init__(
        self, models_dir: str = "models/tts", cache_dir: str = "data/tts_cache"
    ):
        """
        Initialize TTS Engine

        Args:
            models_dir: Directory to store TTS models
            cache_dir: Directory to cache generated audio
        """
        self.models_dir = models_dir
        self.cache_dir = cache_dir

        # Create necessary directories
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)

        # Model and synthesizer placeholders
        self.model_manager = None
        self.synthesizer = None
        self.current_model = None

        # Audio generation lock
        self._generation_lock = threading.Lock()

        # Voice settings
        self.voice_settings = voice_settings_manager.get_settings()

        # Initialize TTS
        self._initialize_tts()

    def _initialize_tts(self):
        """Initialize Coqui TTS model"""
        try:
            # Setup model manager
            self.model_manager = ModelManager(models_dir=self.models_dir)

            # Select model based on settings
            model_name = self.voice_settings.voice
            model_path, config_path, model_item = self.model_manager.download_model(
                model_name
            )

            # Create synthesizer
            self.synthesizer = Synthesizer(
                model_path, config_path, use_cuda=torch.cuda.is_available()
            )

            self.current_model = model_name
            logger.info(f"Initialized TTS with model: {model_name}")

        except Exception as e:
            logger.error(f"TTS initialization failed: {e}")
            raise

    def _generate_cache_key(self, text: str, settings: Dict[str, Any]) -> str:
        """
        Generate a unique cache key for generated speech

        Args:
            text: Input text
            settings: Voice generation settings

        Returns:
            Unique hash key for caching
        """
        key_data = f"{text}_{settings}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def generate_speech(
        self, text: str, settings: Optional[VoiceSettings] = None
    ) -> str:
        """
        Generate speech audio from text

        Args:
            text: Text to synthesize
            settings: Optional voice settings override

        Returns:
            Path to generated audio file
        """
        # Use provided or default settings
        settings = settings or self.voice_settings

        # Thread-safe generation
        with self._generation_lock:
            try:
                # Check cache if enabled
                if settings.cache_enabled:
                    cache_key = self._generate_cache_key(text, settings.dict())
                    cache_path = os.path.join(self.cache_dir, f"{cache_key}.wav")

                    if os.path.exists(cache_path):
                        logger.info(f"Using cached audio for: {text}")
                        return cache_path

                # Generate audio
                wav = self.synthesizer.tts(
                    text,
                    speaker_wav=None,  # No speaker reference audio
                    language=settings.language,
                    emotion=settings.emotion,  # Experimental emotion parameter
                    speed=settings.speed,
                )

                # Adjust volume
                wav = [int(sample * settings.volume * 32767) for sample in wav]

                # Save to file
                output_path = os.path.join(
                    self.cache_dir,
                    f"{self._generate_cache_key(text, settings.dict())}.wav",
                )
                sf.write(output_path, wav, 22050)  # 22.05 kHz standard TTS sample rate

                logger.info(f"Generated speech: {output_path}")
                return output_path

            except Exception as e:
                logger.error(f"Speech generation error: {e}")
                raise

    def speak(
        self,
        text: str,
        settings: Optional[VoiceSettings] = None,
        play_audio: bool = True,
    ) -> str:
        """
        Generate and optionally play speech

        Args:
            text: Text to speak
            settings: Optional voice settings
            play_audio: Whether to play audio immediately

        Returns:
            Path to audio file
        """
        audio_path = self.generate_speech(text, settings)

        if play_audio:
            try:
                # Read audio file
                data, samplerate = sf.read(audio_path)

                # Play audio
                sd.play(data, samplerate)
                sd.wait()  # Block until playback complete
            except Exception as e:
                logger.error(f"Audio playback error: {e}")

        return audio_path

    def list_available_voices(self) -> list:
        """
        List available TTS voices

        Returns:
            List of available voice model names
        """
        try:
            return self.model_manager.list_models()
        except Exception as e:
            logger.error(f"Error listing voices: {e}")
            return []


# Global TTS engine instance
tts_engine = TTSEngine()
