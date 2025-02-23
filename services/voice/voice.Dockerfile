# Base Image (Python + FFmpeg)
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pulseaudio \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement file and install dependencies
COPY voice_docker_requirements.txt .
RUN pip install --no-cache-dir -r voice_docker_requirements.txt

# Copy API and scripts
COPY voice_api.py /app/voice_api.py
COPY voice.py /app/voice.py

# Command to start the API
CMD ["python", "/app/voice_api.py"]
