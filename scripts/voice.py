"""
2️⃣ voice.py – Text-to-Speech (TTS) & AI Voice Output
🔹 Purpose: Converts text into natural-sounding speech and plays it aloud.
🔹 Key Functions:
✔ speak(text) – Uses Jenny TTS to synthesize speech.
✔ play_audio(file_path) – Plays the generated speech file.
✔ Handles audio playback clean-up automatically.
🔹 Use Cases:
✅ Narrates detected text from the screen for accessibility.
✅ Provides AI-generated responses via voice output.
✅ Enhances natural interaction with Sabrina.
"""
import os
import subprocess
from TTS.api import TTS  # Jenny TTS

class Voice:
    def __init__(self, tts_model="tts_models/en/jenny/jenny"):
        """Initialize the Voice class with the specified TTS model."""
        self.tts = TTS(tts_model)
        self.output_audio_path = "output.wav"
    
    def speak(self, text):
        """Convert text to speech and play the generated audio."""
        if not text.strip():
            print("Error: No text provided for speech synthesis.")
            return
        
        self.tts.tts_to_file(text=text, file_path=self.output_audio_path)
        self.play_audio(self.output_audio_path)
    
    def play_audio(self, file_path):
        """Play the generated speech audio file."""
        if os.path.exists(file_path):
            try:
                if os.name == "nt":  # Windows
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:  # macOS/Linux
                    subprocess.run(["afplay", file_path])
                os.remove(file_path)  # Clean up after playback
            except Exception as e:
                print(f"Error playing audio: {e}")
        else:
            print("Error: Audio file not found!")

if __name__ == "__main__":
    v = Voice()
    v.speak("Hello! This is a test of the Jenny TTS system.")
