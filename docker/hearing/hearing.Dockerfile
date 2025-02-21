# Base Image (Python + FFmpeg)
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies (FFmpeg + PortAudio + ALSA)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    alsa-utils \
    pulseaudio \
    && rm -rf /var/lib/apt/lists/*

# Copy requirement file and install dependencies
COPY docker/hearing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API and scripts
COPY api/hearing_api.py /app/api/hearing_api.py
COPY scripts/hearing.py /app/scripts/hearing.py

# Command to start the API
CMD ["python", "/app/api/hearing_api.py"]
