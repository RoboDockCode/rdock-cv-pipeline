#!/usr/bin/env python3
"""
RealisticReconstructor class for MAST3R-based 3D reconstruction
Used by process_captures.py and infer_from_s3.py
"""
import sys
import os
import numpy as np
import torch
from datetime import datetime

# Fix CUDA linear algebra backend issue - use magma instead of cusolver
try:
    torch.backends.cuda.preferred_linalg_library('magma')
except RuntimeError:
    # If magma not available, fall back to CPU for linear algebra
    torch.backends.cuda.preferred_linalg_library('default')

# Add the project root and models directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'models', 'mast3r'))
sys.path.append(project_root)

from mast3r.model import AsymmetricMASt3R
from dust3r.utils.image import load_images
from dust3r.image_pairs import make_pairs
from dust3r.cloud_opt import global_aligner, GlobalAlignerMode
from dust3r.inference import inference
from frame_processing_pipeline.ply_utils import write_ply


class RealisticReconstructor:
    """Simplified realistic reconstructor using global alignment"""
    
    def __init__(self):
        print("Loading MAST3R for realistic reconstruction...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Print device info
        if self.device == 'cuda':
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"🎮 Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        else:
            print("⚠️  No GPU detected - using CPU (will be slow)")
        
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
        return inference(pairs, self.model, self.device, batch_size=64, verbose=False)

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

            # Use much lower confidence threshold
            conf_threshold = 1.0
            mask = conf > conf_threshold
            
            print(f"   Image {i+1}/{scene.n_imgs}: confidence range [{conf.min():.2f}, {conf.max():.2f}], {mask.sum()} points above {conf_threshold}")
            
            if mask.sum() == 0:
                continue

            # Move to CPU before applying mask to avoid CUDA tensor issues
            pts = pts3d[mask].detach().cpu().numpy()
            
            # Get image colors - handle both tensor and numpy array cases
            img = scene.imgs[i]
            if torch.is_tensor(img):
                img = img.detach().cpu().numpy()
            
            mask_cpu = mask.cpu() if torch.is_tensor(mask) else mask
            if torch.is_tensor(mask_cpu):
                mask_cpu = mask_cpu.numpy()
            
            colors = (img[mask_cpu] * 255).astype(np.uint8)
            
            # Filter out NaN and Inf values
            valid_mask = np.isfinite(pts).all(axis=1)
            pts_before = len(pts)
            pts = pts[valid_mask]
            colors = colors[valid_mask]
            
            if pts_before != len(pts):
                print(f"   Filtered {pts_before - len(pts)} NaN/Inf points")
            
            if len(pts) > 0:
                all_points.append(pts)
                all_colors.append(colors)

        if all_points:
            total_points = sum(len(p) for p in all_points)
            print(f"✅ Collected {total_points:,} total points from {len(all_points)} images")
            return np.vstack(all_points), np.vstack(all_colors)

        return None, None
    
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
