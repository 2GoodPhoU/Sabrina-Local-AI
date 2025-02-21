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
COPY docker/voice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API and scripts
COPY api/voice_api.py /app/api/voice_api.py
COPY scripts/voice.py /app/scripts/voice.py

# Command to start the API
CMD ["python", "/app/api/voice_api.py"]
