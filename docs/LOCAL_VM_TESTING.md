# Local VM Testing Guide

## Overview

Test the complete pipeline locally on your GPU VM before adding S3 integration.

## Current Setup ✅

Your pipeline **already supports** local-only operation:
- ✅ Images saved to `captures/` (persistent)
- ✅ PLY files saved locally
- ✅ No S3 required
- ✅ Ready for VM testing

## Workflow: Laptop → VM → Laptop

### Step 1: Push Code to GitHub (Laptop)

```bash
# On your laptop
cd /home/armaan/robodock-repos/rdock-cv-pipeline

# Check status
git status

# Add and commit changes
git add -A
git commit -m "feat: Save captures locally for VM testing"

# Push to your branch
git push origin test/fetch-upload-s3-helper-script
```

---

### Step 2: Setup on GPU VM

```bash
# SSH into your GPU VM/RunPod instance
ssh your-vm

# Clone repository
git clone https://github.com/your-username/rdock-cv-pipeline.git
cd rdock-cv-pipeline

# Checkout your test branch
git checkout test/fetch-upload-s3-helper-script

# Initialize submodules
git submodule update --init --recursive

# Setup conda environment
conda env create -f environment.yml
conda activate rdock-cv

# Install PyTorch with CUDA (if not already installed)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Verify GPU
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

---

### Step 3: Test Capture & Reconstruction on VM

#### Option A: With Camera (if VM has camera/display)

```bash
# Run realistic reconstruction
python scripts/realistic_reconstruction_simple.py \
  --duration 15 \
  --interval 2 \
  --output vm_test_reconstruction.ply
```

**What happens:**
1. Captures 7-8 images over 15 seconds
2. Saves images to `captures/capture_YYYYMMDD_HHMMSS/`
3. Runs MAST3R reconstruction
4. Saves PLY to `vm_test_reconstruction.ply`

#### Option B: Upload Test Images to VM (if no camera)

**From your laptop:**
```bash
# Copy your existing captures to VM
scp -r captures/capture_20251004_191045 your-vm:~/rdock-cv-pipeline/test_images/
```

**On the VM:**
```bash
# Run reconstruction on uploaded images
python scripts/realistic_reconstruction_simple.py \
  --images test_images/ \
  --output vm_test_reconstruction.ply
```

Wait, the script doesn't have `--images` flag. Let me check...

#### Option B: Process Existing Images

Since the realistic reconstruction captures its own images, for testing with existing images, you'd modify it slightly or use this Python approach:

**On the VM:**
```bash
# Create a simple test script
cat > test_reconstruction.py << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.append('models/mast3r')
sys.path.append('.')

from mast3r.model import AsymmetricMASt3R
from dust3r.utils.image import load_images
from dust3r.image_pairs import make_pairs
from dust3r.cloud_opt import global_aligner, GlobalAlignerMode
from dust3r.inference import inference
from frame_processing_pipeline.ply_utils import write_ply
import torch
import numpy as np

print("Loading MAST3R...")
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = AsymmetricMASt3R.from_pretrained("naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric").to(device)
model.eval()

print("Loading images...")
imgs = load_images("test_images/", size=512, verbose=True)

print("Creating pairs...")
pairs = make_pairs(imgs, scene_graph='complete', prefilter=None, symmetrize=True)

print("Running inference...")
output = inference(pairs, model, device, batch_size=1, verbose=True)

print("Global alignment...")
scene = global_aligner(output, device=device, mode=GlobalAlignerMode.PointCloudOptimizer, verbose=True)
loss = scene.compute_global_alignment(init='mst', niter=300, schedule='cosine', lr=0.01)
print(f"Loss: {loss}")

