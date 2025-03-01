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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY voice_docker_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r voice_docker_requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/models/piper

# Install Piper TTS
RUN cd /tmp && \
    git clone https://github.com/rhasspy/piper.git && \
    cd piper && \
    git submodule update --init && \
    mkdir build && \
    cd build && \
    cmake -DBUILD_SHARED_LIBS=ON .. && \
    make -j4 && \
    cp ./piper /app/piper && \
    rm -rf /tmp/piper

# Download Amy TTS model and explicitly verify it exists
RUN mkdir -p /app/models/piper && \
    cd /app/models/piper && \
    echo "Downloading Amy voice model..." && \
    curl -LO "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx" && \
    curl -LO "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json" && \
    ls -la && \
    test -f "en_US-amy-medium.onnx" || (echo "ERROR: Amy model failed to download" && exit 1)

# Copy voice module code
COPY voice_api.py .
COPY voice_settings.json .

# Expose API port
EXPOSE 8100

# Command to run the service
CMD ["python", "voice_api.py"]