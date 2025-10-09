#!/bin/bash
# Simple test script to verify Docker setup
# Run from project root: ./docker/scripts/test_docker.sh

set -e

# Change to project root (parent of docker directory)
cd "$(dirname "$0")/../.."

echo "=================================================="
echo "🧪 Testing MAST3R Docker Setup"
echo "=================================================="
echo ""

# Test 1: Check Docker
echo "✓ Test 1: Docker installed"
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi
docker --version
echo ""

# Test 2: Check Docker Compose
echo "✓ Test 2: Docker Compose installed"
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Please install docker-compose."
    exit 1
fi
docker-compose --version
echo ""

# Test 3: Check for NVIDIA Docker (GPU support)
echo "✓ Test 3: NVIDIA Docker support"
if docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "✅ GPU support available"
else
    echo "⚠️  GPU support not available (will use CPU mode - slower)"
fi
echo ""

# Test 4: Build the image (if not already built)
echo "✓ Test 4: Building Docker image"
if docker images | grep -q "rdock-cv-pipeline"; then
    echo "✅ Image already exists"
else
    echo "Building image (this may take 15-20 minutes)..."
    docker-compose -f docker/docker-compose.yml build
fi
echo ""

# Test 5: Check Python in container
echo "✓ Test 5: Python environment"
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python --version"
echo ""

# Test 6: Check PyTorch and CUDA
echo "✓ Test 6: PyTorch and CUDA"
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python -c 'import torch; print(f\"PyTorch: {torch.__version__}\"); print(f\"CUDA available: {torch.cuda.is_available()}\")'"
echo ""

# Test 7: Check MAST3R model
echo "✓ Test 7: MAST3R model loading"
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python -c 'from scripts.realistic_reconstruction_simple import RealisticReconstructor; print(\"✅ MAST3R can be imported\")'"
echo ""

# Test 8: Check volume mounts
echo "✓ Test 8: Volume mounts"
docker-compose -f docker/docker-compose.yml run --rm reconstruction "ls -la /app/captures /app/outputs /app/point_clouds 2>&1 | head -3"
echo ""

echo "=================================================="
echo "🎉 All tests passed!"
echo "=================================================="
echo ""
echo "Quick usage:"
echo "  docker-compose -f docker/docker-compose.yml run --rm reconstruction 'python process_captures.py'"
echo "  docker-compose -f docker/docker-compose.yml run --rm reconstruction bash"
echo ""
echo "See docker/docs/README_DOCKER.md for complete documentation."

