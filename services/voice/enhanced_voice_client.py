"""
Fixed Enhanced Voice Client for Sabrina AI
=========================================
This version fixes the event bus integration to properly work with Sabrina's EventBus implementation.
"""

import time
import logging
from typing import Dict, Any

# Import base client
from services.voice.voice_api_client import VoiceAPIClient

# Import event system components
from utilities.event_system import Event, EventType

# Configure logging
logger = logging.getLogger("enhanced_voice_client")


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

        # When posting speaking_started event:
        if self.event_bus:
            try:
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.VOICE,  # Make sure this is the same as below
                        data={"status": "speaking_started", "text": text},
                        source="enhanced_voice_client",
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
                event_status = "speaking_completed" if success else "speaking_failed"
                event_data = {"status": event_status, "text": text, "success": success}

                # Create and post event using correct method
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.VOICE,  # Use EventType.VOICE from your event system
                        data=event_data,
                        source="enhanced_voice_client",
                    )
                )
            except Exception as e:
                logger.error(f"Error posting {event_status} event: {str(e)}")
                import traceback

                logger.error(traceback.format_exc())

        return success

    def test_connection(self) -> bool:
        """Test connection to the Voice API"""
        return self.client.test_connection()

    def get_voices(self):
        """Get list of available voices"""
        return self.client.get_voices()

    def get_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self.client.get_settings()

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update voice settings"""
        return self.client.update_settings(settings)

    def is_speaking(self) -> bool:
        """
        Check if currently speaking

        Returns:
            bool: True if speaking, False otherwise
        """
        return self.speaking
