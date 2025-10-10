"""S3 utilities for uploading and downloading frames and results"""
import boto3
import os
from typing import List, Optional
from datetime import datetime
import json


class S3Manager:
    """Manage S3 operations for frame storage and retrieval"""
    
    def __init__(self, bucket_name: str, region: str = "us-east-2"):
        """
        Initialize S3 manager
        
        Args:
            bucket_name: Name of the S3 bucket
            region: AWS region (default: us-east-2)
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region)
        self.s3_resource = boto3.resource('s3', region_name=region)
        self.bucket = self.s3_resource.Bucket(bucket_name)
        
    def upload_frame(self, local_path: str, s3_key: str, metadata: Optional[dict] = None) -> bool:
        """
        Upload a single frame to S3
        
        Args:
            local_path: Local file path
            s3_key: S3 key (path in bucket)
            metadata: Optional metadata dict
            
        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            self.s3_client.upload_file(
                local_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            print(f"✅ Uploaded: {s3_key}")
            return True
        except Exception as e:
            print(f"❌ Upload failed for {s3_key}: {e}")
            return False
    
    def upload_frames_batch(self, frame_paths: List[str], s3_prefix: str, session_id: str = None, images_subdir: str = "Images") -> List[str]:
        """
        Upload multiple frames to S3
        
        Args:
            frame_paths: List of local frame paths
            s3_prefix: S3 prefix (e.g., 'input/')
            session_id: Optional session identifier (e.g., 'job_20251004_191045')
            images_subdir: Subdirectory for images (default: 'Images')
            
        Returns:
            List of S3 keys for uploaded frames
        """
        if session_id is None:
            session_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        uploaded_keys = []
        
        for i, frame_path in enumerate(frame_paths):
            filename = os.path.basename(frame_path)
            # Build key: input/job_20251004_191045/Images/frame_000000.jpg
            s3_key = f"{s3_prefix.rstrip('/')}/{session_id}/{images_subdir}/{filename}"
            
            metadata = {
                'session_id': session_id,
                'frame_index': i,
                'timestamp': datetime.now().isoformat()
            }
            
            if self.upload_frame(frame_path, s3_key, metadata):
                uploaded_keys.append(s3_key)
        
        # Upload session metadata
        self._upload_session_metadata(s3_prefix, session_id, uploaded_keys, images_subdir)
        
        return uploaded_keys
    
    def download_frame(self, s3_key: str, local_path: str) -> bool:
        """
        Download a single frame from S3
        
        Args:
            s3_key: S3 key to download
            local_path: Local destination path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            return True
        except Exception as e:
            print(f"❌ Download failed for {s3_key}: {e}")
            return False
    
    def download_frames_batch(self, s3_keys: List[str], local_dir: str) -> List[str]:
        """
        Download multiple frames from S3
        
        Args:
            s3_keys: List of S3 keys to download
            local_dir: Local directory to save frames
            
        Returns:
            List of local paths for downloaded frames
        """
        os.makedirs(local_dir, exist_ok=True)
        local_paths = []
        
        print(f"📥 Downloading {len(s3_keys)} frames...")
        for i, s3_key in enumerate(s3_keys):
            filename = os.path.basename(s3_key)
            local_path = os.path.join(local_dir, filename)
            
            if self.download_frame(s3_key, local_path):
                local_paths.append(local_path)
                if (i + 1) % 5 == 0:
                    print(f"   Downloaded {i + 1}/{len(s3_keys)}")
        
        print(f"✅ Downloaded {len(local_paths)}/{len(s3_keys)} frames")
        return local_paths
    
    def list_sessions(self, s3_prefix: str) -> List[str]:
        """
        List all capture sessions in S3
        
        Args:
            s3_prefix: S3 prefix to search (e.g., 'input/frames/')
            
        Returns:
            List of session IDs
        """
        try:
            result = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=s3_prefix,
                Delimiter='/'
            )
            
            sessions = []
            if 'CommonPrefixes' in result:
                for prefix in result['CommonPrefixes']:
                    session_path = prefix['Prefix']
                    session_id = session_path.rstrip('/').split('/')[-1]
                    sessions.append(session_id)
            
            return sorted(sessions, reverse=True)
        except Exception as e:
            print(f"❌ Failed to list sessions: {e}")
            return []
    
    def get_session_frames(self, s3_prefix: str, session_id: str, images_subdir: str = "Images") -> List[str]:
        """
        Get all frame keys for a specific session
        
        Args:
            s3_prefix: S3 prefix (e.g., 'input/')
            session_id: Session identifier (e.g., 'job_20251004_191045')
            images_subdir: Subdirectory containing images (default: 'Images')
            
        Returns:
            List of S3 keys for frames in the session
        """
        # Build prefix: input/job_20251004_191045/Images/
        session_prefix = f"{s3_prefix.rstrip('/')}/{session_id}/{images_subdir}/"
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=session_prefix
            )
            
            if 'Contents' not in response:
                return []
            
            # Filter out metadata files and get image files only
            frames = [
                obj['Key'] for obj in response['Contents']
                if obj['Key'].lower().endswith(('.jpg', '.jpeg', '.png'))
            ]
            
            return sorted(frames)
        except Exception as e:
            print(f"❌ Failed to get session frames: {e}")
            return []
    
    def upload_result(self, local_path: str, s3_prefix: str, session_id: str) -> Optional[str]:
        """
        Upload reconstruction result (PLY file) to S3
        
        Args:
            local_path: Local PLY file path
            s3_prefix: S3 prefix for results (e.g., 'output/reconstructions/')
            session_id: Session identifier to link with input frames
            
        Returns:
            S3 key if successful, None otherwise
        """
        filename = os.path.basename(local_path)
        s3_key = f"{s3_prefix}/{session_id}/{filename}"
        
        metadata = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'file_type': 'reconstruction'
        }
        
        if self.upload_frame(local_path, s3_key, metadata):
            return s3_key
        return None
    
    def _upload_session_metadata(self, s3_prefix: str, session_id: str, frame_keys: List[str], images_subdir: str = "Images"):
        """Upload session metadata JSON file"""
        metadata = {
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'frame_count': len(frame_keys),
            'frames': frame_keys
        }
        
        # Put metadata at job level, not inside Images/
        metadata_key = f"{s3_prefix.rstrip('/')}/{session_id}/metadata.json"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )
        except Exception as e:
            print(f"⚠️  Failed to upload session metadata: {e}")

