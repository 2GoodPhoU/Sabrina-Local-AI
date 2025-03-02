"""
Enhanced Voice Client for Sabrina AI
===================================
Advanced voice client with additional features for deep integration with the Sabrina AI system.

This module extends the base VoiceAPIClient with:
- Emotional voice synthesis based on content sentiment
- Voice activity tracking and statistics
- Text preprocessing and optimization for better TTS results
- Automatic punctuation and formatting
- Speech queue management
- Voice pattern customization based on context
"""

import re
import time
import logging
import threading
import queue
from typing import Dict, Any, Optional, List, Callable
import traceback

# Import base client
from services.voice.voice_api_client import VoiceAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
)
logger = logging.getLogger("enhanced_voice_client")


class SpeechQueueItem:
    """Represents an item in the speech queue"""

    def __init__(
        self,
        text: str,
        settings: Optional[Dict[str, Any]] = None,
        priority: int = 0,
        callback: Optional[Callable[[bool], None]] = None,
    ):
        """
        Initialize a speech queue item

        Args:
            text: Text to speak
            settings: Voice settings to use
            priority: Priority level (higher = more important)
            callback: Function to call when speech is completed
        """
        self.text = text
        self.settings = settings or {}
        self.priority = priority
        self.callback = callback
        self.timestamp = time.time()
        self.id = f"speech_{int(self.timestamp * 1000)}"

    def __lt__(self, other):
        """Compare items by priority for priority queue"""
        if self.priority == other.priority:
            return self.timestamp < other.timestamp
        return self.priority > other.priority


