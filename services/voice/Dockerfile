# Use Python 3.10 base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies 
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY voice_docker_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r voice_docker_requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/models

# Copy voice module code
COPY voice_api.py .
COPY voice_settings.json .

# Expose API port
EXPOSE 8100

# Command to run the service
CMD ["python", "voice_api.py"]