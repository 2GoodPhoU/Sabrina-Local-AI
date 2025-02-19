# Sabrina AI

This project sets up **Ollama (DeepSeek model)** and **Open-WebUI** in separate Docker containers, using your **Nvidia GPU** for acceleration.

## Prerequisites

- **Docker** installed ([Install Docker](https://docs.docker.com/get-docker/))
- **Nvidia Container Toolkit** installed ([Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html))
- **Docker Compose** installed ([Install Compose](https://docs.docker.com/compose/install/))

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/Sabrina-AI.git
cd Sabrina-AI
```

### 2. Start the Containers
Run the following command to start both Ollama and Open-WebUI:
```bash
docker compose up -d
```

### 3. Access the Services
Ollama API: http://localhost:11434
Open-WebUI: http://localhost:8080

### 4. Stop and Remove Containers
```bash
docker compose down
```