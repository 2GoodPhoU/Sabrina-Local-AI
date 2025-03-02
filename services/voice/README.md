# Sabrina AI Voice Module

## 🎙️ Overview
The Sabrina AI Voice Module provides advanced Text-to-Speech (TTS) capabilities through a comprehensive API for voice generation, settings management, and speech processing. This module enables natural, expressive voice interactions for the Sabrina AI Assistant.

## 🌟 Key Features
- 🔊 High-quality TTS using Coqui TTS (Jenny model)
- 🎛️ Configurable voice settings (speed, pitch, volume, emotion)
- 🚀 FastAPI-based microservice architecture
- 💾 Intelligent audio caching for efficiency
- 🔒 Secure settings management with API key authentication
- 📦 Containerized deployment with Docker
- 🔄 Event-driven integration with Sabrina AI Core

## 🛠️ Core Components

### 1. Voice API (`voice_api.py`)
A FastAPI-based service that provides:
- REST endpoints for TTS generation
- Voice settings management
- Audio caching for performance
- Secure API access

### 2. Voice API Client (`voice_api_client.py`)
A Python client library that:
- Handles communication with the Voice API
- Provides a simple interface for other Sabrina components
- Offers basic error handling and reconnection strategies
- Includes event bus integration for the enhanced client version

### 3. Enhanced Voice Client (`enhanced_voice_client.py`)
An advanced client with additional features:
- Emotional voice synthesis based on content sentiment
- Voice activity tracking and statistics
- Text preprocessing and optimization
- Speech queue management
- Voice profile customization

### 4. Testing and Deployment
- Comprehensive test script (`voice_module_test.py`)
- Docker configuration for containerized deployment
- Setup guide for configuration and usage

## 📦 Installation

### Prerequisites
- Python 3.10+
- TTS (Coqui TTS library)
- FFmpeg
- Docker (optional, for containerized deployment)

### Quick Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/sabrina-ai.git
cd sabrina-ai/services/voice

# Install dependencies
pip install -r voice_docker_requirements.txt

# Start the Voice API
python voice_api.py
```

### Docker Deployment
```bash
# Build and start the container
docker-compose up -d
```

## 🔧 Voice Configuration
The voice service supports the following configurable parameters:

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `voice` | TTS voice model | en_US-jenny-medium | Available voices |
| `speed` | Speech speed | 1.0 | 0.5-2.0 |
| `pitch` | Voice pitch | 1.0 | 0.5-2.0 |
| `volume` | Audio volume | 0.8 | 0.0-1.0 |
| `emotion` | Emotional style | neutral | neutral, happy, sad |
| `cache_enabled` | Enable audio caching | true | true, false |

## 🔌 API Endpoints

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

### Get Voices
```
GET /voices
X-API-Key: your-api-key
```
Returns a list of available voice models.

### Get Settings
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
Updates the voice settings.

## 📝 Usage Examples

### Basic Usage
```python
from services.voice.voice_api_client import VoiceAPIClient

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

### Using the Enhanced Client
```python
from services.voice.enhanced_voice_client import EnhancedVoiceClient
from utilities.event_system import EventBus

# Create event bus
event_bus = EventBus()
event_bus.start()

# Create enhanced client
client = EnhancedVoiceClient(
    api_url="http://localhost:8100",
    event_bus=event_bus,
    voice_profile="casual",
    auto_punctuate=True
)

# Queue multiple speech requests
client.speak("This will be said first.")
client.speak("This will be said second.")

# Interrupt with important message
client.interrupt("This is an important message!")

# Use different voice profiles
client.set_voice_profile("formal")
client.speak("I am now speaking in a more formal tone.")

# Clean up
event_bus.stop()
```

## 🚀 Docker Deployment
The voice module comes with Docker support for easy deployment:

- `voice.Dockerfile`: Container definition for the Voice API
- `docker-compose.yml`: Orchestration for the voice service
- `voice_docker_requirements.txt`: Dependencies for the container

Environment variables for Docker:
- `VOICE_API_PORT`: Port for the Voice API (default: 8100)
- `VOICE_API_KEY`: API key for securing the API
- `DEBUG`: Enable debug mode (true/false)

## 🔒 Security Considerations
- API authentication via API key
- Docker network isolation for added security
- Validation of all input parameters
- Error handling to prevent information leakage

## 📋 Project Structure
```
/services/voice/
│-- voice_api.py                  # FastAPI-based Voice API server
│-- voice_api_client.py           # API client for voice interactions
│-- enhanced_voice_client.py      # Advanced voice client with additional features
│-- voice_module_test.py          # Test script for the voice service
│-- voice.Dockerfile              # Docker container setup
│-- docker-compose.yml            # Container orchestration
│-- voice_docker_requirements.txt # Dependencies for Docker
│-- setup_guide.md                # Installation and configuration guide
│-- README.md                     # Module documentation
```

## 🧪 Testing
The voice module includes a comprehensive test script that verifies all functionality:

```bash
# Run all tests
python voice_module_test.py --test all

# Test specific functionality
python voice_module_test.py --test speak
python voice_module_test.py --test settings
```

## 🛣️ Roadmap
- [ ] Multi-language support
- [ ] Voice cloning for personalized voices
- [ ] SSML (Speech Synthesis Markup Language) support
- [ ] Real-time voice parameter adjustment
- [ ] Integration with additional TTS backends

## 🤝 Integration with Sabrina AI Core
The voice module integrates with the Sabrina AI Core through:

1. The Enhanced Voice Client with event bus integration
2. Standardized voice status events
3. Speech queue management for coordinated voice output
4. Emotional voice adaptation based on context

## 💡 Troubleshooting
See the `setup_guide.md` file for detailed troubleshooting steps and solutions to common issues.

## 📄 License
MIT License

## 🌐 Contact
Sabrina AI Development Team
