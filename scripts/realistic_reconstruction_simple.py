#!/usr/bin/env python3
"""
Simplified realistic 3D reconstruction using MAST3R global alignment
"""
import cv2 as cv
import sys
import os
import time
import tempfile
import shutil
import numpy as np
import torch
from datetime import datetime

# Fix CUDA linear algebra backend issue - use magma instead of cusolver
try:
    torch.backends.cuda.preferred_linalg_library('magma')
except RuntimeError:
    # If magma not available, fall back to CPU for linear algebra
    torch.backends.cuda.preferred_linalg_library('default')

sys.path.append('/home/armaan/robodock-repos/rdock-cv-pipeline/models/mast3r')

from mast3r.model import AsymmetricMASt3R
from dust3r.utils.image import load_images
from dust3r.image_pairs import make_pairs
from dust3r.cloud_opt import global_aligner, GlobalAlignerMode
from dust3r.inference import inference

sys.path.append('/home/armaan/robodock-repos/rdock-cv-pipeline')
from frame_processing_pipeline.camera_utils import open_camera
from frame_processing_pipeline.ply_utils import write_ply


class RealisticReconstructor:
    """Simplified realistic reconstructor using global alignment"""
    
    def __init__(self):
        print("Loading MAST3R for realistic reconstruction...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        try:
            model_name = "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric"
            self.model = AsymmetricMASt3R.from_pretrained(f"naver/{model_name}").to(self.device)
            self.model.eval()
            print("✅ Model loaded")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.model = None

    @staticmethod
    def _prepare_inputs(image_files):
        """Load images and create inference pairs."""
        print("📖 Loading images...")
        imgs = load_images(image_files, size=512, verbose=False)

        print("🔗 Creating pairs...")
        pairs = make_pairs(imgs, scene_graph='complete', prefilter=None, symmetrize=True)
        return imgs, pairs

    def _run_inference(self, pairs):
        """Run MAST3R inference for the prepared pairs."""
        print("🧠 Running inference...")
        return inference(pairs, self.model, self.device, batch_size=1, verbose=False)

    def _align_scene(self, inference_output, n_imgs):
        """Apply global alignment and optional optimization."""
        print("🌍 Global alignment...")
        mode = GlobalAlignerMode.PointCloudOptimizer if n_imgs > 2 else GlobalAlignerMode.PairViewer
        scene = global_aligner(inference_output, device=self.device, mode=mode, verbose=False)

        if mode == GlobalAlignerMode.PointCloudOptimizer:
            print("⚙️  Optimizing...")
            loss = scene.compute_global_alignment(init='mst', niter=300, schedule='cosine', lr=0.01)
            print(f"Final loss: {loss:.6f}")

        return scene

    @staticmethod
    def _collect_point_cloud(scene):
        """Extract merged point cloud data from the aligned scene."""
        print("🎨 Extracting point cloud...")
        all_points = []
        all_colors = []

        for i in range(scene.n_imgs):
            pts3d = scene.get_pts3d()[i]
            conf = scene.im_conf[i]

            mask = conf > 3.0
            if mask.sum() == 0:
                continue

            # Move to CPU before applying mask to avoid CUDA tensor issues
            pts = pts3d[mask].detach().cpu().numpy()
            
            # Get image colors - ensure on CPU before indexing
            img = scene.imgs[i].detach().cpu()
            mask_cpu = mask.cpu()
            colors = (img[mask_cpu].numpy() * 255).astype(np.uint8)

            all_points.append(pts)
            all_colors.append(colors)

        if all_points:
            return np.vstack(all_points), np.vstack(all_colors)

        return None, None

    def capture_images(self, duration=30, interval=2.0):
        """Capture image sequence for reconstruction"""
        print(f"📸 Capturing for {duration}s (every {interval}s)")

        temp_dir = tempfile.mkdtemp(prefix='mast3r_')
        cap = open_camera()
        if cap is None:
            return None
        
        captured = []
        start_time = time.time()
        last_capture = 0
        
        print("🎥 Move camera around the scene! Press 'q' to stop")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                current = time.time()
                elapsed = current - start_time
                
                if elapsed >= duration:
                    break
                
                cv.imshow("Capturing - Press 'q' to stop", frame)
                
                # Capture at intervals
                if current - last_capture >= interval:
                    img_path = os.path.join(temp_dir, f"img_{len(captured):03d}.jpg")
                    cv.imwrite(img_path, frame)
                    captured.append(img_path)
                    last_capture = current
                    
                    progress = (elapsed / duration) * 100
                    print(f"📸 Image {len(captured)} ({progress:.1f}%)")
                
                if cv.waitKey(1) & 0xFF == ord('q'):
                    print("⏹️  Stopped early")
                    break
                    
        except KeyboardInterrupt:
            print("⏹️  Interrupted")
        finally:
            cap.release()
            cv.destroyAllWindows()
        
        print(f"✅ Captured {len(captured)} images")
        return captured if len(captured) >= 2 else None
    
    def reconstruct(self, image_files, output_name=None):
        """Create realistic reconstruction with global alignment"""
        if self.model is None or len(image_files) < 2:
            return None
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"realistic_{timestamp}.ply"
        
        print(f"\n🔄 Reconstructing from {len(image_files)} images...")
        
        try:
            imgs, pairs = self._prepare_inputs(image_files)
            inference_output = self._run_inference(pairs)
            scene = self._align_scene(inference_output, len(imgs))
            points, colors = self._collect_point_cloud(scene)

            if points is not None and colors is not None:
                write_ply(output_name, points, colors)
                print(f"✅ Saved: {output_name} ({len(points):,} points)")
                return output_name

            return None

        except Exception as e:
            print(f"❌ Reconstruction failed: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Realistic 3D Reconstruction')
    parser.add_argument('--duration', '-d', type=int, default=30,
                       help='Capture duration (default: 30s)')
    parser.add_argument('--interval', '-i', type=float, default=2.0,
                       help='Capture interval (default: 2.0s)')
    parser.add_argument('--output', '-o', type=str,
                       help='Output filename')
    
    args = parser.parse_args()
    
    print("🎬 REALISTIC 3D RECONSTRUCTION")
    print("="*50)
    
    reconstructor = RealisticReconstructor()
    if reconstructor.model is None:
        print("❌ Failed to load model")
        return
    
    # Capture images
    images = reconstructor.capture_images(args.duration, args.interval)
    if not images:
        print("❌ Failed to capture images")
        return
    
    # Reconstruct
    result = reconstructor.reconstruct(images, args.output)
    
    if result:
        print("\n" + "="*50)
        print("🎉 SUCCESS!")
        print("="*50)
        print(f"📁 File: {result}")
        print(f"\n🎨 Visualize: python view_ply.py {result}")
    else:
        print("❌ Reconstruction failed")
    
    # Cleanup
    if images:
        temp_dir = os.path.dirname(images[0])
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
