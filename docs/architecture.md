# AI Embodiment Project - Architecture Overview

## **1. Overview**
This document outlines the architecture for the AI Embodiment project, detailing the integration of real-time AI-driven PC automation, smart home control, and future AI embodiment phases.

## **2. High-Level System Architecture**
The system consists of multiple interdependent components structured into four key layers:

### **2.1 Core AI System**
- **Natural Language Processing (NLP)**: ChatGPT API for reasoning and conversation.
- **Local AI Execution**: Python-based agent for automation (AutoGPT, OpenDevin, or custom scripts).
- **Memory & Recall**: Vector database or RAG system for adaptive responses.

### **2.2 Input & Sensory Layer**
- **Voice Processing**: Whisper ASR for always-on listening.
- **Vision System**: OCR & object detection (Tesseract, OpenCV, PaddleOCR).
- **Screen Awareness**: Dynamic screen capture and context analysis.
- **Keyboard & Mouse Interactions**: Low-level OS hooks for real-time input tracking.

### **2.3 Automation & Execution Layer**
- **PC Control**: Home Assistant + Node-RED for command execution.
- **Smart Home Integration**: Google Home, Home Assistant for proactive automation.
- **Remote Execution API**: Webhook/API gateway for dynamic interactions.

### **2.4 AI Presence & Interaction Layer**
- **Voice Output**: Jenny TTS for realistic voice synthesis.
- **Visual Representation**: AI-generated images for dynamic UI.
- **Virtual Companion Mode**: Persistent AI avatar overlay on PC screen.

---

## **3. System Components & Modules**

### **3.1 Input & Sensory Modules**
#### **Voice Processing**
- **Module:** `hearing.py`
- **API:** `hearing_api.py`
- **Function:** Converts spoken commands into structured inputs.
- **Tech Stack:** Whisper ASR, PyAudio, WebSockets.

#### **Vision & Screen Awareness**
- **Module:** `vision.py`
- **API:** `vision_api.py`
- **Function:** Extracts text and UI elements from the screen.
- **Tech Stack:** OpenCV, Tesseract, PaddleOCR, PyGetWindow.

#### **Keyboard & Mouse Hooks**
- **Module:** `input_tracker.py`
- **Function:** Monitors and records keyboard/mouse inputs for AI interaction.
- **Tech Stack:** PyHook, Pynput.

---

### **3.2 Processing & AI Execution Modules**
#### **Core AI Engine**
- **Module:** `core.py`
- **Function:** Main reasoning engine for AI interaction.
- **Tech Stack:** Python, OpenAI API, LangChain, Local RAG.

#### **Memory & Recall System**
- **Module:** `memory.py`
- **Function:** Stores long-term interactions and contextual knowledge.
- **Tech Stack:** ChromaDB, SQLite, Postgres (future upgrade).

#### **PC Automation & Control**
- **Module:** `automation.py`
- **API:** `automation_api.py`
- **Function:** Controls PC tasks, applications, and settings.
- **Tech Stack:** Home Assistant, Node-RED, Python scripts.

#### **Smart Home Integration**
- **Module:** `smart_home.py`
- **Function:** Interfaces with Google Home and Home Assistant for proactive automation.
- **Tech Stack:** Google Home API, Home Assistant, MQTT.

---

### **3.3 Output & AI Presence Modules**
#### **Voice Output (TTS)**
- **Module:** `voice.py`
- **API:** `voice_api.py`
- **Function:** Generates spoken responses for user interaction.
- **Tech Stack:** Jenny TTS, Coqui TTS.

#### **Virtual AI Representation**
- **Module:** `visual_ai.py`
- **Function:** Displays dynamic AI-generated images based on mood and interactions.
- **Tech Stack:** Stable Diffusion, Electron.js, PyQt.

---

## **4. System APIs & Communication**
### **4.1 API Gateway**
- Acts as the main communication hub for AI services.
- Routes requests between voice, vision, automation, and memory systems.

#### **Key API Endpoints**
| Endpoint            | Functionality                          | Technology |
|--------------------|----------------------------------|------------|
| `/hearing`         | Processes voice input            | Flask, Whisper |
| `/vision`          | Extracts screen content         | OpenCV, Tesseract |
| `/memory`          | Stores & retrieves context      | ChromaDB, SQLite |
| `/automation`      | Executes PC control commands   | Home Assistant, Python |
| `/smart_home`      | Manages home automation        | Google Home API |
| `/voice`           | Generates AI speech            | Jenny TTS |
| `/visual_ai`       | Updates AI representation      | Stable Diffusion, Electron.js |

---

## **5. Infrastructure & Deployment**
### **5.1 Dockerized Services**
To maintain modularity and avoid dependency conflicts, services are containerized:
- **Hearing & TTS API** → Docker container (`hearing_api.py`, `voice_api.py`)
- **Vision Processing** → Runs natively for real-time screen access
- **Automation & PC Control** → Dockerized (`automation_api.py`)
- **Memory System** → Dockerized (ChromaDB, SQLite, PostgreSQL in future upgrade)

#### **Docker Compose Setup**
```yaml
version: '3.8'
services:
  hearing:
    build: ./hearing
    ports:
      - "5001:5001"
  vision:
    build: ./vision
    ports:
      - "5002:5002"
  automation:
    build: ./automation
    ports:
      - "5003:5003"
  memory:
    build: ./memory
    ports:
      - "5004:5004"
```

### **5.2 Startup Sequence**
1. **Spin up all Docker containers** (`hearing_api.py`, `voice_api.py`, `memory.py`)
2. **Initialize API Gateway** for communication between modules
3. **Launch vision module** to start screen monitoring
4. **Enable voice listening** for real-time interactions
5. **Start smart home automation services**

---

## **6. Future Enhancements & Phases**
### **Phase 2: Enhanced AI Presence & Virtual Representation**
- AI-generated overlay on PC screen for real-time interaction
- Real-time lip sync and facial animation using Live2D

### **Phase 3: AI-Augmented Interactions & Proactive Automation**
- Predictive automation: task handling before user requests
- VR/AR integration for full AI presence
- AI-guided automation workflows

### **Phase 4: Physical AI Embodiment**
- Design a humanoid robotic form
- Integrate haptic feedback & AI touch response
- Research Neuralink-style BCI for direct AI-human interaction

---

## **7. Conclusion**
This architecture ensures modularity, scalability, and flexibility in implementing AI-driven PC automation, smart home control, and future AI embodiment phases. The current focus is on real-time screen awareness, voice interaction, and automation, with a structured roadmap for expanding AI presence in virtual and physical spaces.

