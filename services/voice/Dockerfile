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
    libespeak-ng1 \
    git \
    wget \
    curl \
    cmake \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY voice_docker_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r voice_docker_requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/models/piper

# Build and install Piper from source with specific path handling
RUN cd /tmp && \
    git clone https://github.com/rhasspy/piper.git && \
    cd piper && \
    git submodule update --init --recursive && \
    mkdir -p build && \
    cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc) && \
    find . -name "piper" -type f -executable -exec cp {} /app/piper \; && \
    chmod +x /app/piper && \
    cd / && \
    rm -rf /tmp/piper

# Download Amy TTS model
RUN wget -O /app/models/piper/en_US-amy-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" && \
    wget -O /app/models/piper/en_US-amy-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" && \
    # Verify files were downloaded correctly
    ls -la /app/models/piper/

# Copy voice module code
COPY voice_api.py .
COPY voice_settings.json .

# Expose API port
EXPOSE 8100

# Command to run the service
CMD ["python", "voice_api.py"]