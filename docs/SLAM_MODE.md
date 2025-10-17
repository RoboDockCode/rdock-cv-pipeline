# MASt3R-SLAM Mode Documentation

## Overview

The pipeline now supports two reconstruction modes:

### 1. **Batch Mode** (Default - Best Quality)
- **Method**: Global MASt3R with complete graph optimization
- **Best for**: Short sequences (< 1 minute), highest quality needed
- **Pros**: 
  - ✅ Best reconstruction quality
  - ✅ Global optimization considers all frame relationships
  - ✅ Dense point clouds
- **Cons**:
  - ⚠️ High memory usage (all frames in RAM)
  - ⚠️ Slower for long sequences
  - ⚠️ No camera trajectory output

### 2. **SLAM Mode** (New - Memory Efficient)
- **Method**: Sequential MASt3R-SLAM with incremental mapping
- **Best for**: Long sequences (1+ minutes), assembly line walks, large scenes
- **Pros**:
  - ✅ Memory efficient (constant RAM usage)
  - ✅ Better for long sequences
  - ✅ Outputs camera trajectory
  - ✅ Handles relocalization and loop closure
- **Cons**:
  - ⚠️ Slightly lower quality than batch mode
  - ⚠️ No global optimization of all frames

## Setup

### Install SLAM Dependencies

After setting up the base environment:

```bash
# Activate your environment
conda activate rdock-cv

# Run the SLAM installation script
./install_slam.sh
```

This will install:
- MASt3R (from SLAM submodule)
- in3d (3D visualization library)
- lietorch (Lie algebra library)
- MASt3R-SLAM package

## Usage

### Basic Usage

```bash
# Default batch mode (best quality)
python scripts/infer_from_mp4.py --fps 5

# SLAM mode (memory efficient + trajectory)
python scripts/infer_from_mp4.py --mode slam --fps 5
```

### Full Options

```bash
python scripts/infer_from_mp4.py \
    --mode slam \
    --input-bucket video-test-bucket-2985 \
    --output-bucket frame-storage \
    --fps 5 \
    --video specific_video.mp4
```

### Arguments

- `--mode`, `-m`: Reconstruction mode
  - `batch` (default): Global MASt3R - best quality
  - `slam`: Sequential SLAM - memory efficient
- `--fps`, `-f`: Target FPS for frame extraction (default: 2.0)
  - Lower FPS (1-2): Fewer frames, faster processing
  - Higher FPS (5-10): More frames, better detail
- `--input-bucket`, `-i`: S3 bucket with MP4 videos
- `--output-bucket`, `-o`: S3 bucket for outputs
- `--video`, `-v`: Specific video key (optional, uses latest if not specified)
- `--keep-temp`: Keep temporary files for debugging

## Outputs

### Batch Mode
- `reconstruction.ply`: Point cloud with RGB colors

### SLAM Mode
- `reconstruction.ply`: Point cloud with RGB colors
- `trajectory.txt`: Camera poses (format: `frame_id x y z qx qy qz qw`)

Both are uploaded to S3 at:
```
s3://frame-storage/output/job_YYYYMMDD_HHMMSS/
├── reconstruction.ply
└── trajectory.txt  (SLAM mode only)
```

## When to Use Each Mode

### Use **Batch Mode** for:
- 🎥 Short videos (< 1 minute)
- 🏆 When you need maximum quality
- 📊 Simple reconstruction tasks
- 💻 When you have sufficient RAM

### Use **SLAM Mode** for:
- 🏭 Assembly line walkthroughs (1+ minutes)
- 🗺️ Large scene mapping
- 📍 When you need camera trajectory
- 💾 Memory-constrained environments
- 🔄 Real-time incremental processing

## Performance Comparison

| Metric | Batch Mode | SLAM Mode |
|--------|-----------|-----------|
| **Quality** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Memory** | High (grows with frames) | Constant |
| **Speed (short)** | Fast | Medium |
| **Speed (long)** | Slow | Fast |
| **Max Length** | ~50 frames | Unlimited |
| **Trajectory** | ❌ | ✅ |

## Example Use Cases

### Product Scanning (Short)
```bash
# 30 second video, 2 FPS = ~60 frames
python scripts/infer_from_mp4.py --fps 2
# Uses batch mode for best quality
```

### Assembly Line Walk (Long)
```bash
# 2 minute video, 5 FPS = 600 frames
python scripts/infer_from_mp4.py --mode slam --fps 5
# Uses SLAM for memory efficiency
```

### Large Warehouse Mapping
```bash
# 5+ minute video, 3 FPS
python scripts/infer_from_mp4.py --mode slam --fps 3
# SLAM handles long sequences efficiently
```

## Troubleshooting

### Out of Memory (Batch Mode)
**Problem**: GPU runs out of memory with many frames

**Solutions**:
1. Lower FPS: `--fps 1`
2. Switch to SLAM: `--mode slam`
3. Process shorter clips

### SLAM Tracking Lost
**Problem**: SLAM mode fails to track frames

**Solutions**:
1. Increase FPS for better temporal overlap: `--fps 5`
2. Ensure smooth camera motion (avoid quick movements)
3. Check for sufficient visual features in scene

### Installation Issues
**Problem**: lietorch or backend compilation fails

**Solutions**:
1. Ensure CUDA toolkit is installed: `nvcc --version`
2. Check PyTorch CUDA version matches system CUDA
3. See [MASt3R-SLAM issues](https://github.com/rmurai0610/MASt3R-SLAM/issues)

## Technical Details

### SLAM Architecture

```
Frame Sequence → Tracker → Keyframe Selection → Factor Graph → Optimization
                    ↓           ↓                    ↓              ↓
                 Matching   Add to Map          Loop Closure    Update Poses
```

### Camera Trajectory Format

The `trajectory.txt` file contains camera poses in format:
```
frame_id x y z qx qy qz qw
```

Where:
- `x, y, z`: Camera position in world coordinates
- `qx, qy, qz, qw`: Camera orientation as quaternion

This can be used for:
- Visualizing camera path
- Aligning with other data
- AR/VR applications
- Multi-modal fusion

## References

- [MASt3R Paper](https://arxiv.org/abs/2406.09756)
- [MASt3R-SLAM Paper](https://arxiv.org/abs/2412.12392)
- [MASt3R-SLAM GitHub](https://github.com/rmurai0610/MASt3R-SLAM)

