#!/bin/bash
# Entrypoint script for rdock-cv-pipeline Docker container

set -e

# Print GPU information if available
if command -v nvidia-smi &> /dev/null; then
    echo "==================================="
    echo "GPU Information:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    echo "==================================="
else
    echo "⚠️  Warning: No GPU detected. Processing will be slow."
fi

# Print Python and PyTorch information
echo "Python version: $(python --version)"
echo "PyTorch version: $(python -c 'import torch; print(torch.__version__)')"
echo "CUDA available: $(python -c 'import torch; print(torch.cuda.is_available())')"
echo "==================================="

# Execute the command passed to the container
exec "$@"

