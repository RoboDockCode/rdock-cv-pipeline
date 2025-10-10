"""Frame processing pipeline for MAST3R 3D reconstruction"""

# Lazy imports to avoid loading heavy dependencies when not needed
# Import MAST3RProcessor only when actually used (requires mast3r model)
from .camera_utils import open_camera, FrameCaptureSession
from .ply_utils import write_ply, read_ply, merge_ply_files, get_ply_point_count

__all__ = [
    'MAST3RProcessor',
    'open_camera',
    'FrameCaptureSession',
    'write_ply',
    'read_ply',
    'merge_ply_files',
    'get_ply_point_count',
]

def __getattr__(name):
    """Lazy import for MAST3RProcessor to avoid loading mast3r when not needed"""
    if name == 'MAST3RProcessor':
        from .mast3r_processor import MAST3RProcessor
        return MAST3RProcessor
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

