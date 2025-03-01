# TODO
- integration
   - add LLM 
   - add standardized formats and framework for LLM input/output to communicate to core.py
   - LLM short term memory storage
   - training feedback loop
   - presence+task integration
- vision
   - implement yolov8 again
- presence
   - fix clickthrough, implement position saving
   - implement acutal animations
- improve automation
   - add click and drag fuctionality
   - add scroll functionality
   - add shortcuts for common PC actions
- general
   - auto download requirements
   - startup via .exe

# Sabrina AI - Enhanced Local AI Assistant

## 🚀 Project Overview

Sabrina AI is a privacy-focused, locally-running AI assistant that combines advanced voice interaction, screen awareness, automation, and smart home control into a comprehensive, intelligent system.

## 📂 Project Structure

```
/SABRINA-LOCAL-AI
│-- /core
│   │-- core.py  # Main AI Orchestration Engine
│   │-- memory.py  # Memory & recall system
│   │-- config.py  # Configuration settings
│-- /services  # AI Services & Modules
│   │-- /hearing  # Voice recognition
│   │   │-- hearing.py  # Whisper ASR-based recognition
│   │-- /vision  # AI-powered screen analysis
│   │   │-- constants.py
│   │   │-- vision_core.py  # Screen capture & tracking
│   │   │-- vision_ocr.py  # Text extraction
│   │   │-- vision_detection.py  # UI element detection
│   │-- /automation  # PC automation
│   │   │-- automation.py  # Keyboard & mouse control
│   │-- /smart_home  # Home automation
│   │   │-- smart_home.py  # Google Home & Home Assistant control
│   │-- /voice  # Voice synthesis
│   │   │-- voice.py  # TTS-based voice output
│-- /models  # AI models & training data
│   │-- /vosk-model  # Voice recognition models
│   │-- /yolov8  # Object detection models
│-- /scripts  # Utility scripts
│   │-- start_services.py  # Starts AI services
│   │-- setup_env.py  # Environment setup
│-- /config  # Configuration files
│   │-- settings.yaml  # System configuration
│   │-- api_keys.env  # External API credentials
│-- /data  # Storage for logs, databases
│   │-- logs/  # System logs
│   │-- db/  # Database files
│-- /tests  # Unit and integration tests
│-- README.md  # Project documentation
│-- requirements.txt  # Project dependencies
```

## ✨ Key Features

### 🗣️ Voice Interaction
- Wake word detection with Vosk
- Speech recognition using Whisper ASR
- Text-to-speech with Jenny TTS
- Configurable voice settings

### 👀 Vision & Screen Awareness
- Advanced screen capture
- Optical Character Recognition (OCR)
- UI element detection with YOLOv8
- Active window tracking and analysis

### 💻 PC Automation
- Cross-application keyboard/mouse control
- Task automation
- Workflow recording and playback
- Context-aware UI interaction

### 🏡 Smart Home Integration
- Google Home API integration
- Home Assistant support
- Device control and routine management
- Cross-platform smart home automation

### 🤖 AI Presence
- Animated avatar with dynamic expressions
- Context-aware interactions
- Mood-based visual feedback

## 🛠️ Technology Stack

### Core Technologies
- **Language**: Python 3.10+
- **Frameworks**: 
  - FastAPI
  - PyTorch
  - PyQt5
- **Machine Learning**:
  - Whisper
  - YOLOv8
  - Vosk

### Speech Processing
- **ASR**: Whisper
- **TTS**: Jenny TTS
- **Wake Word**: Vosk

### Computer Vision
- **Image Processing**: OpenCV
- **Object Detection**: YOLOv8
- **OCR**: Tesseract, PaddleOCR

### Automation
- **Input Control**: PyAutoGUI
- **Window Management**: PyGetWindow

## 🔧 Installation & Setup

### Prerequisites
- Python 3.10+
- Docker (recommended)
- CUDA-capable GPU (optional, for accelerated processing)

### Quick Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/sabrina-ai.git
cd sabrina-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run setup script
python scripts/setup_env.py
```

### Running Sabrina AI
```bash
# Start voice service
python services/voice/voice_api.py

# Run main system
python scripts/start_sabrina.py
```

## 📋 Command Line Options
- `--config`: Specify configuration file
- `--debug`: Enable debug mode
- `--no-voice`: Disable voice output
- `--no-vision`: Disable vision processing

## 🤝 Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m 'Add your feature'`
4. Push branch: `git push origin feature/your-feature`
5. Submit a pull request

## 🔬 Current Development Focus
- Improved conversational memory
- Enhanced AI reasoning
- VR/AR integration
- Continuous learning mechanisms

## 📄 License
MIT License

## 🌟 Project Vision
Sabrina AI aims to create a fully embodied, privacy-first AI assistant that seamlessly integrates with your digital and physical environment.