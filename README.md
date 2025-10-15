# rdock-cv-pipeline

Computer vision pipeline for 3D reconstruction using MAST3R (Matching and Stereo 3D Reconstruction).

## Overview

This pipeline provides tools for capturing frames from a camera and generating 3D point cloud reconstructions. It supports two workflows:

1. **Integrated Workflow**: Capture and process in real-time (for local development)
2. **Decoupled S3 Workflow**: Separate capture and inference via S3 storage (for production/cloud)

## Quick Start

### Setup Environment

```bash
# Clone repository
git clone https://github.com/RoboDockCode/rdock-cv-pipeline.git
cd rdock-cv-pipeline

# Initialize submodules (MAST3R model)
git submodule update --init --recursive

# Create conda environment
conda env create -f environment.yml
conda activate rdock-cv

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

**Step 1 - Capture frames (on device with camera):**
```bash
python scripts/capture_to_s3.py --bucket your-bucket-name --duration 30
```

**Step 2 - Run inference (on GPU server):**
```bash
python scripts/infer_from_s3.py --bucket your-bucket-name
```

See [S3 Workflow Documentation](docs/S3_WORKFLOW.md) for detailed usage.

## Architecture

```
frame_processing_pipeline/
├── camera_utils.py      # Camera capture utilities
├── mast3r_processor.py  # MAST3R inference wrapper
├── ply_utils.py         # Point cloud file operations
└── s3_utils.py          # S3 upload/download manager

scripts/
├── capture_to_s3.py                    # Capture frames → S3
├── infer_from_s3.py                    # S3 → Inference → S3
├── realistic_reconstruction_simple.py  # Integrated workflow
├── auto_reconstruction_simple.py       # Integrated with merging
└── view_ply.py                         # Visualize PLY files
```

## Documentation

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
