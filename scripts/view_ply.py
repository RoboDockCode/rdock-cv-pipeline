#!/usr/bin/env python3
"""
PLY viewer - uses CloudCompare if available, otherwise matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import struct
import sys
import subprocess
import shutil
import os
import platform
import tempfile
import re
import time

def read_ply_file(filename):
    """Read PLY file and return points, colors, confidences"""
    points = []
    colors = []
    confidences = []
    
    with open(filename, 'rb') as f:
        # Skip header
        line = f.readline()
        while line:
            if line.strip() == b'end_header':
                break
            line = f.readline()
        
        # Read vertex data
        while True:
            data = f.read(19)  # 3*4 + 3*1 + 1*4 = 19 bytes per vertex
            if len(data) < 19:
                break
            
            # Unpack: 3 floats (xyz), 3 bytes (rgb), 1 float (conf)
            x, y, z, r, g, b, conf = struct.unpack('<fffBBBf', data)
            points.append([x, y, z])
            colors.append([r/255.0, g/255.0, b/255.0])  # Normalize to 0-1
            confidences.append(conf)
    
    return np.array(points), np.array(colors), np.array(confidences)

def visualize_ply(filename, max_points=100000):
    """Visualize PLY file with matplotlib"""
    print(f"Loading PLY file: {filename}")
    
    points, colors, confidences = read_ply_file(filename)
    
    print(f"Loaded {len(points)} points")
    print(f"Point range: X({points[:, 0].min():.3f}, {points[:, 0].max():.3f})")
    print(f"             Y({points[:, 1].min():.3f}, {points[:, 1].max():.3f})")
    print(f"             Z({points[:, 2].min():.3f}, {points[:, 2].max():.3f})")
    print(f"Confidence range: {confidences.min():.3f} to {confidences.max():.3f}")
    
    # Subsample for visualization if too many points
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        colors = colors[indices]
        confidences = confidences[indices]
        print(f"Subsampled to {max_points} points for visualization")
    
    # Create 3D plot
    fig = plt.figure(figsize=(12, 8))
    
    # Plot 1: 3D point cloud with colors
    ax1 = fig.add_subplot(121, projection='3d')
    ax1.scatter(points[:, 0], points[:, 1], points[:, 2], 
                c=colors, s=1, alpha=0.6)
    ax1.set_xlabel('X')
    ax1.set_ylabel('Y')
    ax1.set_zlabel('Z')
    ax1.set_title('3D Point Cloud (RGB)')
    
    # Plot 2: 3D point cloud colored by confidence
    ax2 = fig.add_subplot(122, projection='3d')
    scatter = ax2.scatter(points[:, 0], points[:, 1], points[:, 2], 
                         c=confidences, s=1, alpha=0.6, cmap='viridis')
    ax2.set_xlabel('X')
    ax2.set_ylabel('Y')
    ax2.set_zlabel('Z')
    ax2.set_title('3D Point Cloud (Confidence)')
    plt.colorbar(scatter, ax=ax2, label='Confidence')
    
    plt.tight_layout()
    plt.show()

def find_latest_s3_reconstruction(bucket_name="frame-storage", prefix="output/reconstructions"):
    """Find the most recent reconstruction in S3"""
    try:
        import boto3
        from datetime import datetime
    except ImportError:
        return None
    
    try:
        s3_client = boto3.client('s3')
        
        # List all jobs
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix + '/',
            Delimiter='/'
        )
        
        if 'CommonPrefixes' not in response:
            return None
        
        # Get all job directories
        jobs = []
        for prefix_obj in response['CommonPrefixes']:
            job_prefix = prefix_obj['Prefix']
            job_id = job_prefix.rstrip('/').split('/')[-1]
            
            # List PLY files in this job
            files_response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=job_prefix
            )
            
            if 'Contents' in files_response:
                for obj in files_response['Contents']:
                    if obj['Key'].endswith('.ply'):
                        jobs.append({
                            'key': obj['Key'],
                            'modified': obj['LastModified'],
                            'job_id': job_id
                        })
        
        if not jobs:
            return None
        
        # Sort by modification time, most recent first
        jobs.sort(key=lambda x: x['modified'], reverse=True)
        latest = jobs[0]
        
        return f"s3://{bucket_name}/{latest['key']}", latest['job_id'], latest['modified']
        
    except Exception as e:
        print(f"⚠️  Could not check S3: {e}")
        return None


def find_latest_local_ply():
    """Find the most recent PLY file in current directory and subdirectories"""
    import glob
    
    # Search patterns
    patterns = [
        "*.ply",
        "point_clouds/*.ply",
        "outputs/*.ply",
        "reconstruction*.ply"
    ]
    
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(pattern))
    
    if not all_files:
        return None
    
    # Sort by modification time
    all_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return all_files[0]


def download_from_s3(s3_path):
    """Download PLY file from S3 to temporary location"""
    try:
        import boto3
    except ImportError:
        print("❌ boto3 not installed. Install with: pip install boto3")
        return None
    
    # Parse S3 URL: s3://bucket-name/path/to/file.ply
    match = re.match(r's3://([^/]+)/(.+)', s3_path)
    if not match:
        print(f"❌ Invalid S3 path format: {s3_path}")
        print("   Expected format: s3://bucket-name/path/to/file.ply")
        return None
    
    bucket_name = match.group(1)
    s3_key = match.group(2)
    
    print(f"📥 Downloading from S3...")
    print(f"   Bucket: {bucket_name}")
    print(f"   Key: {s3_key}")
    
    try:
        s3_client = boto3.client('s3')
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ply')
        temp_path = temp_file.name
        temp_file.close()
        
        # Download
        s3_client.download_file(bucket_name, s3_key, temp_path)
        
        # Get file size
        file_size = os.path.getsize(temp_path)
        print(f"✅ Downloaded {file_size / 1024 / 1024:.1f} MB to {temp_path}")
        
        return temp_path
        
    except Exception as e:
        print(f"❌ Failed to download from S3: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None


def open_with_cloudcompare(ply_file):
    """Try to open PLY file with CloudCompare"""
    
    # Check if CloudCompare is installed
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Try common CloudCompare locations on Mac
        cc_paths = [
            "/Applications/CloudCompare.app",
            "/Applications/cloudcompare.app",
            shutil.which("CloudCompare"),
            shutil.which("cloudcompare")
        ]
        
        for cc_path in cc_paths:
            if cc_path and (os.path.exists(cc_path) if cc_path.startswith('/') else True):
                try:
                    if cc_path.endswith('.app'):
                        # Use 'open' command for .app bundles
                        subprocess.Popen(['open', '-a', cc_path, os.path.abspath(ply_file)])
                    else:
                        # Use direct command
                        subprocess.Popen([cc_path, os.path.abspath(ply_file)])
                    print(f"✅ Opened in CloudCompare: {ply_file}")
                    return True
                except Exception as e:
                    continue
    
    elif system == "Linux":
        # Try common CloudCompare commands on Linux
        cc_commands = ['cloudcompare', 'CloudCompare', 'cloudcompare.CloudCompare']
        
        for cmd in cc_commands:
            if shutil.which(cmd):
                try:
                    subprocess.Popen([cmd, os.path.abspath(ply_file)])
                    print(f"✅ Opened in CloudCompare: {ply_file}")
                    return True
                except Exception:
                    continue
    
    elif system == "Windows":
        # Try common CloudCompare paths on Windows
        cc_paths = [
            r"C:\Program Files\CloudCompare\CloudCompare.exe",
            r"C:\Program Files (x86)\CloudCompare\CloudCompare.exe"
        ]
        
        for cc_path in cc_paths:
            if os.path.exists(cc_path):
                try:
                    subprocess.Popen([cc_path, os.path.abspath(ply_file)])
                    print(f"✅ Opened in CloudCompare: {ply_file}")
                    return True
                except Exception:
                    continue
    
    return False


if __name__ == "__main__":
    ply_file = None
    temp_file = None
    
    # If no arguments, find the most recent reconstruction
    if len(sys.argv) < 2:
        print("🔍 No file specified, looking for most recent reconstruction...")
        
        # Check S3 first (most common for GPU inference)
        s3_result = find_latest_s3_reconstruction()
        if s3_result:
            ply_file, job_id, modified = s3_result
            print(f"✅ Found latest S3 reconstruction:")
            print(f"   Job: {job_id}")
            print(f"   Modified: {modified}")
            print(f"   Path: {ply_file}")
        else:
            # Fallback to local files
            ply_file = find_latest_local_ply()
            if ply_file:
                print(f"✅ Found latest local PLY: {ply_file}")
            else:
                print("\n❌ No PLY files found")
                print("\nUsage: python view_ply.py [ply_file] [max_points]")
                print("\nExamples:")
                print("  python view_ply.py                              # Open latest")
                print("  python view_ply.py point_clouds/frame_000001.ply")
                print("  python view_ply.py output.ply 500000            # Show 500k points")
                print("  python view_ply.py s3://bucket/path/to/file.ply # From S3")
                print("\nNote: Will use CloudCompare if installed, otherwise matplotlib")
                sys.exit(1)
    else:
        ply_file = sys.argv[1]
    
    # Check if it's an S3 path
    if ply_file.startswith('s3://'):
        temp_file = download_from_s3(ply_file)
        if not temp_file:
            sys.exit(1)
        ply_file = temp_file
    
    # Check if local file exists
    if not os.path.exists(ply_file):
        print(f"❌ File not found: {ply_file}")
        sys.exit(1)
    
    # Try CloudCompare first
    print("🔍 Looking for CloudCompare...")
    if open_with_cloudcompare(ply_file):
        print("📊 CloudCompare launched successfully!")
        
        # For S3 files, keep temp file around for CloudCompare to read
        if temp_file:
            print(f"\n⚠️  Keep this terminal open until you close CloudCompare!")
            print(f"   (Temporary file will be deleted when you close this terminal)")
            print(f"   Location: {temp_file}")
            print("\nPress Ctrl+C when done viewing to clean up...")
            
            # Wait for user to press Ctrl+C
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🗑️  Cleaning up temporary file...")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print("✅ Done!")
        else:
            print("   (You can close this terminal)")
        
        sys.exit(0)
    
    # Fallback to matplotlib
    print("⚠️  CloudCompare not found, using matplotlib viewer")
    print("   Install CloudCompare for better performance:")
    print("   macOS:  brew install --cask cloudcompare")
    print("   Linux:  sudo snap install cloudcompare")
    print("")
    
    try:
        max_points = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
        visualize_ply(ply_file, max_points=max_points)
    finally:
        # Clean up temp file after matplotlib viewing
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"\n🗑️  Cleaned up temporary file")
            except:
                pass
