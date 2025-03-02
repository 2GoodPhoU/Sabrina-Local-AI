# Sabrina AI Voice Service

This is the voice service component of Sabrina AI, providing high-quality text-to-speech (TTS) capabilities through a REST API.

## 🚀 Features

- **High-quality text-to-speech** using the Jenny TTS model
- **FastAPI-based REST API** for speech generation
- **Docker support** for easy deployment
- **Configurable voice settings** (speed, pitch, volume, emotion)
- **Audio caching** for improved performance
- **Cross-platform audio playback** support

## 📦 Installation

### Prerequisites

- Python 3.8+ (3.10 recommended)
- Docker (optional, for containerized deployment)
- FFmpeg (recommended for audio processing)

### Option 1: Setup Script (Recommended)

Run the included setup script to automatically install dependencies and set up the service:

```bash
python setup_voice.py
```

For additional options:

```bash
python setup_voice.py --help
```

### Option 2: Manual Setup

1. **Create a virtual environment**:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:

```bash
pip install -r voice_docker_requirements.txt
```

3. **Create required directories**:

```bash
mkdir -p logs data/audio_cache config models
```

## 🚀 Usage

### Option 1: Running with Docker (Recommended)

1. **Build the Docker image**:

```bash
docker compose build
```

2. **Start the container**:

```bash
docker compose up -d
```

3. **Check logs**:

```bash
docker compose logs -f
```

### Option 2: Running Directly

1. **Start the voice service**:

```bash
python voice_api.py
```

The service will start on port 8100 by default.

## 🧪 Testing

You can test the voice service using the included test script:

```bash
python voice_module_test.py
```

This script will:
- Test connection to the voice service
- Test speech generation
- Test voice settings
- Test available voices

## 📋 API Endpoints

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

### Available Voices

```
GET /voices
X-API-Key: your-api-key
```

Returns a list of available voice models.

### Voice Settings

```
GET /settings
X-API-Key: your-api-key
```

Returns the current voice settings.

### Update Settings

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

## 📢 Client Usage Examples

### Basic Usage

```python
from voice_api_client import VoiceAPIClient

# Create client
client = VoiceAPIClient(api_url="http://localhost:8100")

# Test connection
if client.test_connection():
    print("Connected to Voice API")

# Convert text to speech
client.speak("Hello, I am Sabrina AI")

# Update voice settings
client.update_settings({
    "speed": 1.2,
    "pitch": 0.9
})
```

### With Event Bus

```python
from voice_api_client import EnhancedVoiceClient
from utilities.event_system import EventBus, EventType, Event

# Create event bus
event_bus = EventBus()
event_bus.start()

# Create enhanced client
client = EnhancedVoiceClient(
    api_url="http://localhost:8100",
    event_bus=event_bus
)

# Speak with event notifications
client.speak("This will trigger voice status events")

# Clean up
event_bus.stop()
```

## 🔧 Configuration

Configuration is stored in `config/voice_settings.json` and includes:

- `voice`: TTS voice model name
- `speed`: Speech speed (0.5-2.0)
- `pitch`: Voice pitch (0.5-2.0)
- `volume`: Audio volume (0.0-1.0)
- `emotion`: Emotional style (neutral, happy, sad)
- `cache_enabled`: Whether to cache generated audio files

## 🚀 Docker Environment Variables

When running with Docker, you can configure:

- `VOICE_API_PORT`: Port for the Voice API (default: 8100)
- `VOICE_API_KEY`: API key for securing the API (default: sabrina-dev-key)
- `DEBUG`: Enable debug mode (true/false)

## 🔍 Troubleshooting

If you encounter issues:

1. **API is not accessible**:
   - Check if the service is running: `docker ps` or check the process list
   - Verify port 8100 is not in use by another application

2. **Audio playback issues**:
   - Check if the required audio libraries are installed
   - Try installing additional audio backends: `pip install pygame sounddevice soundfile playsound`

3. **TTS model issues**:
   - Check if the model was downloaded correctly
   - Look for error messages in the logs

4. **Container won't start**:
   - Check docker logs: `docker compose logs`
   - Ensure volumes are properly mounted

## 📦 File Structure

```
/services/voice/
│-- voice_api.py                  # FastAPI server
│-- voice_api_client.py           # Client library
│-- tts_implementation.py         # TTS engine implementation
│-- voice_playback.py             # Audio playback utilities
│-- voice_module_test.py          # Test script
│-- voice.Dockerfile              # Docker configuration
│-- docker-compose.yml            # Docker compose setup
│-- voice_docker_requirements.txt # Dependencies
│-- setup_voice.py                # Setup script
│-- /config/                      # Configuration files
│-- /data/                        # Data storage
│   │-- /audio_cache/            # Cached audio files
│-- /logs/                        # Log files
│-- /models/                      # TTS models
```

## 📋 License

MIT License