print("Extracting points...")
all_points = []
all_colors = []
for i in range(scene.n_imgs):
    pts3d = scene.get_pts3d()[i]
    conf = scene.im_conf[i]
    mask = conf > 3.0
    if mask.sum() > 0:
        pts = pts3d[mask].detach().cpu().numpy()
        colors = (scene.imgs[i][mask].detach().cpu().numpy() * 255).astype(np.uint8)
        all_points.append(pts)
        all_colors.append(colors)

if all_points:
    points = np.vstack(all_points)
    colors = np.vstack(all_colors)
    write_ply("vm_test_reconstruction.ply", points, colors)
    print(f"Saved {len(points):,} points to vm_test_reconstruction.ply")
EOF

python test_reconstruction.py
```

---

### Step 4: Verify Output on VM

```bash
# Check PLY file was created
ls -lh vm_test_reconstruction.ply

# Check captures directory
ls -lh captures/

# Get file sizes
du -sh captures/
du -sh *.ply
```

---

### Step 5: Download Results to Laptop

```bash
# From your laptop
scp your-vm:~/rdock-cv-pipeline/vm_test_reconstruction.ply ./

# Or download everything
scp -r your-vm:~/rdock-cv-pipeline/captures ./vm_captures/
scp your-vm:~/rdock-cv-pipeline/*.ply ./vm_outputs/
```

---

### Step 6: Visualize on Laptop

```bash
# On your laptop
cd /home/armaan/robodock-repos/rdock-cv-pipeline

# Visualize the VM reconstruction
python scripts/view_ply.py vm_test_reconstruction.ply

# Or if you have other PLY files
python scripts/view_ply.py vm_outputs/vm_test_reconstruction.ply
```

---

### Step 7: Commit VM Results (Optional)

```bash
# On the VM
git add captures/ *.ply
git commit -m "test: Add VM reconstruction results"
git push origin test/fetch-upload-s3-helper-script

# On laptop
git pull origin test/fetch-upload-s3-helper-script
```

---

## Directory Structure

### On VM After Testing:

```
rdock-cv-pipeline/
├── captures/
│   └── capture_20251004_HHMMSS/
│       ├── img_000.jpg
│       ├── img_001.jpg
│       └── ...
├── vm_test_reconstruction.ply
├── point_clouds/ (if using auto_reconstruction)
└── outputs/
```

### On Laptop After Download:

```
rdock-cv-pipeline/
├── vm_outputs/
│   └── vm_test_reconstruction.ply
├── vm_captures/
│   └── capture_20251004_HHMMSS/
│       └── *.jpg
```

---

## Quick Commands Summary

**On Laptop (push code):**
```bash
git add -A
git commit -m "feat: Ready for VM testing"
git push
```

**On VM (test):**
```bash
git clone <repo>
git checkout test/fetch-upload-s3-helper-script
git submodule update --init --recursive
conda activate rdock-cv
python scripts/realistic_reconstruction_simple.py -d 15 -i 2 -o vm_test.ply
```

**On Laptop (get results):**
```bash
scp vm:~/rdock-cv-pipeline/vm_test.ply ./
python scripts/view_ply.py vm_test.ply
```

---

## Performance Expectations

### GPU VM (RTX 3090/4090):
- Model loading: 10-20 seconds
- 7 images processing: 2-3 minutes
- Total time: ~3-4 minutes

### CPU (if no GPU):
- Model loading: 2-3 minutes
- 7 images processing: 20-30 minutes
- Total time: ~30-40 minutes

---

## Troubleshooting

### "CUDA out of memory"
- Reduce number of images
- Use smaller resolution
- Try CPU mode

### "Camera not found"
- Use Option B (upload test images)
- Or run headless with pre-captured images

### "Module not found"
- Activate conda environment: `conda activate rdock-cv`
- Check submodules: `git submodule update --init --recursive`

---

## Next Steps

After local VM testing works:
1. ✅ Verify reconstruction quality
2. ✅ Confirm captures are saved correctly
3. ✅ Test download/visualization workflow
4. Then add S3 integration

This validates your entire pipeline before adding cloud storage complexity!

