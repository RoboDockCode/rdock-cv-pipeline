# MAST3R Real-Time 3D Reconstruction Pipeline

## 🎯 What You Now Have

A complete real-time 3D reconstruction system that:

- **Loads MAST3R model** (2.75GB) with CUDA acceleration
- **Captures live camera feed** 
- **Processes stereo frame pairs** every 10th frame
- **Generates 3D point clouds** with RGB colors and confidence
- **Saves PLY files** for 3D reconstruction
- **Merges multiple PLY files** into complete reconstructions

## 🎮 Controls

When running `python frame_processing_pipeline/feed_mast3r.py`:

- **'q'** - quit
- **'s'** - save current frame as JPG
- **'p'** - save current 3D points as PLY file
- **'m'** - merge all saved PLY files into single reconstruction

## 📁 Output Files

### Individual PLY Files
- Location: `point_clouds/frame_XXXXXX.ply`
- Contains: 3D points (X,Y,Z), RGB colors, confidence values
- Format: Binary PLY for efficiency
- Size: ~2-3 MB per frame (100k+ points)

### Merged Reconstruction
- File: `merged_reconstruction.ply`
- Contains: Combined point clouds from multiple frames
- Use: Complete 3D scene reconstruction

## 🔧 Technical Details

### Point Cloud Data
- **3D Coordinates**: (X, Y, Z) in meters
- **RGB Colors**: From original camera frame
- **Confidence**: MAST3R reconstruction quality (2.0+ threshold)
- **Filtering**: Low-confidence points removed automatically

### Example Output
```
Loaded 123,642 points
Point range: X(-0.382, 0.378)
             Y(-0.311, 0.268) 
             Z(0.541, 1.147)
Confidence range: 2.000 to 3.383
```

## 🎨 Visualization

### Live Windows (during capture)
1. **Current Frame** - Live camera feed
2. **MAST3R Depth View1** - Depth map (red=close, blue=far)
3. **MAST3R Confidence View1** - Quality map (bright=confident)
4. **MAST3R Depth View2** - Second view depth
5. **MAST3R Confidence View2** - Second view confidence

### PLY File Viewing
```bash
# View generated PLY file
python view_ply.py point_clouds/frame_000001.ply
```

## 🚀 Usage Workflow

1. **Start live capture**:
   ```bash
   python frame_processing_pipeline/feed_mast3r.py
   ```

2. **Capture 3D points**: Press 'p' when you see interesting geometry

3. **Save multiple frames**: Move camera and press 'p' multiple times

4. **Merge reconstruction**: Press 'm' to combine all PLY files

5. **View results**: Use `view_ply.py` or import into Blender/MeshLab

## 🎯 Applications

- **3D Scene Reconstruction**: Capture rooms, objects, environments
- **DUSt3R Pipeline**: Prepared frames with depth and pose data
- **Point Cloud Processing**: Raw data for further 3D algorithms
- **Visualization**: Real-time depth and confidence feedback

## 📊 Performance

- **GPU Acceleration**: CUDA-enabled MAST3R processing
- **Real-time**: ~10 FPS processing rate
- **Quality**: 100k+ points per frame with confidence filtering
- **Storage**: ~2-3 MB per PLY file

This system gives you a complete pipeline from live camera to 3D reconstruction files! 🎥✨
