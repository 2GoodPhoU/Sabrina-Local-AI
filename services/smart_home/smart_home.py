"""
smart_home.py – AI Smart Home Control Module
🔹 Purpose: Interfaces with Google Home & Home Assistant for proactive automation.
🔹 Key Functions:
✔ Control smart lights, thermostat, and locks.
✔ Trigger automations based on AI interactions.
✔ Expose an API for smart home control.
"""
from fastapi import FastAPI, Query
import requests
import os
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()
HOME_ASSISTANT_URL = os.getenv("HOME_ASSISTANT_URL")
HOME_ASSISTANT_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN")

app = FastAPI()

def call_home_assistant(service: str, entity_id: str):
    """Send a request to Home Assistant API to control devices."""
    headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}
    payload = {"entity_id": entity_id}
    
    response = requests.post(f"{HOME_ASSISTANT_URL}/api/services/{service}", json=payload, headers=headers)
    return response.json() if response.status_code == 200 else {"status": "error", "message": response.text}

@app.get("/turn_on")
def turn_on(entity: str = Query(..., description="Home Assistant entity ID")):
    """Turn on a smart home device."""
    return call_home_assistant("homeassistant/turn_on", entity)

@app.get("/turn_off")
def turn_off(entity: str = Query(..., description="Home Assistant entity ID")):
    """Turn off a smart home device."""
    return call_home_assistant("homeassistant/turn_off", entity)

@app.get("/adjust_temperature")
def adjust_temperature(entity: str = Query(...), temperature: int = Query(...)):
    """Set thermostat temperature."""
    headers = {"Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}", "Content-Type": "application/json"}
    payload = {"entity_id": entity, "temperature": temperature}
    
    response = requests.post(f"{HOME_ASSISTANT_URL}/api/services/climate/set_temperature", json=payload, headers=headers)
    return response.json() if response.status_code == 200 else {"status": "error", "message": response.text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8500)
