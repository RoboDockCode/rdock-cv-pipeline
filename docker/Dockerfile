# Multi-stage Docker build for MAST3R 3D reconstruction pipeline
# Base: NVIDIA CUDA for GPU acceleration

FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    git \
    wget \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Download MAST3R model weights at build time (cached)
# This downloads ~2GB from HuggingFace, so it's cached in the image
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download('naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric', \
    cache_dir='/root/.cache/huggingface')"

# Set environment variables
ENV PYTHONPATH=/app:/app/models/mast3r:$PYTHONPATH
ENV TORCH_HOME=/root/.cache/torch
ENV HF_HOME=/root/.cache/huggingface

# Create output directories
RUN mkdir -p /app/outputs /app/captures /app/point_clouds

# Copy and set entrypoint
COPY docker/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port for future API (optional)
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command shows usage
CMD ["echo", "MAST3R 3D Reconstruction Container Ready!\n\nUsage examples:\n  docker-compose run reconstruction python process_captures.py\n  docker-compose run reconstruction bash\n\nSee README_DOCKER.md for more details."]

