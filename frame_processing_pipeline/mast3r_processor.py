"""Optimized MASt3R processing (RAM-safe, MASt3R-only) with multi-process runner."""
import cv2 as cv
import numpy as np
import torch
import sys
import os
import gc
import glob
import multiprocessing as mp
from contextlib import nullcontext
import tempfile
from PIL import Image

# Optional: lightweight RSS logging (safe if psutil missing)
try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False

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

    def __init__(
        self,
        model_name: str = "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric",
        device_id: int | None = None
    ):
        print("Loading MASt3R model...")
        # Pin to the requested GPU (if any) before touching CUDA context
        if torch.cuda.is_available():
            if device_id is not None:
                torch.cuda.set_device(device_id)
                self.device = f"cuda:{device_id}"
            else:
                self.device = "cuda"
        else:
            self.device = "cpu"
        print(f"Using device: {self.device}")

        try:
            self.model = AsymmetricMASt3R.from_pretrained(f"naver/{model_name}").to(self.device)
            self.model.eval()
            # Optional: channels-last for better memory locality
            if self.device.startswith("cuda"):
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

    # ---------- main one-shot: arrays -> PLY ----------
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
                autocast_ctx = (
                    torch.autocast(device_type='cuda', dtype=torch.bfloat16)
                    if (use_autocast and self.device.startswith("cuda"))
                    else nullcontext()
                )
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

                # Flatten
                points = pts3d.reshape(-1, 3)                          # float32
                colors = f1_small_rgb.reshape(-1, 3).astype(np.uint8, copy=False)
                conf1d = conf.reshape(-1)                              # float32

                # Confidence + finiteness mask
                finite = np.isfinite(points).all(axis=1)
                valid = (conf1d > conf_threshold) & finite
                if not np.any(valid):
                    return None

                points = points[valid].astype(np.float32, copy=False)
                colors = colors[valid]
                conf1d = conf1d[valid].astype(np.float32, copy=False)

                ply_path = os.path.join(output_dir, f"frame_{frame_id:06d}.ply")
                write_ply(ply_path, points, colors, conf1d)

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

    # ---------- path-based one-shot: paths -> PLY (avoids shipping big arrays) ----------
    def process_pair_paths_to_ply(self,
                                  img1_path: str,
                                  img2_path: str,
                                  frame_id: int,
                                  output_dir: str = "point_clouds",
                                  size: int = 512,
                                  conf_threshold: float = 2.0,
                                  use_autocast: bool = False):
        """
        Same as above but takes image paths (best for multi-process pools).
        """
        if self.model is None:
            return None

        os.makedirs(output_dir, exist_ok=True)
        ply_path = None

        try:
            imgs = load_images([img1_path, img2_path], size=size, verbose=False)
            if len(imgs) < 2:
                return None
            pairs = [(imgs[0], imgs[1])]

            torch.set_grad_enabled(False)
            autocast_ctx = (
                torch.autocast(device_type='cuda', dtype=torch.bfloat16)
                if (use_autocast and self.device.startswith("cuda"))
                else nullcontext()
            )
            with torch.inference_mode(), autocast_ctx:
                results = inference(
                    pairs, self.model, self.device,
                    batch_size=64, verbose=False
                )

            pred = self._get_primary_prediction(results)
            if not pred or ('pts3d' not in pred):
                return None

            pts3d = self._tensor_to_numpy(pred['pts3d'], dtype=np.float32)
            if pts3d is None:
                return None
            conf = self._tensor_to_numpy(pred.get('conf'), dtype=np.float32)
            if conf is None:
                conf = np.ones(pts3d.shape[:2], dtype=np.float32)

            # Colors from first image (read once)
            frame1_bgr = cv.imread(img1_path, cv.IMREAD_COLOR)
            if frame1_bgr is None:
                return None
            h, w = pts3d.shape[:2]
            f1_small = cv.resize(frame1_bgr, (w, h))
            f1_small_rgb = cv.cvtColor(f1_small, cv.COLOR_BGR2RGB)

            points = pts3d.reshape(-1, 3)
            colors = f1_small_rgb.reshape(-1, 3).astype(np.uint8, copy=False)
            conf1d = conf.reshape(-1)

            finite = np.isfinite(points).all(axis=1)
            valid = (conf1d > conf_threshold) & finite
            if not np.any(valid):
                return None

            points = points[valid].astype(np.float32, copy=False)
            colors = colors[valid]
            conf1d = conf1d[valid].astype(np.float32, copy=False)

            ply_path = os.path.join(output_dir, f"frame_{frame_id:06d}.ply")
            write_ply(ply_path, points, colors, conf1d)

        finally:
            for v in ('results', 'pred', 'pts3d', 'conf', 'points', 'colors',
                      'conf1d', 'f1_small', 'f1_small_rgb', 'frame1_bgr'):
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

    # ---------- optional viz ----------
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


