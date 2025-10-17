#!/usr/bin/env python3
"""
Quick test to verify SLAM integration works
Tests the SLAMReconstructor class with a simple image sequence
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from frame_processing_pipeline.slam_processor import SLAMReconstructor
    print("✅ Successfully imported SLAMReconstructor")
except ImportError as e:
    print(f"❌ Failed to import SLAMReconstructor: {e}")
    print("\nMake sure you've installed SLAM dependencies:")
    print("  ./install_slam.sh")
    sys.exit(1)


def test_slam_imports():
    """Test that all SLAM dependencies can be imported"""
    print("\n" + "=" * 50)
    print("Testing SLAM Dependencies")
    print("=" * 50)
    
    deps = [
        ('lietorch', 'lietorch'),
        ('MASt3R config', 'mast3r_slam.config'),
        ('MASt3R utils', 'mast3r_slam.mast3r_utils'),
        ('MASt3R tracker', 'mast3r_slam.tracker'),
        ('PLY file support', 'plyfile'),
    ]
    
    all_ok = True
    for name, module in deps:
        try:
            __import__(module)
            print(f"✅ {name}: OK")
        except ImportError as e:
            print(f"❌ {name}: FAILED - {e}")
            all_ok = False
    
    return all_ok


def test_slam_init():
    """Test that SLAM reconstructor can be initialized"""
    print("\n" + "=" * 50)
    print("Testing SLAM Reconstructor Initialization")
    print("=" * 50)
    
    try:
        reconstructor = SLAMReconstructor()
        if reconstructor.model is None:
            print("⚠️  Model loaded but is None (expected if checkpoints not downloaded)")
            return False
        print("✅ SLAM reconstructor initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_sample_images():
    """Test reconstruction with sample images if available"""
    print("\n" + "=" * 50)
    print("Testing SLAM Reconstruction")
    print("=" * 50)
    
    # Look for sample images in captures directory
    captures_dir = Path(project_root) / "captures"
    sample_dirs = []
    
    if captures_dir.exists():
        sample_dirs = [d for d in captures_dir.iterdir() if d.is_dir()]
    
    if not sample_dirs:
        print("⚠️  No sample images found in captures/ directory")
        print("To test with real data, add some images to captures/")
        return None
    
    # Use first available capture directory
    sample_dir = sample_dirs[0]
    images = sorted(sample_dir.glob("*.jpg"))
    
    if len(images) < 2:
        print(f"⚠️  Not enough images in {sample_dir} (need at least 2)")
        return None
    
    print(f"📁 Using {len(images)} images from {sample_dir.name}")
    
    # Create output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_ply = Path(temp_dir) / "test_reconstruction.ply"
        
        try:
            reconstructor = SLAMReconstructor()
            if reconstructor.model is None:
                print("⚠️  Cannot test reconstruction: model not loaded")
                print("Download MASt3R-SLAM checkpoints:")
                print("  mkdir -p models/mast3r-slam/checkpoints/")
                print("  wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth -P models/mast3r-slam/checkpoints/")
                return False
            
            print("\n🔄 Running SLAM reconstruction...")
            result = reconstructor.reconstruct([str(img) for img in images[:10]], str(output_ply))
            
            if result and result['success']:
                print(f"✅ Reconstruction succeeded!")
                print(f"   Points: {result['num_points']:,}")
                print(f"   Keyframes: {result['num_keyframes']}")
                print(f"   PLY: {result['ply']}")
                print(f"   Trajectory: {result['trajectory']}")
                return True
            else:
                print("❌ Reconstruction failed")
                return False
                
        except Exception as e:
            print(f"❌ Error during reconstruction: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run all tests"""
    print("=" * 50)
    print("MASt3R-SLAM Integration Test")
    print("=" * 50)
    
    results = {
        'imports': test_slam_imports(),
        'init': test_slam_init(),
        'reconstruction': test_with_sample_images(),
    }
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"{test_name:20s}: {status}")
    
    print("\n" + "=" * 50)
    
    if results['imports'] and results['init']:
        print("✅ SLAM integration is ready to use!")
        print("\nUsage:")
        print("  python scripts/infer_from_mp4.py --mode slam --fps 5")
    else:
        print("⚠️  SLAM integration needs setup")
        print("\nSetup steps:")
        print("1. Install dependencies:")
        print("     ./install_slam.sh")
        print("2. Download checkpoints:")
        print("     mkdir -p models/mast3r-slam/checkpoints/")
        print("     wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth -P models/mast3r-slam/checkpoints/")
    
    return 0 if all(r in [True, None] for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

