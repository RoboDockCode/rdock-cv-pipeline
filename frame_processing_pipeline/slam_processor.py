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
from datetime import datetime
from pathlib import Path

# Add the project root and models directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'models', 'mast3r-slam'))
sys.path.append(os.path.join(project_root, 'models', 'mast3r-slam', 'thirdparty', 'mast3r'))
sys.path.append(project_root)

import lietorch
from mast3r_slam.config import load_config, config, set_global_config
from mast3r_slam.dataloader import Intrinsics, MP4Dataset
from mast3r_slam.frame import Mode, SharedKeyframes, SharedStates, create_frame
from mast3r_slam.mast3r_utils import load_mast3r, load_retriever, mast3r_inference_mono
from mast3r_slam.tracker import FrameTracker
from mast3r_slam.global_opt import FactorGraph
from mast3r_slam.geometry import constrain_points_to_ray
from frame_processing_pipeline.ply_utils import write_ply


class SLAMReconstructor:
    """MASt3R-SLAM based reconstructor"""
    
    def __init__(self, config_path=None):
        """Initialize MASt3R-SLAM processor"""
        print("Loading MASt3R-SLAM for sequential reconstruction...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
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
        Create SLAM reconstruction
        
        Args:
            image_files: List containing single MP4 path: ['/path/to/video.mp4']
            output_name: Output PLY filename
            
        Returns:
            Dictionary with paths to outputs
        """
        if self.model is None:
            return {'success': False, 'ply': None, 'trajectory': None}
        
        if output_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"slam_{timestamp}.ply"
        
        if not output_name.endswith('.ply'):
            output_base = output_name
            output_name = f"{output_base}.ply"
        else:
            output_base = output_name[:-4]
        
        trajectory_file = f"{output_base}_trajectory.txt"
        
        print(f"\n🔄 SLAM Reconstruction from video...")
        
        try:
            # Convert JPG frames to PNG for RGBFiles
            if len(image_files) < 2:
                print(f"❌ Need at least 2 frames, got {len(image_files)}")
                return {'success': False, 'ply': None, 'trajectory': None}
            
            print(f"📁 Converting {len(image_files)} frames to PNG...")
            from PIL import Image
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix='slam_frames_')
            
            for img_path in image_files:
                img = Image.open(img_path)
                png_name = Path(img_path).stem + '.png'
                img.save(Path(temp_dir) / png_name)
            
            print(f"   Saved to: {temp_dir}")
            
            # Use RGBFiles dataset
            from mast3r_slam.dataloader import RGBFiles
            dataset = RGBFiles(temp_dir)
            dataset.subsample(config["dataset"]["subsample"])
            h, w = dataset.get_img_shape()[0]
            
            # RGBFiles knows its length from the PNG files
            dataset_len = len(dataset)
            
            print(f"   Video: {dataset_len} frames, {h}x{w}")
            
            # Dummy manager for single-threaded
            class DummyManager:
                def list(self):
                    return []
                def Value(self, *args, **kwargs):
                    return type('obj', (object,), {'value': args[1] if len(args) > 1 else 0})()
                def Lock(self):
                    return type('obj', (object,), {
                        '__enter__': lambda s: None,
                        '__exit__': lambda s, *a: None
                    })()
                def RLock(self):
                    return type('obj', (object,), {
                        '__enter__': lambda s: None,
                        '__exit__': lambda s, *a: None
                    })()
            
            manager = DummyManager()
            keyframes = SharedKeyframes(manager, h, w)
            states = SharedStates(manager, h, w)
            
            # Initialize
            K = None
            factor_graph = FactorGraph(self.model, keyframes, K, self.device)
            retrieval_database = load_retriever(self.model)
            tracker = FrameTracker(self.model, keyframes, self.device)
            
            # Process frames
            print("🎥 Processing frames...")
            mode = Mode.INIT
            
            for i in range(dataset_len):
                if i % 10 == 0:
                    print(f"   Frame {i+1}/{dataset_len}...")
                
                try:
                    timestamp, img = dataset[i]
                except (ValueError, RuntimeError) as e:
                    print(f"   Skipping frame {i} (read error: {e})")
                    continue
                
                T_WC = (
                    lietorch.Sim3.Identity(1, device=self.device)
                    if i == 0
                    else keyframes[len(keyframes) - 1].T_WC
                )
                frame = create_frame(i, img, T_WC, img_size=dataset.img_size, device=self.device)
                
                if mode == Mode.INIT:
                    X_init, C_init = mast3r_inference_mono(self.model, frame)
                    frame.update_pointmap(X_init, C_init)
                    keyframes.append(frame)
                    mode = Mode.TRACKING
                    continue
                
                if mode == Mode.TRACKING:
                    add_new_kf, match_info, try_reloc = tracker.track(frame)
                    
                    if try_reloc:
                        X, C = mast3r_inference_mono(self.model, frame)
                        frame.update_pointmap(X, C)
                        keyframes.append(frame)
                        n_kf = len(keyframes)
                        
                        retrieval_inds = retrieval_database.update(
                            frame, add_after_query=False,
                            k=config["retrieval"]["k"],
                            min_thresh=config["retrieval"]["min_thresh"],
                        )
                        
                        if retrieval_inds:
                            kf_idx = list(retrieval_inds)
                            frame_idx = [n_kf - 1] * len(kf_idx)
                            
                            if factor_graph.add_factors(
                                frame_idx, kf_idx,
                                config["reloc"]["min_match_frac"],
                                is_reloc=config["reloc"]["strict"],
                            ):
                                retrieval_database.update(
                                    frame, add_after_query=True,
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
                        
                        kf_idx = []
                        if idx > 0:
                            kf_idx.append(idx - 1)
                        
                        retrieval_inds = retrieval_database.update(
                            frame, add_after_query=True,
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
            
            # Extract point cloud
            print("🎨 Extracting point cloud...")
            all_points = []
            all_colors = []
            c_conf_threshold = 1.5
            
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
            
            # Save
            write_ply(output_name, points, colors)
            print(f"💾 Saved PLY: {output_name} ({len(points):,} points)")
            
            # Save trajectory
            print("📍 Saving camera trajectory...")
            with open(trajectory_file, 'w') as f:
                for i in range(len(keyframes)):
                    keyframe = keyframes[i]
                    T_WC = keyframe.T_WC
                    pose_data = T_WC.data.cpu().numpy().reshape(-1)
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
