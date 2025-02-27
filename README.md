# Sabrina AI - Enhanced Local AI Assistant

An integrated AI assistant that combines voice interaction, screen awareness, and PC automation into a cohesive, privacy-focused local AI system.

## 🚀 New Architecture Overview

This repository contains the enhanced version of Sabrina AI with a new, more robust architecture featuring:

- **Centralized Error Handling**: Comprehensive error tracking, logging, and recovery
- **Event-Based Communication**: Cross-module messaging using a central event bus
- **Unified Configuration**: Centralized configuration with validation and hot-reloading
- **Modular Component Design**: Clean separation between core functionalities
- **Docker Integration**: Containerized services for easier deployment
- **Improved Voice Integration**: Robust TTS system with error handling and retries

## 📋 Prerequisites

- **Python 3.10+**
- **Docker** and **Docker Compose** (for containerized deployment)
- **FFmpeg** (for audio processing)
- **Tesseract OCR** (for text recognition)
- **CUDA-capable GPU** (recommended for object detection)

## 🔧 Installation & Setup

### Option 1: Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/sabrina-ai.git
   cd sabrina-ai
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create required directories:**
   ```bash
   mkdir -p logs data config models
   ```

5. **Run the setup script:**
   ```bash
   python scripts/setup_env.py
   ```

### Option 2: Docker Deployment

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/sabrina-ai.git
   cd sabrina-ai
   ```

2. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

## 🚀 Running Sabrina AI

### Running the Core System (Local Development)

```bash
# Start the Voice API service
cd services/voice
python voice_api.py &

# Run the main Sabrina AI system
python scripts/start_sabrina.py
```

### Command Line Options

```
usage: start_sabrina.py [-h] [--config CONFIG] [--debug] [--no-voice] [--no-vision]

Sabrina AI - Local AI Assistant

options:
  -h, --help       show this help message and exit
  --config CONFIG  Path to configuration file
  --debug          Enable debug mode
  --no-voice       Disable voice output
  --no-vision      Disable vision processing
```

## 📂 Project Structure

```
/sabrina-ai
│-- /core
│   │-- sabrina_core.py  # Enhanced core engine
│-- /utilities
│   │-- config_manager.py  # Unified configuration
│   │-- error_handler.py   # Centralized error handling
│   │-- event_system.py    # Event-based communication
│-- /services
│   │-- /hearing
│   │-- /vision
│   │-- /automation
│   │-- /voice
│   │   │-- voice_api.py
│   │   │-- voice_api_client.py
│   │-- /smart_home
│-- /scripts
│   │-- start_sabrina.py  # Main startup script
│   │-- setup_env.py      # Environment setup
│-- /config
│   │-- settings.yaml     # Main configuration
│-- /data                 # Data storage
│-- /logs                 # System logs
│-- /models               # AI models
│-- /docs                 # Documentation
│-- docker-compose.yml    # Docker Compose setup
│-- Dockerfile            # Docker configuration
│-- requirements.txt      # Project dependencies
│-- README.md             # This file
```

## 🧩 Core Components

- **SabrinaCore**: Central orchestration engine for the AI system
- **ConfigManager**: Unified configuration handling
- **ErrorHandler**: Comprehensive error handling system
- **EventBus**: Event-based communication between components
- **VoiceAPIClient**: Client for the TTS Voice API service
- **VisionCore**: Screen analysis and OCR functionality
- **Hearing**: Voice recognition and command processing
- **Actions**: PC automation and control

## 🛠️ Configuration

The main configuration file is located at `config/settings.yaml` and follows this structure:

```yaml
core:
  debug_mode: false
  log_level: INFO

voice:
  api_url: http://localhost:8100
  volume: 0.8
  speed: 1.0
  pitch: 1.0
  emotion: normal

vision:
  capture_method: auto
  use_ocr: true
  use_object_detection: true
  max_images: 5

# Additional sections...
```

## 🔄 Event System

Components communicate through a centralized event system. Example:

```python
# Register an event handler
def handle_voice_event(event):
    print(f"Voice event received: {event.data.get('text')}")

handler_id = event_bus.register_handler(
    event_bus.create_event_handler(
        EventType.VOICE,
        handle_voice_event
    )
)

# Post an event
event_bus.post_event(
    Event(
        event_type=EventType.VOICE,
        data={"text": "Hello, world!"},
        source="example"
    )
)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -am 'Add your feature'`
4. Push the branch: `git push origin feature/your-feature`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.