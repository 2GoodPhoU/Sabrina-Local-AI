#!/usr/bin/env python3
"""
Unit tests for Sabrina AI Hearing Service
Tests the core functionality of the hearing service
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import time

# Import test utilities
from tests.test_utils.paths import ensure_project_root_in_sys_path

# Import the class to test
from services.hearing.hearing import Hearing

# Ensure the project root is in the Python path
ensure_project_root_in_sys_path()


class TestHearing(unittest.TestCase):
    """Test case for the Hearing class"""

    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures"""
        # Create a temporary directory for test files
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_model_path = os.path.join(cls.temp_dir.name, "test_model")

        # Create a mock model directory structure
        os.makedirs(cls.test_model_path, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures"""
        cls.temp_dir.cleanup()

    def setUp(self):
        """Set up test fixtures"""
        # Create patchers for external dependencies
        self._setup_patchers()

        # Create an instance of the Hearing class with test configuration
        self.hearing = Hearing(wake_word="hey sabrina", model_path=self.test_model_path)

    def tearDown(self):
        """Clean up test fixtures"""
        # Close the hearing instance
        if hasattr(self, "hearing") and self.hearing:
            self.hearing.close()

        # Stop all patchers
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()

    def _setup_patchers(self):
        """Set up mock objects for external dependencies"""
        self._patchers = []

        # Mock PyAudio
        pyaudio_patcher = patch("pyaudio.PyAudio")
        self.mock_pyaudio = pyaudio_patcher.start()
        self._patchers.append(pyaudio_patcher)

        # Mock PyAudio stream
        self.mock_stream = MagicMock()
        self.mock_pyaudio.return_value.open.return_value = self.mock_stream

        # Mock the stream's read method to return sample audio data
        self.mock_stream.read.return_value = (
            b"\x00" * 8192
        )  # Empty audio data for testing

        # Mock keyboard for hotkey detection
        keyboard_patcher = patch("keyboard.is_pressed")
        self.mock_keyboard = keyboard_patcher.start()
        self._patchers.append(keyboard_patcher)
        self.mock_keyboard.return_value = False  # Default: hotkey not pressed

        # Mock playsound for wake sound
        playsound_patcher = patch("playsound.playsound")
        self.mock_playsound = playsound_patcher.start()
        self._patchers.append(playsound_patcher)

        # Mock Vosk model components
        # We'll use a two-layer approach to mock both the import and the class

        # First mock the import
        vosk_module_patcher = patch.dict("sys.modules", {"vosk": MagicMock()})
        vosk_module_patcher.start()
        self._patchers.append(vosk_module_patcher)

        # Then mock the Model and KaldiRecognizer classes
        import sys

        if "vosk" not in sys.modules:
            sys.modules["vosk"] = MagicMock()

        vosk_model_patcher = patch("sys.modules.vosk.Model")
        self.mock_vosk_model_class = vosk_model_patcher.start()
        self._patchers.append(vosk_model_patcher)

        vosk_recognizer_patcher = patch("sys.modules.vosk.KaldiRecognizer")
        self.mock_vosk_recognizer_class = vosk_recognizer_patcher.start()
        self._patchers.append(vosk_recognizer_patcher)

        # Create mock instances
        self.mock_vosk_model = MagicMock()
        self.mock_vosk_model_class.return_value = self.mock_vosk_model

        self.mock_vosk_recognizer = MagicMock()
        self.mock_vosk_recognizer_class.return_value = self.mock_vosk_recognizer

        # Configure mock behavior
        self.mock_vosk_recognizer.AcceptWaveform.return_value = (
            False  # Default: no speech detected
        )
        self.mock_vosk_recognizer.Result.return_value = (
            '{"text": ""}'  # Default: empty result
        )

    def test_initialization(self):
        """Test initialization of the Hearing class"""
        # Test basic attributes
        self.assertEqual(self.hearing.wake_word, "hey sabrina")
        self.assertEqual(self.hearing.model_path, self.test_model_path)
        self.assertEqual(self.hearing.hotkey, "ctrl+shift+s")  # Default hotkey

        # Check that PyAudio was initialized
        self.mock_pyaudio.assert_called_once()

        # Check that Vosk model was loaded
        if hasattr(self.hearing, "vosk_model"):
            self.assertIsNotNone(self.hearing.vosk_model)
            self.mock_vosk_model_class.assert_called_once_with(self.test_model_path)
            self.mock_vosk_recognizer_class.assert_called_once()

    def test_wake_word_detection_by_voice(self):
        """Test wake word detection through voice input"""
        # Configure mock to simulate detected wake word
        self.mock_vosk_recognizer.AcceptWaveform.return_value = True
        self.mock_vosk_recognizer.Result.return_value = (
            '{"text": "hey sabrina what time is it"}'
        )

        # Call the method
        result = self.hearing.listen_for_wake_word()

        # Check the result
        self.assertTrue(result)

        # Verify the wake word was processed
        self.mock_vosk_recognizer.AcceptWaveform.assert_called()
        self.mock_vosk_recognizer.Result.assert_called()

    def test_wake_word_detection_by_hotkey(self):
        """Test wake word detection through hotkey"""
        # Configure mock to simulate hotkey press
        self.mock_keyboard.return_value = True

        # Call the method
        result = self.hearing.listen_for_wake_word()

        # Check the result
        self.assertTrue(result)

        # Verify hotkey was checked
        self.mock_keyboard.assert_called_with(self.hearing.hotkey)

    def test_listening_with_timeout(self):
        """Test listening for speech with timeout"""

        # Configure mock to simulate speech after a delay
        def side_effect_generator():
            # First call returns False, second call returns True to simulate delayed speech
            yield False
            yield True

        side_effect = side_effect_generator()
        self.mock_vosk_recognizer.AcceptWaveform.side_effect = lambda data: next(
            side_effect
        )

        # Configure result with transcription
        self.mock_vosk_recognizer.Result.return_value = '{"text": "test transcription"}'

        # Call listen with a short timeout
        result = self.hearing.listen(timeout=1.0)

        # Check the result
        self.assertEqual(result, "test transcription")

        # Verify the speech was processed
        self.mock_vosk_recognizer.AcceptWaveform.assert_called()
        self.mock_vosk_recognizer.Result.assert_called()

        # Verify the Reset method was called for new input
        self.mock_vosk_recognizer.Reset.assert_called_once()

    def test_listening_timeout(self):
        """Test listening timeout with no speech detected"""
        # Configure mock to never detect speech
        self.mock_vosk_recognizer.AcceptWaveform.return_value = False

        # Call listen with a very short timeout to speed up the test
        result = self.hearing.listen(timeout=0.1)

        # Check the result (should be empty when timeout occurs)
        self.assertEqual(result, "")

    def test_close_method(self):
        """Test the close method for resource cleanup"""
        # Call the close method
        self.hearing.close()

        # Check that the audio stream was closed
        if hasattr(self.hearing, "stream") and self.hearing.stream:
            self.mock_stream.stop_stream.assert_called_once()
            self.mock_stream.close.assert_called_once()

        # Check that PyAudio was terminated
        self.mock_pyaudio.return_value.terminate.assert_called_once()

    def test_vosk_unavailable(self):
        """Test fallback behavior when Vosk is not available"""
        # Create a new set of patchers for this test
        test_patchers = []

        # Mock ImportError when importing Vosk
        import_error_patcher = patch(
            "services.hearing.hearing.Hearing._load_vosk_model",
            side_effect=ImportError("No module named 'vosk'"),
        )
        mock_import_error = import_error_patcher.start()
        test_patchers.append(import_error_patcher)

        try:
            # Create a new instance with mocked import error
            hearing_no_vosk = Hearing(
                wake_word="hey sabrina", model_path=self.test_model_path
            )

            # Check that vosk_model is None
            self.assertIsNone(hearing_no_vosk.vosk_model)

            # Test wake word detection should use console input
            with patch("builtins.input", return_value="hey sabrina"):
                result = hearing_no_vosk.listen_for_wake_word()
                self.assertTrue(result)

            # Test listen should use console input
            with patch(
                "builtins.input", return_value="test transcription without vosk"
            ):
                result = hearing_no_vosk.listen()
                self.assertEqual(result, "test transcription without vosk")

        finally:
            # Clean up
            for patcher in test_patchers:
                patcher.stop()

            if "hearing_no_vosk" in locals():
                hearing_no_vosk.close()


if __name__ == "__main__":
    unittest.main()
