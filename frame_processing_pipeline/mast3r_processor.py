"""Simplified MAST3R processing pipeline"""
import cv2 as cv
import numpy as np
import torch
import sys
import os
import tempfile
from PIL import Image

# Add MAST3R to path
sys.path.append('/home/armaan/robodock-repos/rdock-cv-pipeline/models/mast3r')

from mast3r.model import AsymmetricMASt3R
import mast3r.utils.path_to_dust3r  # noqa
from dust3r.utils.image import load_images
from dust3r.inference import inference

from .ply_utils import write_ply


class MAST3RProcessor:
    """Simplified MAST3R processor for 3D reconstruction"""
    
    def __init__(self, model_name="MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric"):
        """Initialize MAST3R model"""
        print("Loading MAST3R model...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {self.device}")
        
        try:
            self.model = AsymmetricMASt3R.from_pretrained(f"naver/{model_name}").to(self.device)
            self.model.eval()
            print("✅ MAST3R model loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.model = None
    
    def process_frame_pair(self, frame1, frame2):
        """
        Process a pair of frames with MAST3R
        
        Args:
            frame1: First frame (BGR format)
            frame2: Second frame (BGR format)
            
        Returns:
            Dictionary with 'pred1' and 'pred2' results, or None if failed
        """
        if self.model is None:
            return None
        
        try:
            # Convert BGR to RGB
            frame1_rgb = cv.cvtColor(frame1, cv.COLOR_BGR2RGB)
            frame2_rgb = cv.cvtColor(frame2, cv.COLOR_BGR2RGB)
            
            # Save frames temporarily (MAST3R expects file paths)
            with tempfile.TemporaryDirectory() as temp_dir:
                img1_path = os.path.join(temp_dir, "frame1.jpg")
                img2_path = os.path.join(temp_dir, "frame2.jpg")
                
                Image.fromarray(frame1_rgb).save(img1_path)
                Image.fromarray(frame2_rgb).save(img2_path)
                
                # Load images in DUSt3R format
                imgs = load_images([img1_path, img2_path], size=512, verbose=False)
                
                if len(imgs) < 2:
                    return None
                
                # Create pairs and run inference
                pairs = [(imgs[0], imgs[1])]
                
                with torch.no_grad():
                    results = inference(pairs, self.model, self.device, batch_size=1, verbose=False)
                    return results
                    
        except Exception as e:
            print(f"❌ Processing error: {e}")
            return None
    
    def extract_point_cloud(self, results, original_frame, conf_threshold=2.0):
        """
        Extract 3D point cloud from MAST3R results
        
        Args:
            results: MAST3R inference results
            original_frame: Original frame for color information (BGR)
            conf_threshold: Minimum confidence threshold
            
        Returns:
            (points, colors, confidences) tuple or (None, None, None) if failed
        """
        try:
            # Get the first view's prediction
            if isinstance(results, dict) and 'pred1' in results:
                pred = results['pred1']
            elif isinstance(results, (list, tuple)):
                pred = results[0]
            else:
                return None, None, None
            
            # Extract 3D points
            if 'pts3d' not in pred:
                return None, None, None
            
            pts3d = pred['pts3d']
            conf = pred.get('conf', None)
            
            # Convert tensors to numpy
            if len(pts3d.shape) == 4:
                pts3d_np = pts3d[0].cpu().numpy()  # [H, W, 3]
            else:
                pts3d_np = pts3d.cpu().numpy()
            
            if conf is not None:
                if len(conf.shape) == 3:
                    conf_np = conf[0].cpu().numpy()  # [H, W]
                else:
                    conf_np = conf.cpu().numpy()
            else:
                conf_np = np.ones(pts3d_np.shape[:2])
            
            # Get colors from original frame
            h, w = pts3d_np.shape[:2]
            frame_resized = cv.resize(original_frame, (w, h))
            frame_rgb = cv.cvtColor(frame_resized, cv.COLOR_BGR2RGB)
            
            # Flatten arrays
            points = pts3d_np.reshape(-1, 3)
            colors = frame_rgb.reshape(-1, 3)
            confidences = conf_np.reshape(-1)
            
            # Filter by confidence
            valid_mask = confidences > conf_threshold
            points = points[valid_mask]
            colors = colors[valid_mask]
            confidences = confidences[valid_mask]
            
            return points, colors, confidences
            
        except Exception as e:
            print(f"❌ Point cloud extraction error: {e}")
            return None, None, None
    
    def save_point_cloud(self, results, frame, frame_id, output_dir="point_clouds", conf_threshold=2.0):
        """
        Save point cloud from MAST3R results as PLY file
        
        Args:
            results: MAST3R inference results
            frame: Original frame for colors (BGR)
            frame_id: Frame identifier
            output_dir: Directory to save PLY files
            conf_threshold: Minimum confidence threshold
            
        Returns:
            Path to saved PLY file, or None if failed
        """
        os.makedirs(output_dir, exist_ok=True)
        
        points, colors, confidences = self.extract_point_cloud(results, frame, conf_threshold)
        
        if points is None or len(points) == 0:
            return None
        
        ply_filename = os.path.join(output_dir, f"frame_{frame_id:06d}.ply")
        write_ply(ply_filename, points, colors, confidences)
        
        print(f"💾 Saved {len(points):,} points to {ply_filename}")
        return ply_filename
    
    def visualize_depth(self, results):
        """
        Visualize depth map from MAST3R results
        
        Args:
            results: MAST3R inference results
            
        Returns:
            Colored depth visualization (BGR) or None
        """
        try:
            # Get the first view's prediction
            if isinstance(results, dict) and 'pred1' in results:
                pred = results['pred1']
            elif isinstance(results, (list, tuple)):
                pred = results[0]
            else:
                return None
            
            if 'pts3d' not in pred:
                return None
            
            pts3d = pred['pts3d']
            
            # Convert to numpy
            if len(pts3d.shape) == 4:
                pts3d_np = pts3d[0].cpu().numpy()
            else:
                pts3d_np = pts3d.cpu().numpy()
            
            # Extract depth (Z component)
            depth_map = pts3d_np[:, :, 2]
            
            # Handle NaN and infinite values
            depth_clean = np.nan_to_num(depth_map, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Normalize and colorize
            if depth_clean.max() > depth_clean.min():
                depth_normalized = cv.normalize(depth_clean, None, 0, 255, cv.NORM_MINMAX)
                depth_colored = cv.applyColorMap(depth_normalized.astype(np.uint8), cv.COLORMAP_JET)
                return depth_colored
            
            return None
            
        except Exception as e:
            print(f"❌ Depth visualization error: {e}")
            return None

