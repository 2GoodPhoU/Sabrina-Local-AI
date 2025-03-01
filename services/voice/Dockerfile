# Use Python 3.10 base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/usr/local/lib:/app/lib

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
RUN mkdir -p /app/logs /app/models/piper /app/lib

# Build Piper from source - using a simpler build approach
RUN cd /tmp && \
    git clone https://github.com/rhasspy/piper.git && \
    cd piper && \
    git submodule update --init --recursive && \
    mkdir -p build && \
    cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc) && \
    # Copy executables and libraries
    cp bin/piper /app/ && \
    # Find and copy all shared libraries to app/lib
    find . -name "*.so*" -exec cp -P {} /app/lib/ \; && \
    # Create symbolic links for library compatibility
    ln -sf /app/lib/libpiper_phonemize.so /app/lib/libpiper_phonemize.so.1 && \
    cd / && \
    rm -rf /tmp/piper

# Download voice models
RUN wget -O /app/models/piper/en_GB-alan-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx" && \
    wget -O /app/models/piper/en_GB-alan-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json" && \
    wget -O /app/models/piper/en_US-ryan-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx" && \
    wget -O /app/models/piper/en_US-ryan-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json" && \
    # Verify files were downloaded
    ls -la /app/models/piper/

# Copy voice module code
COPY voice_api.py .
COPY voice_settings.json .

# Expose API port
EXPOSE 8100

# Command to run the service
CMD ["python", "voice_api.py"]