"""
Sabrina AI Voice API Client
=========================
Client library for interacting with the Voice API service.

This module provides a simple interface for other Sabrina AI components
to use the voice synthesis capabilities without directly dealing with
the API requests and responses.
"""

import os
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("voice_api_client")


class VoiceAPIClient:
    """Client for the Sabrina AI Voice API"""

    def __init__(self, api_url="http://localhost:8100", api_key=None):
        """
        Initialize the Voice API client

        Args:
            api_url: URL of the Voice API service
            api_key: API key for authentication (optional)
        """
        self.api_url = api_url.rstrip("/")  # Remove trailing slash if present
        self.api_key = api_key or os.getenv("VOICE_API_KEY", "sabrina-dev-key")
        self.headers = {"X-API-Key": self.api_key} if self.api_key else {}
        self.connected = False
        self.voices_cache = None
        self.settings_cache = None

        # Test connection during initialization
        self.connected = self.test_connection()

    def test_connection(self) -> bool:
        """
        Test connection to the Voice API

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            response = requests.get(f"{self.api_url}/status", timeout=3.0)
            if response.status_code == 200:
                logger.info(f"Connected to Voice API at {self.api_url}")
                return True
            else:
                logger.warning(
                    f"Voice API responded with status code {response.status_code}"
                )
                return False
        except requests.RequestException as e:
            logger.error(f"Failed to connect to Voice API: {str(e)}")
            return False

    def speak(self, text: str, **kwargs) -> bool:
        """
        Convert text to speech and play it

        Args:
            text: Text to convert to speech
            **kwargs: Additional parameters (voice, speed, pitch, volume, emotion)

        Returns:
            bool: True if successful, False otherwise
        """
        if not text:
            logger.warning("Empty text provided to speak method")
            return False

        # Check if connected
        if not self.connected and not self.test_connection():
            logger.error("Not connected to Voice API")
            return False

        try:
            # Prepare request payload
            payload = {"text": text}

            # Add optional parameters if provided
            for key in ["voice", "speed", "pitch", "volume", "emotion", "cache"]:
                if key in kwargs and kwargs[key] is not None:
                    payload[key] = kwargs[key]

            # Make API request
            response = requests.post(
                f"{self.api_url}/speak",
                json=payload,
                headers=self.headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                audio_url = data.get("audio_url")

                if audio_url:
                    # In a real implementation, we might play the audio file here
                    # For now, we'll just log it
                    full_audio_url = f"{self.api_url}{audio_url}"
                    logger.info(f"Speech generated successfully: {full_audio_url}")

                    # Simulate playing the audio
                    self._play_audio(full_audio_url)
                    return True
                else:
                    logger.warning("No audio URL in response")
                    return False
            else:
                logger.error(
                    f"Voice API request failed: {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Error in speak_simple request: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in speak_simple: {str(e)}")
            return False
