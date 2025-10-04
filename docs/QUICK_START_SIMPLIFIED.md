# Quick Start Guide - Simplified MAST3R Pipeline

## Overview

The simplified MAST3R pipeline provides clean, modular tools for 3D reconstruction. This guide shows you how to use the new system.

## Installation

```bash
# Activate your environment
source activate_env.sh

# Ensure MAST3R model is available
cd models/mast3r
# Follow MAST3R setup instructions if needed
```

## Usage Options

### Option 1: Live Feed Processing (Interactive)

**Best for**: Real-time experimentation, testing, manual control

```bash
python -m frame_processing_pipeline.feed_mast3r_simple
```

**Controls**:
- `q` - quit
- `p` - save current point cloud
- `a` - toggle auto-capture mode
- `m` - merge all saved point clouds

**What you get**:
- Real-time depth visualization
- Manual control over when to capture
- Interactive merging

---

### Option 2: Automatic Reconstruction

**Best for**: Automated capture with minimal interaction

```bash
# Capture for 60 seconds, save PLY every 30 frames
python auto_reconstruction_simple.py --duration 60 --interval 30

# Custom output name
python auto_reconstruction_simple.py --duration 45 --interval 20 --output my_scene.ply

# Short capture for testing
python auto_reconstruction_simple.py -d 30 -i 30
```

**What you get**:
- Automated capture and merging
- Single output file
- Progress indicators

---

### Option 3: Realistic Reconstruction (Global Alignment)

**Best for**: High-quality reconstructions of static scenes

```bash
# Capture images for 30 seconds (one image every 2 seconds)
python realistic_reconstruction_simple.py --duration 30 --interval 2

# Longer capture for complex scenes
python realistic_reconstruction_simple.py -d 60 -i 1.5

# Custom output
python realistic_reconstruction_simple.py -d 30 -i 2 -o office_scene.ply
```

**What you get**:
- Globally aligned reconstruction
- Better spatial coherence
- Optimized camera poses

---

## Programmatic Usage

### Basic Example

```python
from frame_processing_pipeline import MAST3RProcessor, open_camera

# Initialize
processor = MAST3RProcessor()
cap = open_camera()

# Capture two frames
ret1, frame1 = cap.read()
ret2, frame2 = cap.read()

# Process
results = processor.process_frame_pair(frame1, frame2)

# Save point cloud
if results:
    ply_file = processor.save_point_cloud(results, frame1, frame_id=1)
    print(f"Saved: {ply_file}")

cap.release()
```

### Advanced Example with Session Management

```python
from frame_processing_pipeline import (
    MAST3RProcessor, 
    FrameCaptureSession, 
    open_camera,
    merge_ply_files
)
import cv2 as cv

# Setup
processor = MAST3RProcessor()
cap = open_camera()
session = FrameCaptureSession(cap, process_interval=10)

saved_files = []

try:
    while True:
        frame = session.read_frame()
        if frame is None:
            break
        
        cv.imshow("Frame", frame)
        
        # Process every 10th frame
        if session.should_process():
            results = processor.process_frame_pair(session.prev_frame, frame)
            
            if results:
                # Save point cloud
                ply = processor.save_point_cloud(
                    results, 
                    frame, 
                    session.frame_count
                )
                if ply:
                    saved_files.append(ply)
                
                # Visualize depth
                depth_viz = processor.visualize_depth(results)
                if depth_viz is not None:
                    cv.imshow("Depth", depth_viz)
        
        session.update_prev_frame(frame)
        
        if cv.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    session.release()
    
    # Merge results
    if len(saved_files) >= 2:
        merged = merge_ply_files(saved_files, "output.ply")
        print(f"Merged reconstruction: {merged}")
    
    # Print statistics
    stats = session.get_stats()
    print(f"Captured {stats['frames']} frames at {stats['fps']:.1f} FPS")
```

### Custom PLY Processing

```python
from frame_processing_pipeline import read_ply, write_ply
import numpy as np

# Read existing PLY file
points, colors, confidences = read_ply("input.ply")

# Filter by confidence
if confidences is not None:
    mask = confidences > 5.0
    points = points[mask]
    colors = colors[mask]
    confidences = confidences[mask]

# Write filtered PLY
write_ply("filtered_output.ply", points, colors, confidences)
```

## Module API Reference

### MAST3RProcessor