class EnhancedVoiceClient:
    """
    Advanced voice client with enhanced functionality for Sabrina AI

    Features:
    - Emotional voice synthesis
    - Speech queue management
    - Text preprocessing and optimization
    - Voice activity tracking
    - Event-based integration
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8100",
        event_bus=None,
        api_key: Optional[str] = None,
        voice_profile: str = "default",
        auto_punctuate: bool = True,
        auto_queue: bool = True,
    ):
        """
        Initialize the enhanced voice client

        Args:
            api_url: URL of the Voice API service
            event_bus: Event bus instance for event-driven architecture
            api_key: API key for authentication
            voice_profile: Voice profile to use (default, formal, casual, etc.)
            auto_punctuate: Automatically add punctuation to input text
            auto_queue: Automatically queue speech requests
        """
        # Initialize base client
        self.client = VoiceAPIClient(api_url, api_key)

        # Save parameters
        self.event_bus = event_bus
        self.voice_profile = voice_profile
        self.auto_punctuate = auto_punctuate
        self.auto_queue = auto_queue

        # Initialize state
        self.speaking = False
        self.last_text = ""
        self.last_audio_url = ""
        self.last_settings = {}
        self.speech_count = 0
        self.speech_history = []
        self.max_history = 50
        self.connected = self.client.connected

        # Speech queue
        self.speech_queue = queue.PriorityQueue()
        self.queue_thread = None
        self.queue_running = False
        self.queue_lock = threading.Lock()

        # Voice profiles
        self.voice_profiles = {
            "default": {},
            "formal": {"speed": 0.9, "pitch": 0.95, "volume": 0.8, "emotion": "sad"},
            "assertive": {
                "speed": 1.1,
                "pitch": 1.1,
                "volume": 0.95,
                "emotion": "neutral",
            },
        }

        # Emotion detection patterns
        self.emotion_patterns = {
            "happy": [
                r"great|amazing|wonderful|excellent|fantastic|happy|joy|delighted|excited|pleased",
                r"congratulations|achievement|success|well done|good job|perfect|brilliant",
                r"🙂|😊|😄|😁|😆|😀|🤗|🥰|😍",
            ],
            "sad": [
                r"sad|sorry|unfortunate|regret|disappointed|upset|depressed|unhappy",
                r"bad news|failed|trouble|problem|issue|error|fault|mistake",
                r"😔|😞|😢|😭|😥|😪|😓|😩|😿",
            ],
            "neutral": [
                r"update|status|report|information|data|details|analysis|summary",
                r"normal|standard|regular|usual|typical|common|general|basic",
            ],
        }

        # Start queue processing if auto_queue is enabled
        if self.auto_queue:
            self.start_queue_processing()

    def test_connection(self) -> bool:
        """Test connection to the Voice API"""
        self.connected = self.client.test_connection()
        return self.connected

    def start_queue_processing(self):
        """Start the speech queue processing thread"""
        if self.queue_thread and self.queue_thread.is_alive():
            # Already running
            return

        self.queue_running = True
        self.queue_thread = threading.Thread(
            target=self._process_speech_queue, daemon=True
        )
        self.queue_thread.start()
        logger.info("Speech queue processing started")

    def stop_queue_processing(self):
        """Stop the speech queue processing thread"""
        self.queue_running = False
        if self.queue_thread:
            self.queue_thread.join(timeout=1.0)
        logger.info("Speech queue processing stopped")

    def _process_speech_queue(self):
        """Process items in the speech queue"""
        while self.queue_running:
            try:
                # Get item from queue with timeout
                try:
                    item = self.speech_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                # Process the item
                try:
                    # Set speaking state
                    with self.queue_lock:
                        self.speaking = True

                    # Post event if event bus is available
                    self._post_voice_event(
                        "speaking_started", {"text": item.text, "id": item.id}
                    )

                    # Speak the text
                    success = self.client.speak(item.text, **item.settings)

                    # Call callback if provided
                    if item.callback:
                        try:
                            item.callback(success)
                        except Exception as e:
                            logger.error(f"Error in speech callback: {str(e)}")

                    # Update speech history
                    self._update_speech_history(item.text, success, item.settings)

                    # Post event
                    self._post_voice_event(
                        "speaking_completed" if success else "speaking_failed",
                        {"text": item.text, "success": success, "id": item.id},
                    )

                except Exception as e:
                    logger.error(f"Error processing speech queue item: {str(e)}")
                    if item.callback:
                        try:
                            item.callback(False)
                        except Exception as callback_error:
                            logger.error(
                                f"Error in speech callback: {str(callback_error)}"
                            )

                finally:
                    # Update speaking state
                    with self.queue_lock:
                        self.speaking = False

                    # Mark item as done
                    self.speech_queue.task_done()

            except Exception as e:
                logger.error(f"Error in speech queue processing: {str(e)}")
                logger.error(traceback.format_exc())
                time.sleep(1.0)  # Sleep to avoid tight loop on error

    def speak(self, text: str, **kwargs) -> bool:
        """
        Convert text to speech

        Args:
            text: Text to convert to speech
            **kwargs: Additional parameters (voice, speed, pitch, volume, emotion)

        Returns:
            bool: True if request was accepted, False otherwise
        """
        # Skip if empty text
        if not text or not text.strip():
            logger.warning("Empty text provided to speak method")
            return False

        # Check connection
        if not self.connected and not self.test_connection():
            logger.error("Not connected to Voice API")
            return False

        # Pre-process text
        processed_text = self._preprocess_text(text)
        if not processed_text:
            logger.warning("Text preprocessing resulted in empty text")
            return False

        # Get voice settings
        settings = self._get_voice_settings(processed_text, kwargs)

        # If auto_queue is enabled, add to queue
        if self.auto_queue:
            # Get priority and callback if specified
            priority = kwargs.pop("priority", 0)
            callback = kwargs.pop("callback", None)

            # Create queue item
            item = SpeechQueueItem(
                text=processed_text,
                settings=settings,
                priority=priority,
                callback=callback,
            )

            # Add to queue
            self.speech_queue.put(item)
            logger.debug(
                f"Added text to speech queue (priority={priority}): {processed_text[:50]}..."
            )

            # Make sure queue processing is running
            if (
                not self.queue_running
                or not self.queue_thread
                or not self.queue_thread.is_alive()
            ):
                self.start_queue_processing()

            return True
        else:
            # Speak directly
            with self.queue_lock:
                self.speaking = True

            try:
                # Post event
                self._post_voice_event("speaking_started", {"text": processed_text})

                # Speak the text
                success = self.client.speak(processed_text, **settings)

                # Update speech history
                self._update_speech_history(processed_text, success, settings)

                # Post event
                self._post_voice_event(
                    "speaking_completed" if success else "speaking_failed",
                    {"text": processed_text, "success": success},
                )

                return success

            finally:
                with self.queue_lock:
                    self.speaking = False

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text for better TTS results

        Args:
            text: Input text

        Returns:
            Preprocessed text
        """
        # Skip if empty
        if not text:
            return ""

        # Strip extra whitespace
        result = " ".join(text.split())

        # Add punctuation if enabled and missing
        if self.auto_punctuate and result and not result[-1] in ".!?":
            result += "."

        # Add spacing after punctuation if missing
        result = re.sub(r"([.!?,:;])([a-zA-Z])", r"\1 \2", result)

        # Replace some common abbreviations
        abbreviations = {
            "e.g.": "for example",
            "i.e.": "that is",
            "etc.": "etcetera",
            "vs.": "versus",
            "Dr.": "Doctor",
            "Mr.": "Mister",
            "Mrs.": "Misses",
            "Ms.": "Miss",
            "Prof.": "Professor",
        }

        for abbr, expanded in abbreviations.items():
            result = result.replace(abbr, expanded)

        return result

    def _get_voice_settings(self, text: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get voice settings for the given text

        Args:
            text: Text to analyze
            kwargs: User-provided settings

        Returns:
            Voice settings dictionary
        """
        # Start with profile settings
        profile = self.voice_profiles.get(self.voice_profile, {})
        settings = profile.copy()

        # Detect emotion from text content if not specified
        if "emotion" not in kwargs and self.auto_detect_emotion(text):
            settings["emotion"] = self.auto_detect_emotion(text)

        # Override with user settings
        settings.update({k: v for k, v in kwargs.items() if v is not None})

        return settings

    def auto_detect_emotion(self, text: str) -> Optional[str]:
        """
        Automatically detect emotion from text content

        Args:
            text: Text to analyze

        Returns:
            Detected emotion or None
        """
        if not text:
            return None

        # Convert to lowercase for pattern matching
        lower_text = text.lower()

        # Check each emotion's patterns
        for emotion, patterns in self.emotion_patterns.items():
            for pattern in patterns:
                if re.search(pattern, lower_text):
                    logger.debug(
                        f"Detected emotion '{emotion}' in text: {text[:50]}..."
                    )
                    return emotion

        # Default to None (use profile default)
        return None

    def _update_speech_history(
        self, text: str, success: bool, settings: Dict[str, Any]
    ):
        """
        Update speech history

        Args:
            text: Spoken text
            success: Whether speech was successful
            settings: Voice settings used
        """
        # Update state
        self.last_text = text
        self.last_settings = settings
        self.speech_count += 1

        # Add to history
        history_item = {
            "text": text,
            "success": success,
            "settings": settings,
            "timestamp": time.time(),
        }

        self.speech_history.append(history_item)

        # Trim history if needed
        if len(self.speech_history) > self.max_history:
            self.speech_history = self.speech_history[-self.max_history :]

    def _post_voice_event(self, status: str, data: Dict[str, Any]):
        """
        Post voice event to event bus if available

        Args:
            status: Event status (speaking_started, speaking_completed, etc.)
            data: Event data
        """
        if not self.event_bus:
            return

        try:
            # Create event data
            event_data = {"status": status, **data}

            # Post event
            self.event_bus.post_event(
                self.event_bus.create_event(event_type="VOICE_STATUS", data=event_data)
            )

        except Exception as e:
            logger.error(f"Error posting voice event: {str(e)}")

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update voice settings"""
        return self.client.update_settings(settings)

    def get_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self.client.get_settings()

    def get_voices(self) -> List[str]:
        """Get available voice models"""
        return self.client.get_voices()

    def clear_queue(self):
        """Clear the speech queue"""
        # Create a new queue
        with self.queue_lock:
            old_queue = self.speech_queue
            self.speech_queue = queue.PriorityQueue()

        # Drain the old queue
        try:
            while True:
                old_queue.get_nowait()
                old_queue.task_done()
        except queue.Empty:
            pass

        logger.info("Speech queue cleared")

    def get_queue_size(self) -> int:
        """Get the current size of the speech queue"""
        return self.speech_queue.qsize()

    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        with self.queue_lock:
            return self.speaking

    def set_voice_profile(self, profile: str) -> bool:
        """
        Set the voice profile

        Args:
            profile: Profile name (default, formal, casual, etc.)

        Returns:
            bool: True if profile exists, False otherwise
        """
        if profile in self.voice_profiles:
            self.voice_profile = profile
            logger.info(f"Voice profile set to '{profile}'")
            return True
        else:
            logger.warning(f"Voice profile '{profile}' not found")
            return False

    def add_voice_profile(self, name: str, settings: Dict[str, Any]) -> bool:
        """
        Add a new voice profile

        Args:
            name: Profile name
            settings: Voice settings

        Returns:
            bool: True if added successfully, False otherwise
        """
        if not name or not settings:
            return False

        self.voice_profiles[name] = settings
        logger.info(f"Added voice profile '{name}'")
        return True

    def say_next(self, text: str, **kwargs) -> bool:
        """
        Say text next (add to front of queue)

        Args:
            text: Text to speak
            **kwargs: Additional parameters

        Returns:
            bool: True if added to queue, False otherwise
        """
        # Set highest priority
        kwargs["priority"] = 100
        return self.speak(text, **kwargs)

    def interrupt(self, text: str, **kwargs) -> bool:
        """
        Interrupt current speech and say text immediately

        Args:
            text: Text to speak
            **kwargs: Additional parameters

        Returns:
            bool: True if successful, False otherwise
        """
        # Clear the queue
        self.clear_queue()

        # Say with highest priority
        return self.say_next(text, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get speech statistics

        Returns:
            Dict with statistics
        """
        return {
            "speech_count": self.speech_count,
            "queue_size": self.speech_queue.qsize(),
            "speaking": self.speaking,
            "connected": self.connected,
            "voice_profile": self.voice_profile,
            "auto_queue": self.auto_queue,
            "auto_punctuate": self.auto_punctuate,
        }
