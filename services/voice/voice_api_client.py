"""
Modified Voice API Client for Sabrina AI
======================================
Improved version of the voice client with better Docker compatibility
and more robust audio file handling.
"""

import os
import time
import logging
import requests
import tempfile
from typing import Dict, Any, List, Optional
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("voice_api_client")

# Try to import improved audio playback
try:
    from voice_playback import play_audio, stop_audio, is_playing

    audio_playback_available = True
    logger.info("Audio playback module loaded successfully")
except ImportError:
    logger.warning("Audio playback module not found, attempting fallback methods")

    # Try to find standard audio libraries
    audio_playback_available = False
    standard_audio_available = False

    try:
        import pygame

        pygame.mixer.init(frequency=48000)

        def play_audio(file_path):
            try:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()

                # Wait for playback to complete
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                return True
            except Exception as e:
                logger.error(f"Pygame audio playback failed: {e}")
                return False

        def stop_audio():
            try:
                pygame.mixer.music.stop()
            except Exception as e:
                logger.warning(f"Error: {e}")
                pass

        def is_playing():
            try:
                return pygame.mixer.music.get_busy()
            except Exception as e:
                logger.warning(f"Error: {e}")
                return False

        audio_playback_available = True
        standard_audio_available = True
        logger.info("Using pygame for audio playback")
    except ImportError:
        logger.debug("pygame not available")

    # Try sounddevice if pygame failed
    if not standard_audio_available:
        try:
            import sounddevice as sd
            import soundfile as sf

            def play_audio(file_path):
                try:
                    data, samplerate = sf.read(file_path)
                    sd.play(data, samplerate)
                    sd.wait()  # Wait until playback is finished
                    return True
                except Exception as e:
                    logger.error(f"Sounddevice audio playback failed: {e}")
                    return False

            def stop_audio():
                try:
                    sd.stop()
                except Exception as e:
                    logger.warning(f"Error: {e}")
                    pass

            def is_playing():
                try:
                    return sd.get_status().active
                except Exception as e:
                    logger.warning(f"Error: {e}")
                    return False

            audio_playback_available = True
            standard_audio_available = True
            logger.info("Using sounddevice for audio playback")
        except ImportError:
            logger.debug("sounddevice not available")

    # If all else fails, use dummy functions
    if not standard_audio_available:

        def play_audio(file_path):
            logger.info(f"Would play audio file: {file_path}")
            return False

        def stop_audio():
            pass

        def is_playing():
            return False

        logger.warning("Using dummy audio playback functions (no audio will play)")


