from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import uvicorn
from voice import Voice  # Import Voice class
import threading

app = FastAPI()
voice_instance = Voice()

# Preload the Jenny TTS model on startup
def preload_model():
    print("Preloading Jenny TTS model...")
    voice_instance.speak("Model preloaded")  # Warm up the model

preload_thread = threading.Thread(target=preload_model)
preload_thread.start()

@app.get("/status")
def status():
    return {"message": "Voice API is running"}

@app.get("/speak")
def get_audio_file(text: str = Query(..., description="Text to convert to speech")):
    file_path = voice_instance.speak(text)  # Generate audio
    return FileResponse(file_path, media_type="audio/wav")  # Return audio file

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)  # Port 8100 for voice
