# Sabrina AI - Local AI Assistant

## **What is Sabrina AI?**
Sabrina AI is a **local AI-powered personal assistant** that integrates **voice interaction, screen awareness, and PC automation** to assist in daily tasks. Unlike cloud-based AI, Sabrina runs **entirely on your machine**, ensuring **privacy and full control** over interactions.

### **Key Features:**
- **Real-time Speech Recognition** (via Whisper ASR)
- **Text-to-Speech Synthesis** (via Jenny TTS API)
- **Screen OCR & Object Detection** (via OpenCV, YOLO, Tesseract)
- **PC Automation** (via PyAutoGUI for keyboard & mouse control)
- **Voice Command Execution** (hands-free interaction)
- **Smart Home Integration** (Google Home & Home Assistant)

---

## **How to Set Up & Use Sabrina AI**

### **1️⃣ Install Python 3.10+**
Ensure you have Python installed:
```bash
python --version  # Ensure version 3.10 or higher
```
If not installed, download it from [Python’s official site](https://www.python.org/downloads/).

### **2️⃣ Set Up a Python Virtual Environment**
Create and activate a virtual environment to avoid dependency conflicts:
```bash
# Create virtual environment
python -m venv sabrina_env

# Activate the environment
# Windows:
sabrina_env\Scripts\activate
# Linux/macOS:
source sabrina_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### **3️⃣ Start the AI Components**
To launch **Sabrina AI**, follow these steps:

#### **Step 1: Spin Up Required Docker Containers**
```bash
# Ensure Docker is running
docker --version  # Check if Docker is installed

# Build and start voice & vision services
cd docker
docker-compose up -d
```

#### **Step 2: Run Sabrina AI Core**
```bash
cd core
python core.py
```

### **4️⃣ Interacting with Sabrina AI**
Once running, Sabrina listens for voice commands, analyzes your screen, and performs automation tasks.

#### **Basic Commands:**
| Command        | Functionality |
|---------------|--------------|
| `!say Hello`  | Speak aloud using TTS |
| `!click`      | Click at the cursor position |
| `!move X Y`   | Move cursor to (X, Y) |
| `!type Hello` | Type ‘Hello’ |
| `!exit`       | Shut down AI assistant |

---

## **Project Structure**
```
/ai-embodiment
│-- /api
│   │-- voice_api.py
│-- /core
│   │-- core.py
│   │-- memory.py
│   │-- config.py
│-- /services
│   │-- /hearing
│   │   │-- hearing.py
│   │-- /vision
│   │   │-- vision.py
│   │-- /automation
│   │   │-- automation.py
│   │-- /smart_home
│   │   │-- smart_home.py
│   │-- /voice
│   │   │-- voice.py
│-- /models
│   │-- nlp_model.py
│   │-- vision_model.py
│   │-- automation_model.py
│   │-- memory_model.py
│-- /scripts
│   │-- start_services.py
│   │-- setup_env.py
│   │-- deploy_containers.py
│-- /config
│   │-- settings.yaml
│   │-- api_keys.env
│-- /data
│   │-- logs/
│   │-- db/
│   │-- cache/
│-- /tests
│   │-- test_hearing.py
│   │-- test_vision.py
│   │-- test_automation.py
│   │-- test_memory.py
│-- /docs
│   │-- architecture.md
│   │-- system_overview.md
│-- /docker
│   │-- /voice
│   │   │-- Dockerfile
│   │   │-- docker-compose.yml
│   │-- /smart_home
│   │   │-- Dockerfile
│   │   │-- docker-compose.yml
│-- README.md
│-- requirements.txt
```

### **5️⃣ Stopping Sabrina AI**
To shut down Sabrina AI and its services:
```bash
# Stop AI Core
Ctrl + C  # In terminal running core.py

# Stop and remove all running containers
cd docker
docker-compose down
```

### **6️⃣ Additional Notes & Future Enhancements**
Planned improvements include:
- **Advanced Conversational Memory**
- **Real-time Event-Driven Automations**
- **3D Virtual AI Avatar Integration**

For any issues, refer to the [architecture documentation](docs/architecture.md) or open an issue in the repository.
