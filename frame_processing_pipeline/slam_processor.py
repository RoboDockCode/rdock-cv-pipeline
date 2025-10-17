#!/usr/bin/env python3
"""
SLAMReconstructor class for MASt3R-SLAM based 3D reconstruction
Compatible interface with RealisticReconstructor for drop-in replacement
"""
import sys
import os
import numpy as np
import torch
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Add the project root and models directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'models', 'mast3r-slam'))
sys.path.append(os.path.join(project_root, 'models', 'mast3r-slam', 'thirdparty', 'mast3r'))
sys.path.append(project_root)

import lietorch
from mast3r_slam.config import load_config, config, set_global_config
from mast3r_slam.dataloader import Intrinsics, ImageFolderDataset
from mast3r_slam.frame import Mode, SharedKeyframes, SharedStates, create_frame
from mast3r_slam.mast3r_utils import load_mast3r, load_retriever, mast3r_inference_mono
from mast3r_slam.tracker import FrameTracker
from mast3r_slam.global_opt import FactorGraph
from mast3r_slam.geometry import constrain_points_to_ray
from frame_processing_pipeline.ply_utils import write_ply


class SLAMReconstructor:
    """
    MASt3R-SLAM based reconstructor with interface compatible with RealisticReconstructor.
    
    Key differences from batch MASt3R:
    - Sequential processing (frame by frame)
    - Camera trajectory tracking
    - Better for long sequences (memory efficient)
    - Outputs: PLY + camera trajectory
    """
    
    def __init__(self, config_path=None):
        """
        Initialize MASt3R-SLAM processor
        
        Args:
            config_path: Path to SLAM config YAML (defaults to base.yaml)
        """
        print("Loading MASt3R-SLAM for sequential reconstruction...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Print device info
        if self.device == 'cuda':
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"🎮 Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        else:
            print("⚠️  No GPU detected - using CPU (will be slow)")
        
        # Load SLAM config
        if config_path is None:
            config_path = os.path.join(project_root, 'models', 'mast3r-slam', 'config', 'base.yaml')
        
        load_config(config_path)
        # Disable visualization and multiprocessing for headless GPU server
        config['single_thread'] = True
        set_global_config(config)
        
        # Load MASt3R model
        try:
            self.model = load_mast3r(device=self.device)
            print("✅ MASt3R-SLAM model loaded")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.model = None

    def reconstruct(self, image_files, output_name=None):
        """
        Create SLAM reconstruction with sequential processing
        
        Args:
            image_files: List of image file paths (in temporal order)
            output_name: Output PLY filename (default: slam_<timestamp>.ply)
            
        Returns:
            Dictionary with paths to outputs:
            {
                'ply': path to reconstruction PLY,
                'trajectory': path to camera trajectory file,
                'success': bool
            }
        """
        if self.model is None or len(image_files) < 2:
            return {'success': False, 'ply': None, 'trajectory': None}
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"slam_{timestamp}.ply"
        
        # Ensure output_name has .ply extension
        if not output_name.endswith('.ply'):
            output_base = output_name
            output_name = f"{output_base}.ply"
        else:
            output_base = output_name[:-4]
        
        trajectory_file = f"{output_base}_trajectory.txt"
        
        print(f"\n🔄 SLAM Reconstruction from {len(image_files)} images...")
        
        try:
            # Create temporary directory for dataset
            with tempfile.TemporaryDirectory() as temp_dir:
                # Copy images to temp directory with sequential naming
                temp_img_dir = Path(temp_dir) / "images"
                temp_img_dir.mkdir(exist_ok=True)
                
                print("📁 Preparing image sequence...")
                for i, img_path in enumerate(image_files):
                    ext = Path(img_path).suffix
                    dst = temp_img_dir / f"{i:06d}{ext}"
                    shutil.copy2(img_path, dst)
                
                # Load dataset
                dataset = ImageFolderDataset(str(temp_img_dir))
                dataset.subsample(config["dataset"]["subsample"])
                h, w = dataset.get_img_shape()[0]
                
                # Initialize shared states (using dummy manager for single-threaded)
                class DummyManager:
                    """Dummy manager for single-threaded SLAM"""
                    def list(self):
                        return []
                    def Value(self, *args, **kwargs):
                        return type('obj', (object,), {'value': args[1] if len(args) > 1 else 0})()
                    def Lock(self):
                        return type('obj', (object,), {
                            '__enter__': lambda s: None,
                            '__exit__': lambda s, *a: None
                        })()
                
                manager = DummyManager()
                keyframes = SharedKeyframes(manager, h, w)
                states = SharedStates(manager, h, w)
                
                # Initialize factor graph
                K = None
                factor_graph = FactorGraph(self.model, keyframes, K, self.device)
                retrieval_database = load_retriever(self.model)
                
                # Initialize tracker
                tracker = FrameTracker(self.model, keyframes, self.device)
                
                # Process frames sequentially
                print("🎥 Processing frames...")
                mode = Mode.INIT
                
                for i in range(len(dataset)):
                    if i % 10 == 0:
                        print(f"   Frame {i+1}/{len(dataset)}...")
                    
                    timestamp, img = dataset[i]
                    
                    # Create frame
                    T_WC = (
                        lietorch.Sim3.Identity(1, device=self.device)
                        if i == 0
                        else keyframes[len(keyframes) - 1].T_WC
                    )
                    frame = create_frame(i, img, T_WC, img_size=dataset.img_size, device=self.device)
                    
                    if mode == Mode.INIT:
                        # Initialize with first frame
                        X_init, C_init = mast3r_inference_mono(self.model, frame)
                        frame.update_pointmap(X_init, C_init)
                        keyframes.append(frame)
                        mode = Mode.TRACKING
                        continue
                    
                    if mode == Mode.TRACKING:
                        add_new_kf, match_info, try_reloc = tracker.track(frame)
                        
                        if try_reloc:
                            # Relocalization needed
                            X, C = mast3r_inference_mono(self.model, frame)
                            frame.update_pointmap(X, C)
                            
                            # Try relocalization
                            keyframes.append(frame)
                            n_kf = len(keyframes)
                            retrieval_inds = retrieval_database.update(
                                frame,
                                add_after_query=False,
                                k=config["retrieval"]["k"],
                                min_thresh=config["retrieval"]["min_thresh"],
                            )
                            
                            if retrieval_inds:
                                kf_idx = list(retrieval_inds)
                                frame_idx = [n_kf - 1] * len(kf_idx)
                                
                                if factor_graph.add_factors(
                                    frame_idx,
                                    kf_idx,
                                    config["reloc"]["min_match_frac"],
                                    is_reloc=config["reloc"]["strict"],
                                ):
                                    retrieval_database.update(
                                        frame,
                                        add_after_query=True,
                                        k=config["retrieval"]["k"],
                                        min_thresh=config["retrieval"]["min_thresh"],
                                    )
                                    keyframes.T_WC[n_kf - 1] = keyframes.T_WC[kf_idx[0]].clone()
                                    
                                    if config["use_calib"]:
                                        factor_graph.solve_GN_calib()
                                    else:
                                        factor_graph.solve_GN_rays()
                                else:
                                    keyframes.pop_last()
                        
                        if add_new_kf:
                            keyframes.append(frame)
                            idx = len(keyframes) - 1
                            
                            # Add factors and optimize
                            kf_idx = []
                            if idx > 0:
                                kf_idx.append(idx - 1)
                            
                            retrieval_inds = retrieval_database.update(
                                frame,
                                add_after_query=True,
                                k=config["retrieval"]["k"],
                                min_thresh=config["retrieval"]["min_thresh"],
                            )
                            kf_idx += retrieval_inds
                            
                            kf_idx = set(kf_idx)
                            kf_idx.discard(idx)
                            kf_idx = list(kf_idx)
                            frame_idx = [idx] * len(kf_idx)
                            
                            if kf_idx:
                                factor_graph.add_factors(
                                    kf_idx, frame_idx, config["local_opt"]["min_match_frac"]
                                )
                            
                            if config["use_calib"]:
                                factor_graph.solve_GN_calib()
                            else:
                                factor_graph.solve_GN_rays()
                
                print(f"✅ Processed {len(keyframes)} keyframes")
                
                # Extract point cloud and trajectory
                print("🎨 Extracting point cloud...")
                all_points = []
                all_colors = []
                c_conf_threshold = 1.5  # Confidence threshold
                
                for i in range(len(keyframes)):
                    keyframe = keyframes[i]
                    if config["use_calib"]:
                        X_canon = constrain_points_to_ray(
                            keyframe.img_shape.flatten()[:2], 
                            keyframe.X_canon[None], 
                            keyframe.K
                        )
                        keyframe.X_canon = X_canon.squeeze(0)
                    
                    pW = keyframe.T_WC.act(keyframe.X_canon).cpu().numpy().reshape(-1, 3)
                    color = (keyframe.uimg.cpu().numpy() * 255).astype(np.uint8).reshape(-1, 3)
                    valid = (
                        keyframe.get_average_conf().cpu().numpy().astype(np.float32).reshape(-1)
                        > c_conf_threshold
                    )
                    
                    all_points.append(pW[valid])
                    all_colors.append(color[valid])
                
                points = np.concatenate(all_points, axis=0)
                colors = np.concatenate(all_colors, axis=0)
                
                # Save point cloud
                write_ply(output_name, points, colors)
                print(f"💾 Saved PLY: {output_name} ({len(points):,} points)")
                
                # Save trajectory
                print("📍 Saving camera trajectory...")
                with open(trajectory_file, 'w') as f:
                    for i in range(len(keyframes)):
                        keyframe = keyframes[i]
                        T_WC = keyframe.T_WC
                        # Extract pose (translation + quaternion)
                        pose_data = T_WC.data.cpu().numpy().reshape(-1)
                        # Format: frame_id x y z qx qy qz qw
                        f.write(f"{keyframe.frame_id} ")
                        f.write(" ".join(f"{v:.6f}" for v in pose_data[:7]))
                        f.write("\n")
                
                print(f"💾 Saved trajectory: {trajectory_file} ({len(keyframes)} poses)")
                
                return {
                    'success': True,
                    'ply': output_name,
                    'trajectory': trajectory_file,
                    'num_points': len(points),
                    'num_keyframes': len(keyframes)
                }
        
        except Exception as e:
            print(f"❌ SLAM reconstruction failed: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'ply': None, 'trajectory': None}

