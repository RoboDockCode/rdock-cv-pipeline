#!/usr/bin/env python3
"""
Run MAST3R inference on frames from S3
Decoupled from capture - only handles inference and result upload
"""
import sys
import os
import tempfile
import shutil
import argparse
from datetime import datetime

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.join(parent_dir, 'models/mast3r'))

from frame_processing_pipeline.s3_utils import S3Manager
from scripts.realistic_reconstruction_simple import RealisticReconstructor


def infer_from_s3(
    bucket_name: str,
    job_id: str = None,
    input_prefix: str = "input",
    output_prefix: str = "output/reconstructions",
    keep_local: bool = False
):
    """
    Download frames from S3, run inference, upload results
    
    Args:
        bucket_name: S3 bucket name
        job_id: Job ID to process (e.g., 'job_20251004_191045', if None uses latest)
        input_prefix: S3 prefix where job folders are stored (e.g., 'input')
        output_prefix: S3 prefix where results will be uploaded
        keep_local: Keep local files after upload
        
    Returns:
        S3 key of uploaded PLY file, or None if failed
    """
    print("🧠 MAST3R INFERENCE FROM S3")
    print("=" * 60)
    print(f"🪣  Bucket: {bucket_name}")
    print(f"📥 Input: {input_prefix}/")
    print(f"📤 Output: {output_prefix}/")
    
    # Initialize S3 manager
    try:
        s3_manager = S3Manager(bucket_name)
        print("✅ S3 connection established")
    except Exception as e:
        print(f"❌ Failed to connect to S3: {e}")
        return None
    
    # Get job ID
    if job_id is None:
        print("\n🔍 Finding latest job...")
        jobs = s3_manager.list_sessions(input_prefix)
        if not jobs:
            print("❌ No jobs found in S3")
            return None
        job_id = jobs[0]
        print(f"✅ Using latest job: {job_id}")
    else:
        print(f"📋 Job ID: {job_id}")
    
    # Get frame keys for job (looking in Images/ subdirectory)
    print("\n🔍 Looking for frames in Images/ directory...")
    frame_keys = s3_manager.get_session_frames(input_prefix, job_id, images_subdir="Images")
    
    if len(frame_keys) < 2:
        print(f"❌ Not enough frames found: {len(frame_keys)} (need at least 2)")
        return None
    
    print(f"✅ Found {len(frame_keys)} frames")
    
    # Download frames to temp directory
    print("\n📥 DOWNLOADING FRAMES")
    print("-" * 60)
    temp_dir = tempfile.mkdtemp(prefix='mast3r_inference_')
    frames_dir = os.path.join(temp_dir, 'frames')
    
    local_frames = s3_manager.download_frames_batch(frame_keys, frames_dir)
    
    if len(local_frames) < 2:
        print(f"❌ Failed to download enough frames: {len(local_frames)}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    # Run inference
    print("\n" + "=" * 60)
    print("🧠 RUNNING INFERENCE")
    print("=" * 60)
    
    reconstructor = RealisticReconstructor()
    if reconstructor.model is None:
        print("❌ Failed to load MAST3R model")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    # Generate output filename
    output_filename = f"reconstruction_{job_id}.ply"
    output_path = os.path.join(temp_dir, output_filename)
    
    result_ply = reconstructor.reconstruct(local_frames, output_path)
    
    if not result_ply or not os.path.exists(result_ply):
        print("❌ Reconstruction failed")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    # Upload result to S3
    print("\n" + "=" * 60)
    print("☁️  UPLOADING RESULT")
    print("=" * 60)
    
    s3_result_key = s3_manager.upload_result(result_ply, output_prefix, job_id)
    
    if s3_result_key:
        print("\n" + "=" * 60)
        print("✅ INFERENCE COMPLETE")
        print("=" * 60)
        print(f"📋 Job ID: {job_id}")
        print(f"📸 Frames processed: {len(local_frames)}")
        print(f"📁 Result location: s3://{bucket_name}/{s3_result_key}")
        
        if keep_local:
            # Copy to current directory
            local_copy = os.path.join(os.getcwd(), output_filename)
            shutil.copy(result_ply, local_copy)
            print(f"💾 Local copy: {local_copy}")
        
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return s3_result_key
    else:
        print("❌ Failed to upload result to S3")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None


def list_available_sessions(bucket_name: str, input_prefix: str = "input"):
    """List all available jobs in S3"""
    print("🔍 AVAILABLE JOBS")
    print("=" * 60)
    
    try:
        s3_manager = S3Manager(bucket_name)
        jobs = s3_manager.list_sessions(input_prefix)
        
        if not jobs:
            print("No jobs found")
            return
        
        print(f"Found {len(jobs)} job(s):\n")
        for i, job in enumerate(jobs, 1):
            frames = s3_manager.get_session_frames(input_prefix, job, images_subdir="Images")
            print(f"{i}. {job} ({len(frames)} frames)")
            print(f"   s3://{bucket_name}/{input_prefix}/{job}/Images/")
        
    except Exception as e:
        print(f"❌ Error listing sessions: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Run MAST3R inference on frames from S3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process latest job
  python infer_from_s3.py --bucket frame-storage

  # Process specific job
  python infer_from_s3.py --bucket frame-storage --job job_20251004_191045

  # Keep local copy of result
  python infer_from_s3.py --bucket frame-storage --keep-local

  # List available jobs
  python infer_from_s3.py --bucket frame-storage --list
        """
    )
    
    parser.add_argument(
        '--bucket', '-b',
        required=True,
        help='S3 bucket name'
    )
    parser.add_argument(
        '--job', '-j',
        type=str,
        help='Job ID to process (e.g., job_20251004_191045, default: latest job)'
    )
    parser.add_argument(
        '--input-prefix', '-i',
        default='input',
        help='S3 prefix where job folders are stored (default: input)'
    )
    parser.add_argument(
        '--output-prefix', '-o',
        default='output/reconstructions',
        help='S3 prefix for results (default: output/reconstructions)'
    )
    parser.add_argument(
        '--keep-local', '-k',
        action='store_true',
        help='Keep local copy of result PLY file'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available jobs and exit'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_available_sessions(args.bucket, args.input_prefix)
        sys.exit(0)
    
    result = infer_from_s3(
        bucket_name=args.bucket,
        job_id=args.job,
        input_prefix=args.input_prefix,
        output_prefix=args.output_prefix,
        keep_local=args.keep_local
    )
    
    if result:
        sys.exit(0)
    else:
        print("\n❌ INFERENCE FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()

