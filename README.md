# rdock-cv-pipeline

Computer vision pipeline for 3D reconstruction using MAST3R and MASt3R-SLAM.

## Overview

This pipeline provides tools for capturing frames from a camera and generating 3D point cloud reconstructions. It supports:

### Workflows
1. **Integrated Workflow**: Capture and process in real-time (for local development)
2. **Decoupled S3 Workflow**: Separate capture and inference via S3 storage (for production/cloud)

### Reconstruction Modes
1. **Batch Mode** (default): Global MASt3R optimization - best quality for short sequences
2. **SLAM Mode** (new): Sequential processing - memory efficient for long sequences, outputs camera trajectory

See [SLAM Mode Documentation](docs/SLAM_MODE.md) for detailed comparison.

## Quick Start

### Setup Environment

```bash
# Clone repository
git clone https://github.com/RoboDockCode/rdock-cv-pipeline.git
cd rdock-cv-pipeline

# Initialize submodules (MAST3R and MASt3R-SLAM)
git submodule update --init --recursive

# Create conda environment
conda env create -f environment.yml
conda activate rdock-cv

# Optional: Install SLAM dependencies (for --mode slam)
./install_slam.sh

# Or use the activation script
source activate_env.sh
```

### Option 1: Integrated Workflow (Local)

Run capture and reconstruction together:

```bash
# Quick reconstruction (30 seconds)
python scripts/realistic_reconstruction_simple.py --duration 30 --interval 2

# Automatic reconstruction with merging
python scripts/auto_reconstruction_simple.py --duration 60 --interval 30
```

### Option 2: Decoupled S3 Workflow (Production)

Process MP4 videos from S3 and upload results:

```bash
# Batch mode (default - best quality)
python scripts/infer_from_mp4.py --fps 5

# SLAM mode (for long sequences, outputs trajectory)
python scripts/infer_from_mp4.py --mode slam --fps 5

# With specific video
python scripts/infer_from_mp4.py --video my_video.mp4 --mode slam --fps 3
```

**Options:**
- `--mode`: `batch` (default, best quality) or `slam` (memory efficient, long sequences)
- `--fps`: Frame extraction rate (1-10, default: 2)
- `--input-bucket`: S3 bucket with MP4 videos
- `--output-bucket`: S3 bucket for results

See [SLAM Mode Documentation](docs/SLAM_MODE.md) for mode comparison.

## Architecture

```
frame_processing_pipeline/
├── camera_utils.py      # Camera capture utilities
├── mast3r_processor.py  # Batch MASt3R inference wrapper
├── slam_processor.py    # Sequential SLAM processor
├── ply_utils.py         # Point cloud file operations
└── s3_utils.py          # S3 upload/download manager

scripts/
├── infer_from_mp4.py                   # MP4 → Reconstruction (batch or SLAM)
├── realistic_reconstruction_simple.py  # Integrated batch workflow
├── auto_reconstruction_simple.py       # Integrated with merging
├── view_ply.py                         # Visualize PLY files
└── test_slam_integration.py            # Test SLAM setup

models/
├── mast3r/              # MASt3R submodule (batch processing)
└── mast3r-slam/         # MASt3R-SLAM submodule (sequential processing)
```

## Documentation

- **[SLAM Mode Guide](docs/SLAM_MODE.md)** - Batch vs SLAM comparison, when to use each
- [S3 Workflow Guide](docs/S3_WORKFLOW.md) - Decoupled capture and inference
- [EC2/GPU Setup Guide](docs/EC2_SETUP_GUIDE.md) - Setting up cloud GPU instances
- [Quick Start](docs/QUICK_START_SIMPLIFIED.md) - Getting started guide
- [System Summary](docs/FINAL_SYSTEM_SUMMARY.md) - Complete system overview

## Requirements

- Python 3.9+
- CUDA-capable GPU (for inference)
- Camera/video source (for capture)
- AWS account with S3 (for decoupled workflow)

## Use Cases

### Development/Testing
Use integrated workflow for quick iterations on local machine with GPU.

### Production/Edge Computing
Use decoupled workflow:
- Capture on edge devices (robot, mobile, etc.)
- Process on powerful GPU servers
- Store everything in S3 for auditing/reprocessing

### Cloud-Only Processing
Upload pre-recorded videos to S3, run inference in batch on GPU instances.

## License

[Add your license here]
