"""Optimized MASt3R processing (RAM-safe, MASt3R-only)."""
import cv2 as cv
import numpy as np
import torch
import sys
import os
import gc
import tempfile
from PIL import Image

# Add MAST3R to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(project_root, 'models', 'mast3r'))

from mast3r.model import AsymmetricMASt3R
import mast3r.utils.path_to_dust3r  # noqa
from dust3r.utils.image import load_images
from dust3r.inference import inference

from .ply_utils import write_ply


class MAST3RProcessor:
    """MASt3R processor optimized to bound system RAM on long captures (no SLAM)."""

    def __init__(self, model_name="MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric"):
        print("Loading MASt3R model...")
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {self.device}")

        try:
            self.model = AsymmetricMASt3R.from_pretrained(f"naver/{model_name}").to(self.device)
            self.model.eval()
            # Optional: channels-last helps memory locality on GPU (safe to keep)
            if self.device == 'cuda':
                for m in self.model.modules():
                    if isinstance(m, torch.nn.Conv2d):
                        m.to(memory_format=torch.channels_last)
            print("✅ MASt3R model loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            self.model = None

    # ---------- helpers ----------
    @staticmethod
    def _get_primary_prediction(results):
        if isinstance(results, dict):
            return results.get('pred1') or results.get('pred2')
        if isinstance(results, (list, tuple)) and results:
            cand = results[0]
            if isinstance(cand, dict):
                return cand
        return None

    @staticmethod
    def _tensor_to_numpy(tensor, dtype=None):
        """Detach->CPU->numpy, drop batch, enforce dtype without extra copy when possible."""
        if tensor is None:
            return None
        if isinstance(tensor, np.ndarray):
            return tensor.astype(dtype, copy=False) if dtype else tensor
        if not torch.is_tensor(tensor):
            return None
        arr = tensor.detach().cpu().numpy()
        if arr.ndim == 4:
            arr = arr[0]
        elif arr.ndim == 3 and arr.shape[0] == 1:
            arr = arr[0]
        if dtype:
            arr = arr.astype(dtype, copy=False)
        return arr

    @staticmethod
    def _encode_temp_jpeg(rgb, path, quality=90):
        # PIL is fine; keep memory small by not making extra copies
        Image.fromarray(rgb).save(path, quality=quality, subsampling=1, optimize=True)

    # ---------- main one-shot path ----------
    def process_pair_to_ply(self,
                            frame1_bgr: np.ndarray,
                            frame2_bgr: np.ndarray,
                            frame_id: int,
                            output_dir: str = "point_clouds",
                            size: int = 512,
                            conf_threshold: float = 2.0,
                            use_autocast: bool = False):
        """
        Run MASt3R on a single pair and immediately write a PLY.
        Returns PLY path or None. Keeps RAM bounded by scoping and hard cleanup.
        """
        if self.model is None:
            return None

        os.makedirs(output_dir, exist_ok=True)
        ply_path = None

        # Convert once; keep uint8 on CPU
        f1_rgb = cv.cvtColor(frame1_bgr, cv.COLOR_BGR2RGB)
        f2_rgb = cv.cvtColor(frame2_bgr, cv.COLOR_BGR2RGB)

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                p1 = os.path.join(temp_dir, "f1.jpg")
                p2 = os.path.join(temp_dir, "f2.jpg")
                self._encode_temp_jpeg(f1_rgb, p1)
                self._encode_temp_jpeg(f2_rgb, p2)

                imgs = load_images([p1, p2], size=size, verbose=False)
                if len(imgs) < 2:
                    return None

                pairs = [(imgs[0], imgs[1])]

                # Inference with minimal buffers
                torch.set_grad_enabled(False)
                if use_autocast and self.device == 'cuda':
                    autocast_ctx = torch.autocast(device_type='cuda', dtype=torch.bfloat16)
                else:
                    # no-op context manager
                    from contextlib import nullcontext
                    autocast_ctx = nullcontext()

                with torch.inference_mode(), autocast_ctx:
                    results = inference(
                        pairs, self.model, self.device,
                        batch_size=64, verbose=False
                    )

                # Extract minimal outputs and discard everything else
                pred = self._get_primary_prediction(results)
                if not pred or ('pts3d' not in pred):
                    return None

                # Enforce small dtypes on CPU
                pts3d = self._tensor_to_numpy(pred['pts3d'], dtype=np.float32)
                if pts3d is None:
                    return None
                conf = self._tensor_to_numpy(pred.get('conf'), dtype=np.float32)
                if conf is None:
                    conf = np.ones(pts3d.shape[:2], dtype=np.float32)

                # Colors from first frame only; match pts3d resolution
                h, w = pts3d.shape[:2]
                f1_small = cv.resize(frame1_bgr, (w, h))
                f1_small_rgb = cv.cvtColor(f1_small, cv.COLOR_BGR2RGB)

                # Flatten views (views = lightweight if we avoid copies)
                points = pts3d.reshape(-1, 3)                          # float32
                colors = f1_small_rgb.reshape(-1, 3).astype(np.uint8, copy=False)
                conf1d = conf.reshape(-1)                              # float32

                # Confidence + finiteness mask
                finite = np.isfinite(points).all(axis=1)
                valid = (conf1d > conf_threshold) & finite
                if not np.any(valid):
                    return None

                # Boolean indexing creates compact arrays; still fine, then immediately write
                points = points[valid]
                colors = colors[valid]
                conf1d = conf1d[valid]

                ply_path = os.path.join(output_dir, f"frame_{frame_id:06d}.ply")
                write_ply(ply_path, points, colors, conf1d)  # ensure writer uses float32 for points/conf

        finally:
            # Hard cleanup to avoid slow RAM creep across many pairs
            for v in ('results', 'pred', 'pts3d', 'conf', 'points', 'colors',
                      'conf1d', 'imgs', 'pairs', 'f1_small', 'f1_small_rgb',
                      'f1_rgb', 'f2_rgb'):
                if v in locals():
                    del locals()[v]
            gc.collect()
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

        if ply_path:
            print(f"💾 Saved PLY → {ply_path}")
        return ply_path

    # Optional: keep your depth viz function, but make it local-scope-safe
    def visualize_depth(self, results):
        try:
            pred = self._get_primary_prediction(results)
            if not pred or ('pts3d' not in pred):
                return None
            pts3d = self._tensor_to_numpy(pred['pts3d'], dtype=np.float32)
            if pts3d is None:
                return None
            depth = pts3d[:, :, 2]
            depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
            if depth.max() <= depth.min():
                return None
            depth_norm = cv.normalize(depth, None, 0, 255, cv.NORM_MINMAX)
            return cv.applyColorMap(depth_norm.astype(np.uint8), cv.COLORMAP_JET)
        except Exception as e:
            print(f"❌ Depth visualization error: {e}")
            return None
