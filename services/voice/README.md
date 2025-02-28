# Sabrina Voice API Docker Setup

This directory contains a Docker-based voice synthesis service for Sabrina AI.

## Features

- REST API for text-to-speech conversion
- Multiple TTS engines support (Edge TTS, Coqui TTS, pyttsx3)
- Support for various emotions and voice styles
- Dockerized for consistent deployment
- Auto-start capability in the client

## Setup Instructions

### Prerequisites

- Docker and Docker Compose installed
- Python 3.7+ (for client)
- Network connectivity for Docker container

### Files

The Docker setup consists of the following files:

1. `Dockerfile` - Container definition
2. `docker-compose.yml` - Service configuration
3. `voice_docker_requirements.txt` - Python dependencies
4. `voice_api.py` - The Voice API service
5. `voice_settings.json` - Default voice settings

### Installation

1. Place all files in the `services/voice` directory
2. Build and start the Docker container:

```bash
cd services/voice
docker-compose up -d
```

3. Verify the service is running:

```bash
curl http://localhost:8100/status
```

## Using the Voice API

### Direct API Calls

```bash
# Basic speech synthesis
curl "http://localhost:8100/speak?text=Hello%20World"

# With custom parameters
curl "http://localhost:8100/speak?text=Hello%20World&speed=1.2&emotion=happy"
```

### Using the Python Client

```python
from services.voice.voice_api_client import VoiceAPIClient

# Create client (will auto-start Docker container if needed)
client = VoiceAPIClient()

# Speak text
client.speak("Hello, this is a test")

# Change voice settings
client.set_speed(1.5)
client.set_emotion("happy")
client.speak("This is faster and happier speech")
```

## Voice Settings

The following settings can be configured:

- `speed` (0.5-2.0): Speech rate
- `pitch` (0.5-2.0): Voice pitch
- `emotion` ("normal", "happy", "sad", "angry", "excited", "calm"): Emotional style
- `voice`: Voice model/name (e.g., "en-US-JennyNeural" for Edge TTS)
- `volume` (0.0-1.0): Audio volume

## Troubleshooting

### Container Won't Start

Check Docker logs:
```bash
docker-compose logs voice-api
```

### API Not Responding

Ensure ports are properly mapped:
```bash
docker-compose ps
```

### Audio Not Playing

Ensure audio devices are properly mapped in docker-compose.yml:
```yaml
devices:
  - /dev/snd:/dev/snd
```

On Windows, you may need to install additional audio drivers for Docker.

### Client Can't Connect to Container

Make sure port 8100 is exposed and not blocked by a firewall:
```bash
docker-compose ps
netstat -tuln | grep 8100
```

## Advanced Configuration

### Changing the Default Voice

Edit `voice_settings.json`:
```json
{
  "speed": 1.0,
  "pitch": 1.0,
  "emotion": "normal",
  "volume": 0.8,
  "voice": "en-US-JennyNeural"
}
```

### Available Voices (Edge TTS)

Some popular Edge TTS voices:
- `en-US-JennyNeural` - Female American English
- `en-US-GuyNeural` - Male American English
- `en-GB-SoniaNeural` - Female British English
- `en-AU-NatashaNeural` - Female Australian English

### Custom TTS Engine Selection

You can modify the `tts_type` variable in `voice_api.py` to prefer a specific TTS engine:
```python
tts_type = "edge-tts"  # Options: "edge-tts", "coqui-tts", "pyttsx3"
```

## Updating the Service

To update the service with new code:

1. Copy the updated files to the service directory
2. Rebuild and restart the container:

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## License

This Voice API service is part of the Sabrina AI project and is available under the same license as the main project.