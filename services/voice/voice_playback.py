"""
Audio Playback Module for Sabrina AI Voice Client
================================================
Provides audio playback capabilities for the Voice API Client.
"""

import os
import time
import logging
import threading
import traceback

logger = logging.getLogger("voice_playback")


class AudioPlayer:
    """Handles audio playback for voice output"""

    def __init__(self):
        """Initialize the audio player"""
        self.current_audio = None
        self.playing = False
        self.playback_thread = None
        self.stop_requested = False
        self.playback_methods = []

        # Initialize playback methods in order of preference
        self._init_playback_methods()

    def _init_playback_methods(self):
        """Initialize available audio playback methods"""
        # Try to initialize various audio playback libraries
        # in order of preference

        # 1. Try playsound - simple cross-platform playback
        try:
            from playsound import playsound

            def play_with_playsound(file_path):
                playsound(file_path)
                return True

            self.playback_methods.append(("playsound", play_with_playsound))
            logger.info("Initialized playsound for audio playback")
        except ImportError:
            logger.debug("playsound not available")

        # 2. Try pygame - good cross-platform alternative
        try:
            import pygame

            # Initialize pygame mixer
            pygame.mixer.init()

            def play_with_pygame(file_path):
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()

                # Wait for playback to complete
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                    if self.stop_requested:
                        pygame.mixer.music.stop()
                        break
                return True

            self.playback_methods.append(("pygame", play_with_pygame))
            logger.info("Initialized pygame for audio playback")
        except ImportError:
            logger.debug("pygame not available")

        # 3. Try sounddevice with soundfile - high quality but more dependencies
        try:
            import sounddevice as sd
            import soundfile as sf

            def play_with_sounddevice(file_path):
                data, samplerate = sf.read(file_path)
                sd.play(data, samplerate)
                sd.wait()  # Wait until playback is finished
                return True

            self.playback_methods.append(("sounddevice", play_with_sounddevice))
            logger.info("Initialized sounddevice for audio playback")
        except ImportError:
            logger.debug("sounddevice or soundfile not available")

        # 4. As a last resort, try using system commands
        if os.name == "posix":  # Unix/Linux/MacOS

            def play_with_system_unix(file_path):
                # Try several common audio players
                players = ["aplay", "paplay", "mplayer", "afplay"]
                for player in players:
                    try:
                        import subprocess

                        result = subprocess.run(
                            [player, file_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        if result.returncode == 0:
                            return True
                    except Exception as e:
                        logger.debug(f"Error: {str(e)}")
                        continue
                return False

            self.playback_methods.append(("system_unix", play_with_system_unix))
            logger.info("Initialized system commands for audio playback on Unix")

        elif os.name == "nt":  # Windows

            def play_with_system_windows(file_path):
                try:
                    import winsound

                    winsound.PlaySound(file_path, winsound.SND_FILENAME)
                    return True
                except Exception as e:
                    logger.debug(f"Error: {str(e)}")
                    # Try PowerShell as fallback
                    try:
                        import subprocess

                        ps_command = f'powershell -c (New-Object Media.SoundPlayer "{file_path}").PlaySync();'
                        subprocess.run(ps_command, shell=True)
                        return True
                    except Exception as e:
                        logger.debug(f"Error: {str(e)}")
                        return False

            self.playback_methods.append(("system_windows", play_with_system_windows))
            logger.info("Initialized system commands for audio playback on Windows")

        # Log available methods
        if self.playback_methods:
            logger.info(
                f"Available audio playback methods: {[m[0] for m in self.playback_methods]}"
            )
        else:
            logger.warning(
                "No audio playback methods available! Voice output won't be audible."
            )

    def play(self, audio_file: str) -> bool:
        """
        Play an audio file

        Args:
            audio_file: Path to the audio file

        Returns:
            bool: True if playback started, False otherwise
        """
        if not os.path.exists(audio_file):
            logger.error(f"Audio file not found: {audio_file}")
            return False

        # Stop any current playback
        self.stop()

        # Set current audio
        self.current_audio = audio_file
        self.stop_requested = False

        # Start playback in a separate thread
        self.playback_thread = threading.Thread(
            target=self._play_audio_thread, args=(audio_file,), daemon=True
        )
        self.playback_thread.start()

        return True

    def _play_audio_thread(self, audio_file: str):
        """
        Thread function for audio playback

        Args:
            audio_file: Path to the audio file
        """
        self.playing = True

        try:
            # Try each playback method until one succeeds
            success = False

            for method_name, play_func in self.playback_methods:
                if self.stop_requested:
                    break

                try:
                    logger.debug(f"Trying playback with {method_name}")
                    if play_func(audio_file):
                        logger.debug(f"Playback with {method_name} successful")
                        success = True
                        break
                except Exception as e:
                    logger.debug(f"Playback with {method_name} failed: {str(e)}")
                    continue

            if not success and not self.stop_requested:
                logger.warning(f"All playback methods failed for {audio_file}")

        except Exception as e:
            logger.error(f"Error in audio playback thread: {str(e)}")
            logger.error(traceback.format_exc())

        finally:
            self.playing = False
            self.current_audio = None

    def stop(self):
        """Stop current audio playback"""
        if self.playing and self.playback_thread:
            # Signal playback to stop
            self.stop_requested = True

            # Wait for thread to finish (with timeout)
            if self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)

            # Reset state
            self.playing = False
            self.current_audio = None

    def is_playing(self) -> bool:
        """
        Check if audio is currently playing

        Returns:
            bool: True if playing, False otherwise
        """
        return self.playing


# Create an easy-to-use function to play audio files
_audio_player = None


def play_audio(file_path: str) -> bool:
    """
    Play an audio file using the best available method

    Args:
        file_path: Path to the audio file

    Returns:
        bool: True if playback started, False otherwise
    """
    global _audio_player

    if _audio_player is None:
        _audio_player = AudioPlayer()

    return _audio_player.play(file_path)


def stop_audio():
    """Stop current audio playback"""
    global _audio_player

    if _audio_player is not None:
        _audio_player.stop()


def is_playing() -> bool:
    """
    Check if audio is currently playing

    Returns:
        bool: True if playing, False otherwise
    """
    global _audio_player

    if _audio_player is None:
        return False

    return _audio_player.is_playing()


# Enhanced VoiceAPIClient methods for audio playback


def speak_with_playback(client, text: str, **kwargs) -> bool:
    """
    Convert text to speech and play it

    Args:
        client: VoiceAPIClient instance
        text: Text to convert to speech
        **kwargs: Additional parameters

    Returns:
        bool: True if successful, False otherwise
    """
    # First, get the full URL
    audio_url, success = get_audio_url(client, text, **kwargs)

    if not success or not audio_url:
        logger.error(f"Failed to get audio URL for text: {text}")
        return False

    # Download the audio file if it's a URL
    if audio_url.startswith(("http://", "https://")):
        import requests
        import tempfile

        try:
            response = requests.get(audio_url, stream=True, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"Failed to download audio file: {response.status_code}")
                return False

            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)

                audio_path = temp_file.name
        except Exception as e:
            logger.error(f"Error downloading audio file: {str(e)}")
            return False
    else:
        # If it's a local path, use it directly
        audio_path = audio_url

    # Play the audio file
    return play_audio(audio_path)


