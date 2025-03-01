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
    sox \
    libespeak-ng1 \
    espeak-ng \
    python3-dev \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /app/logs /app/models/piper

# Copy requirements
COPY voice_docker_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r voice_docker_requirements.txt

# Install Piper TTS from pip instead of using the binary
RUN pip install --no-cache-dir piper-tts

# Download voice models from the preferred voices list in the API script
RUN mkdir -p /app/models/piper && \
    wget -O /app/models/piper/en_US-amy-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx" || echo "Amy model download failed" && \
    wget -O /app/models/piper/en_US-amy-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json" || echo "Amy config download failed" && \
    wget -O /app/models/piper/en_US-kathleen-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/kathleen/medium/en_US-kathleen-medium.onnx" || echo "Kathleen model download failed" && \
    wget -O /app/models/piper/en_US-kathleen-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/kathleen/medium/en_US-kathleen-medium.onnx.json" || echo "Kathleen config download failed" && \
    wget -O /app/models/piper/en_US-jenny-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/jenny/medium/en_US-jenny-medium.onnx" || echo "Jenny model download failed" && \
    wget -O /app/models/piper/en_US-jenny-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/jenny/medium/en_US-jenny-medium.onnx.json" || echo "Jenny config download failed"

# Add a fallback voice if the preferred ones fail to download
RUN ls -la /app/models/piper/ && \
    if [ ! -s /app/models/piper/en_US-amy-medium.onnx ] && [ ! -s /app/models/piper/en_US-kathleen-medium.onnx ] && [ ! -s /app/models/piper/en_US-jenny-medium.onnx ]; then \
        echo "Downloading fallback voice model..." && \
        wget -O /app/models/piper/en_US-lessac-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" && \
        wget -O /app/models/piper/en_US-lessac-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"; \
    fi

# Copy voice module code
COPY voice_api.py .
COPY voice_settings.json .

# Update voice_settings.json with the best available voice
RUN if [ -f /app/models/piper/en_US-amy-medium.onnx ]; then \
        sed -i 's/"voice": ".*"/"voice": "en_US-amy-medium"/' voice_settings.json; \
    elif [ -f /app/models/piper/en_US-kathleen-medium.onnx ]; then \
        sed -i 's/"voice": ".*"/"voice": "en_US-kathleen-medium"/' voice_settings.json; \
    elif [ -f /app/models/piper/en_US-jenny-medium.onnx ]; then \
        sed -i 's/"voice": ".*"/"voice": "en_US-jenny-medium"/' voice_settings.json; \
    elif [ -f /app/models/piper/en_US-lessac-medium.onnx ]; then \
        sed -i 's/"voice": ".*"/"voice": "en_US-lessac-medium"/' voice_settings.json; \
    fi

# Expose API port
EXPOSE 8100

# Command to run the service
CMD ["python", "voice_api.py"]