"""
Enhanced Hearing Module for Sabrina AI
=====================================
Provides real voice recognition with wake word detection.
"""

import os
import time
import logging
import json
import pyaudio
import keyboard
import playsound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hearing")


class Hearing:
    """Enhanced hearing module with real wake word detection and voice recognition"""

    def __init__(self, wake_word="hey sabrina", model_path="models/vosk-model"):
        """
        Initialize the hearing module with real functionality

        Args:
            wake_word: Wake word to activate the system
            model_path: Path to the voice recognition model
        """
        self.wake_word = wake_word.lower()
        self.model_path = model_path
        self.hotkey = "ctrl+shift+s"  # Default hotkey

        # Initialize audio settings
        self.rate = 16000
        self.channels = 1
        self.chunk = 4096
        self.format = pyaudio.paInt16

        # Initialize components
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.listening_thread = None
        self.running = False

        # Initialize models
        self.vosk_model = self._load_vosk_model()
        self.active = True  # Whether the listener is active

        logger.info(f"Hearing module initialized with wake word: {self.wake_word}")

    def _load_vosk_model(self):
        """
        Load the Vosk model for wake word detection

        Returns:
            Vosk model, or None if not available
        """
        try:
            from vosk import Model, KaldiRecognizer

            # Check if model directory exists
            if not os.path.exists(self.model_path):
                logger.warning(f"Vosk model directory not found: {self.model_path}")

                # Check if parent directory exists
                parent_dir = os.path.dirname(self.model_path)
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)

                # Download model if not available
                logger.info("Attempting to download Vosk model...")
                self._download_vosk_model()

            # Load model
            if os.path.exists(self.model_path):
                model = Model(self.model_path)
                recognizer = KaldiRecognizer(model, self.rate)
                logger.info("Vosk model loaded successfully")
                return recognizer
            else:
                logger.error("Failed to load Vosk model")
                return None

        except ImportError:
            logger.error("Vosk not installed - wake word detection will be limited")
            return None
        except Exception as e:
            logger.error(f"Error loading Vosk model: {str(e)}")
            return None

    def _download_vosk_model(self):
        """Download the Vosk model if not available"""
        try:
            import wget
            import zipfile

            # URL for small English model
            model_url = (
                "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
            )

            # Create temporary file for download
            model_zip_path = "models/vosk-model.zip"

            # Download model
            logger.info(f"Downloading Vosk model from {model_url}")
            wget.download(model_url, model_zip_path)

            # Extract model
            logger.info("Extracting Vosk model...")
            with zipfile.ZipFile(model_zip_path, "r") as zip_ref:
                zip_ref.extractall("models/")

            # Remove zip file
            os.remove(model_zip_path)

            # Find extracted directory and rename if needed
            for item in os.listdir("models/"):
                if (
                    os.path.isdir(os.path.join("models/", item))
                    and "vosk-model" in item
                ):
                    if item != os.path.basename(self.model_path):
                        os.rename(os.path.join("models/", item), self.model_path)
                    break

            logger.info("Vosk model downloaded and extracted successfully")

        except Exception as e:
            logger.error(f"Error downloading Vosk model: {str(e)}")

    def play_wake_sound(self, sound_path="assets/wake_sound.mp3"):
        """Plays a wake-up sound (MP3) when the wake word is detected."""
        if not os.path.exists(sound_path):
            logger.warning(f"Wake sound file not found: {sound_path}")
            return

        try:
            playsound.playsound(sound_path)
            logger.info("Wake sound played successfully.")

        except Exception as e:
            logger.error(f"Error playing wake sound: {str(e)}")

    # Modify the `listen_for_wake_word` function to play MP3 sound
    def listen_for_wake_word(self):
        """
        Listen for the wake word or hotkey activation.

        Returns:
            True if wake word detected, False otherwise.
        """
        logger.info(
            f"Listening for wake word '{self.wake_word}' or hotkey {self.hotkey}"
        )

        if not self.vosk_model:
            logger.warning("Vosk model not available - using console input for testing")
            user_input = input("Say the wake word or press Enter to simulate it: ")
            print(user_input)
            self.play_wake_sound()  # Play MP3 sound for simulation
            return True

        # Start audio stream if not already running
        if not self.stream:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

        # Listen for wake word
        self.active = True
        while self.active:
            try:
                # Check for hotkey
                if keyboard.is_pressed(self.hotkey):
                    logger.info(f"Hotkey {self.hotkey} activated")
                    self.play_wake_sound()
                    return True

                # Get audio data
                data = self.stream.read(self.chunk, exception_on_overflow=False)

                # Process with Vosk
                if self.vosk_model.AcceptWaveform(data):
                    result = json.loads(self.vosk_model.Result())
                    text = result.get("text", "").lower()

                    # Check for wake word
                    if self.wake_word in text:
                        logger.info(f"Wake word detected: {self.wake_word}")
                        self.play_wake_sound()  # Play sound when wake word is detected
                        return True

                # Pause briefly to reduce CPU usage
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in wake word detection: {str(e)}")
                time.sleep(1)  # Pause longer on error

    def listen(self, timeout=10.0):
        """
        Listen for user input with timeout

        Args:
            timeout: Timeout in seconds

        Returns:
            Transcribed text, or empty string if timeout
        """
        logger.info("Listening for user input...")

        if not self.vosk_model:
            logger.warning("Vosk model not available - using console input for testing")
            return input("Say something: ")

        # Start audio stream if not already running
        if not self.stream:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )

        # Reset recognizer for new input
        self.vosk_model.Reset()

        # Listen for user input with timeout
        start_time = time.time()
        result_text = ""

        while time.time() - start_time < timeout:
            try:
                # Get audio data
                data = self.stream.read(self.chunk, exception_on_overflow=False)

                # Process with Vosk
                if self.vosk_model.AcceptWaveform(data):
                    result = json.loads(self.vosk_model.Result())
                    text = result.get("text", "").strip()

                    if text:
                        logger.info(f"Heard: {text}")
                        result_text = text
                        break

                # Pause briefly to reduce CPU usage
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in voice recognition: {str(e)}")
                time.sleep(1)  # Pause longer on error

        # Handle timeout
        if not result_text:
            logger.warning("Listening timeout - no input detected")

        return result_text

    def close(self):
        """Close the hearing module and release resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        if self.audio:
            self.audio.terminate()
            self.audio = None

        logger.info("Hearing module closed")
