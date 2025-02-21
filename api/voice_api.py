import sys
import os
from fastapi import FastAPI

import uvicorn

# Ensure Python can find scripts/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.voice import Voice  # Import Voice class

app = FastAPI()

@app.get("/status")
def status():
    return {"message": "Voice API is running"}

import sys
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn

# Ensure Python can find scripts/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.voice import Voice  # Import Voice class

app = FastAPI()

@app.get("/status")
def status():
    return {"message": "Voice API is running"}

@app.get("/get_file_audio")
def get_audio_file():
    voice_instance = Voice()
    file_path = voice_instance.speak("Hi I'm Sabrina, your personal assistant.")  # Generate audio
    return FileResponse(file_path, media_type="audio/wav")  # Return audio file

if __name__ == "__main__":
    ### Make a note to spin up the jenny model asap so we dont have to wait when we run other api calls
    uvicorn.run(app, host="0.0.0.0", port=8100)  # Port 8100 for voice