def get_audio_url(client, text: str, **kwargs) -> tuple:
    """
    Get the audio URL for the given text

    Args:
        client: VoiceAPIClient instance
        text: Text to convert to speech
        **kwargs: Additional parameters

    Returns:
        tuple: (audio_url, success)
    """
    if not text:
        logger.warning("Empty text provided")
        return None, False

    # Check if connected
    if not client.connected and not client.test_connection():
        logger.error("Not connected to Voice API")
        return None, False

    try:
        # Prepare request payload
        payload = {"text": text}

        # Add optional parameters if provided
        for key in ["voice", "speed", "pitch", "volume", "emotion", "cache"]:
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        # Make API request
        response = client.session.post(
            f"{client.api_url}/speak",
            json=payload,
            headers=client.headers,
            timeout=10.0,
        )

        if response.status_code == 200:
            data = response.json()
            audio_url = data.get("audio_url")

            if audio_url:
                # Get full URL
                full_audio_url = f"{client.api_url}{audio_url}"
                logger.info(f"Speech generated successfully: {full_audio_url}")
                return full_audio_url, True
            else:
                logger.warning("No audio URL in response")
                return None, False
        else:
            logger.error(
                f"Voice API request failed: {response.status_code} - {response.text}"
            )
            return None, False

    except Exception as e:
        logger.error(f"Error in get_audio_url: {str(e)}")
        logger.error(traceback.format_exc())
        return None, False