# =========================
# Multi-process runner
# =========================

# Globals set per worker
_PROC = None
_WORKER_CFG = None

def _init_worker(model_name: str, device_ids: list[int] | None,
                 size: int, conf_threshold: float, use_autocast: bool):
    """
    Pool initializer: each worker loads its own model (on a pinned GPU if provided).
    """
    global _PROC, _WORKER_CFG
    # Pick GPU based on worker index (1-based identity in multiprocessing)
    if torch.cuda.is_available() and device_ids:
        try:
            widx = (mp.current_process()._identity[0] - 1)  # 0-based
        except Exception:
            widx = 0
        device_id = device_ids[widx % len(device_ids)]
    else:
        device_id = None

    _PROC = MAST3RProcessor(model_name=model_name, device_id=device_id)
    _WORKER_CFG = dict(size=size, conf_threshold=conf_threshold, use_autocast=use_autocast)

def _job_pair_paths(args):
    """Worker job: process one pair of image paths."""
    global _PROC, _WORKER_CFG
    img1_path, img2_path, frame_id, output_dir = args
    out = _PROC.process_pair_paths_to_ply(
        img1_path, img2_path, frame_id,
        output_dir=output_dir, **_WORKER_CFG
    )
    if _HAS_PSUTIL:
        rss = psutil.Process(os.getpid()).memory_info().rss / (1024**3)
        print(f"[worker {os.getpid()}] RSS={rss:.2f} GB after {frame_id}")
    return out

def adjacent_pairs_from_dir(frames_dir: str, pattern: str = "*.jpg",
                            step: int = 1, overlap: int = 1, start: int = 0, end: int | None = None):
    """
    Yields (img1_path, img2_path, frame_id) over a directory of frames.
    Uses lexicographic sort; ensure filenames are zero-padded.
    """
    files = sorted(glob.glob(os.path.join(frames_dir, pattern)))
    if end is not None:
        files = files[start:end]
    else:
        files = files[start:]
    # Adjacent (or overlapped) pairing
    for i in range(0, len(files) - overlap, step):
        yield files[i], files[i + overlap], i

def run_pairs_pool_from_dir(frames_dir: str,
                            output_dir: str = "point_clouds",
                            pattern: str = "*.jpg",
                            step: int = 1,
                            overlap: int = 1,
                            model_name: str = "MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric",
                            device_ids: list[int] | None = None,
                            processes: int | None = None,
                            maxtasksperchild: int = 12,
                            size: int = 512,
                            conf_threshold: float = 2.0,
                            use_autocast: bool = True):
    """
    RAM-safe runner:
      - spawns a pool (default: 1 proc if no GPUs; else len(device_ids))
      - each worker loads MASt3R once on its GPU
      - workers auto-restart every N tasks (maxtasksperchild) to kill any hidden caches
      - jobs pass only file paths (not image arrays), keeping parent RAM flat
    """
    mp.set_start_method("spawn", force=True)

    os.makedirs(output_dir, exist_ok=True)
    if device_ids is None and torch.cuda.is_available():
        device_ids = [0]
    if processes is None:
        processes = len(device_ids) if device_ids else 1

    initargs = (model_name, device_ids, size, conf_threshold, use_autocast)
    pairs_iter = ((p1, p2, fid, output_dir)
                  for (p1, p2, fid) in adjacent_pairs_from_dir(frames_dir, pattern, step, overlap))

    with mp.Pool(processes=processes,
                 initializer=_init_worker,
                 initargs=initargs,
                 maxtasksperchild=maxtasksperchild) as pool:
        for _ in pool.imap_unordered(_job_pair_paths, pairs_iter, chunksize=1):
            pass

    if _HAS_PSUTIL:
        rss = psutil.Process(os.getpid()).memory_info().rss / (1024**3)
        print(f"[parent] Final RSS={rss:.2f} GB")


# -------------------------
# Example CLI usage
# -------------------------
if __name__ == "__main__":
    # Example:
    # run_pairs_pool_from_dir(
    #     frames_dir="/path/to/frames",
    #     output_dir="point_clouds",
    #     pattern="*.jpg",
    #     step=1,
    #     overlap=1,                # (i, i+1) pairs
    #     device_ids=[0],           # or [0,1,2,3] for multi-GPU
    #     processes=None,           # defaults to len(device_ids)
    #     maxtasksperchild=12,      # restart workers every 12 pairs
    #     size=512,
    #     conf_threshold=2.0,
    #     use_autocast=True
    # )
    pass
