#!/bin/bash

# Script to activate the rdock-cv conda environment
# Usage: source activate_env.sh

# Initialize conda
source ~/miniconda3/etc/profile.d/conda.sh

# Set environment variables for Qt/OpenCV
export QT_QPA_PLATFORM=xcb
export QT_X11_NO_MITSHM=1

# Activate the environment
conda activate rdock-cv

echo "Activated rdock-cv environment"
echo "Python path: $(which python)"
echo "NumPy version: $(python -c 'import numpy; print(numpy.__version__)')"
echo "OpenCV version: $(python -c 'import cv2; print(cv2.__version__)')"
echo "Qt platform: $QT_QPA_PLATFORM"
