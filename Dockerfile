# Base Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-venv \
    pulseaudio \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    tesseract-ocr \
    libtesseract-dev \
    wget \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create directory structure
RUN mkdir -p /app/logs /app/data /app/config /app/models

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user to run the application
RUN useradd -m sabrina
RUN chown -R sabrina:sabrina /app
USER sabrina

# Set up entrypoint
ENTRYPOINT ["python", "scripts/start_sabrina.py"]

# Default command (can be overridden)
CMD ["--config", "config/settings.yaml"]