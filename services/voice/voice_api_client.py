"""
Sabrina AI Voice API Client
=========================
Client library for interacting with the Voice API service.

This module provides a simple interface for other Sabrina AI components
to use the voice synthesis capabilities without directly dealing with
the API requests and responses.
"""

import os
import time
import logging
import requests
from typing import Dict, Any, List
import traceback

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
                    full_audio_url = f"{self.api_url}{audio_url}"
                    logger.info(f"Speech generated successfully: {full_audio_url}")
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
            logger.error(f"Error in speak request: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in speak: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def speak_simple(self, text: str) -> bool:
        """
        Simple text-to-speech without authentication or additional parameters

        Args:
            text: Text to convert to speech

        Returns:
            bool: True if successful, False otherwise
        """
        if not text:
            logger.warning("Empty text provided to speak_simple method")
            return False

        try:
            response = requests.post(
                f"{self.api_url}/speak_simple", params={"text": text}, timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                audio_url = data.get("audio_url")

                if audio_url:
                    # In a real implementation, we might play the audio file here
                    full_audio_url = f"{self.api_url}{audio_url}"
                    logger.info(f"Speech generated successfully: {full_audio_url}")
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

    def get_voices(self) -> List[str]:
        """
        Get list of available voices

        Returns:
            List of voice names or empty list if failed
        """
        # Use cached result if available
        if self.voices_cache is not None:
            return self.voices_cache

        try:
            response = requests.get(
                f"{self.api_url}/voices", headers=self.headers, timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                self.voices_cache = data.get("voices", [])
                return self.voices_cache
            else:
                logger.error(
                    f"Failed to get voices: {response.status_code} - {response.text}"
                )
                return []

        except requests.RequestException as e:
            logger.error(f"Error in get_voices request: {str(e)}")
            return []

    def get_settings(self) -> Dict[str, Any]:
        """
        Get current voice settings

        Returns:
            Dict with settings or empty dict if failed
        """
        try:
            response = requests.get(
                f"{self.api_url}/settings", headers=self.headers, timeout=5.0
            )

            if response.status_code == 200:
                self.settings_cache = response.json()
                return self.settings_cache
            else:
                logger.error(
                    f"Failed to get settings: {response.status_code} - {response.text}"
                )
                return {}

        except requests.RequestException as e:
            logger.error(f"Error in get_settings request: {str(e)}")
            return {}

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update voice settings

        Args:
            settings: Dictionary with settings to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            response = requests.post(
                f"{self.api_url}/settings",
                json=settings,
                headers=self.headers,
                timeout=5.0,
            )

            if response.status_code == 200:
                # Update cache
                self.settings_cache = response.json().get("settings", {})
                logger.info("Voice settings updated successfully")
                return True
            else:
                logger.error(
                    f"Failed to update settings: {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            logger.error(f"Error in update_settings request: {str(e)}")
            return False


class EnhancedVoiceClient:
    """
    Enhanced Voice Client with event bus integration for Sabrina AI

    This client extends the base VoiceAPIClient with additional features:
    - Event bus integration for event-driven architecture
    - Enhanced error handling and retry mechanisms
    - Status tracking and monitoring
    """

    def __init__(self, api_url="http://localhost:8100", event_bus=None, api_key=None):
        """
        Initialize the Enhanced Voice Client

        Args:
            api_url: URL of the Voice API service
            event_bus: Event bus instance for event-driven architecture
            api_key: API key for authentication (optional)
        """
        self.client = VoiceAPIClient(api_url, api_key)
        self.event_bus = event_bus
        self.speaking = False
        self.last_text = ""
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    def speak(self, text: str, **kwargs) -> bool:
        """
        Convert text to speech with event notifications

        Args:
            text: Text to convert to speech
            **kwargs: Additional parameters (voice, speed, pitch, volume, emotion)

        Returns:
            bool: True if successful, False otherwise
        """
        # Skip if empty text
        if not text:
            logger.warning("Empty text provided to speak method")
            return False

        # Track speaking state
        self.speaking = True
        self.last_text = text

        # Post event if event bus is available
        if self.event_bus:
            try:
                self.event_bus.post_event(
                    self.event_bus.create_event(
                        event_type="VOICE_STATUS",
                        data={"status": "speaking_started", "text": text},
                    )
                )
            except Exception as e:
                logger.error(f"Error posting speaking_started event: {str(e)}")

        # Call parent speak method
        success = self.client.speak(text, **kwargs)

        # Handle results and retry if needed
        if not success and self.retry_count < self.max_retries:
            self.retry_count += 1
            logger.info(
                f"Retrying speech synthesis (attempt {self.retry_count}/{self.max_retries})"
            )
            time.sleep(self.retry_delay)
            success = self.client.speak(text, **kwargs)

        # Reset retry count
        self.retry_count = 0

        # Update speaking state
        self.speaking = False

        # Post event if event bus is available
        if self.event_bus:
            try:
                event_type = "speaking_completed" if success else "speaking_failed"
                self.event_bus.post_event(
                    self.event_bus.create_event(
                        event_type="VOICE_STATUS",
                        data={"status": event_type, "text": text, "success": success},
                    )
                )
            except Exception as e:
                logger.error(f"Error posting {event_type} event: {str(e)}")

        return success

    def test_connection(self) -> bool:
        """Test connection to the Voice API"""
        return self.client.test_connection()

    def get_voices(self) -> List[str]:
        """Get list of available voices"""
        return self.client.get_voices()

    def get_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self.client.get_settings()

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update voice settings"""
        return self.client.update_settings(settings)
