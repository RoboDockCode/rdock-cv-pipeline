#!/usr/bin/env python3
"""
Download MP4 from S3, extract frames, run MAST3R reconstruction, upload result
"""
import sys
import os
import tempfile
import shutil
import glob
from datetime import datetime
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    import boto3
    import cv2
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("Install with: pip install boto3 opencv-python")
    sys.exit(1)

from scripts.realistic_reconstruction_simple import RealisticReconstructor
from frame_processing_pipeline.slam_processor import SLAMReconstructor


def get_latest_mp4_from_s3(bucket_name):
    """Find the latest MP4 file in the S3 bucket"""
    print(f"🔍 Searching for latest MP4 in s3://{bucket_name}/")
    
    s3_client = boto3.client('s3')
    
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        if 'Contents' not in response:
            print(f"❌ No files found in bucket: {bucket_name}")
            return None
        
        # Filter for MP4 files and sort by last modified
        mp4_files = [
            obj for obj in response['Contents']
            if obj['Key'].lower().endswith('.mp4')
        ]
        
        if not mp4_files:
            print(f"❌ No MP4 files found in bucket: {bucket_name}")
            return None
        
        # Sort by LastModified, most recent first
        mp4_files.sort(key=lambda x: x['LastModified'], reverse=True)
        latest = mp4_files[0]
        
        print(f"✅ Found latest MP4: {latest['Key']}")
        print(f"   Size: {latest['Size'] / 1024 / 1024:.2f} MB")
        print(f"   Modified: {latest['LastModified']}")
        
        return latest['Key']
        
    except Exception as e:
        print(f"❌ Error accessing S3: {e}")
        return None


