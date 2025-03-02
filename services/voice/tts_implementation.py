"""
Enhanced TTS Engine Implementation for Sabrina AI
================================================
Provides text-to-speech conversion using Coqui TTS with simplified
fallback mechanisms and cleaner code organization.
"""

import os
import logging
import json
import hashlib
import numpy as np
from typing import Dict, Any

# Configure logging
logger = logging.getLogger("tts_engine")


class TTSEngine:
    """Enhanced TTS engine using Coqui TTS with simplified fallbacks"""

    def __init__(self, settings_manager):
        """Initialize the TTS engine

        Args:
            settings_manager: Settings manager for voice configuration
        """
        self.settings_manager = settings_manager
        self.cache_dir = "data/audio_cache"
        self.tts_initialized = False
        self.tts = None

        # Available voice models (mapped to TTS model names)
        self.voice_models = [
            "en_US-jenny-medium",  # Default voice
            "en_US-jenny-high",  # Higher quality jenny voice
            "en_US-default",  # Generic fallback
            "en_US-tacotron2",  # Alternative model
            "en_US-hifigan",  # Another alternative
        ]

        # Emotion presets with speed, pitch, and energy adjustments
        self.emotion_map = {
            "neutral": {"speed": 1.0, "pitch_factor": 1.0, "energy_factor": 1.0},
            "happy": {"speed": 1.1, "pitch_factor": 1.1, "energy_factor": 1.2},
            "sad": {"speed": 0.9, "pitch_factor": 0.9, "energy_factor": 0.8},
            "angry": {"speed": 1.1, "pitch_factor": 1.2, "energy_factor": 1.5},
            "fearful": {"speed": 1.2, "pitch_factor": 1.3, "energy_factor": 0.7},
            "surprised": {"speed": 1.2, "pitch_factor": 1.4, "energy_factor": 1.3},
        }

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initialize TTS
        self._init_tts()

    def _init_tts(self):
        """Initialize TTS library with proper error handling"""
        try:
            # Import TTS
            import torch
            from TTS.api import TTS

            # Check for CUDA availability
            use_cuda = torch.cuda.is_available()
            device = "cuda" if use_cuda else "cpu"
            logger.info(f"TTS initialization using device: {device}")

            try:
                # Try to initialize with newer API
                self.tts = TTS(model_name="tts_models/en/jenny/jenny")

                # Move to GPU if available
                if use_cuda and hasattr(self.tts, "to"):
                    self.tts.to(device)

                self.tts_initialized = True
                logger.info("TTS engine initialized successfully")

                # Log available options
                if hasattr(self.tts, "speakers"):
                    logger.info(f"Available speakers: {self.tts.speakers}")
                if hasattr(self.tts, "languages"):
                    logger.info(f"Available languages: {self.tts.languages}")

            except Exception as e:
                logger.error(f"Failed to initialize TTS: {str(e)}")
                self.tts_initialized = False

        except ImportError:
            logger.warning("TTS library not installed. Install with: pip install TTS")
            self.tts_initialized = False
        except Exception as e:
            logger.error(f"Unexpected error initializing TTS: {str(e)}")
            self.tts_initialized = False

    def _get_cache_path(self, text: str, settings: Dict[str, Any]) -> str:
        """Get cache file path for the given text and settings

        Args:
            text: Input text
            settings: Voice settings

        Returns:
            Path to the cache file
        """
        # Remove cache flag from settings hash
        settings_for_hash = {k: v for k, v in settings.items() if k != "cache_enabled"}

        # Create hash from text and settings
        cache_key = f"{text}|{json.dumps(settings_for_hash)}"
        cache_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()

        return os.path.join(self.cache_dir, f"{cache_hash}.wav")

    def _process_text(self, text: str) -> str:
        """Process text for better TTS results

        Args:
            text: Input text

        Returns:
            Processed text
        """
        # Remove extra whitespace
        text = " ".join(text.split())

        # Ensure text ends with punctuation
        if text and not text[-1] in ".!?":
            text += "."

        # Replace common abbreviations
        replacements = {
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

        for abbr, expanded in replacements.items():
            text = text.replace(abbr, expanded)

        return text

    async def speak(self, text: str, voice_settings: Dict[str, Any] = None) -> str:
        """Generate speech for the given text

        Args:
            text: Text to convert to speech
            voice_settings: Voice settings to use

        Returns:
            Path to generated audio file
        """
        # Get settings
        settings = self.settings_manager.get_settings().model_dump()
        if voice_settings:
            # Update with provided settings, skipping None values
            for key, value in voice_settings.items():
                if value is not None:
                    settings[key] = value

        # Determine if we should use cache
        use_cache = settings.get("cache_enabled", True)
        if "cache" in voice_settings:
            use_cache = voice_settings["cache"]

        # Get cache path
        output_path = self._get_cache_path(text, settings)

        # Check if cached file exists
        if use_cache and os.path.exists(output_path):
            logger.info(f"Using cached audio file: {output_path}")
            return output_path

        # Generate speech
        if self.tts_initialized:
            success = await self._generate_speech(text, output_path, settings)
            if success:
                return output_path

        # Fall back to placeholder synthesis if TTS fails
        return await self._fallback_synthesis(text, output_path, settings)

    async def _generate_speech(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> bool:
        """Generate speech using TTS library

        Args:
            text: Text to convert
            output_path: Output file path
            settings: Voice settings

        Returns:
            True if successful, False otherwise
        """
        if not self.tts_initialized or not self.tts:
            logger.error("TTS not initialized, cannot generate speech")
            return False

        try:
            # Process text
            processed_text = self._process_text(text)

            # Extract settings
            speed = settings.get("speed", 1.0)
            pitch = settings.get("pitch", 1.0)
            volume = settings.get("volume", 0.8)
            emotion = settings.get("emotion", "neutral")

            # Apply emotion settings
            emotion_settings = self.emotion_map.get(
                emotion, self.emotion_map["neutral"]
            )
            adjusted_speed = speed * emotion_settings["speed"]

            logger.info(
                f"Generating speech for: {processed_text[:100]}{'...' if len(processed_text) > 100 else ''}"
            )

            # Generate speech with appropriate parameters
            speaker = None
            language = None

            if hasattr(self.tts, "speakers") and self.tts.speakers:
                speaker = self.tts.speakers[0]  # Use first available speaker

            if hasattr(self.tts, "languages") and self.tts.languages:
                language = "en"  # Use English

            # Generate speech with available parameters
            if speaker and language:
                wav = self.tts.tts(processed_text, speaker=speaker, language=language)
            elif speaker:
                wav = self.tts.tts(processed_text, speaker=speaker)
            elif language:
                wav = self.tts.tts(processed_text, language=language)
            else:
                wav = self.tts.tts(processed_text)

            # Apply audio effects
            wav = self._apply_audio_effects(wav, pitch, volume, adjusted_speed)

            # Save to file
            self._save_wav(wav, output_path)

            logger.info(f"Speech generated and saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            return False

    def _apply_audio_effects(
        self, wav: np.ndarray, pitch_factor: float, volume: float, speed: float
    ) -> np.ndarray:
        """Apply audio effects to the generated speech

        Args:
            wav: Audio data
            pitch_factor: Pitch adjustment
            volume: Volume adjustment
            speed: Speed adjustment

        Returns:
            Processed audio data
        """
        try:
            # Convert to numpy array if needed
            if not isinstance(wav, np.ndarray):
                try:
                    wav = np.array(wav, dtype=np.float32)
                except Exception as e:
                    logger.warning(f"Could not convert audio to numpy array: {e}")
                    return wav

            # Apply volume adjustment
            wav_adjusted = wav * volume

            # Skip time/pitch adjustments if close to default
            if abs(pitch_factor - 1.0) < 0.01 and abs(speed - 1.0) < 0.01:
                return wav_adjusted

            # Simple resampling for speed adjustment
            if abs(speed - 1.0) >= 0.01:
                original_length = len(wav_adjusted)
                new_length = int(original_length / speed)

                # Linear interpolation for resampling
                indices = np.linspace(0, original_length - 1, new_length)
                indices = np.clip(indices.astype(np.int32), 0, original_length - 1)
                wav_adjusted = wav_adjusted[indices]

                logger.info(f"Applied speed adjustment: {speed}")

            return wav_adjusted

        except Exception as e:
            logger.error(f"Error applying audio effects: {str(e)}")
            return wav

    def _save_wav(self, wav: np.ndarray, output_path: str, sample_rate: int = 48000):
        """Save audio data to WAV file

        Args:
            wav: Audio data
            output_path: Output file path
            sample_rate: Sample rate in Hz
        """
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Try soundfile first
            try:
                import soundfile as sf

                sf.write(output_path, wav, sample_rate)
            except ImportError:
                # Fall back to scipy
                try:
                    import scipy.io.wavfile

                    scipy.io.wavfile.write(output_path, sample_rate, wav)
                except ImportError:
                    logger.error("Neither soundfile nor scipy available for saving WAV")
                    raise ImportError("Cannot save audio: soundfile or scipy required")

        except Exception as e:
            logger.error(f"Error saving WAV file: {str(e)}")
            raise

    async def _fallback_synthesis(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> str:
        """Create a simple fallback audio when TTS fails

        Args:
            text: Text to convert
            output_path: Output file path
            settings: Voice settings

        Returns:
            Path to the generated audio file
        """
        try:
            # Calculate duration based on word count
            words = text.split()
            duration = min(0.1 * len(words), 10)  # 0.1s per word, max 10s
            duration = max(duration, 1.0)  # At least 1 second

            # Create simple audio based on text
            sample_rate = 48000
            samples = int(sample_rate * duration)

            # Create a seed value from text
            seed_value = sum(ord(c) for c in text)
            np.random.seed(seed_value)

            # Generate a simple tone sequence
            audio = np.zeros(samples, dtype=np.float32)

            # Create tone segments for each word
            if len(words) > 0:
                samples_per_word = samples // len(words)
                base_freq = 220  # A3

                for i, word in enumerate(words):
                    # Vary frequency based on word
                    word_seed = sum(ord(c) for c in word)
                    freq = base_freq * (1.0 + (word_seed % 8) / 10)  # Vary by ±40%

                    # Calculate start and end indices for this word
                    start_idx = i * samples_per_word
                    end_idx = start_idx + samples_per_word
                    if (
                        i == len(words) - 1
                    ):  # Make sure last word uses all remaining samples
                        end_idx = samples

                    # Generate tone for this word
                    t = np.linspace(
                        0, 2 * np.pi * freq * duration / len(words), end_idx - start_idx
                    )
                    word_audio = 0.5 * np.sin(t)

                    # Add envelope
                    env = np.ones_like(word_audio)
                    env_len = min(int(0.01 * sample_rate), len(word_audio) // 4)
                    if env_len > 0:
                        env[:env_len] = np.linspace(0, 1, env_len)
                        env[-env_len:] = np.linspace(1, 0, env_len)

                    # Apply envelope
                    word_audio = word_audio * env

                    # Add to main audio
                    audio[start_idx:end_idx] = word_audio
            else:
                # If no words, generate a simple tone
                t = np.linspace(0, 2 * np.pi * 440 * duration, samples)
                audio = 0.5 * np.sin(t)

            # Apply volume from settings
            volume = settings.get("volume", 0.8)
            audio = audio * volume

            # Convert to 16-bit integer format
            audio_int16 = np.int16(audio * 32767)

            # Save as WAV file
            try:
                import scipy.io.wavfile

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                scipy.io.wavfile.write(output_path, sample_rate, audio_int16)
            except ImportError:
                # Last resort - create a silent audio file
                self._create_silent_audio(output_path, sample_rate, duration)

            logger.info(f"Created fallback audio file: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Fallback synthesis failed: {str(e)}")
            # Create a silent audio file as absolute last resort
            return self._create_silent_audio(output_path, 48000, 1.0)

    def _create_silent_audio(
        self, output_path: str, sample_rate: int = 48000, duration: float = 1.0
    ) -> str:
        """Create a silent audio file as ultimate fallback

        Args:
            output_path: Output file path
            sample_rate: Sample rate in Hz
            duration: Duration in seconds

        Returns:
            Path to the generated silent audio file
        """
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Generate silent audio
            samples = int(sample_rate * duration)
            silent_audio = np.zeros(samples, dtype=np.int16)

            # Save it
            try:
                import scipy.io.wavfile

                scipy.io.wavfile.write(output_path, sample_rate, silent_audio)
            except ImportError:
                # Manual WAV file creation as absolute last resort
                with open(output_path, "wb") as f:
                    # Create minimal WAV header
                    # RIFF header
                    f.write(b"RIFF")
                    f.write((36 + samples * 2).to_bytes(4, "little"))  # File size
                    f.write(b"WAVE")

                    # Format chunk
                    f.write(b"fmt ")
                    f.write((16).to_bytes(4, "little"))  # Chunk size
                    f.write((1).to_bytes(2, "little"))  # Audio format (PCM)
                    f.write((1).to_bytes(2, "little"))  # Channels
                    f.write(sample_rate.to_bytes(4, "little"))  # Sample rate
                    f.write((sample_rate * 2).to_bytes(4, "little"))  # Byte rate
                    f.write((2).to_bytes(2, "little"))  # Block align
                    f.write((16).to_bytes(2, "little"))  # Bits per sample

                    # Data chunk
                    f.write(b"data")
                    f.write((samples * 2).to_bytes(4, "little"))  # Chunk size

                    # Silent audio data (all zeros)
                    f.write(b"\x00" * (samples * 2))

            logger.info(f"Created silent audio file: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to create silent audio file: {str(e)}")
            return output_path  # Return path anyway
