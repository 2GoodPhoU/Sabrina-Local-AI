# Handles vision requests
import sys
import os
from fastapi import FastAPI, UploadFile, File
import uvicorn

# Ensure Python can find scripts/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.vision import Vision  # Import Vision class

app = FastAPI()

# Preload vision system
print("🚀 Loading vision system...")
vision_instance = Vision()  
print("✅ Vision system loaded successfully!")

@app.get("/status")
def status():
    return {"message": "Vision API is running"}

@app.post("/process_image")
async def process_image(file: UploadFile = File(...)):
    """Processes an uploaded image"""
    contents = await file.read()
    result = vision_instance.process_image(contents)
    return {"message": "Image processed", "result": result}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8200)  # Port 8200 for vision
