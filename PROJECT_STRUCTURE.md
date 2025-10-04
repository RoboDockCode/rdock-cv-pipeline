# 📁 Project Structure

## Overview
This repository contains the CV (Computer Vision) aspects of the RoboDock mapping pipeline, featuring MAST3R-based 3D reconstruction from video.

## 🗂️ Directory Structure

```
rdock-cv-pipeline/
├── 📚 docs/                          # All documentation
│   ├── COMPLEXITY_COMPARISON.md
│   ├── FINAL_SYSTEM_SUMMARY.md
│   ├── QUICK_START_SIMPLIFIED.md    # 👈 START HERE for usage
│   ├── README_PLY_RECONSTRUCTION.md
│   ├── README_REFACTORING.md
│   ├── REFACTORING_INDEX.md
│   ├── REFACTORING_SUMMARY.md
│   └── VISUAL_SUMMARY.md
│
├── 🚀 scripts/                       # Mission-oriented scripts
│   ├── auto_reconstruction_simple.py      # Automatic 3D reconstruction
│   ├── realistic_reconstruction_simple.py # Realistic reconstruction mode
│   ├── test_simplified_pipeline.py        # Test suite
│   └── view_ply.py                        # PLY file viewer
│
├── 🧩 frame_processing_pipeline/     # Core pipeline modules
│   ├── __init__.py
│   ├── mast3r_processor.py          # MAST3R AI processing
│   ├── camera_utils.py              # Camera capture utilities
│   ├── ply_utils.py                 # PLY file I/O
│   └── feed_mast3r_simple.py        # Live feed demo
│
├── 📦 models/                        # AI models
│   └── mast3r/                       # MAST3R submodule
│
├── 💾 outputs/                       # Generated PLY files
│   ├── auto_reconstruction_*.ply
│   └── test_merged_reconstruction.ply
│
├── 💾 point_clouds/                  # Intermediate point clouds
│   └── frame_*.ply
│
├── 🌌 cosmos-predict2/               # Cosmos prediction (separate project)
│
├── ⚙️ Configuration Files
│   ├── environment.yml              # Conda environment
│   ├── activate_env.sh             # Environment activation
│   └── README.md                   # This file
│
└── PROJECT_STRUCTURE.md            # This document
```

## 🎯 Quick Start

### Run 3D Reconstruction
```bash
# Activate environment
source activate_env.sh

# Automatic reconstruction (60 seconds)
python scripts/auto_reconstruction_simple.py

# Custom duration and interval
python scripts/auto_reconstruction_simple.py --duration 120 --interval 20

# View results
python scripts/view_ply.py outputs/auto_reconstruction_*.ply
```

### Use as Library
```python
from frame_processing_pipeline import MAST3RProcessor, open_camera

processor = MAST3RProcessor()
cap = open_camera()

# Process frame pairs
ret, frame1 = cap.read()
ret, frame2 = cap.read()
results = processor.process_frame_pair(frame1, frame2)
ply_file = processor.save_point_cloud(results, frame2, frame_id=1)
```

## 📚 Documentation

- **New User?** → Read [`docs/QUICK_START_SIMPLIFIED.md`](docs/QUICK_START_SIMPLIFIED.md)
- **Understanding the System?** → Read [`docs/FINAL_SYSTEM_SUMMARY.md`](docs/FINAL_SYSTEM_SUMMARY.md)
- **Technical Details?** → Read [`docs/REFACTORING_SUMMARY.md`](docs/REFACTORING_SUMMARY.md)
- **Visual Overview?** → Read [`docs/VISUAL_SUMMARY.md`](docs/VISUAL_SUMMARY.md)

## 🔧 Core Modules

| Module | Purpose | Lines |
|--------|---------|-------|
| `mast3r_processor.py` | MAST3R AI model wrapper | 220 |
| `camera_utils.py` | Camera capture & management | 81 |
| `ply_utils.py` | PLY file I/O operations | 160 |
| `feed_mast3r_simple.py` | Live feed application | 130 |

**Total Core: ~600 lines** (clean, modular, well-documented)

## 🚀 Scripts

| Script | Purpose |
|--------|---------|
| `auto_reconstruction_simple.py` | Automated 3D reconstruction from live camera |
| `realistic_reconstruction_simple.py` | Advanced reconstruction with multiple modes |
| `test_simplified_pipeline.py` | Automated testing suite |
| `view_ply.py` | Visualize PLY files with Open3D |

## 🗑️ Removed Files

The following old/deprecated files have been removed:
- ❌ `auto_reconstruction.py` → Use `scripts/auto_reconstruction_simple.py`
- ❌ `realistic_reconstruction.py` → Use `scripts/realistic_reconstruction_simple.py`
- ❌ `frame_processing_pipeline/feed_mast3r.py` → Use `feed_mast3r_simple.py`
- ❌ `frame_processing_pipeline/frame.py` → Replaced by `camera_utils.py`

## 📦 Output Files

- **`outputs/`** - Final merged reconstructions
- **`point_clouds/`** - Intermediate frame-by-frame PLY files

## 🧪 Testing

```bash
python scripts/test_simplified_pipeline.py
```

## 📊 Project Stats

- **Code Lines**: ~600 (core) + ~500 (scripts) = 1,100 total
- **Documentation**: 8 comprehensive guides (~3,000+ lines)
- **Modules**: 4 focused, single-purpose modules
- **Code Duplication**: Zero ✅
- **Test Coverage**: Core modules ✅

## 🎉 Features

✅ Real-time 3D reconstruction from live camera  
✅ MAST3R AI model integration  
✅ GPU acceleration (CUDA)  
✅ PLY file generation with RGB colors  
✅ Point cloud merging  
✅ Interactive and automatic capture modes  
✅ Comprehensive documentation  
✅ Modular, maintainable architecture  

---

**Last Updated**: October 2, 2025  
**Status**: ✅ Production Ready