```python
from frame_processing_pipeline import MAST3RProcessor

processor = MAST3RProcessor(
    model_name="MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric"
)

# Process frame pair → returns dict with 'pred1', 'pred2'
results = processor.process_frame_pair(frame1, frame2)

# Extract point cloud → returns (points, colors, confidences)
points, colors, confs = processor.extract_point_cloud(
    results, 
    original_frame, 
    conf_threshold=2.0
)

# Save point cloud → returns PLY filename
ply_file = processor.save_point_cloud(
    results, 
    frame, 
    frame_id,
    output_dir="point_clouds",
    conf_threshold=2.0
)

# Visualize depth → returns colored depth image
depth_viz = processor.visualize_depth(results)
```

### Camera Utils

```python
from frame_processing_pipeline import open_camera, FrameCaptureSession

# Open camera with fallback
cap = open_camera(camera_indices=[0, 1, 2])

# Create managed session
session = FrameCaptureSession(cap, process_interval=10)

frame = session.read_frame()                    # Read next frame
should_process = session.should_process()       # Check if should process
session.update_prev_frame(frame)                # Store for next pair
elapsed = session.get_elapsed_time()            # Time since start
stats = session.get_stats()                     # Get statistics
session.release()                               # Cleanup
```

### PLY Utils

```python
from frame_processing_pipeline import (
    write_ply, 
    read_ply, 
    merge_ply_files, 
    get_ply_point_count
)

# Write PLY file
write_ply("output.ply", points, colors, confidences=None)

# Read PLY file
points, colors, confidences = read_ply("input.ply")

# Merge multiple PLY files
merged_file = merge_ply_files(
    ["file1.ply", "file2.ply", "file3.ply"],
    "merged.ply"
)

# Get point count without loading
count = get_ply_point_count("file.ply")
```

## Tips & Best Practices

### Camera Capture
- **Frame rate**: Processing every 10th frame balances speed and quality
- **Movement**: Move camera slowly for better reconstruction
- **Lighting**: Consistent lighting improves results
- **Overlap**: Ensure adjacent frames overlap by ~60-70%

### Point Cloud Quality
- **Confidence threshold**: Higher values (3-5) give cleaner but sparser clouds
- **Capture interval**: Smaller intervals give denser reconstructions
- **Duration**: 30-60 seconds is usually sufficient for room-scale scenes

### Merging
- **Minimum files**: Need at least 2 PLY files to merge
- **Memory**: Large merges may require significant RAM
- **Alignment**: For best results, use realistic reconstruction with global alignment

### Troubleshooting

**Camera won't open**:
```bash
# Add yourself to video group
sudo usermod -a -G video $USER
# Then logout and login

# Or temporarily:
sudo chmod 666 /dev/video0
```

**Out of memory**:
- Reduce capture duration
- Increase capture interval
- Process fewer frames
- Lower confidence threshold for sparser clouds

**Poor reconstruction quality**:
- Increase overlap between frames
- Move camera more slowly
- Use realistic reconstruction for static scenes
- Ensure good lighting

## Example Workflows

### Quick Test
```bash
# 30-second automatic capture
python auto_reconstruction_simple.py -d 30 -i 30
```

### High-Quality Room Scan
```bash
# 60-second realistic reconstruction
python realistic_reconstruction_simple.py -d 60 -i 1.5 -o room_scan.ply
```

### Interactive Experimentation
```bash
# Manual control over capture
python -m frame_processing_pipeline.feed_mast3r_simple
# Use 'a' for auto-mode, 'p' for manual captures
```

## Visualization

View your reconstructions:

```bash
# Using the provided viewer
python view_ply.py output.ply

# Or use external tools
# - MeshLab (GUI application)
# - CloudCompare (professional tool)
# - Blender (import PLY addon)
```

## Integration with Other Projects

The modular design makes integration easy:

```python
# In your own script
from frame_processing_pipeline import MAST3RProcessor

# Use as a component in your pipeline
class MyPipeline:
    def __init__(self):
        self.mast3r = MAST3RProcessor()
        
    def process_video(self, video_path):
        # Your custom video processing
        # Use self.mast3r for 3D reconstruction
        pass
```

## Next Steps

1. Try the live feed: `python -m frame_processing_pipeline.feed_mast3r_simple`
2. Experiment with parameters
3. Integrate into your own projects
4. Check out the comparison docs: `COMPLEXITY_COMPARISON.md`
5. Read the full refactoring details: `REFACTORING_SUMMARY.md`

## Support

For issues or questions:
1. Check the refactoring documentation
2. Review module docstrings
3. Examine the example scripts
4. Test with the simple live feed first

Happy reconstructing! 🎉

