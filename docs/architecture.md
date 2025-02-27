# Sabrina AI Architecture Overview

## Introduction

Sabrina AI is designed as a locally-running AI assistant with comprehensive capabilities spanning voice interaction, screen awareness, automation, and smart home control. This document provides an overview of Sabrina's architectural design and how its components work together.

## Core Architecture

At the heart of Sabrina is a modular, event-driven architecture that focuses on:

1. **Stability**: Comprehensive error handling and recovery mechanisms
2. **Modularity**: Cleanly separated components that can be developed and improved independently
3. **Integration**: Consistent interfaces and communication patterns
4. **Extensibility**: Easy addition of new features and capabilities

The system is built around these core principles to ensure it remains maintainable and can evolve over time.

## Key Components

### 1. Core System (`core/sabrina_core.py`)

The central orchestration engine that:
- Initializes and manages all components
- Processes user commands
- Coordinates activities between modules
- Maintains system state
- Handles startup and shutdown

The Core System implements the main interaction loop and acts as the central integration point.

### 2. Utilities

#### Configuration Manager (`utilities/config_manager.py`)
- Provides centralized configuration handling
- Supports multiple file formats (YAML, JSON)
- Enables environment variable overrides
- Offers configuration validation and defaults
- Supports hot-reloading of settings

#### Error Handler (`utilities/error_handler.py`)
- Provides structured error logging and tracking
- Categorizes errors by severity and type
- Enables recovery mechanisms
- Generates error reports and statistics
- Offers contextual error information

#### Event System (`utilities/event_system.py`)
- Implements asynchronous event-based communication
- Supports priority-based event processing
- Provides event filtering by type and source
- Enables loose coupling between components
- Maintains event history for debugging

### 3. Service Modules

#### Voice Processing (`services/voice/`)
- `voice_api.py`: FastAPI-based TTS service
- `voice_api_client.py`: Client for accessing voice services
- Handles text-to-speech synthesis
- Manages voice settings (speed, pitch, emotion)
- Provides audio playback

#### Vision System (`services/vision/`)
- `vision_core.py`: Main vision system controller
- `vision_ocr.py`: Optical character recognition
- Performs screen capture and analysis
- Extracts text from images using OCR
- Identifies UI elements (in advanced versions)
- Tracks active window content

#### Hearing Module (`services/hearing/`)
- `hearing.py`: Voice recognition and command detection
- Listens for wake word activation
- Converts speech to text
- Handles noise filtering
- Supports hotkey activation

#### Automation System (`services/automation/`)
- `automation.py`: PC control and automation
- Controls mouse and keyboard
- Performs UI interaction
- Executes automation sequences
- Provides safety mechanisms

#### Smart Home Integration (`services/smart_home/`)
- `smart_home.py`: Home automation control
- Connects to Home Assistant
- Controls smart home devices
- Manages automation routines
- Provides sensor data access

#### Presence System (`services/presence/`) (Planned)
- Visual representation of Sabrina
- Animated character with expressions
- Status and activity indicators
- User interaction controls

### 4. Support Scripts

- `scripts/start_sabrina.py`: Main entry point
- `scripts/setup_env.py`: Environment setup
- `scripts/test_integration.py`: Integration testing
- Various utility and maintenance scripts

## Communication Flow

Sabrina uses an event-driven architecture for component communication:

1. **Events** are the primary means of inter-component communication
2. Components publish events and subscribe to event types they're interested in
3. The Event Bus routes events to appropriate handlers based on type and priority
4. Components respond to events they're registered to handle

![Event Flow Diagram](docs/event_flow.png)

### Example Event Flow

1. User speaks a command ("Capture the screen")
2. Hearing module converts speech to text
3. Hearing module publishes a `USER_INPUT` event
4. Core system receives the event and processes the command
5. Core system publishes a `VISION` event with "capture" command
6. Vision module receives the event and captures the screen
7. Vision module publishes a `SCREEN_UPDATE` event with OCR results
8. Core system processes the results and publishes a `VOICE` event
9. Voice module speaks the response to the user

This decoupled approach allows components to evolve independently while maintaining system cohesion.

## Data Flow

### Configuration Data
- Loaded at startup from `config/settings.yaml`
- Accessed by all components through ConfigManager
- Can be updated during runtime

### User Input
- Comes from voice recognition or direct text input
- Converted to commands or queries
- Processed by Core System

### System State
- Maintained in Core System
- Includes current context, active components, etc.
- Components can query state as needed

### Results and Outputs
- Voice responses through TTS
- Visual feedback (in future versions)
- Automation actions
- Smart home controls

## Deployment Options

### Local Development
- Run directly on the local machine
- Components started individually or via startup script
- Ideal for development and testing

### Containerized Deployment
- Docker containers for each major component
- Docker Compose for orchestration
- Enables consistent deployment across environments

### Hybrid Approach
- Core system and essential components run locally
- Resource-intensive components run in containers
- Balances performance and isolation

## Extension Points

The architecture is designed with clear extension points:

1. **Plugin System** (Planned): Add new capabilities without modifying core code
2. **Service Interfaces**: Replace or enhance individual services
3. **Event Handlers**: Add new event types and handlers
4. **Configuration Options**: Customize behavior through configuration
5. **Voice and Vision Models**: Replace with custom or improved models

## Technical Stack

- **Python 3.10+**: Core programming language
- **FastAPI**: API services
- **PyQt5**: GUI components (for presence system)
- **PyTorch**: Machine learning framework
- **OpenCV**: Computer vision
- **Tesseract OCR**: Text extraction
- **Vosk/Whisper**: Speech recognition
- **TTS (Jenny/Coqui)**: Text-to-speech
- **Docker**: Containerization
- **YAML/JSON**: Configuration

## Development Workflow

1. **Component Development**: Enhance individual components
2. **Integration Testing**: Verify component interaction
3. **System Testing**: Test end-to-end functionality
4. **Performance Optimization**: Ensure efficient resource usage
5. **Deployment**: Package for distribution

## Future Directions

The architecture is designed to support future enhancements:

1. **AI Integration**: Local language models for advanced reasoning
2. **Extended Context Awareness**: Better understanding of user activity
3. **Advanced Automation**: Complex task sequences and workflows
4. **Physical Integration**: Control of physical devices and robots
5. **Enhanced Presence**: More sophisticated visual and auditory presence

## Conclusion

Sabrina AI's architecture provides a solid foundation for a privacy-focused, locally-running AI assistant. Its modular, event-driven design enables continuous improvement and extension while maintaining system integrity and reliability.