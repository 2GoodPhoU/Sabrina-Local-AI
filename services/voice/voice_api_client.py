"""
Enhanced Voice API Client for Sabrina AI
=======================================
This module provides an improved client for interacting with the Voice API service,
with better event system integration and error handling.
"""

import os
import json
import time
import logging
import requests
import tempfile
import subprocess
from typing import Dict, Any, Optional, Union

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_api_client")

class EnhancedVoiceClient:
    """
    Enhanced client for the Voice API service with robust error handling, retries,
    and event system integration.
    
    This client handles:
    - Text-to-speech requests with event notifications
    - Audio playback
    - Voice configuration settings management
    - Integration with the Sabrina event system
    """
    
    def __init__(self, api_url: str = "http://localhost:8100", event_bus=None):
        """
        Initialize the Voice API client
        
        Args:
            api_url: Base URL for the Voice API service
            event_bus: Event bus instance for sending/receiving events
        """
        self.api_url = api_url.rstrip('/')
        self.event_bus = event_bus
        self.last_request_time = 0
        self.last_audio_file = None
        self.connected = False
        self.retries = 3
        self.retry_delay = 1.0  # seconds
        self.timeout = 10.0  # seconds
        
        # Voice settings
        self.settings = {
            "speed": 1.0,
            "pitch": 1.0,
            "emotion": "normal",
            "volume": 0.8
        }
        
        # Load settings from file if available
        self._load_settings()
        
        logger.info(f"Enhanced Voice API client initialized with API URL: {api_url}")
        
        # Test connection on initialization
        self.test_connection()
        
        # Register for voice events if event bus is provided
        if self.event_bus:
            self._register_event_handlers()
    
    def _register_event_handlers(self):
        """Register handlers for voice-related events"""
        try:
            # Import here to avoid circular imports
            from utilities.event_system import EventType, EventPriority
            
            # Register handler for VOICE events
            handler = self.event_bus.create_event_handler(
                event_types=[EventType.VOICE],
                callback=self._handle_voice_event,
                min_priority=EventPriority.NORMAL
            )
            self.event_bus.register_handler(handler)
            
            logger.info("Registered voice event handler")
        except Exception as e:
            logger.error(f"Failed to register event handlers: {str(e)}")
    
    def _handle_voice_event(self, event):
        """
        Handle voice events from the event system
        
        Args:
            event: Voice event with text to speak
        """
        # Extract text from event data
        text = event.data.get("text", "")
        if not text:
            logger.warning("Received voice event without text")
            return
        
        # Extract optional settings from event data
        settings = event.data.get("settings", {})
        if settings:
            # Temporarily update settings for this request
            old_settings = self.settings.copy()
            self.update_settings(settings)
            
            # Speak the text
            result = self.speak(text)
            
            # Restore original settings
            self.settings = old_settings
        else:
            # Speak with current settings
            result = self.speak(text)
        
        # Post result event if event bus is available
        if self.event_bus and hasattr(self.event_bus, 'post_event'):
            try:
                from utilities.event_system import Event, EventType, EventPriority
                
                # Post result event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.VOICE_RESULT,
                        data={
                            "text": text,
                            "success": result is not None,
                            "audio_file": result
                        },
                        source="voice_client"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to post voice result event: {str(e)}")
    
    def _load_settings(self):
        """Load voice settings from file"""
        settings_file = "config/voice_settings.json"
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    saved_settings = json.load(f)
                
                # Update settings with saved values
                for key, value in saved_settings.items():
                    if key in self.settings:
                        self.settings[key] = value
                
                logger.info("Loaded voice settings from file")
            except Exception as e:
                logger.error(f"Failed to load voice settings: {str(e)}")
    
    def _save_settings(self):
        """Save current voice settings to file"""
        try:
            # Ensure config directory exists
            os.makedirs("config", exist_ok=True)
            
            # Save settings to file
            with open("config/voice_settings.json", 'w') as f:
                json.dump(self.settings, f, indent=2)
            
            logger.info("Saved voice settings to file")
        except Exception as e:
            logger.error(f"Failed to save voice settings: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test the connection to the Voice API service
        
        Returns:
            bool: True if connected, False otherwise
        """
        try:
            response = requests.get(f"{self.api_url}/status", timeout=self.timeout)
            self.connected = response.status_code == 200
            
            if self.connected:
                logger.info("Successfully connected to Voice API service")
                
                # If connected and event bus is available, post status event
                if self.event_bus and hasattr(self.event_bus, 'post_event'):
                    try:
                        from utilities.event_system import Event, EventType, EventPriority
                        
                        # Post status event
                        self.event_bus.post_event(
                            Event(
                                event_type=EventType.COMPONENT_STATUS,
                                data={
                                    "component": "voice",
                                    "status": "connected",
                                    "url": self.api_url
                                },
                                source="voice_client"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to post status event: {str(e)}")
                
                return True
            else:
                logger.warning(f"Voice API connection test failed: {response.status_code}")
                
                # If not connected and event bus is available, post status event
                if self.event_bus and hasattr(self.event_bus, 'post_event'):
                    try:
                        from utilities.event_system import Event, EventType, EventPriority
                        
                        # Post status event
                        self.event_bus.post_event(
                            Event(
                                event_type=EventType.COMPONENT_STATUS,
                                data={
                                    "component": "voice",
                                    "status": "disconnected",
                                    "url": self.api_url,
                                    "error": f"Failed to connect: {response.status_code}"
                                },
                                source="voice_client",
                                priority=EventPriority.HIGH
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to post status event: {str(e)}")
                
                return False
                
        except requests.RequestException as e:
            logger.error(f"Failed to connect to Voice API: {str(e)}")
            self.connected = False
            
            # If not connected and event bus is available, post status event
            if self.event_bus and hasattr(self.event_bus, 'post_event'):
                try:
                    from utilities.event_system import Event, EventType, EventPriority
                    
                    # Post status event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.COMPONENT_STATUS,
                            data={
                                "component": "voice",
                                "status": "error",
                                "url": self.api_url,
                                "error": str(e)
                            },
                            source="voice_client",
                            priority=EventPriority.HIGH
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to post status event: {str(e)}")
            
            return False
    
    def speak(self, text: str) -> Optional[str]:
        """
        Send text to the Voice API for TTS processing and play the resulting audio
        
        Args:
            text: Text to convert to speech
            
        Returns:
            str: Path to the generated audio file, or None if failed
        """
        if not text or not isinstance(text, str) or not text.strip():
            logger.warning("Empty or invalid text provided to speak function")
            return None
        
        # Log the request
        logger.info(f"Sending TTS request: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        # Post event about starting speech if event bus is available
        if self.event_bus and hasattr(self.event_bus, 'post_event'):
            try:
                from utilities.event_system import Event, EventType
                
                # Post speech start event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.VOICE_STATUS,
                        data={
                            "status": "speaking_started",
                            "text": text
                        },
                        source="voice_client"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to post speech start event: {str(e)}")
        
        # Rate limiting - avoid sending requests too quickly
        elapsed = time.time() - self.last_request_time
        if elapsed < 0.1:  # Minimum 100ms between requests
            time.sleep(0.1 - elapsed)
        
        # Update last request time
        self.last_request_time = time.time()
        
        # Try to generate speech with retries
        for attempt in range(self.retries):
            try:
                # Prepare request parameters
                params = {
                    "text": text,
                    **self.settings
                }
                
                # Send request to voice API
                response = requests.get(
                    f"{self.api_url}/speak",
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    # Save audio to temporary file
                    audio_file = self._save_audio(response.content)
                    if audio_file:
                        # Play audio
                        self._play_audio(audio_file)
                        
                        # Store last audio file
                        self.last_audio_file = audio_file
                        
                        # Post event about completed speech if event bus is available
                        if self.event_bus and hasattr(self.event_bus, 'post_event'):
                            try:
                                from utilities.event_system import Event, EventType
                                
                                # Post speech completed event
                                self.event_bus.post_event(
                                    Event(
                                        event_type=EventType.VOICE_STATUS,
                                        data={
                                            "status": "speaking_completed",
                                            "text": text,
                                            "audio_file": audio_file
                                        },
                                        source="voice_client"
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Failed to post speech completed event: {str(e)}")
                        
                        return audio_file
                    else:
                        logger.error("Failed to save audio file")
                else:
                    logger.error(f"Voice API error: {response.status_code}, {response.text}")
                
                # If we get here, the request failed
                if attempt < self.retries - 1:
                    logger.warning(f"Retrying TTS request (attempt {attempt + 1}/{self.retries})")
                    time.sleep(self.retry_delay)
                
            except requests.RequestException as e:
                logger.error(f"Failed to reach Voice API: {str(e)}")
                
                if attempt < self.retries - 1:
                    logger.warning(f"Retrying TTS request (attempt {attempt + 1}/{self.retries})")
                    time.sleep(self.retry_delay)
        
        # All retries failed
        logger.error(f"Failed to generate speech after {self.retries} attempts")
        
        # Post event about failed speech if event bus is available
        if self.event_bus and hasattr(self.event_bus, 'post_event'):
            try:
                from utilities.event_system import Event, EventType, EventPriority
                
                # Post speech failed event
                self.event_bus.post_event(
                    Event(
                        event_type=EventType.VOICE_STATUS,
                        data={
                            "status": "speaking_failed",
                            "text": text,
                            "error": "Failed to generate speech after multiple attempts"
                        },
                        source="voice_client",
                        priority=EventPriority.HIGH
                    )
                )
            except Exception as e:
                logger.error(f"Failed to post speech failed event: {str(e)}")
        
        return None
    
    def _save_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Save audio data to a temporary file
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            str: Path to the saved audio file, or None if failed
        """
        try:
            # Create a temporary file with .wav extension
            fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            logger.debug(f"Saved audio to {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error saving audio file: {str(e)}")
            return None
    
    def _play_audio(self, audio_file: str) -> bool:
        """
        Play an audio file using an appropriate player for the platform
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return False
        
        try:
            # Play audio based on platform
            if os.name == 'nt':  # Windows
                subprocess.Popen(['start', '', audio_file], shell=True)
            elif os.name == 'posix':  # Linux/Mac
                if os.uname().sysname == 'Darwin':  # Mac
                    subprocess.Popen(['afplay', audio_file])
                else:  # Linux
                    subprocess.Popen(['aplay', audio_file])
            
            logger.debug(f"Playing audio file: {audio_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error playing audio file: {str(e)}")
            return False
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update voice settings
        
        Args:
            settings: Dictionary of settings to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not isinstance(settings, dict):
            logger.error("Invalid settings: not a dictionary")
            return False
        
        # Track if any settings were updated
        updated = False
        
        # Validate and update settings
        for key, value in settings.items():
            if key not in self.settings:
                logger.warning(f"Unknown voice setting: {key}")
                continue
            
            # Type checking and validation
            if key == "speed" or key == "pitch":
                # Must be a float between 0.5 and 2.0
                if not isinstance(value, (int, float)):
                    logger.warning(f"Invalid value for {key}: {value} (must be a number)")
                    continue
                
                value = float(value)
                if value < 0.5 or value > 2.0:
                    logger.warning(f"Invalid value for {key}: {value} (must be between 0.5 and 2.0)")
                    continue
                
            elif key == "emotion":
                # Must be a string from the allowed emotions
                if not isinstance(value, str):
                    logger.warning(f"Invalid value for {key}: {value} (must be a string)")
                    continue
                
                allowed_emotions = ["normal", "happy", "sad", "angry", "excited", "calm"]
                if value.lower() not in allowed_emotions:
                    logger.warning(f"Invalid emotion: {value} (must be one of {allowed_emotions})")
                    continue
                
                value = value.lower()
                
            elif key == "volume":
                # Must be a float between 0.0 and 1.0
                if not isinstance(value, (int, float)):
                    logger.warning(f"Invalid value for {key}: {value} (must be a number)")
                    continue
                
                value = float(value)
                if value < 0.0 or value > 1.0:
                    logger.warning(f"Invalid value for {key}: {value} (must be between 0.0 and 1.0)")
                    continue
            
            # Update the setting if it changed
            if self.settings.get(key) != value:
                self.settings[key] = value
                updated = True
                logger.debug(f"Updated voice setting: {key} = {value}")
        
        # Save settings if updated
        if updated:
            self._save_settings()
            
            # Post settings change event if event bus is available
            if self.event_bus and hasattr(self.event_bus, 'post_event'):
                try:
                    from utilities.event_system import Event, EventType
                    
                    # Post settings change event
                    self.event_bus.post_event(
                        Event(
                            event_type=EventType.SETTINGS_CHANGE,
                            data={
                                "component": "voice",
                                "settings": self.settings
                            },
                            source="voice_client"
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to post settings change event: {str(e)}")
        
        return True
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get current voice settings
        
        Returns:
            Dict of current voice settings
        """
        return self.settings.copy()
    
    def set_speed(self, speed: float) -> bool:
        """
        Set voice speed
        
        Args:
            speed: Speed multiplier (0.5 to 2.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings({"speed": speed})
    
    def set_pitch(self, pitch: float) -> bool:
        """
        Set voice pitch
        
        Args:
            pitch: Pitch multiplier (0.5 to 2.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings({"pitch": pitch})
    
    def set_emotion(self, emotion: str) -> bool:
        """
        Set voice emotion
        
        Args:
            emotion: Emotion name (normal, happy, sad, angry, excited, calm)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings({"emotion": emotion})
    
    def set_volume(self, volume: float) -> bool:
        """
        Set voice volume
        
        Args:
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_settings({"volume": volume})
    
    def get_last_audio_file(self) -> Optional[str]:
        """
        Get the path to the last generated audio file
        
        Returns:
            str: Path to the last audio file, or None if none exists
        """
        return self.last_audio_file
    
    def get_voices(self) -> List[Dict[str, Any]]:
        """
        Get available voices from the Voice API
        
        Returns:
            List of available voices with their properties
        """
        try:
            response = requests.get(f"{self.api_url}/voices", timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get voices: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting voices: {str(e)}")
            return []