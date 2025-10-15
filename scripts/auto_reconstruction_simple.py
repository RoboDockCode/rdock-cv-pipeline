#!/usr/bin/env python3
"""
Simplified automatic 3D reconstruction script
"""
import cv2 as cv
import sys
from datetime import datetime

# Add project root to path
import os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from frame_processing_pipeline.mast3r_processor import MAST3RProcessor
from frame_processing_pipeline.camera_utils import open_camera, FrameCaptureSession
from frame_processing_pipeline.ply_utils import merge_ply_files, get_ply_point_count


def auto_reconstruction(duration=60, capture_interval=30, output_name=None):
    """
    Automatically capture and merge 3D reconstruction
    
    Args:
        duration: Capture duration in seconds
        capture_interval: Capture PLY every N frames
        output_name: Custom output filename
    """
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"auto_reconstruction_{timestamp}.ply"
    
    print("🎬 AUTOMATIC 3D RECONSTRUCTION")
    print("="*50)
    print(f"⏱️  Duration: {duration}s")
    print(f"📸 Interval: every {capture_interval} frames")
    print(f"💾 Output: {output_name}")
    print("="*50)
    
    # Initialize
    processor = MAST3RProcessor()
    if processor.model is None:
        return None
    
    cap = open_camera()
    if cap is None:
        return None
    
    print("✅ Starting capture... Press 'q' to stop early")
    
    saved_ply_files = []
    session = FrameCaptureSession(cap, process_interval=10)

    try:
        while True:
            frame = session.read_frame()
            if frame is None:
                break

            elapsed = session.get_elapsed_time()
            
            # Check duration
            if elapsed >= duration:
                print(f"\n⏰ Reached {duration}s duration")
                break

            cv.imshow("Auto Reconstruction - Press 'q' to stop", frame)

            # Process frames
            if session.should_process():
                results = processor.process_frame_pair(session.prev_frame, frame)
                
                if results and session.frame_count % capture_interval == 0:
                    print(f"📸 Capturing PLY {len(saved_ply_files)+1} ({elapsed:.1f}s)")
                    ply_file = processor.save_point_cloud(results, frame, session.frame_count)
                    if ply_file:
                        saved_ply_files.append(ply_file)
                        progress = (elapsed / duration) * 100
                        print(f"✅ Progress: {progress:.1f}%")

            session.update_prev_frame(frame)

            if cv.waitKey(1) & 0xFF == ord('q'):
                print(f"\n⏹️  Stopped at {elapsed:.1f}s")
                break
                
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted")
    finally:
        session.release()
    
    # Merge results
    print("\n" + "="*50)
    print("🔄 MERGING RECONSTRUCTION")
    print("="*50)
    
    if len(saved_ply_files) >= 2:
        merged = merge_ply_files(saved_ply_files, output_name)
        if merged:
            points = get_ply_point_count(merged)
            print(f"\n✅ SUCCESS!")
            print(f"📁 File: {merged}")
            print(f"📈 Points: {points:,}")
            print(f"\n🎨 Visualize: python view_ply.py {merged}")
            return merged
    else:
        print(f"❌ Need at least 2 PLY files, got {len(saved_ply_files)}")
    
    return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatic 3D Reconstruction')
    parser.add_argument('--duration', '-d', type=int, default=60,
                       help='Capture duration in seconds (default: 60)')
    parser.add_argument('--interval', '-i', type=int, default=30,
                       help='Capture every N frames (default: 30)')
    parser.add_argument('--output', '-o', type=str,
                       help='Output filename')
    
    args = parser.parse_args()
    
    result = auto_reconstruction(args.duration, args.interval, args.output)
    
    if not result:
        print("\n❌ FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
