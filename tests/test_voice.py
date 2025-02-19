import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))

import unittest
from unittest.mock import patch, MagicMock
import time
import subprocess
from scripts.voice import speak

class TestVoiceFunctions(unittest.TestCase):

    @patch("voice.ask_sabrina", return_value="Hello, this is Sabrina!")
    @patch("voice.load_settings", return_value={"speed": 1.0, "emotion": "neutral"})
    @patch("voice.TTS")
    @patch("voice.subprocess.Popen")
    def test_speak(self, mock_popen, mock_tts, mock_load_settings, mock_ask_sabrina):
        """ Test the speak function """

        # Mocking TTS model
        mock_tts_instance = MagicMock()
        mock_tts.return_value = mock_tts_instance

        # Mocking subprocess
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        test_text = "Test speech output."
        speak(test_text)

        # Ensure AI response was requested
        mock_ask_sabrina.assert_called_once_with(test_text)

        # Ensure settings were loaded
        mock_load_settings.assert_called_once()

        # Ensure TTS model was initialized correctly
        mock_tts.assert_called_once_with("tts_models/en/jenny/jenny", gpu=True)

        # Ensure TTS was used to generate audio
        mock_tts_instance.tts_to_file.assert_called_once()
        
        # Verify subprocess was used to play audio
        mock_popen.assert_called()

        # Ensure output file was removed after playback
        output_dir = os.path.join(os.getcwd(), "output")
        timestamp = int(time.time())
        output_file = os.path.join(output_dir, f"response_{timestamp}.wav")
        if os.path.exists(output_file):
            os.remove(output_file)
        self.assertFalse(os.path.exists(output_file), "Output file was not deleted.")

if __name__ == "__main__":
    unittest.main()
