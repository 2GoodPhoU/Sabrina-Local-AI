# Sabrina-Local-AI

AI Assistant

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

SABRINA-LOCAL-AI/
│── scripts/ 
│   │── __init__.py          # Make this a Python package
│   │── core.py              # Core AI logic (merged sabrina_local_ai.py)
│   │── vision.py            # Handles screen monitoring & OCR
│   │── voice.py             # Manages TTS & ASR
│   │── actions.py           # PC automation
│   │── rtod.py              # (Need to define role)
│   └── config.py            # Stores AI settings & system paths
│── data/
│   │── conversation_history.json
│   │── default_memory.json
│   │── voice_settings.json
│── startup.sh               # Auto-start script
│── requirements.txt         # All dependencies
│── README.md                # Project Documentation
└── main.py                  # Entry point for running Sabrina AI

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