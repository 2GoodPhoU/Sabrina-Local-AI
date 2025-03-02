"""
Improved Audio Playback Module for Sabrina AI Voice Client
=========================================================
Provides robust audio playback capabilities with multiple fallback methods.
"""

import os
import time
import logging
import threading
import traceback
import tempfile
import subprocess

logger = logging.getLogger("voice_playback")


class AudioPlayer:
    """Handles audio playback for voice output with improved error handling"""

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

        # 1. Try sounddevice - high quality and reliable
        try:
            import sounddevice as sd
            import soundfile as sf

            def play_with_sounddevice(file_path):
                try:
                    data, samplerate = sf.read(file_path)
                    sd.play(data, samplerate)
                    status = sd.wait()  # Wait until playback is finished
                    print(status)
                    return True
                except Exception as e:
                    logger.warning(f"sounddevice playback failed: {e}")
                    return False

            self.playback_methods.append(("sounddevice", play_with_sounddevice))
            logger.info("Initialized sounddevice for audio playback")
        except ImportError:
            logger.debug("sounddevice or soundfile not available")

        # 2. Try pygame - good cross-platform alternative
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
                    logger.warning(f"pygame playback failed: {e}")
                    return False

            self.playback_methods.append(("pygame", play_with_pygame))
            logger.info("Initialized pygame for audio playback")
        except ImportError:
            logger.debug("pygame not available")

        # 3. Try playsound - but with better path handling
        try:
            # Try to import playsound but handle path issues
            from playsound import playsound

            def play_with_playsound(file_path):
                try:
                    # Create a temporary file with a simple name if the path has spaces
                    if " " in file_path or ":" in file_path:
                        temp_dir = tempfile.gettempdir()
                        temp_filename = f"sabrina_temp_{os.path.basename(file_path)}"
                        temp_path = os.path.join(temp_dir, temp_filename)

                        # Copy the file
                        with open(file_path, "rb") as src, open(temp_path, "wb") as dst:
                            dst.write(src.read())

                        # Play from the temp location
                        playsound(temp_path, block=True)

                        # Clean up
                        try:
                            os.remove(temp_path)
                        except Exception as e:
                            logger.warning(f"Cleanup Error: {e}")
                            pass
                    else:
                        playsound(file_path, block=True)
                    return True
                except Exception as e:
                    logger.warning(f"playsound failed: {e}")
                    return False

            self.playback_methods.append(("playsound_fixed", play_with_playsound))
            logger.info("Initialized playsound with path fixing for audio playback")
        except ImportError:
            logger.debug("playsound not available")

        # 4. As a last resort, try using system commands
        if os.name == "posix":  # Unix/Linux/MacOS

            def play_with_system_unix(file_path):
                # Try several common audio players
                players = [
                    ["aplay", file_path],
                    ["paplay", file_path],
                    ["mplayer", file_path],
                    ["afplay", file_path],
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
                    except Exception as e:
                        logger.debug(f"Player {player_cmd[0]} error: {str(e)}")
                        continue
                return False

            self.playback_methods.append(("system_unix", play_with_system_unix))
            logger.info("Initialized system commands for audio playback on Unix")

        elif os.name == "nt":  # Windows

            def play_with_system_windows(file_path):
                try:
                    # Clean up the file path for PowerShell
                    clean_path = file_path.replace("\\", "\\\\")

                    # Try PowerShell approach first
                    ps_command = f"powershell -c \"(New-Object Media.SoundPlayer '{clean_path}').PlaySync();\""
                    result = subprocess.run(
                        ps_command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if result.returncode == 0:
                        return True

                    # Fall back to winsound if available
                    import winsound

                    winsound.PlaySound(file_path, winsound.SND_FILENAME)
                    return True
                except Exception as e:
                    logger.debug(f"Windows audio playback error: {str(e)}")
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

            # Log the full file path for debugging
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
                    logger.debug(traceback.format_exc())
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


# Create global player instance for easy access
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
