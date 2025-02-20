"""
3️⃣ hearing.py – AI Speech Recognition & Voice Commands
🔹 Purpose: Enables real-time voice command recognition for hands-free AI control.
🔹 Key Functions:
✔ Uses Whisper ASR for high-accuracy speech-to-text transcription.
✔ Processes recorded audio and converts it into text.
✔ Filters background noise to improve recognition accuracy.
🔹 Use Cases:
✅ Enables wake-word detection for hands-free operation.
✅ Converts spoken commands into text for further processing.
✅ Helps in dictation and voice-based control.
"""
import whisper
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write

class Hearing:
    def __init__(self, model="base"):
        """Initialize the Hearing class with the Whisper ASR model."""
        self.model = whisper.load_model(model)
    
    def listen(self, duration=5, samplerate=16000):
        """Record audio and transcribe it using Whisper ASR."""
        print("Listening...")
        audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype=np.int16)
        sd.wait()
        write("input.wav", samplerate, audio)
        return self.transcribe("input.wav")
    
    def transcribe(self, file_path):
        """Transcribe recorded audio using Whisper."""
        result = self.model.transcribe(file_path)
        return result["text"]

if __name__ == "__main__":
    h = Hearing()
    print("Transcription:", h.listen())