#!/usr/bin/env python3
"""
Capture frames from camera and upload to S3
Decoupled from inference - only handles capture and storage
"""
import cv2 as cv
import sys
import os
import time
import tempfile
import shutil
from datetime import datetime
import argparse

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

from frame_processing_pipeline.camera_utils import open_camera
from frame_processing_pipeline.s3_utils import S3Manager


def capture_and_upload(
    bucket_name: str,
    s3_prefix: str = "input",
    duration: int = 30,
    interval: float = 2.0,
    session_id: str = None
):
    """
    Capture frames from camera and upload to S3
    
    Args:
        bucket_name: S3 bucket name
        s3_prefix: S3 prefix for frames (e.g., 'input')
        duration: Capture duration in seconds
        interval: Capture interval in seconds
        session_id: Optional custom session ID (e.g., 'job_20251004_191045')
        
    Returns:
        Session ID if successful, None otherwise
    """
    # Generate session ID if not provided
    if session_id is None:
        session_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print("📸 FRAME CAPTURE TO S3")
    print("=" * 60)
    print(f"🪣  Bucket: {bucket_name}")
    print(f"📁 Path: {s3_prefix}/{session_id}/Images/")
    print(f"⏱️  Duration: {duration}s")
    print(f"📷 Interval: {interval}s")
    print("=" * 60)
    
    # Initialize S3 manager
    try:
        s3_manager = S3Manager(bucket_name)
        print("✅ S3 connection established")
    except Exception as e:
        print(f"❌ Failed to connect to S3: {e}")
        return None
    
    # Open camera
    cap = open_camera()
    if cap is None:
        print("❌ Failed to open camera")
        return None
    
    print("✅ Camera opened")
    
    # Warmup camera - read a few frames to let it initialize
    print("🔥 Warming up camera...")
    for _ in range(10):
        ret, _ = cap.read()
        if ret:
            break
        time.sleep(0.1)
    
    if not ret:
        print("❌ Camera opened but cannot read frames. Check camera permissions.")
        print("   Go to System Settings → Privacy & Security → Camera")
        print("   Make sure Terminal/Python has camera access.")
        cap.release()
        return None
    
    print("✅ Camera ready")
    
    # Create temporary directory for frames
    temp_dir = tempfile.mkdtemp(prefix='capture_')
    captured_frames = []
    
    print("\n🎥 Capturing... Press 'q' to stop early")
    print("-" * 60)
    
    start_time = time.time()
    last_capture = 0
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ Failed to read from camera")
                break
            
            current_time = time.time()
            elapsed = current_time - start_time
            
            # Check if duration reached
            if elapsed >= duration:
                print(f"\n⏰ Reached {duration}s duration")
                break
            
            # Show preview
            display_frame = frame.copy()
            cv.putText(
                display_frame,
                f"Session: {session_id} | Time: {elapsed:.1f}s | Frames: {frame_count}",
                (10, 30),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            cv.imshow("Capturing - Press 'q' to stop", display_frame)
            
            # Capture at intervals
            if current_time - last_capture >= interval:
                frame_filename = os.path.join(temp_dir, f"frame_{frame_count:06d}.jpg")
                cv.imwrite(frame_filename, frame)
                captured_frames.append(frame_filename)
                last_capture = current_time
                frame_count += 1
                
                progress = (elapsed / duration) * 100
                print(f"📸 Frame {frame_count:3d} captured ({progress:5.1f}% complete)")
            
            # Check for quit
            if cv.waitKey(1) & 0xFF == ord('q'):
                print(f"\n⏹️  Stopped early at {elapsed:.1f}s")
                break
    
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    
    finally:
        cap.release()
        cv.destroyAllWindows()
    
    # Upload to S3
    if len(captured_frames) < 2:
        print(f"\n❌ Not enough frames captured ({len(captured_frames)}). Need at least 2.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    print("\n" + "=" * 60)
    print("☁️  UPLOADING TO S3")
    print("=" * 60)
    print(f"📦 Uploading {len(captured_frames)} frames...")
    
    uploaded_keys = s3_manager.upload_frames_batch(
        captured_frames,
        s3_prefix,
        session_id
    )
    
    # Cleanup temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    if len(uploaded_keys) == len(captured_frames):
        print("\n" + "=" * 60)
        print("✅ CAPTURE COMPLETE")
        print("=" * 60)
        print(f"📋 Job ID: {session_id}")
        print(f"📸 Frames uploaded: {len(uploaded_keys)}")
        print(f"📁 S3 location: s3://{bucket_name}/{s3_prefix}/{session_id}/Images/")
        print("\n🔄 Next step: Run inference with this job ID")
        print(f"   python scripts/infer_from_s3.py --bucket {bucket_name} --job {session_id}")
        return session_id
    else:
        print(f"\n⚠️  Partial upload: {len(uploaded_keys)}/{len(captured_frames)} frames uploaded")
        return session_id


def main():
    parser = argparse.ArgumentParser(
        description='Capture frames from camera and upload to S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Capture 30 seconds, one frame every 2 seconds
  python capture_to_s3.py --bucket my-bucket --duration 30 --interval 2

  # Capture with custom session ID
  python capture_to_s3.py --bucket my-bucket --session my_capture_001

  # Quick capture (10 seconds, 1 frame/sec)
  python capture_to_s3.py --bucket my-bucket -d 10 -i 1
        """
    )
    
    parser.add_argument(
        '--bucket', '-b',
        required=True,
        help='S3 bucket name'
    )
    parser.add_argument(
        '--prefix', '-p',
        default='input',
        help='S3 prefix for frames (default: input)'
    )
    parser.add_argument(
        '--duration', '-d',
        type=int,
        default=30,
        help='Capture duration in seconds (default: 30)'
    )
    parser.add_argument(
        '--interval', '-i',
        type=float,
        default=2.0,
        help='Capture interval in seconds (default: 2.0)'
    )
    parser.add_argument(
        '--session', '-s',
        type=str,
        help='Custom job ID (default: auto-generated job_YYYYMMDD_HHMMSS)'
    )
    
    args = parser.parse_args()
    
    result = capture_and_upload(
        bucket_name=args.bucket,
        s3_prefix=args.prefix,
        duration=args.duration,
        interval=args.interval,
        session_id=args.session
    )
    
    if result:
        sys.exit(0)
    else:
        print("\n❌ CAPTURE FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

