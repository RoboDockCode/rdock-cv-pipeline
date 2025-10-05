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
    
    # Upload to S3
    print("\n" + "="*70)
    print("📤 UPLOADING TO S3")
    print("="*70)
    
    try:
        import boto3
        from datetime import datetime
        
        s3 = boto3.client('s3')
        bucket_name = 'frame-storage'
        job_id = capture_dir.split('/')[-1].replace('capture_', 'job_')
        s3_key = f"output/{job_id}/reconstruction.ply"
        
        print(f"📤 Uploading to s3://{bucket_name}/{s3_key}")
        s3.upload_file(result, bucket_name, s3_key)
        
        print(f"✅ Upload complete!")
        print(f"\n📥 Download on laptop:")
        print(f"   aws s3 cp s3://{bucket_name}/{s3_key} ./")
        print(f"\n🎨 Then visualize:")
        print(f"   python scripts/view_ply.py reconstruction.ply")
        
    except ImportError:
        print("⚠️  boto3 not installed - skipping S3 upload")
        print(f"\n📥 Download to laptop:")
        print(f"   scp vm:~/rdock-cv-pipeline/{result} ./")
    except Exception as e:
        print(f"⚠️  S3 upload failed: {e}")
        print("💡 Configure AWS credentials with:")
        print("   export AWS_ACCESS_KEY_ID='your-key'")
        print("   export AWS_SECRET_ACCESS_KEY='your-secret'")
        print(f"\n📥 Alternative - Download to laptop:")
        print(f"   scp vm:~/rdock-cv-pipeline/{result} ./")
else:
    print("\n❌ Reconstruction failed")
    sys.exit(1)

