# Sabrina Voice API Service

## 🎙️ Overview
A robust, containerized voice synthesis service for Sabrina AI, providing high-quality text-to-speech capabilities with advanced configuration and integration.

## 📂 Service Structure
```
/services/voice/
│-- voice_api.py        # Main FastAPI service
│-- voice_api_client.py # Client for voice interactions
│-- Dockerfile          # Docker container configuration
│-- docker-compose.yml  # Service orchestration
│-- voice_settings.json # Default voice configuration
│-- models/             # Voice model storage
│   │-- piper/          # Piper TTS models
│-- logs/               # Service log files
│-- tests/              # Voice service tests
```

## ✨ Features

### 🔊 Voice Synthesis
- Multiple TTS engines support
- Configurable voice parameters
- High-quality speech generation
- Multi-voice selection

### 🛠️ Technical Capabilities
- REST API for voice interactions
- Docker-based deployment
- Piper TTS integration
- Extensive voice model support

### 🔧 Configuration Options
```json
{
  "speed": 1.0,
  "pitch": 1.0,
  "emotion": "normal",
  "volume": 0.8,
  "voice": "en_US-amy-medium"
}
```

## 🚀 Installation & Setup

### Prerequisites
- Docker
- Docker Compose
- Python 3.10+

### Docker Deployment
```bash
# Build and start the service
docker-compose build
docker-compose up -d
```

### Manual Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start the voice API
python voice_api.py
```

## 📡 API Endpoints

### Status Check
```bash
GET /status
```
- Returns service health and configuration

### List Voices
```bash
GET /voices
```
- Retrieves available voice models

### Generate Speech
```bash
GET /speak?text=Hello%20World&voice=en_US-amy-medium&speed=1.0
```
- Synthesizes speech with optional parameters

### Update Settings
```bash
POST /update_settings
{
  "speed": 1.2,
  "pitch": 1.0,
  "voice": "en_US-jenny-medium"
}
```
- Dynamically update voice synthesis settings

## 🎙️ Available Voices
- `en_US-amy-medium`
- `en_US-kathleen-medium`
- `en_US-jenny-medium`

## 🐞 Troubleshooting
- Check Docker logs: `docker-compose logs voice-api`
- Verify port mapping
- Ensure audio devices are configured

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch
3. Implement changes
4. Submit a pull request

## 📋 Testing
```bash
# Run voice module tests
python -m pytest tests/voice_module_test.py

# Debug voice models
python services/voice/voice_debug.py
```

## 🔬 Future Improvements
- Multi-language support
- Enhanced emotion detection
- Advanced voice cloning
- Improved audio processing

## 📄 License
MIT License
