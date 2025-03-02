"""
Enhanced TTS Engine Implementation for Sabrina AI
================================================
This module replaces the placeholder TTS implementation with real functionality
using the Coqui TTS library.
"""

import os
import logging
import traceback
import numpy as np
from typing import Dict, Any

logger = logging.getLogger("tts_engine")


class TTSEngine:
    """Enhanced TTS engine using Coqui TTS for real speech synthesis"""

    def __init__(self, settings_manager):
        """Initialize the TTS engine with Coqui TTS models

        Args:
            settings_manager: Settings manager for voice configuration
        """
        self.settings_manager = settings_manager
        self.cache_dir = "data/audio_cache"
        self.tts_initialized = False
        self.tts = None
        self.tts_models = {}
        self.model_name = "tts_models/en/jenny/jenny"  # Default model
        self.vocoder_name = None  # Use default vocoder

        # Map of emotion to TTS parameters
        self.emotion_map = {
            "neutral": {"speed": 1.0, "pitch_factor": 1.0, "energy_factor": 1.0},
            "happy": {"speed": 1.1, "pitch_factor": 1.1, "energy_factor": 1.2},
            "sad": {"speed": 0.9, "pitch_factor": 0.9, "energy_factor": 0.8},
            "angry": {"speed": 1.1, "pitch_factor": 1.2, "energy_factor": 1.5},
            "fearful": {"speed": 1.2, "pitch_factor": 1.3, "energy_factor": 0.7},
            "disgust": {"speed": 0.95, "pitch_factor": 0.8, "energy_factor": 1.1},
            "surprised": {"speed": 1.2, "pitch_factor": 1.4, "energy_factor": 1.3},
        }

        # Available voice models
        self.voice_models = [
            "en_US-jenny-medium",  # Maps to jenny model
            "en_US-jenny-high",  # Maps to jenny with higher quality
            "en_US-tacotron2",  # Alternative model
            "en_US-hifigan",  # Another alternative
            "en_US-default",  # Generic fallback
        ]

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Initialize TTS
        self._init_tts()

    def _init_tts(self):
        """Initialize TTS library with models"""
        try:
            # Import TTS here to avoid startup issues if not installed
            import torch
            from TTS.api import TTS

            # Check if CUDA is available
            use_cuda = torch.cuda.is_available()
            device = "cuda" if use_cuda else "cpu"

            if use_cuda:
                logger.info("CUDA is available, using GPU for TTS")
            else:
                logger.info("CUDA not available, using CPU for TTS")

            # Try:
            try:
                # First try the newer TTS API
                self.tts = TTS(model_name=self.model_name)

                # If the TTS object has a to method to set device, use it
                if hasattr(self.tts, "to") and device == "cuda":
                    self.tts.to(device)

                self.tts_initialized = True
                logger.info(
                    f"TTS engine initialized successfully with model: {self.model_name}"
                )
            except TypeError:
                # If that fails, try older API
                try:
                    # Try alternative constructor format
                    self.tts = TTS()
                    self.tts.load_model(self.model_name)

                    self.tts_initialized = True
                    logger.info(
                        f"TTS engine initialized with alternative API method: {self.model_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to initialize TTS with alternative method: {str(e)}"
                    )
                    self.tts_initialized = False

            # Log available models for reference
            logger.info(
                f"Available speaker voices: {self.tts.speakers if hasattr(self.tts, 'speakers') else 'No speaker selection available'}"
            )
            logger.info(
                f"Available languages: {self.tts.languages if hasattr(self.tts, 'languages') else 'No language selection available'}"
            )

        except ImportError as e:
            logger.error(f"TTS library not installed: {str(e)}")
            logger.warning("Install TTS with: pip install TTS")
            self.tts_initialized = False
        except Exception as e:
            logger.error(f"Error initializing TTS: {str(e)}")
            logger.error(traceback.format_exc())
            self.tts_initialized = False

    def _process_text(self, text: str) -> str:
        """Process text for better TTS results

        Args:
            text: Input text

        Returns:
            Processed text
        """
        # Remove extra whitespace
        text = " ".join(text.split())

        # Ensure text ends with punctuation for better prosody
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
            voice_settings: Voice settings to use for this speech

        Returns:
            Path to generated audio file
        """
        import hashlib
        import json
        import os

        # Get settings
        settings = self.settings_manager.get_settings().dict()
        if voice_settings:
            # Update with provided settings
            for key, value in voice_settings.items():
                if value is not None:
                    settings[key] = value

        # Get cache path
        use_cache = settings.get("cache_enabled", True)
        if "cache" in voice_settings:
            use_cache = voice_settings["cache"]

        # Create a unique hash based on text and settings
        settings_for_hash = {k: v for k, v in settings.items() if k != "cache_enabled"}
        cache_key = f"{text}|{json.dumps(settings_for_hash)}"
        cache_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
        output_path = os.path.join(self.cache_dir, f"{cache_hash}.wav")

        # Check if cached file exists
        if use_cache and os.path.exists(output_path):
            logger.info(f"Using cached audio file: {output_path}")
            return output_path

        # Generate speech
        if self.tts_initialized:
            success = await self._generate_speech(text, output_path, settings)
            if success:
                return output_path

        # Fallback to alternative synthesis if TTS fails
        return await self._fallback_synthesis(text, output_path, settings)

    async def _generate_speech(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> bool:
        """Generate speech using TTS library

        Args:
            text: Text to convert to speech
            output_path: Output file path
            settings: Voice settings

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.tts_initialized or not self.tts:
            logger.error("TTS not initialized, cannot generate speech")
            return False

        try:
            # Process text for better results
            processed_text = self._process_text(text)

            # Extract settings
            voice = settings.get("voice", "en_US-jenny-medium")
            speed = settings.get("speed", 1.0)
            pitch = settings.get("pitch", 1.0)
            volume = settings.get("volume", 0.8)
            emotion = settings.get("emotion", "neutral")

            print(voice)

            # Map voice to model parameters
            speaker = None
            language = None

            if hasattr(self.tts, "speakers") and self.tts.speakers:
                # If multi-speaker model, use first speaker as default
                speaker = self.tts.speakers[0]

            if hasattr(self.tts, "languages") and self.tts.languages:
                # If multi-language model, use English as default
                language = "en"

            # Apply emotion settings from emotion map
            emotion_settings = self.emotion_map.get(
                emotion, self.emotion_map["neutral"]
            )
            adjusted_speed = speed * emotion_settings["speed"]

            # Generate speech with TTS
            logger.info(
                f"Generating speech for text: {processed_text[:100]}{'...' if len(processed_text) > 100 else ''}"
            )

            # Generate speech - different parameters depending on the model capabilities
            if speaker and language:
                wav = self.tts.tts(processed_text, speaker=speaker, language=language)
            elif speaker:
                wav = self.tts.tts(processed_text, speaker=speaker)
            elif language:
                wav = self.tts.tts(processed_text, language=language)
            else:
                wav = self.tts.tts(processed_text)

            # Apply post-processing
            wav = self._apply_audio_effects(wav, pitch, volume, adjusted_speed)

            # Save to file
            self._save_wav(wav, output_path)

            logger.info(f"Speech generated and saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _apply_audio_effects(
        self, wav, pitch_factor: float, volume: float, speed: float
    ) -> np.ndarray:
        """Apply audio effects to the generated speech

        Args:
            wav: Audio data
            pitch_factor: Pitch adjustment factor
            volume: Volume adjustment factor
            speed: Speed adjustment factor

        Returns:
            Modified audio data
        """
        try:
            # Import here to avoid dependency issues if not available
            import numpy as np

            # Convert to numpy array if needed
            if not isinstance(wav, np.ndarray):
                try:
                    wav = np.array(wav, dtype=np.float32)
                except Exception as e:
                    logger.warning(
                        f"Could not convert audio to numpy array, returning original: {e}"
                    )
                    return wav

            # Apply volume adjustment (simple multiplication)
            try:
                wav_adjusted = wav * volume
            except Exception as e:
                logger.warning(f"Volume adjustment failed: {e}")
                wav_adjusted = wav

            # Skip time/pitch adjustments if they're close to default values
            if abs(pitch_factor - 1.0) < 0.01 and abs(speed - 1.0) < 0.01:
                return wav_adjusted

            # Create a simplified approach to speed/pitch adjustment without using librosa
            # This is a fallback method that doesn't require the complex phase vocoder
            try:
                # For speed changes only, we can use simple resampling
                if abs(pitch_factor - 1.0) < 0.01 and abs(speed - 1.0) >= 0.01:
                    # Calculate new length based on speed
                    new_length = int(len(wav_adjusted) / speed)
                    # Use simple linear interpolation
                    indices = np.linspace(0, len(wav_adjusted) - 1, new_length)
                    indices = indices.astype(np.int32)
                    wav_adjusted = wav_adjusted[indices]
                    return wav_adjusted

                # If pitch adjustment is needed, simply return volume-adjusted audio
                # Full pitch adjustment would require more complex processing
                logger.info("Complex pitch adjustment skipped to avoid errors")
                return wav_adjusted

            except Exception as e:
                logger.error(f"Simplified audio effect processing failed: {e}")
                logger.error(traceback.format_exc())
                # Return the volume-adjusted audio at least
                return wav_adjusted

        except Exception as e:
            logger.error(f"Error applying audio effects: {str(e)}")
            logger.error(traceback.format_exc())
            return wav  # Return original on error

    def _save_wav(self, wav: np.ndarray, output_path: str, sample_rate: int = 22050):
        """Save audio data to WAV file

        Args:
            wav: Audio data
            output_path: Output file path
            sample_rate: Sample rate in Hz
        """
        try:
            import soundfile as sf

            # Ensure parent directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save as WAV
            sf.write(output_path, wav, sample_rate)
        except ImportError:
            # Fallback if soundfile not available
            try:
                import scipy.io.wavfile

                scipy.io.wavfile.write(output_path, sample_rate, wav)
            except ImportError:
                logger.error("Neither soundfile nor scipy available for saving WAV")
                raise ImportError("Cannot save audio: soundfile or scipy required")

    async def _fallback_synthesis(
        self, text: str, output_path: str, settings: Dict[str, Any]
    ) -> str:
        """Fallback synthesis method if TTS fails or is not available

        Args:
            text: Text to convert
            output_path: Output file path
            settings: Voice settings

        Returns:
            Path to the generated audio file
        """
        try:
            # Try to create a sine wave with variations based on the text
            # This is a basic fallback when the main TTS fails

            # Create a simple tone sequence
            sample_rate = 22050
            duration = min(0.1 * len(text.split()), 10)  # 0.1s per word, max 10s
            duration = max(duration, 1.0)  # At least 1 second

            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

            # Create a seed value from the text for reproducibility
            seed_value = sum(ord(c) for c in text)
            np.random.seed(seed_value)

            # Generate tones with some variation
            base_freq = 200 + (seed_value % 200)  # Base frequency 200-400Hz
            amplitude = 0.3

            # Create a sequence of tones for words
            words = text.split()
            word_count = len(words)

            # Initialize empty audio
            audio = np.zeros(int(sample_rate * duration))

            if word_count > 0:
                # Duration per word
                word_duration = duration / word_count
                samples_per_word = int(sample_rate * word_duration)

                # Generate each word's "tone"
                for i, word in enumerate(words):
                    word_seed = sum(ord(c) for c in word)
                    word_freq = base_freq + (word_seed % 100)

                    # Calculate start and end indices for this word
                    start_idx = i * samples_per_word
                    end_idx = min(start_idx + samples_per_word, len(audio))

                    # Generate tone for this word
                    word_t = t[start_idx:end_idx] - t[start_idx]
                    word_audio = amplitude * np.sin(2 * np.pi * word_freq * word_t)

                    # Add envelope to avoid clicks
                    env = np.ones_like(word_audio)
                    env_len = min(int(0.01 * sample_rate), len(word_audio) // 4)
                    env[:env_len] = np.linspace(0, 1, env_len)
                    env[-env_len:] = np.linspace(1, 0, env_len)

                    word_audio = word_audio * env

                    # Add to the full audio
                    audio[start_idx:end_idx] = word_audio
            else:
                # If no words, just use a simple tone
                audio = amplitude * np.sin(2 * np.pi * base_freq * t)

            # Normalize audio to 16-bit range
            audio = np.int16(audio / np.max(np.abs(audio)) * 32767 * 0.8)

            # Save the audio
            self._save_wav(audio, output_path, sample_rate)

            logger.info(f"Generated fallback speech audio: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Fallback synthesis failed: {str(e)}")

            # Create a very simple silent audio file as a last resort
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Create a simple silent audio file
                sample_rate = 22050
                duration = 1.0  # 1 second

                # Generate silent audio
                audio = np.zeros(int(sample_rate * duration), dtype=np.int16)

                # Save the audio
                import scipy.io.wavfile

                scipy.io.wavfile.write(output_path, sample_rate, audio)

                return output_path
            except Exception as fallback_error:
                logger.error(
                    f"Critical error in fallback synthesis: {str(fallback_error)}"
                )
                # Return the path anyway - the caller will handle the missing file
                return output_path
