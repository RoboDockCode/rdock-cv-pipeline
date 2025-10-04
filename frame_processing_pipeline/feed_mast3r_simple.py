#!/usr/bin/env python3
"""
Simplified MAST3R live feed processing
Reduces complexity while preserving all functionality
"""
import cv2 as cv
import sys

from .mast3r_processor import MAST3RProcessor
from .camera_utils import open_camera, FrameCaptureSession
from .ply_utils import merge_ply_files, get_ply_point_count


def main():
    print("🎬 Starting MAST3R Live Processing")
    print("="*50)
    
    # Initialize MAST3R
    processor = MAST3RProcessor()
    if processor.model is None:
        print("❌ Failed to load MAST3R model")
        return
    
    # Open camera
    cap = open_camera()
    if cap is None:
        print("💡 Tip: Add yourself to video group or run: sudo chmod 666 /dev/video*")
        return
    
    # Setup capture session
    session = FrameCaptureSession(cap, process_interval=10)
    saved_ply_files = []
    auto_capture = False
    auto_capture_interval = 30
    
    print("\n📸 Controls:")
    print("  'q' - quit")
    print("  'p' - save current point cloud")
    print("  'a' - toggle auto-capture (every 30 frames)")
    print("  'm' - merge all saved PLY files")
    print("="*50)
    
    current_results = None
    
    try:
        while True:
            frame = session.read_frame()
            if frame is None:
                break
            
            # Display current frame
            cv.imshow("MAST3R Live Feed - Press 'q' to quit", frame)
            
            # Process frame pairs
            if session.should_process():
                print(f"Processing frame pair {session.frame_count}...")
                
                results = processor.process_frame_pair(session.prev_frame, frame)
                
                if results is not None:
                    current_results = results
                    print("✅ Processing successful")
                    
                    # Visualize depth
                    depth_viz = processor.visualize_depth(results)
                    if depth_viz is not None:
                        cv.imshow("Depth Map", depth_viz)
                    
                    # Auto-capture if enabled
                    if auto_capture and session.frame_count % auto_capture_interval == 0:
                        print(f"🎯 Auto-capturing PLY...")
                        ply_file = processor.save_point_cloud(results, frame, session.frame_count)
                        if ply_file:
                            saved_ply_files.append(ply_file)
                            print(f"✅ Saved PLY #{len(saved_ply_files)}")
            
            # Update previous frame
            session.update_prev_frame(frame)
            
            # Handle keyboard input
            key = cv.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('p') and current_results is not None:
                print("💾 Saving point cloud...")
                ply_file = processor.save_point_cloud(current_results, frame, session.frame_count)
                if ply_file:
                    saved_ply_files.append(ply_file)
            elif key == ord('a'):
                auto_capture = not auto_capture
                status = "ENABLED" if auto_capture else "DISABLED"
                print(f"🔄 Auto-capture {status}")
            elif key == ord('m'):
                if len(saved_ply_files) >= 2:
                    print(f"🔄 Merging {len(saved_ply_files)} PLY files...")
                    merged = merge_ply_files(saved_ply_files, "merged_reconstruction.ply")
                    if merged:
                        points = get_ply_point_count(merged)
                        print(f"✅ Merged: {points:,} points")
                else:
                    print("❌ Need at least 2 PLY files to merge")
    
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    
    finally:
        session.release()
        
        # Print summary
        stats = session.get_stats()
        print("\n" + "="*50)
        print("📊 SESSION SUMMARY")
        print("="*50)
        print(f"Frames processed: {stats['frames']}")
        print(f"Duration: {stats['elapsed']:.1f}s")
        print(f"Average FPS: {stats['fps']:.1f}")
        print(f"PLY files saved: {len(saved_ply_files)}")
        
        if saved_ply_files:
            total_points = sum(get_ply_point_count(f) for f in saved_ply_files)
            print(f"Total points: {total_points:,}")
            print(f"\n🎨 To visualize: python view_ply.py <ply_file>")
        
        print("="*50)


if __name__ == "__main__":
    main()