def download_mp4_from_s3(bucket_name, s3_key, local_path):
    """Download MP4 file from S3"""
    print(f"\n📥 Downloading MP4 from S3...")
    print(f"   From: s3://{bucket_name}/{s3_key}")
    print(f"   To: {local_path}")
    
    s3_client = boto3.client('s3')
    
    try:
        s3_client.download_file(bucket_name, s3_key, local_path)
        file_size = os.path.getsize(local_path) / 1024 / 1024
        print(f"✅ Downloaded: {file_size:.2f} MB")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def extract_frames_from_mp4(mp4_path, output_dir, fps=2):
    """Extract frames from MP4 at specified FPS"""
    print(f"\n🎬 Extracting frames from MP4...")
    print(f"   Input: {mp4_path}")
    print(f"   Output: {output_dir}")
    print(f"   Target FPS: {fps}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(mp4_path)
    
    if not cap.isOpened():
        print(f"❌ Failed to open video: {mp4_path}")
        return []
    
    # Get video properties
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps if video_fps > 0 else 0
    
    print(f"   Video FPS: {video_fps:.2f}")
    print(f"   Total frames: {total_frames}")
    print(f"   Duration: {duration:.2f}s")
    
    # Calculate frame interval
    frame_interval = int(video_fps / fps) if video_fps > 0 else 1
    
    frame_count = 0
    saved_count = 0
    extracted_frames = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Save frame at specified interval
        if frame_count % frame_interval == 0:
            img_path = os.path.join(output_dir, f"img_{saved_count:03d}.jpg")
            cv2.imwrite(img_path, frame)
            extracted_frames.append(img_path)
            saved_count += 1
            
            if saved_count % 10 == 0:
                print(f"   Extracted {saved_count} frames...")
        
        frame_count += 1
    
    cap.release()
    
    print(f"✅ Extracted {saved_count} frames from {total_frames} total frames")
    
    if saved_count < 2:
        print(f"❌ Not enough frames extracted (need at least 2)")
        return []
    
    return extracted_frames


def upload_result_to_s3(ply_path, bucket_name, job_id, trajectory_path=None):
    """Upload reconstruction result to S3"""
    print(f"\n📤 Uploading result to S3...")
    
    s3_client = boto3.client('s3')
    s3_key = f"output/{job_id}/reconstruction.ply"
    
    try:
        print(f"   From: {ply_path}")
        print(f"   To: s3://{bucket_name}/{s3_key}")
        
        s3_client.upload_file(ply_path, bucket_name, s3_key)
        
        file_size = os.path.getsize(ply_path) / 1024 / 1024
        print(f"✅ Uploaded PLY: {file_size:.2f} MB")
        
        # Upload trajectory if provided (SLAM mode)
        if trajectory_path and os.path.exists(trajectory_path):
            traj_s3_key = f"output/{job_id}/trajectory.txt"
            print(f"   Trajectory: {trajectory_path}")
            print(f"   To: s3://{bucket_name}/{traj_s3_key}")
            s3_client.upload_file(trajectory_path, bucket_name, traj_s3_key)
            traj_size = os.path.getsize(trajectory_path) / 1024
            print(f"✅ Uploaded trajectory: {traj_size:.2f} KB")
        
        print(f"\n📥 Download with:")
        print(f"   aws s3 cp s3://{bucket_name}/{s3_key} ./")
        print(f"\n🎨 Visualize with:")
        print(f"   python scripts/view_ply.py reconstruction.ply")
        
        return True
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Process MP4 from S3 into 3D reconstruction'
    )
    parser.add_argument(
        '--input-bucket', '-i',
        default='video-test-bucket-2985',
        help='S3 bucket containing MP4 videos (default: video-test-bucket-2985)'
    )
    parser.add_argument(
        '--output-bucket', '-o',
        default='frame-storage',
        help='S3 bucket for output PLY files (default: frame-storage)'
    )
    parser.add_argument(
        '--fps', '-f',
        type=float,
        default=2.0,
        help='Target FPS for frame extraction (default: 2.0)'
    )
    parser.add_argument(
        '--video', '-v',
        help='Specific video key in S3 (if not provided, uses latest)'
    )
    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help='Keep temporary files (MP4 and frames) after processing'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['batch', 'slam'],
        default='batch',
        help='Reconstruction mode: batch (global MASt3R, better quality) or slam (sequential, memory efficient, with trajectory)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎬 MP4 TO 3D RECONSTRUCTION PIPELINE")
    print("=" * 70)
    print(f"📥 Input bucket: {args.input_bucket}")
    print(f"📤 Output bucket: {args.output_bucket}")
    print(f"🎞️  Target FPS: {args.fps}")
    print(f"🔧 Mode: {args.mode.upper()}")
    if args.mode == 'batch':
        print(f"   └─ Global MASt3R (best quality)")
    else:
        print(f"   └─ Sequential SLAM (memory efficient + trajectory)")
    print("=" * 70)
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix='mp4_reconstruction_')
    print(f"\n📁 Temporary directory: {temp_dir}")
    
    try:
        # Step 1: Find and download MP4
        if args.video:
            mp4_key = args.video
            print(f"\n📹 Using specified video: {mp4_key}")
        else:
            mp4_key = get_latest_mp4_from_s3(args.input_bucket)
            if not mp4_key:
                return 1
        
        mp4_path = os.path.join(temp_dir, 'video.mp4')
        if not download_mp4_from_s3(args.input_bucket, mp4_key, mp4_path):
            return 1
        
        # Step 2: Extract frames
        frames_dir = os.path.join(temp_dir, 'frames')
        frames = extract_frames_from_mp4(mp4_path, frames_dir, args.fps)
        
        if not frames:
            print("❌ Frame extraction failed")
            return 1
        
        # Step 3: Run reconstruction (SLAM or batch)
        print("\n" + "=" * 70)
        if args.mode == 'slam':
            print("🧠 RUNNING MAST3R-SLAM RECONSTRUCTION")
        else:
            print("🧠 RUNNING MAST3R RECONSTRUCTION (BATCH)")
        print("=" * 70)
        
        # Generate job ID from timestamp
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_ply = os.path.join(temp_dir, 'reconstruction.ply')
        trajectory_path = None
        
        if args.mode == 'slam':
            # Use SLAM reconstructor
            reconstructor = SLAMReconstructor()
            if reconstructor.model is None:
                print("❌ Failed to load MASt3R-SLAM model")
                return 1
            
            # SLAM will use extracted frames (MP4 has codec issues)
            result = reconstructor.reconstruct(frames, output_ply)
            
            if not result or not result['success']:
                print("❌ SLAM reconstruction failed")
                return 1
            
            output_ply = result['ply']
            trajectory_path = result['trajectory']
            print(f"\n✅ Generated {result['num_keyframes']} keyframes")
            print(f"✅ Reconstructed {result['num_points']:,} points")
        else:
            # Use batch reconstructor
            reconstructor = RealisticReconstructor()
            if reconstructor.model is None:
                print("❌ Failed to load MAST3R model")
                return 1
            
            result = reconstructor.reconstruct(frames, output_ply)
            
            if not result:
                print("❌ Reconstruction failed")
                return 1
            
            output_ply = result
        
        # Step 4: Upload result to S3
        if not upload_result_to_s3(output_ply, args.output_bucket, job_id, trajectory_path):
            return 1
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETE!")
        print("=" * 70)
        print(f"📹 Input: s3://{args.input_bucket}/{mp4_key}")
        print(f"📊 Frames extracted: {len(frames)}")
        print(f"📁 Output: s3://{args.output_bucket}/output/{job_id}/reconstruction.ply")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup temporary files
        if not args.keep_temp:
            print(f"\n🧹 Cleaning up temporary files...")
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"✅ Cleaned up: {temp_dir}")
        else:
            print(f"\n💾 Keeping temporary files: {temp_dir}")


if __name__ == "__main__":
    sys.exit(main())

