#!/usr/bin/env python3
"""
Process existing captures into PLY reconstruction
Run this on your VM where captures already exist
"""
import sys
import glob

# Add paths
sys.path.append('models/mast3r')
sys.path.append('.')

from scripts.realistic_reconstruction_simple import RealisticReconstructor

# Find your captures
capture_dir = 'captures/capture_20251004_191045'
images = sorted(glob.glob(f'{capture_dir}/*.jpg'))

if not images:
    print(f"❌ No images found in {capture_dir}")
    print("Available captures:")
    import os
    for d in os.listdir('captures'):
        print(f"  - captures/{d}")
    sys.exit(1)

print(f"📸 Found {len(images)} images in {capture_dir}")
print(f"   Images: {images[0]} ... {images[-1]}")

# Create reconstructor and process
print("\n" + "="*70)
print("🎬 STARTING RECONSTRUCTION")
print("="*70)

reconstructor = RealisticReconstructor()
result = reconstructor.reconstruct(images, 'vm_reconstruction.ply')

if result:
    print("\n" + "="*70)
    print("✅ SUCCESS!")
    print("="*70)
    print(f"📁 Output: {result}")
    print(f"\n📥 Download to laptop:")
    print(f"   scp vm:~/rdock-cv-pipeline/{result} ./")
    print(f"\n🎨 Visualize on laptop:")
    print(f"   python scripts/view_ply.py {result}")
else:
    print("\n❌ Reconstruction failed")
    sys.exit(1)

