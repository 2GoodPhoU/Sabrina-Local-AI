# AI Embodiment Project - Folder Structure

## **Root Directory**
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

## **Folder Structure Breakdown**
### **1. `/api/` - API Layer**
Houses only the voice API endpoint, as other services are running natively.

### **2. `/core/` - Main AI Logic**
Contains the central AI processing logic, including conversation, memory, and configuration files.

### **3. `/services/` - Functional AI Modules**
Modularized services that handle different aspects of AI embodiment:
- **Hearing** - Processes voice input.
- **Vision** - Handles screen analysis and object detection.
- **Automation** - Manages PC task execution.
- **Smart Home** - Controls smart devices.
- **Voice** - Handles text-to-speech synthesis.

### **4. `/models/` - AI Models**
Contains NLP, vision, automation, and memory models for inference and processing.

### **5. `/scripts/` - Utility Scripts**
Includes scripts for environment setup, service startup, and deployment automation.

### **6. `/config/` - Configuration Files**
Stores settings, API keys, and environment variables.

### **7. `/data/` - Logs, Databases, and Cache**
Handles persistent storage for logs, databases, and temporary cache.

### **8. `/tests/` - Unit and Integration Testing**
Contains test scripts for each service and module.

### **9. `/docs/` - Documentation**
Stores markdown files for architecture and system overview.

### **10. `/docker/` - Containerization Files**
Includes separate Docker folders for **voice** and **smart home** services:
- **`/docker/voice/`** - Handles containerization for the voice API.
- **`/docker/smart_home/`** - Handles containerization for smart home API.

### **11. Project Root Files**
- **README.md** - Project overview and setup instructions.
- **requirements.txt** - Python dependencies list.

This folder structure ensures modularity, maintainability, and ease of expansion while keeping the **voice and smart home APIs containerized** due to their dependencies. Let me know if you need further refinements! 🚀

