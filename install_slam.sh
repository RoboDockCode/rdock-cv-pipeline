#!/bin/bash
# Install MASt3R-SLAM dependencies
# Run this after creating the conda environment with environment.yml

set -e

echo "========================================="
echo "Installing MASt3R-SLAM dependencies"
echo "========================================="

# Check if we're in the right directory
if [ ! -d "models/mast3r-slam" ]; then
    echo "❌ Error: models/mast3r-slam directory not found"
    echo "Make sure you're running this from the project root"
    exit 1
fi

# Check if conda environment is activated
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  Warning: No conda environment detected"
    echo "Please activate your environment first:"
    echo "  conda activate rdock-cv"
    exit 1
fi

echo "📦 Installing MASt3R (thirdparty)"
pip install -e models/mast3r-slam/thirdparty/mast3r

echo "📦 Installing in3d (thirdparty)"
pip install -e models/mast3r-slam/thirdparty/in3d

echo "📦 Installing MASt3R-SLAM"
pip install --no-build-isolation -e models/mast3r-slam

echo ""
echo "✅ MASt3R-SLAM installation complete!"
echo ""
echo "Optional: Install torchcodec for faster MP4 loading:"
echo "  pip install torchcodec==0.1"
echo ""
echo "Test SLAM processor with:"
echo "  python scripts/infer_from_mp4.py --mode slam --fps 5"

