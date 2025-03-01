"""
Enhanced Voice API Client for Sabrina AI
=======================================
A more efficient client for voice synthesis with better error handling,
caching, and improved voice model selection.
"""

import os
import sys
import json
import time
import logging
import requests
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_client")

class VoiceAPIClient:
    """
    Enhanced client for the Voice API with improved reliability and performance.
    """
    
    def __init__(self, api_url: str = "http://localhost:8100", event_bus=None, auto_start=True):
        """Initialize the Voice API client"""
        self.api_url = api_url.rstrip('/')
        self.event_bus = event_bus
        self.auto_start = auto_start
        self.connected = False
        self.retries = 3
        self.retry_delay = 1.0
        self.timeout = 10.0
        self.available_voices = []
        self.last_audio_file = None
        self.audio_cache = {}  # Simple cache for repeated phrases
        self.max_cache_size = 10
        
        # Voice settings
        self.settings = {
            "speed": 1.0,
            "pitch": 1.0,
            "emotion": "normal",
            "volume": 0.8,
            "voice": None  # Will be set after querying available voices
        }
        
        # Find project root directory
        self.project_dir = self._find_project_root()
        
        # Load settings
        self._load_settings()
        
        # Check connection
        self.test_connection()
        
        # Register event handlers if event bus is provided
        if self.event_bus:
            self._register_event_handlers()
    
    def _find_project_root(self) -> Path:
        """Find the project root directory"""
        # Start with the directory of this file
        current_dir = Path(os.path.abspath(__file__)).parent
        
        # Go up until we find a recognizable project structure
        for _ in range(4):  # Limit the search to 4 levels up
            if (current_dir / "services").exists() or (current_dir / "scripts").exists():
                return current_dir
            parent_dir = current_dir.parent
            if parent_dir == current_dir:  # Reached filesystem root
                break
            current_dir = parent_dir
        
        # Fallback to current directory
        return Path(os.getcwd())
    
    def _load_settings(self):
        """Load voice settings from file"""
        settings_file = os.path.join(self.project_dir, "config/voice_settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    saved_settings = json.load(f)
                
                # Update settings with saved values
                for key, value in saved_settings.items():
                    if key in self.settings:
                        self.settings[key] = value
                
                logger.debug("Loaded voice settings from file")
            except Exception as e:
                logger.error(f"Failed to load voice settings: {str(e)}")
    
    def _save_settings(self):
        """Save current voice settings to file"""
        try:
            # Ensure config directory exists
            config_dir = os.path.join(self.project_dir, "config")
            os.makedirs(config_dir, exist_ok=True)
            
            # Save settings to file
            settings_file = os.path.join(config_dir, "voice_settings.json")
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            
            logger.debug("Saved voice settings to file")
        except Exception as e:
            logger.error(f"Failed to save voice settings: {str(e)}")
    
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
        """Handle voice events from the event system"""
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
    
    def test_connection(self) -> bool:
        """Test the connection to the Voice API service"""
        try:
            response = requests.get(f"{self.api_url}/status", timeout=self.timeout)
            self.connected = response.status_code == 200
            
            if self.connected:
                logger.info("Successfully connected to Voice API service")
                
                # Fetch available voices
                self._fetch_available_voices()
                return True
            
            # Try to start the service if auto-start is enabled
            if self.auto_start and not self.connected:
                logger.info("Attempting to start Voice API service...")
                self.start_voice_service()
                
                # Retry connection
                time.sleep(3)  # Wait for service to start
                response = requests.get(f"{self.api_url}/status", timeout=self.timeout)
                self.connected = response.status_code == 200
                
                if self.connected:
                    logger.info("Successfully connected to Voice API service after auto-start")
                    self._fetch_available_voices()
                    return True
            
            logger.warning("Failed to connect to Voice API service")
            return False
            
        except requests.RequestException as e:
            logger.error(f"Error connecting to Voice API: {str(e)}")
            
            if self.auto_start:
                logger.info("Attempting to start Voice API service...")
                self.start_voice_service()
                
                # Retry connection
                try:
                    time.sleep(3)  # Wait for service to start
                    response = requests.get(f"{self.api_url}/status", timeout=self.timeout)
                    self.connected = response.status_code == 200
                    
                    if self.connected:
                        logger.info("Successfully connected to Voice API service after auto-start")
                        self._fetch_available_voices()
                        return True
                except:
                    pass
            
            self.connected = False
            return False
    
    def _fetch_available_voices(self) -> List[str]:
        """Fetch available voices from the API"""
        if not self.connected:
            return []
            
        try:
            response = requests.get(f"{self.api_url}/voices", timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                self.available_voices = data.get("voices", [])
                
                # Update default voice if needed
                default_voice = data.get("default_voice")
                
                if not self.settings["voice"] or self.settings["voice"] not in self.available_voices:
                    if default_voice and default_voice in self.available_voices:
                        self.settings["voice"] = default_voice
                    elif self.available_voices:
                        self.settings["voice"] = self.available_voices[0]
                        
                logger.info(f"Using voice: {self.settings['voice']}")
                return self.available_voices
        except Exception as e:
            logger.error(f"Failed to fetch available voices: {str(e)}")
        
        return []
    
    def start_voice_service(self, timeout=30) -> bool:
        """Start the Voice API service using Docker or direct run"""
        # Try to find and start the voice service
        voice_service_path = self._find_voice_service()
        if not voice_service_path:
            logger.error("Voice service not found")
            return False
            
        try:
            # Try running with Docker first
            if self._start_with_docker(voice_service_path):
                return True
                
            # If Docker fails, try direct Python run
            if self._start_direct(voice_service_path):
                return True
                
            logger.error("Failed to start voice service")
            return False
        except Exception as e:
            logger.error(f"Error starting voice service: {str(e)}")
            return False
    
    def _find_voice_service(self) -> Optional[str]:
        """Find the voice service directory"""
        # Check common locations
        possible_paths = [
            os.path.join(self.project_dir, "services/voice"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
            os.path.join(os.path.dirname(os.path.abspath(__file__)))
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "voice_api.py")):
                return path
        
        return None
    
    def _start_with_docker(self, service_path: str) -> bool:
        """Try to start the service with Docker"""
        if not os.path.exists(os.path.join(service_path, "docker-compose.yml")):
            return False
            
        try:
            # Run docker-compose up
            subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=service_path,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Check if it started
            for _ in range(10):
                time.sleep(1)
                try:
                    response = requests.get(f"{self.api_url}/status", timeout=2.0)
                    if response.status_code == 200:
                        logger.info("Voice API started successfully with Docker")
                        return True
                except:
                    pass
        except:
            pass
            
        return False
    
    def _start_direct(self, service_path: str) -> bool:
        """Try to start the service directly with Python"""
        api_script = os.path.join(service_path, "voice_api.py")
        if not os.path.exists(api_script):
            return False
            
        try:
            # Start the process in the background
            if sys.platform == 'win32':
                subprocess.Popen(
                    ["start", "python", api_script],
                    shell=True
                )
            else:
                subprocess.Popen(
                    ["python", api_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Check if it started
            for _ in range(10):
                time.sleep(1)
                try:
                    response = requests.get(f"{self.api_url}/status", timeout=2.0)
                    if response.status_code == 200:
                        logger.info("Voice API started successfully with Python")
                        return True
                except:
                    pass
        except:
            pass
            
        return False
    
    def speak(self, text: str) -> Optional[str]:
        """Send text to the Voice API for TTS processing and play the audio"""
        if not text or len(text.strip()) == 0:
            return None
            
        # Check if connected, try to connect if not
        if not self.connected:
            connected = self.test_connection()
            if not connected:
                logger.error("Not connected to Voice API")
                return None
        
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
                logger.error(f"Failed to post event: {str(e)}")
        
        # First check the cache
        cache_key = f"{text}_{self.settings['voice']}_{self.settings['speed']}"
        if cache_key in self.audio_cache:
            cached_file = self.audio_cache[cache_key]
            if os.path.exists(cached_file):
                logger.debug(f"Using cached audio for '{text[:20]}...'")
                self._play_audio(cached_file)
                
                # Update last audio file
                self.last_audio_file = cached_file
                
                # Post completion event
                self._post_completion_event(text, cached_file)
                
                return cached_file
        
        # Try to generate speech with retries
        for attempt in range(self.retries):
            try:
                # Prepare request parameters
                params = {
                    "text": text,
                    "speed": self.settings.get("speed", 1.0),
                    "pitch": self.settings.get("pitch", 1.0),
                    "voice": self.settings.get("voice"),
                    "volume": self.settings.get("volume", 0.8)
                }
                
                # Send request to voice API
                response = requests.get(
                    f"{self.api_url}/speak",
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    # Save audio to file
                    audio_file = self._save_audio(response.content)
                    if audio_file:
                        # Cache the audio file
                        self.audio_cache[cache_key] = audio_file
                        
                        # Limit cache size
                        if len(self.audio_cache) > self.max_cache_size:
                            # Remove oldest entry
                            oldest_key = next(iter(self.audio_cache))
                            del self.audio_cache[oldest_key]
                        
                        # Play audio in a separate thread
                        threading.Thread(
                            target=self._play_audio, 
                            args=(audio_file,),
                            daemon=True
                        ).start()
                        
                        # Store last audio file
                        self.last_audio_file = audio_file
                        
                        # Post completion event
                        self._post_completion_event(text, audio_file)
                        
                        return audio_file
                    else:
                        logger.error("Failed to save audio file")
                else:
                    error_detail = ""
                    try:
                        # Try to get error details from response
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_detail = f": {error_data['detail']}"
                    except:
                        pass
                        
                    logger.error(f"Voice API error: {response.status_code}{error_detail}")
                
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
        logger.error("Failed to generate speech after all retries")
        
        # Post event about failed speech
        self._post_failure_event(text)
        
        return None
    
    def _save_audio(self, audio_data: bytes) -> Optional[str]:
        """Save audio data to a temporary file"""
        try:
            # Create temporary file with appropriate extension (WAV)
            fd, temp_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            logger.debug(f"Saved audio to {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error saving audio file: {str(e)}")
            return None
    
    def _play_audio(self, audio_file: str):
        """Play an audio file using the appropriate player for the platform"""
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return
        
        try:
            # Choose player based on platform
            if sys.platform == 'win32':  # Windows
                # Use PowerShell to play audio
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE
                
                # PowerShell command to play WAV file
                cmd = f'[System.Media.SoundPlayer]::new("{audio_file}").PlaySync()'
                
                subprocess.Popen(
                    ["powershell", "-Command", cmd],
                    startupinfo=startupinfo,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
            elif sys.platform == 'darwin':  # macOS
                subprocess.Popen(['afplay', audio_file], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
                
            else:  # Linux and others
                # Try different players
                players = ['aplay', 'paplay', 'ffplay', 'mplayer']
                
                for player in players:
                    try:
                        subprocess.Popen([player, audio_file], 
                                        stdout=subprocess.DEVNULL, 
                                        stderr=subprocess.DEVNULL)
                        break
                    except FileNotFoundError:
                        continue
            
            logger.debug(f"Playing audio file: {audio_file}")
            
        except Exception as e:
            logger.error(f"Error playing audio file: {str(e)}")
    
    def _post_completion_event(self, text: str, audio_file: str):
        """Post event about completed speech"""
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
                logger.error(f"Failed to post completion event: {str(e)}")
    
    def _post_failure_event(self, text: str):
        """Post event about failed speech"""
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
                logger.error(f"Failed to post failure event: {str(e)}")
    
    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update voice settings"""
        if not isinstance(settings, dict):
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
                if not isinstance(value, (int, float)):
                    continue
                
                value = float(value)
                if value < 0.5 or value > 2.0:
                    continue
                
            elif key == "voice":
                if not isinstance(value, str):
                    continue
                
                # Make sure the voice exists
                if self.available_voices and value not in self.available_voices:
                    logger.warning(f"Voice not available: {value}")
                    continue
                
            elif key == "volume":
                if not isinstance(value, (int, float)):
                    continue
                
                value = float(value)
                if value < 0.0 or value > 1.0:
                    continue
            
            # Update the setting
            if self.settings.get(key) != value:
                self.settings[key] = value
                updated = True
        
        # Save settings if updated
        if updated:
            self._save_settings()
        
        return updated
    
    def set_voice(self, voice: str) -> bool:
        """Set the voice to use"""
        return self.update_settings({"voice": voice})
    
    def set_speed(self, speed: float) -> bool:
        """Set the speech speed (0.5-2.0)"""
        return self.update_settings({"speed": speed})
    
    def set_pitch(self, pitch: float) -> bool:
        """Set the speech pitch (0.5-2.0)"""
        return self.update_settings({"pitch": pitch})
    
    def set_volume(self, volume: float) -> bool:
        """Set the speech volume (0.0-1.0)"""
        return self.update_settings({"volume": volume})
    
    def get_available_voices(self) -> List[str]:
        """Get a list of available voices"""
        if not self.available_voices and self.connected:
            self._fetch_available_voices()
        return self.available_voices
    
    def get_settings(self) -> Dict[str, Any]:
        """Get current voice settings"""
        return self.settings.copy()
    
    def get_last_audio_file(self) -> Optional[str]:
        """Get the path to the last generated audio file"""
        return self.last_audio_file