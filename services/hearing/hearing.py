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
from vosk import Model, KaldiRecognizer
import pyaudio
import json
import keyboard
import time
import os
import wget

def find_vosk_model(directory="../../models/"):
    """Find the correct Vosk model folder dynamically."""
    if not os.path.exists(directory):
        os.makedirs(directory)
    subdirs = [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
    for subdir in subdirs:
        if "vosk-model" in subdir:
            return os.path.join(directory, subdir)
    return None

class Hearing:
    def __init__(self, wake_word="hey sabrina", model_path="models/"): 
        """Initialize Vosk for wake-word detection."""
        self.model_path = find_vosk_model(model_path) or self.download_model()
        self.model = Model(self.model_path)
        self.recognizer = KaldiRecognizer(self.model, 16000)
        self.audio_stream = pyaudio.PyAudio().open(
            rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=4096
        )
        self.wake_word = wake_word.lower()
        self.active = True  # Controls whether the listener is active

    def download_model(self):
        """Download Vosk model if it's not found in the specified path."""
        print("[Downloading Vosk Model]")
        model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        model_zip_path = "models/vosk-model.zip"
        wget.download(model_url, model_zip_path)
        import zipfile
        with zipfile.ZipFile(model_zip_path, 'r') as zip_ref:
            zip_ref.extractall("models/")
        os.remove(model_zip_path)
        print("[Vosk Model Downloaded and Extracted]")
        return find_vosk_model()

    def listen_for_wake_word(self):
        """Continuously listens for the wake word using Vosk."""
        print("[Listening for wake word or hotkey Ctrl+Shift+S]")
        while True:
            if not self.active:
                time.sleep(1)  # Pause listening if not active
                continue

            data = self.audio_stream.read(4096, exception_on_overflow=False)
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                transcript = result.get("text", "").lower()
                if self.wake_word in transcript:
                    print(f"[Wake-word detected: {self.wake_word}]")
                    self.active = False  # Disable listener temporarily
                    command = self.listen()
                    print(f"[User Command] {command}")
                    self.active = True  # Re-enable listener after processing
            
            if keyboard.is_pressed("ctrl+shift+s"):
                print("[Hotkey activated!]")
                self.active = False  # Disable listener temporarily
                command = self.listen()
                print(f"[User Command] {command}")
                self.active = True  # Re-enable listener after processing

    def listen(self):
        """Records and transcribes user speech to text."""
        print("Listening for command...")
        self.recognizer.Reset()
        while True:
            data = self.audio_stream.read(4096, exception_on_overflow=False)
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                transcript = result.get("text", "").strip()
                if transcript:
                    return transcript
        return ""

if __name__ == "__main__":
    hearing = Hearing()
    hearing.listen_for_wake_word()
