# Handles hearing requestsfrom fastapi import FastAPI
import sys
import os
from fastapi import FastAPI
import uvicorn

# Add /app/ to Python’s module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.hearing import Hearing  # Import the Hearing class


app = FastAPI()

@app.get("/status")
def status():
    return {"message": "Hearing API is running"}

@app.get("/test_hearing")
def test_hearing():
    # Create an instance of the Hearing class and call a test function
    hearing_instance = Hearing()  # Ensure Hearing has a test function
    return {"message": "Hearing function triggered"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
