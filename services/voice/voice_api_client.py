"""
Voice API Client for Sabrina AI
Provides a client interface for interacting with the Voice API
"""

import os
import logging
from typing import Dict, Any, Optional

import requests
from requests.exceptions import RequestException

from .voice_settings import VoiceSettings, voice_settings_manager

logger = logging.getLogger(__name__)


class VoiceAPIClient:
    """
    Client for interacting with the Sabrina AI Voice API

    Provides methods for speech generation, settings management,
    and API service interaction
    """

    def __init__(self, base_url: str = "http://localhost:8100", timeout: int = 10):
        """
        Initialize Voice API Client

        Args:
            base_url: Base URL for the Voice API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Track connection status
        self.connected = self.test_connection()

    def test_connection(self) -> bool:
        """
        Test connection to the Voice API

        Returns:
            Boolean indicating API availability
        """
        try:
            response = requests.get(f"{self.base_url}/status", timeout=self.timeout)
            return response.status_code == 200
        except RequestException as e:
            logger.error(f"Voice API connection failed: {e}")
            return False

    def speak(
        self,
        text: str,
        settings: Optional[VoiceSettings] = None,
        save_path: Optional[str] = None,
    ) -> str:
        """
        Generate speech by sending text to the Voice API

        Args:
            text: Text to convert to speech
            settings: Optional voice settings
            save_path: Optional path to save the audio file

        Returns:
            Path to generated audio file
        """
        # Use default settings if not provided
        settings = settings or voice_settings_manager.get_settings()

        try:
            # Prepare request payload
            payload = {
                "text": text,
                "voice": settings.voice,
                "volume": settings.volume,
                "speed": settings.speed,
                "pitch": settings.pitch,
                "emotion": settings.emotion,
            }

            # Send request to Voice API
            response = requests.post(
                f"{self.base_url}/speak", json=payload, timeout=self.timeout
            )

            # Validate response
            response.raise_for_status()

            # Determine save path
            if not save_path:
                save_dir = os.path.join("data", "audio_output")
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"sabrina_speech_{hash(text)}.wav")

            # Save audio file
            with open(save_path, "wb") as f:
                f.write(response.content)

            logger.info(f"Speech generated and saved to {save_path}")
            return save_path

        except RequestException as e:
            logger.error(f"Speech generation error: {e}")
            raise

    def get_settings(self) -> Dict[str, Any]:
        """
        Retrieve current voice settings from API

        Returns:
            Current voice settings dictionary
        """
        try:
            response = requests.get(f"{self.base_url}/settings", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Failed to retrieve voice settings: {e}")
            # Fallback to local settings
            return voice_settings_manager.get_settings().dict()

    def update_settings(self, **kwargs) -> Dict[str, Any]:
        """
        Update voice settings via API

        Args:
            **kwargs: Voice settings to update

        Returns:
            Updated voice settings dictionary
        """
        try:
            response = requests.post(
                f"{self.base_url}/settings", json=kwargs, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Failed to update voice settings: {e}")
            # Fallback to local settings update
            return voice_settings_manager.update_settings(kwargs).dict()

    def list_voices(self) -> list:
        """
        List available TTS voices

        Returns:
            List of available voice models
        """
        try:
            response = requests.get(f"{self.base_url}/voices", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    def clear_cache(self) -> bool:
        """
        Clear the TTS audio cache

        Returns:
            True if cache was cleared successfully
        """
        try:
            response = requests.get(
                f"{self.base_url}/cache/clear", timeout=self.timeout
            )
            response.raise_for_status()
            logger.info("TTS cache cleared successfully")
            return True
        except RequestException as e:
            logger.error(f"Failed to clear TTS cache: {e}")
            return False
