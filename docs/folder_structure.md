# AI Embodiment Project - Folder Structure

## **Root Directory**
```
/SABRINA-LOCAL-AI
│-- /core
│   │-- core.py  # Main AI Orchestration Engine
│   │-- memory.py  # Memory & recall system for AI interactions
│   │-- config.py  # Configuration settings
│-- /services  # AI Services & Modules
│   │-- /hearing  # Voice recognition & processing
│   │   │-- hearing.py  # Whisper ASR-based voice recognition
│   │-- /vision  # AI-powered screen analysis & object detection
│   │-- /vision  # AI-powered screen analysis & object detection
│   │   │-- vision_core.py  # Handles screen capture & active window tracking
│   │   │-- vision_ocr.py  # Extracts text using OCR (Tesseract/PaddleOCR)
│   │   │-- vision_detection.py  # YOLO-based UI element detection
│   │-- /automation  # PC automation & input simulation
│   │   │-- automation.py  # Controls keyboard & mouse automation
│   │-- /smart_home  # Home automation integration
│   │   │-- smart_home.py  # Controls Google Home & Home Assistant
│   │   │-- Dockerfile  # Containerized smart home service
│   │   │-- docker-compose.yml  # Smart home automation setup
│   │-- /voice  # AI voice synthesis & response
│   │   │-- voice.py  # Jenny TTS-based voice output
│   │   │-- Dockerfile  # Containerized voice service
│   │   │-- docker-compose.yml  # Voice module container configuration
│   │   │-- voice_api.py  # FastAPI service for text-to-speech
│-- /models  # AI models & training data
│   │-- /vosk-model  # Pretrained models for voice recognition
│   │-- /yolov8  # YOLO object detection models
│   │-- /sabrina  # Future AI embodiment model
│-- /scripts  # Utility scripts for setup & deployment
│   │-- start_services.py  # Starts all AI services
│   │-- setup_env.py  # Environment setup script
│   │-- deploy_containers.py  # Automates container deployment
│-- /config  # Configuration files & environment settings
│   │-- settings.yaml  # AI system configuration
│   │-- api_keys.env  # Stores API keys for external integrations
│-- /data  # Storage for logs, databases, and cache
│   │-- logs/  # System logs
│   │-- db/  # Database files
│   │-- cache/  # Temporary cache storage
│-- /tests  # Unit tests for various modules
│   │-- test_hearing.py  # Tests for hearing module
│   │-- test_vision.py  # Tests for vision module
│   │-- test_automation.py  # Tests for automation module
│   │-- test_memory.py  # Tests for memory system
│-- /docs  # Documentation for architecture & system overview
│   │-- architecture.md  # AI embodiment architecture breakdown
│   │-- folder_structure.md  # This document (folder structure reference)
│-- README.md  # Project overview & setup instructions
│-- requirements.txt  # Required dependencies & libraries
```