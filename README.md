# Sabrina-Local-AI

AI Assistant

install:
https://www.freedesktop.org/wiki/Software/PulseAudio/Ports/Windows/Support/

How to use:

python -m venv .venv
.venv\Scripts\Activate
pip install -r requirements.txt
cd into scripts
python sabrina_local_ai.py



install Python 3.10
1️⃣ Set Up a Python Virtual Environment
Before working on the repo, let’s set up a clean Python environment to avoid dependency conflicts.

Commands to Set Up a Virtual Environment

# Create virtual environment
python -m venv sabrina_env

# Activate the environment
# Windows:
sabrina_env\Scripts\activate

# Linux/macOS:
source sabrina_env/bin/activate

# Install dependencies
pip install -r requirements.txt

This ensures your Python scripts run in an isolated environment.


2️⃣ Review & Refactor Existing Code
We’ll go through each script and reorganize them into a structured package.

New Project Structure (Planned)

Sabrina AI
│── configs/                 # 🛠️ Configuration files
│   ├── system.yaml          # Global system settings
│   ├── docker-compose.yml   # Docker container definitions
│   ├── api_endpoints.json   # API route definitions
│   ├── dependencies.txt     # Package dependencies (pip, apt, etc.)
│
│── scripts/                 # 🎭 Core scripts (high-speed execution)
│   ├── pc_automation.py     # Controls keyboard/mouse inputs
│   ├── shared_memory.py     # Manages ZeroMQ/Redis shared memory
│   ├── vision_processing.py # OCR & object recognition (PaddleOCR/OpenCV)
│   ├── hearing.py       # Whisper ASR for speech-to-text
│   ├── voice.py      # Jenny TTS for speech synthesis
│
│── api/                     # 🌐 API services (FastAPI/Flask)
│   ├── main.py              # API gateway (manages interactions)
│   ├── vision_api.py        # Handles vision requests
│   ├── voice_api.py         # Handles voice requests
│   ├── automation_api.py    # Handles PC control & automation
│
│── docker/                  # 🐳 Docker files for modular services
│   ├── vision.Dockerfile    # OCR & Object Detection (PaddleOCR)
│   ├── voice.Dockerfile     # Jenny TTS
│   ├── hearing.Dockerfile   # Whisper ASR
│   ├── home_assistant.Dockerfile # Smart home control
│   ├── base.Dockerfile      # Base image (common dependencies)
│
│── containers/              # 📦 Containerized runtime storage (volumes, logs)
│   ├── vision/              # Vision model output/logs
│   ├── voice/               # Voice processing logs
│   ├── hearing/             # Hearing processing logs
│   ├── automation/          # PC control logs
│
│── startup/                 # 🚀 Startup & orchestration
│   ├── start.sh             # Main script to spin up everything
│   ├── stop.sh              # Clean shutdown script
│
│── tests/                   # 🧪 Unit & integration tests
│   ├── test_vision.py       # Tests for vision processing
│   ├── test_voice.py        # Tests for AI voice processing
│   ├── test_hearing.py      # Tests for user voice processing
│   ├── test_automation.py   # Tests for PC automation
│
│── docs/                    # 📖 Documentation & research
│   ├── architecture.md      # AI embodiment system architecture
│   ├── api_reference.md     # API endpoints & usage
│   ├── dependencies.md      # Details of all dependencies
│
└── README.md                # 📜 Overview of the project


3️⃣ Integrate Screen & Application Awareness
We need real-time screen visibility so Sabrina can recognize objects, text, and applications.
This will be handled via OCR & screen monitoring.

Planned Libraries & Features
Tesseract OCR → Extract on-screen text.
PyGetWindow → Detect currently focused window.
MSS (Screen Capture) → Capture the screen in real time.

4️⃣ Enable Seamless Window Switching
Sabrina needs to focus on different applications dynamically.

Solution
PyGetWindow → Get & switch active windows.
PyAutoGUI → Automate window switching.

5️⃣ Implement PC Automation & Command Execution
Sabrina should control the PC & execute commands dynamically.

Planned Libraries
PyAutoGUI → Mouse & keyboard automation.
Subprocess → Execute system commands.

6️⃣ Voice-Guided Execution
Sabrina should provide real-time verbal feedback.

Planned Features
Jenny TTS → Speak responses.
Whisper ASR → Process voice commands.











Manually Start Node-RED First (Without PM2)

1️⃣ Start Node-RED normally:
powershell
"node-red"


2️⃣ Try accessing it in your browser:
http://localhost:1880


🔥 Proposed Design for AI Vision & Automation
🟢 Core Technologies
Function	Tool/Library
Screen Capture (Full or App-Specific)	mss, pygetwindow, pywinctl
OCR (Text Recognition)	pytesseract
Object Recognition (Non-Text Elements)	YOLOv8, OpenCV
PC Automation (Mouse, Keyboard)	pyautogui, keyboard
Voice Interaction	Jenny TTS, pyttsx3
Voice Commands (Listening to You)	Whisper ASR
✅ Phase 1: Set Up Full-Screen & App-Specific Vision
We need Sabrina to see both the entire screen and specific applications. Instead of scanning everything, we will:

Detect active applications & windows
Capture only the relevant region

✅ Phase 2: Object Detection Instead of Just Text
Since you want Sabrina to see objects, we’ll integrate YOLOv8 (for object recognition) to detect UI elements, buttons, and on-screen objects.

✅ Phase 3: Automating PC Actions
Now that Sabrina can see the screen, let’s allow her to perform actions like: 1️⃣ Clicking buttons on screen
2️⃣ Pressing keys when events are detected
3️⃣ Executing scripts or programs based on vision

✅ Phase 4: Voice Responses While Acting
Sabrina should talk while performing actions using Jenny TTS.