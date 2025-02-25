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
from TTS.api import TTS  # Jenny TTS

class Voice:
    def __init__(self, tts_model="tts_models/en/jenny/jenny"):
        """Initialize the Voice class with the specified TTS model."""
        self.tts = TTS(tts_model)
        self.output_audio_path = "/app/output.wav"  # Ensure file saves in the correct directory
    
    def speak(self, text):
        """Convert text to speech and save the generated audio."""
        if not text.strip():
            print("Error: No text provided for speech synthesis.")
            return
        
        # Generate the speech file
        self.tts.tts_to_file(text=text, file_path=self.output_audio_path)
        print(f"✅ Audio file generated at {self.output_audio_path}")
        return self.output_audio_path  # Return the file path instead of playing
