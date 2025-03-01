# Voice Service Dockerfile for Sabrina AI
FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    libsm6 \
    libxext6 \
    libportaudio2 \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/models /app/config /app/data/tts_cache /app/logs

# Copy requirements and install Python dependencies
COPY voice_docker_requirements.txt .
RUN pip install --no-cache-dir -r voice_docker_requirements.txt \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy voice module files
COPY voice_api.py .
COPY voice_settings.py .
COPY tts_engine.py .

# Volume mounts for persistent storage
VOLUME ["/app/models", "/app/config", "/app/data/tts_cache", "/app/logs"]

# Expose the API port
EXPOSE 8100

# Set default environment variables
ENV TTS_MODEL_DIR=/app/models \
    TTS_CACHE_DIR=/app/data/tts_cache

# Run the Voice API
CMD ["uvicorn", "voice_api:app", "--host", "0.0.0.0", "--port", "8100", "--reload"]