class VoiceAPIClient:
    """Client for the Sabrina AI Voice API with improved file handling"""

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
        self.last_audio_file = None
        self.temp_files = []
        self.temp_dir = tempfile.mkdtemp(prefix="sabrina_voice_")

        # Use a persistent session for better performance
        self.session = requests.Session()

        # Set default headers for all requests
        self.session.headers.update(self.headers)

        # Test connection during initialization
        self.connected = self.test_connection()

        # Clean up temporary files on exit
        import atexit

        atexit.register(self._cleanup_temp_files)

        logger.info(f"Temporary directory created: {self.temp_dir}")

    def _cleanup_temp_files(self):
        """Clean up temporary files when the program exits"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.debug(f"Error cleaning up temp file {file_path}: {e}")

        # Try to remove the temp directory
        try:
            if os.path.exists(self.temp_dir):
                import shutil

                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Error: {e}")
            pass

    def test_connection(self) -> bool:
        """
        Test connection to the Voice API

        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            response = self.session.get(f"{self.api_url}/status", timeout=3.0)
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

        # Stop any current playback
        if audio_playback_available:
            stop_audio()

        try:
            # Prepare request payload
            payload = {"text": text}

            # Add optional parameters if provided
            for key in ["voice", "speed", "pitch", "volume", "emotion", "cache"]:
                if key in kwargs and kwargs[key] is not None:
                    payload[key] = kwargs[key]

            # Make API request
            response = self.session.post(
                f"{self.api_url}/speak",
                json=payload,
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                audio_url = data.get("audio_url")

                if audio_url:
                    # Get full audio URL
                    full_audio_url = f"{self.api_url}{audio_url}"
                    logger.info(f"Speech generated successfully: {full_audio_url}")

                    # Download and play the audio if playback is available
                    if audio_playback_available:
                        # Download the audio file
                        audio_file = self._download_audio(full_audio_url)
                        if audio_file:
                            # Play the audio
                            self.last_audio_file = audio_file
                            playback_success = play_audio(audio_file)
                            if not playback_success:
                                logger.warning(
                                    f"Audio playback failed for: {audio_file}"
                                )
                            return True
                        else:
                            logger.error("Failed to download audio file")
                            return False
                    else:
                        # No audio playback, but API request was successful
                        logger.info(
                            "Audio playback not available, but speech was generated successfully"
                        )
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

    def _download_audio(self, audio_url: str) -> Optional[str]:
        """
        Download audio file from URL to a clean temporary location

        Args:
            audio_url: URL of the audio file

        Returns:
            Path to the downloaded file, or None if download failed
        """
        try:
            # Create a unique filename based on url path
            url_path = audio_url.split("/")[-1]
            temp_path = os.path.join(self.temp_dir, f"voice_{url_path}")

            # Download the file
            response = self.session.get(audio_url, stream=True, timeout=10.0)

            if response.status_code == 200:
                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Add to cleanup list
                self.temp_files.append(temp_path)
                logger.info(f"Downloaded audio to {temp_path}")
                return temp_path
            else:
                logger.error(f"Failed to download audio: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading audio: {str(e)}")
            return None

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
            response = self.session.post(
                f"{self.api_url}/speak_simple", params={"text": text}, timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                audio_url = data.get("audio_url")

                if audio_url:
                    # Get full audio URL
                    full_audio_url = f"{self.api_url}{audio_url}"
                    logger.info(f"Speech generated successfully: {full_audio_url}")

                    # Download and play the audio if playback is available
                    if audio_playback_available:
                        audio_file = self._download_audio(full_audio_url)
                        if audio_file:
                            self.last_audio_file = audio_file
                            play_audio(audio_file)
                            return True
                    else:
                        # No audio playback, but API request was successful
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
            response = self.session.get(f"{self.api_url}/voices", timeout=5.0)

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
            response = self.session.get(f"{self.api_url}/settings", timeout=5.0)

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
            response = self.session.post(
                f"{self.api_url}/settings",
                json=settings,
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
                # Create event object - use standard EventType.VOICE if available
                event_type = getattr(self.event_bus, "EventType", None)
                if event_type and hasattr(event_type, "VOICE"):
                    event_cls = getattr(self.event_bus, "Event", None)
                    if event_cls:
                        event = event_cls(
                            event_type=event_type.VOICE,
                            data={"status": "speaking_started", "text": text},
                            source="enhanced_voice_client",
                        )
                        self.event_bus.post_event(event)
                    else:
                        logger.debug("Event class not found, using create_event method")
                        event = self.event_bus.create_event(
                            event_type="VOICE",
                            data={"status": "speaking_started", "text": text},
                            source="enhanced_voice_client",
                        )
                        self.event_bus.post_event(event)
                else:
                    logger.debug("EventType.VOICE not found, using string 'VOICE'")
                    # Fall back to simple event posting
                    self.event_bus.post_event(
                        self.event_bus.create_event(
                            event_type="VOICE",
                            data={"status": "speaking_started", "text": text},
                            source="enhanced_voice_client",
                        )
                    )
            except Exception as e:
                logger.error(f"Error posting speaking_started event: {str(e)}")
                logger.error(traceback.format_exc())

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

                # Create and post event with type adaptation
                event_type = getattr(self.event_bus, "EventType", None)
                if event_type and hasattr(event_type, "VOICE"):
                    event_cls = getattr(self.event_bus, "Event", None)
                    if event_cls:
                        event = event_cls(
                            event_type=event_type.VOICE,
                            data=event_data,
                            source="enhanced_voice_client",
                        )
                        self.event_bus.post_event(event)
                    else:
                        event = self.event_bus.create_event(
                            event_type="VOICE",
                            data=event_data,
                            source="enhanced_voice_client",
                        )
                        self.event_bus.post_event(event)
                else:
                    # Fall back to simple event posting
                    self.event_bus.post_event(
                        self.event_bus.create_event(
                            event_type="VOICE",
                            data=event_data,
                            source="enhanced_voice_client",
                        )
                    )
            except Exception as e:
                logger.error(f"Error posting {event_status} event: {str(e)}")
                logger.error(traceback.format_exc())

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

    def is_speaking(self) -> bool:
        """
        Check if currently speaking

        Returns:
            bool: True if speaking, False otherwise
        """
        return self.speaking
