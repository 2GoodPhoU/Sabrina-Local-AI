# Voice Service Setup Guide

This guide provides instructions for setting up and running the Sabrina AI Voice Service, which provides text-to-speech capabilities for the Sabrina AI Assistant.

## Requirements

- Python 3.10+
- Docker (optional, for containerized deployment)
- FFmpeg (for audio processing)

## Installation Methods

### Method 1: Direct Python Installation

1. **Create a virtual environment (recommended)**:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:

```bash
pip install -r voice_docker_requirements.txt
```

3. **Run the service**:

```bash
python voice_api.py
```

The service will start on port 8100 by default.

### Method 2: Docker Deployment

1. **Build and start the Docker container**:

```bash
docker-compose up -d
```

This will build the Docker image and start the service in detached mode.

2. **View logs**:

```bash
docker-compose logs -f
```

## Configuration

### Environment Variables

- `VOICE_API_PORT`: Port for the Voice API (default: 8100)
- `VOICE_API_KEY`: API key for securing the API (default: sabrina-dev-key)
- `DEBUG`: Enable debug mode (true/false)

### Configuration File

The service uses a configuration file at `config/voice_settings.json`. This file is created automatically on first run with default settings, but you can modify it to customize voice behavior:

```json
{
    "voice": "en_US-jenny-medium",
    "speed": 1.0,
    "pitch": 1.0,
    "volume": 0.8,
    "emotion": "neutral",
    "cache_enabled": true
}
```

## API Usage

The Voice API provides several endpoints:

### Status Check

```
GET /status
```

Returns the service status and TTS initialization state.

### Text-to-Speech

```
POST /speak
Content-Type: application/json
X-API-Key: your-api-key

{
    "text": "Hello, I am Sabrina AI",
    "voice": "en_US-jenny-medium",
    "speed": 1.0,
    "pitch": 1.0,
    "volume": 0.8,
    "emotion": "neutral",
    "cache": true
}
```

Returns a URL to the generated audio file.

### Simple Text-to-Speech

```
POST /speak_simple?text=Hello%20World
```

Simpler endpoint that doesn't require authentication.

### Get Available Voices

```
GET /voices
X-API-Key: your-api-key
```

Returns a list of available voice models.

### Get Voice Settings

```
GET /settings
X-API-Key: your-api-key
```

Returns the current voice settings.

### Update Voice Settings

```
POST /settings
Content-Type: application/json
X-API-Key: your-api-key

{
    "voice": "en_US-jenny-medium",
    "speed": 1.2,
    "pitch": 0.9,
    "volume": 0.8,
    "emotion": "happy",
    "cache_enabled": true
}
```

Updates the voice settings. You can include only the settings you want to change.

## Client Usage

The Voice API Client provides a simple interface for using the Voice API:

```python
from voice_api_client import VoiceAPIClient

# Create client
client = VoiceAPIClient(api_url="http://localhost:8100", api_key="your-api-key")

# Test connection
if client.test_connection():
    print("Connected to Voice API")
else:
    print("Failed to connect to Voice API")

# Convert text to speech
client.speak("Hello, I am Sabrina AI")

# Get available voices
voices = client.get_voices()
print(f"Available voices: {voices}")

# Get current settings
settings = client.get_settings()
print(f"Current settings: {settings}")

# Update settings
client.update_settings({
    "speed": 1.2,
    "pitch": 0.9
})
```

## Enhanced Client with Event Bus

For integration with Sabrina AI's event system, you can use the Enhanced Voice Client:

```python
from voice_api_client import EnhancedVoiceClient
from utilities.event_system import EventBus

# Create event bus
event_bus = EventBus()
event_bus.start()

# Create enhanced client with event bus
client = EnhancedVoiceClient(
    api_url="http://localhost:8100",
    event_bus=event_bus,
    api_key="your-api-key"
)

# Register event handler for voice status events
def handle_voice_events(event):
    status = event.data.get("status")
    if status == "speaking_started":
        print(f"Started speaking: {event.data.get('text')}")
    elif status == "speaking_completed":
        print("Finished speaking")
    elif status == "speaking_failed":
        print("Failed to speak")

handler_id = event_bus.register_handler(
    event_bus.create_event_handler(
        event_types=["VOICE_STATUS"],
        callback=handle_voice_events
    )
)

# Test speaking with events
client.speak("This will trigger voice status events")

# Clean up
event_bus.unregister_handler(handler_id)
event_bus.stop()
```

## Troubleshooting

### Service Won't Start

1. Check if the port is already in use:
   ```bash
   netstat -tuln | grep 8100  # On Linux/Mac
   netstat -an | findstr 8100  # On Windows
   ```

2. Check logs for errors:
   ```bash
   cat logs/voice_api.log
   ```

### TTS Not Working

1. Make sure you have FFmpeg installed.
   ```bash
   ffmpeg -version
   ```

2. Check if TTS library is properly installed:
   ```bash
   pip show TTS
   ```

3. If TTS fails to initialize, the service will use a fallback synthesis method, which may not sound as good.

### Authentication Issues

- Make sure you're using the correct API key.
- Check if the API key is properly set in the environment or client.

## Testing

You can test the Voice Service using the included test script:

```bash
python voice_module_test.py --test all
```

This will run all tests to verify that the service is working correctly.
