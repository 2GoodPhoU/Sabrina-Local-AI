"""
Audio Playback Module for Sabrina AI
===================================
Provides robust audio playback capabilities with multiple fallback methods
and a clean API for voice playback functionality.
"""

import os
import time
import logging
import threading
import tempfile
import subprocess
import shutil

# Configure logging
logger = logging.getLogger("voice_playback")


class AudioPlayer:
    """Handles audio playback with multiple fallback methods"""

    def __init__(self):
        """Initialize the audio player"""
        self.current_audio = None
        self.playing = False
        self.playback_thread = None
        self.stop_requested = False
        self.playback_methods = []
        self.temp_files = []

        # Create a temporary directory for audio files
        self.temp_dir = tempfile.mkdtemp(prefix="sabrina_audio_")

        # Initialize available playback methods
        self._init_playback_methods()

        # Set up cleanup on exit
        import atexit

        atexit.register(self._cleanup)

    def _cleanup(self):
        """Clean up temporary files and directory"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.debug(f"Error cleaning up temp file {file_path}: {e}")

        # Remove temp directory
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            logger.debug(f"Error removing temp directory: {e}")

    def _init_playback_methods(self):
        """Initialize available audio playback methods in priority order"""
        # Track successful initialization
        methods_initialized = 0

        # On Windows, prioritize Windows Media Player via system commands
        if os.name == "nt":
            if self._init_windows_commands():
                methods_initialized += 1

            if self._init_winsound():
                methods_initialized += 1

        # 1. Try sounddevice - high quality and cross-platform
        if self._init_sounddevice():
            methods_initialized += 1

        # 2. Try pygame - good cross-platform alternative
        if self._init_pygame():
            methods_initialized += 1

        # 3. Try playsound - fixed for Windows path issues
        if self._init_playsound():
            methods_initialized += 1

        # Unix system commands as fallback
        if os.name == "posix" and self._init_unix_commands():
            methods_initialized += 1

        # Log available methods
        if methods_initialized > 0:
            logger.info(
                f"Initialized {methods_initialized} audio playback methods: {[m[0] for m in self.playback_methods]}"
            )
        else:
            logger.warning(
                "No audio playback methods available! Voice output won't be audible."
            )

    def _init_sounddevice(self) -> bool:
        """Initialize sounddevice audio playback"""
        try:
            import sounddevice as sd
            import soundfile as sf

            def play_with_sounddevice(file_path):
                try:
                    data, samplerate = sf.read(file_path)
                    sd.play(data, samplerate)
                    sd.wait()  # Wait until playback is finished
                    return True
                except Exception as e:
                    logger.warning(f"Sounddevice playback failed: {e}")
                    return False

            self.playback_methods.append(("sounddevice", play_with_sounddevice))
            logger.info("Initialized sounddevice for audio playback")
            return True
        except ImportError:
            logger.debug("Sounddevice not available")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize sounddevice: {e}")
            return False

    def _init_pygame(self) -> bool:
        """Initialize pygame audio playback"""
        try:
            import pygame

            # Initialize pygame mixer
            pygame.mixer.init(frequency=48000)

            def play_with_pygame(file_path):
                try:
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.play()

                    # Wait for playback to complete
                    while pygame.mixer.music.get_busy():
                        if self.stop_requested:
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.1)
                    return True
                except Exception as e:
                    logger.warning(f"Pygame playback failed: {e}")
                    return False

            self.playback_methods.append(("pygame", play_with_pygame))
            logger.info("Initialized pygame for audio playback")
            return True
        except ImportError:
            logger.debug("Pygame not available")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize pygame: {e}")
            return False

    def _init_playsound(self) -> bool:
        """Initialize playsound with Windows path fixes"""
        try:
            from playsound import playsound

            def play_with_playsound(file_path):
                try:
                    # For Windows, copy to a simple path to avoid issues with spaces
                    if os.name == "nt":
                        # Create a simple temp filename without spaces
                        simple_path = os.path.join(
                            self.temp_dir,
                            f"play_{os.path.basename(file_path).replace(' ', '_')}",
                        )

                        # Copy the file
                        shutil.copy2(file_path, simple_path)
                        self.temp_files.append(simple_path)

                        # Play the copied file
                        playsound(simple_path, block=True)
                    else:
                        # On other systems, play directly
                        playsound(file_path, block=True)

                    return True
                except Exception as e:
                    logger.warning(f"Playsound failed: {e}")
                    return False

            self.playback_methods.append(("playsound", play_with_playsound))
            logger.info("Initialized playsound for audio playback")
            return True
        except ImportError:
            logger.debug("Playsound not available")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize playsound: {e}")
            return False

    def _init_winsound(self) -> bool:
        """Initialize winsound for Windows systems"""
        if os.name != "nt":
            return False

        try:
            import winsound

            def play_with_winsound(file_path):
                try:
                    winsound.PlaySound(file_path, winsound.SND_FILENAME)
                    return True
                except Exception as e:
                    logger.warning(f"Winsound playback failed: {e}")
                    return False

            self.playback_methods.append(("winsound", play_with_winsound))
            logger.info("Initialized winsound for audio playback")
            return True
        except ImportError:
            logger.debug("Winsound not available")
            return False
        except Exception as e:
            logger.warning(f"Failed to initialize winsound: {e}")
            return False

    def _init_unix_commands(self) -> bool:
        """Initialize Unix command-line audio players"""

        def play_with_unix_commands(file_path):
            # Try several common audio players
            players = [
                ["aplay", file_path],
                ["paplay", file_path],
                ["mplayer", file_path],
                ["afplay", file_path],  # macOS
            ]
            for player_cmd in players:
                try:
                    result = subprocess.run(
                        player_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if result.returncode == 0:
                        return True
                except Exception:
                    continue
            return False

        self.playback_methods.append(("unix_commands", play_with_unix_commands))
        logger.info("Initialized Unix command-line audio players")
        return True

    def _init_windows_commands(self) -> bool:
        """Initialize Windows-specific audio playback methods"""

        def play_with_windows_commands(file_path):
            try:
                # Use Windows Media Player to play audio (no quotes needed)
                cmd = f"powershell -c \"(New-Object Media.SoundPlayer -ArgumentList '{file_path}').PlaySync()\""

                result = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if result.returncode == 0:
                    return True

                # Alternative Windows command
                cmd2 = f"powershell -c \"$player = New-Object System.Media.SoundPlayer; $player.SoundLocation = '{file_path}'; $player.PlaySync()\""

                result = subprocess.run(
                    cmd2,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                return result.returncode == 0
            except Exception as e:
                logger.warning(f"Windows commands playback failed: {e}")
                return False

        self.playback_methods.append(("windows_commands", play_with_windows_commands))
        logger.info("Initialized Windows audio playback methods")
        return True

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
            logger.debug(f"Attempting to play audio file: {audio_file}")

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

        finally:
            self.playing = False
            self.current_audio = None

    def stop(self):
        """Stop current audio playback"""
        if self.playing and self.playback_thread and self.playback_thread.is_alive():
            # Signal playback to stop
            self.stop_requested = True

            # Wait for playback to finish (with timeout)
            self.playback_thread.join(timeout=1.0)

        # Reset state
        self.playing = False
        self.current_audio = None
        self.stop_requested = False

    def is_playing(self) -> bool:
        """
        Check if audio is currently playing

        Returns:
            bool: True if playing, False otherwise
        """
        return self.playing and self.playback_thread and self.playback_thread.is_alive()


# Create singleton instance for easy global access
_player_instance = None


def _get_player() -> AudioPlayer:
    """Get or create the singleton AudioPlayer instance"""
    global _player_instance
    if _player_instance is None:
        _player_instance = AudioPlayer()
    return _player_instance


# Public API


def play_audio(file_path: str) -> bool:
    """
    Play an audio file

    Args:
        file_path: Path to the audio file

    Returns:
        bool: True if playback started, False otherwise
    """
    return _get_player().play(file_path)


def stop_audio():
    """Stop current audio playback"""
    _get_player().stop()


def is_playing() -> bool:
    """
    Check if audio is currently playing

    Returns:
        bool: True if playing, False otherwise
    """
    return _get_player().is_playing()
