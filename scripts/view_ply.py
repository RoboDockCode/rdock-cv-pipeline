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
from scipy.spatial.distance import cdist
from scipy.ndimage import gaussian_filter
from scipy.spatial import Delaunay
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

def read_ply_file(filename):
    """Read PLY file and return points, colors, confidences"""
    points = []
    colors = []
    confidences = []
    has_confidence = False
    
    with open(filename, 'rb') as f:
        # Read header to check if confidence field exists
        line = f.readline()
        while line:
            if b'property float confidence' in line:
                has_confidence = True
            if line.strip() == b'end_header':
                break
            line = f.readline()
        
        # Read vertex data
        if has_confidence:
            # Format with confidence: 19 bytes per vertex
            while True:
                data = f.read(19)  # 3*4 + 3*1 + 1*4 = 19 bytes
                if len(data) < 19:
                    break
                x, y, z, r, g, b, conf = struct.unpack('<fffBBBf', data)
                points.append([x, y, z])
                colors.append([r/255.0, g/255.0, b/255.0])
                confidences.append(conf)
        else:
            # Format without confidence: 15 bytes per vertex
            while True:
                data = f.read(15)  # 3*4 + 3*1 = 15 bytes
                if len(data) < 15:
                    break
                x, y, z, r, g, b = struct.unpack('<fffBBB', data)
                points.append([x, y, z])
                colors.append([r/255.0, g/255.0, b/255.0])
                confidences.append(1.0)  # Default confidence
    
    return np.array(points), np.array(colors), np.array(confidences)


def enhance_point_cloud_gaussian(points, colors, confidences, voxel_size=0.01, sigma=0.05, max_points=50000):
    """
    Fill gaps in point cloud using Gaussian color interpolation
    
    Args:
        points: Nx3 array of 3D coordinates
        colors: Nx3 array of RGB colors (0-1 range)
        confidences: N array of confidence values
        voxel_size: Size of voxel grid for interpolation
        sigma: Gaussian kernel standard deviation
        max_points: Maximum points to process (for performance)
    
    Returns:
        enhanced_points, enhanced_colors, enhanced_confidences
    """
    print(f"🎨 Enhancing point cloud with Gaussian interpolation...")
    print(f"   Input points: {len(points)}")
    print(f"   Voxel size: {voxel_size}")
    print(f"   Gaussian sigma: {sigma}")
    
    # Subsample if too many points for performance
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        colors = colors[indices]
        confidences = confidences[indices]
        print(f"   Subsampled to {max_points} points for processing")
    
    # Create voxel grid
    min_coords = points.min(axis=0)
    max_coords = points.max(axis=0)
    
    # Calculate grid dimensions
    grid_size = ((max_coords - min_coords) / voxel_size).astype(int) + 1
    print(f"   Grid size: {grid_size}")
    
    # Create voxel coordinates
    voxel_coords = ((points - min_coords) / voxel_size).astype(int)
    
    # Create 3D grid for colors and confidences
    color_grid = np.zeros((grid_size[0], grid_size[1], grid_size[2], 3))
    confidence_grid = np.zeros((grid_size[0], grid_size[1], grid_size[2]))
    weight_grid = np.zeros((grid_size[0], grid_size[1], grid_size[2]))
    
    # Fill grid with original points
    for i, (voxel, color, conf) in enumerate(zip(voxel_coords, colors, confidences)):
        if 0 <= voxel[0] < grid_size[0] and 0 <= voxel[1] < grid_size[1] and 0 <= voxel[2] < grid_size[2]:
            color_grid[voxel[0], voxel[1], voxel[2]] = color
            confidence_grid[voxel[0], voxel[1], voxel[2]] = conf
            weight_grid[voxel[0], voxel[1], voxel[2]] = 1.0
    
    # Apply Gaussian smoothing to fill gaps
    print(f"   Applying Gaussian smoothing...")
    for channel in range(3):
        color_grid[:, :, :, channel] = gaussian_filter(color_grid[:, :, :, channel], sigma=sigma)
    
    confidence_grid = gaussian_filter(confidence_grid, sigma=sigma)
    weight_grid = gaussian_filter(weight_grid, sigma=sigma)
    
    # Extract enhanced points
    enhanced_points = []
    enhanced_colors = []
    enhanced_confidences = []
    
    # Threshold for inclusion (avoid very low confidence interpolated points)
    confidence_threshold = 0.1
    
    for i in range(grid_size[0]):
        for j in range(grid_size[1]):
            for k in range(grid_size[2]):
                if weight_grid[i, j, k] > 0.1:  # Only include voxels with sufficient weight
                    # Convert back to world coordinates
                    world_coord = min_coords + np.array([i, j, k]) * voxel_size
                    
                    # Check confidence threshold
                    if confidence_grid[i, j, k] > confidence_threshold:
                        enhanced_points.append(world_coord)
                        enhanced_colors.append(color_grid[i, j, k])
                        enhanced_confidences.append(confidence_grid[i, j, k])
    
    enhanced_points = np.array(enhanced_points)
    enhanced_colors = np.array(enhanced_colors)
    enhanced_confidences = np.array(enhanced_confidences)
    
    print(f"   Enhanced points: {len(enhanced_points)}")
    print(f"   Enhancement ratio: {len(enhanced_points) / len(points):.2f}x")
    
    return enhanced_points, enhanced_colors, enhanced_confidences


def reconstruct_surface_poisson(points, colors, confidences, depth=8, width=0, scale=1.1):
    """
    Reconstruct surface using Poisson reconstruction algorithm
    
    Args:
        points: Nx3 array of 3D coordinates
        colors: Nx3 array of RGB colors (0-1 range)
        confidences: N array of confidence values
        depth: Octree depth (higher = more detail)
        width: Width parameter for reconstruction
        scale: Scale parameter for reconstruction
    
    Returns:
        vertices, faces, vertex_colors
    """
    print(f"🔧 Reconstructing surface using Poisson method...")
    print(f"   Input points: {len(points)}")
    print(f"   Octree depth: {depth}")
    
    try:
        # Try to use Open3D for Poisson reconstruction
        import open3d as o3d
        
        # Create Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)
        
        # Estimate normals
        pcd.estimate_normals()
        
        # Poisson reconstruction
        mesh, _ = pcd.create_mesh_poisson(depth=depth, width=width, scale=scale)
        
        # Extract vertices and faces
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.triangles)
        
        # Get vertex colors (interpolated from point cloud)
        vertex_colors = []
        for vertex in vertices:
            # Find nearest point for color assignment
            distances = np.linalg.norm(points - vertex, axis=1)
            nearest_idx = np.argmin(distances)
            vertex_colors.append(colors[nearest_idx])
        
        vertex_colors = np.array(vertex_colors)
        
        print(f"   Generated mesh: {len(vertices)} vertices, {len(faces)} faces")
        
        return vertices, faces, vertex_colors
        
    except ImportError:
        print("   ⚠️  Open3D not available, using Delaunay triangulation fallback")
        return reconstruct_surface_delaunay(points, colors, confidences)


def reconstruct_surface_delaunay(points, colors, confidences, max_points=10000):
    """
    Reconstruct surface using Delaunay triangulation (fallback method)
    
    Args:
        points: Nx3 array of 3D coordinates
        colors: Nx3 array of RGB colors (0-1 range)
        confidences: N array of confidence values
        max_points: Maximum points for triangulation (performance limit)
    
    Returns:
        vertices, faces, vertex_colors
    """
    print(f"🔧 Reconstructing surface using Delaunay triangulation...")
    print(f"   Input points: {len(points)}")
    
    # Subsample for performance
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        colors = colors[indices]
        confidences = confidences[indices]
        print(f"   Subsampled to {max_points} points for triangulation")
    
    # Project to 2D for Delaunay triangulation
    # Use PCA to find the best 2D projection
    from sklearn.decomposition import PCA
    pca = PCA(n_components=2)
    points_2d = pca.fit_transform(points)
    
    # Perform Delaunay triangulation in 2D
    tri = Delaunay(points_2d)
    
    # Convert 2D triangles to 3D faces
    faces = tri.simplices
    
    # Vertices are the original 3D points
    vertices = points
    vertex_colors = colors
    
    print(f"   Generated mesh: {len(vertices)} vertices, {len(faces)} faces")
    
    return vertices, faces, vertex_colors


def reconstruct_surface_alpha_shape(points, colors, confidences, alpha=None):
    """
    Reconstruct surface using alpha shapes
    
    Args:
        points: Nx3 array of 3D coordinates
        colors: Nx3 array of RGB colors (0-1 range)
        confidences: N array of confidence values
        alpha: Alpha parameter (auto-determined if None)
    
    Returns:
        vertices, faces, vertex_colors
    """
    print(f"🔧 Reconstructing surface using alpha shapes...")
    print(f"   Input points: {len(points)}")
    
    try:
        from scipy.spatial import ConvexHull
        from scipy.spatial.distance import pdist
        
        # Subsample for performance
        max_points = 5000
        if len(points) > max_points:
            indices = np.random.choice(len(points), max_points, replace=False)
            points = points[indices]
            colors = colors[indices]
            confidences = confidences[indices]
            print(f"   Subsampled to {max_points} points for alpha shape")
        
        # Auto-determine alpha if not provided
        if alpha is None:
            distances = pdist(points)
            alpha = np.percentile(distances, 10)  # Use 10th percentile as alpha
            print(f"   Auto-determined alpha: {alpha:.4f}")
        
        # Create convex hull as approximation
        hull = ConvexHull(points)
        
        vertices = points[hull.vertices]
        faces = hull.simplices
        
        # Get colors for hull vertices
        vertex_colors = colors[hull.vertices]
        
        print(f"   Generated mesh: {len(vertices)} vertices, {len(faces)} faces")
        
        return vertices, faces, vertex_colors
        
    except Exception as e:
        print(f"   ⚠️  Alpha shape failed: {e}")
        return reconstruct_surface_delaunay(points, colors, confidences)


def visualize_mesh_interactive(vertices, faces, vertex_colors, title="3D Mesh"):
    """
    Create interactive 3D mesh visualization using Plotly
    
    Args:
        vertices: Nx3 array of vertex coordinates
        faces: Mx3 array of face indices
        vertex_colors: Nx3 array of vertex colors (0-1 range)
        title: Plot title
    
    Returns:
        plotly figure
    """
    print(f"🎨 Creating interactive 3D mesh visualization...")
    print(f"   Vertices: {len(vertices)}, Faces: {len(faces)}")
    
    # Convert colors to RGB format for Plotly
    colors_rgb = (vertex_colors * 255).astype(int)
    colors_str = [f'rgb({r},{g},{b})' for r, g, b in colors_rgb]
    
    # Create mesh trace
    mesh_trace = go.Mesh3d(
        x=vertices[:, 0],
        y=vertices[:, 1],
        z=vertices[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        vertexcolor=colors_str,
        lighting=dict(ambient=0.7, diffuse=0.8, specular=0.2),
        lightposition=dict(x=100, y=200, z=0),
        name='Mesh'
    )
    
    # Create figure
    fig = go.Figure(data=[mesh_trace])
    
    # Update layout
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title='X',
            yaxis_title='Y',
            zaxis_title='Z',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5)
            ),
            aspectmode='data'
        ),
        width=800,
        height=600
    )
    
    return fig


def save_mesh_obj(vertices, faces, vertex_colors, filename):
    """
    Save mesh as OBJ file
    
    Args:
        vertices: Nx3 array of vertex coordinates
        faces: Mx3 array of face indices (1-indexed for OBJ)
        vertex_colors: Nx3 array of vertex colors (0-1 range)
        filename: Output filename
    """
    print(f"💾 Saving mesh as OBJ: {filename}")
    
    with open(filename, 'w') as f:
        # Write vertices with colors
        for i, (vertex, color) in enumerate(zip(vertices, vertex_colors)):
            f.write(f"v {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f} {color[0]:.6f} {color[1]:.6f} {color[2]:.6f}\n")
        
        # Write faces (1-indexed)
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
    
    print(f"   Saved {len(vertices)} vertices, {len(faces)} faces")


def visualize_surface_reconstruction(filename, max_points=100000, method='poisson', interactive=True):
    """
    Visualize point cloud with surface reconstruction
    
    Args:
        filename: PLY file path
        max_points: Maximum points to process
        method: Reconstruction method ('poisson', 'delaunay', 'alpha_shape')
        interactive: Use interactive Plotly visualization
    
    Returns:
        None
    """
    print(f"🔧 Surface Reconstruction Visualization")
    print(f"   File: {filename}")
    print(f"   Method: {method}")
    print(f"   Interactive: {interactive}")
    
    # Load point cloud
    points, colors, confidences = read_ply_file(filename)
    
    print(f"   Loaded {len(points)} points")
    
    # Subsample for performance
    if len(points) > max_points:
        indices = np.random.choice(len(points), max_points, replace=False)
        points = points[indices]
        colors = colors[indices]
        confidences = confidences[indices]
        print(f"   Subsampled to {max_points} points")
    
    # Reconstruct surface
    if method == 'poisson':
        vertices, faces, vertex_colors = reconstruct_surface_poisson(points, colors, confidences)
    elif method == 'delaunay':
        vertices, faces, vertex_colors = reconstruct_surface_delaunay(points, colors, confidences)
    elif method == 'alpha_shape':
        vertices, faces, vertex_colors = reconstruct_surface_alpha_shape(points, colors, confidences)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Save mesh
    mesh_filename = filename.replace('.ply', f'_{method}_mesh.obj')
    save_mesh_obj(vertices, faces, vertex_colors, mesh_filename)
    
    if interactive:
        # Create interactive visualization
        fig = visualize_mesh_interactive(vertices, faces, vertex_colors, f"Surface Reconstruction ({method})")
        
        # Save interactive HTML
        html_filename = filename.replace('.ply', f'_{method}_mesh.html')
        fig.write_html(html_filename)
        print(f"💾 Saved interactive visualization: {html_filename}")
        
        # Show plot
        fig.show()
    else:
        # Fallback to matplotlib
        print("   Using matplotlib fallback (interactive disabled)")
        visualize_ply(filename, max_points=max_points, enhance=False, comparison=False)



def visualize_ply(filename, max_points=100000, enhance=True, comparison=True):
    """Visualize PLY file with matplotlib, optionally enhanced with Gaussian interpolation"""
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
    
    # Apply Gaussian enhancement if requested
    if enhance:
        try:
            enhanced_points, enhanced_colors, enhanced_confidences = enhance_point_cloud_gaussian(
                points, colors, confidences, voxel_size=0.005, sigma=0.3, max_points=50000
            )
            
            # Create comparison plot
            if comparison:
                fig = plt.figure(figsize=(20, 10))
            
                # Plot 1: Original point cloud
                ax1 = fig.add_subplot(221, projection='3d')
                ax1.scatter(points[:, 0], points[:, 1], points[:, 2], 
                            c=colors, s=1, alpha=0.6)
                ax1.set_xlabel('X')
                ax1.set_ylabel('Y')
                ax1.set_zlabel('Z')
                ax1.set_title(f'Original ({len(points):,} points)', fontsize=12, fontweight='bold')
                
                # Plot 2: Enhanced point cloud
                ax2 = fig.add_subplot(222, projection='3d')
                ax2.scatter(enhanced_points[:, 0], enhanced_points[:, 1], enhanced_points[:, 2], 
                            c=enhanced_colors, s=1, alpha=0.6)
                ax2.set_xlabel('X')
                ax2.set_ylabel('Y')
                ax2.set_zlabel('Z')
                ax2.set_title(f'Gaussian Enhanced ({len(enhanced_points):,} points)', fontsize=12, fontweight='bold')
                
                # Plot 3: Original confidence
                ax3 = fig.add_subplot(223, projection='3d')
                scatter3 = ax3.scatter(points[:, 0], points[:, 1], points[:, 2], 
                                      c=confidences, s=1, alpha=0.6, cmap='viridis')
                ax3.set_xlabel('X')
                ax3.set_ylabel('Y')
                ax3.set_zlabel('Z')
                ax3.set_title('Original Confidence', fontsize=12, fontweight='bold')
                plt.colorbar(scatter3, ax=ax3, label='Confidence')
                
                # Plot 4: Enhanced confidence
                ax4 = fig.add_subplot(224, projection='3d')
                scatter4 = ax4.scatter(enhanced_points[:, 0], enhanced_points[:, 1], enhanced_points[:, 2], 
                                      c=enhanced_confidences, s=1, alpha=0.6, cmap='viridis')
                ax4.set_xlabel('X')
                ax4.set_ylabel('Y')
                ax4.set_zlabel('Z')
                ax4.set_title('Enhanced Confidence', fontsize=12, fontweight='bold')
                plt.colorbar(scatter4, ax=ax4, label='Confidence')
                
                # Add comparison stats
                enhancement_ratio = len(enhanced_points) / len(points)
                fig.suptitle(f'Point Cloud Enhancement Comparison - {enhancement_ratio:.1f}x more points', 
                            fontsize=14, fontweight='bold')
                
                # Save comparison image
                comparison_file = filename.replace('.ply', '_comparison.png')
                plt.savefig(comparison_file, dpi=150, bbox_inches='tight')
                print(f"💾 Saved comparison image: {comparison_file}")
            else:
                # Simple enhanced view without comparison
                fig = plt.figure(figsize=(12, 8))
                ax = fig.add_subplot(111, projection='3d')
                ax.scatter(enhanced_points[:, 0], enhanced_points[:, 1], enhanced_points[:, 2], 
                          c=enhanced_colors, s=1, alpha=0.6)
                ax.set_xlabel('X')
                ax.set_ylabel('Y')
                ax.set_zlabel('Z')
                ax.set_title(f'Enhanced Point Cloud ({len(enhanced_points):,} points)')
            
        except Exception as e:
            print(f"⚠️  Enhancement failed: {e}")
            print("   Falling back to original visualization")
            enhance = False
    
    if not enhance:
        # Original visualization without enhancement
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

def find_latest_s3_reconstruction(bucket_name="frame-storage", prefix="output"):
    """Find the most recent reconstruction in S3 (output/job_*/reconstruction.ply)"""
    try:
        import boto3
        from datetime import datetime
    except ImportError:
        return None
    
    try:
        s3_client = boto3.client('s3')
        
        # List all jobs in output/ directory
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix + '/',
            Delimiter='/'
        )
        
        if 'CommonPrefixes' not in response:
            return None
        
        # Get all job directories (output/job_*)
        jobs = []
        for prefix_obj in response['CommonPrefixes']:
            job_prefix = prefix_obj['Prefix']
            job_id = job_prefix.rstrip('/').split('/')[-1]
            
            # Only process job_* directories
            if not job_id.startswith('job_'):
                continue
            
            # List PLY files in this job directory
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
    
    # Parse command line arguments
    args = sys.argv[1:]
    ply_file_arg = None
    
    # Look for PLY file argument (not starting with --)
    for arg in args:
        if not arg.startswith('--'):
            ply_file_arg = arg
            break
    
    # If no PLY file specified, find the most recent reconstruction
    if ply_file_arg is None:
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
                print("\nUsage: python view_ply.py [ply_file] [max_points] [options]")
                print("\nPoint Cloud Visualization:")
                print("  python view_ply.py                              # Open latest with comparison")
                print("  python view_ply.py point_clouds/frame_000001.ply")
                print("  python view_ply.py output.ply 500000            # Show 500k points")
                print("  python view_ply.py s3://bucket/path/to/file.ply # From S3")
                print("  python view_ply.py output.ply --no-enhance     # Disable Gaussian enhancement")
                print("  python view_ply.py output.ply --no-comparison  # Enhanced view only")
                print("\nSurface Reconstruction:")
                print("  python view_ply.py output.ply --surface        # Poisson reconstruction")
                print("  python view_ply.py output.ply --surface --method=delaunay  # Delaunay triangulation")
                print("  python view_ply.py output.ply --surface --method=alpha_shape  # Alpha shapes")
                print("  python view_ply.py output.ply --surface --no-interactive  # Static visualization")
                print("\nNote: Will use CloudCompare if installed, otherwise matplotlib")
                print("      Gaussian enhancement fills gaps in point clouds for better visualization")
                print("      Surface reconstruction creates 3D meshes from point clouds")
                print("      Interactive mode uses Plotly for 3D mesh visualization")
                sys.exit(1)
    else:
        ply_file = ply_file_arg
    
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
        # Parse arguments for max_points, enhance, comparison, and surface reconstruction
        max_points = 100000
        enhance = True
        comparison = True
        surface_reconstruction = False
        reconstruction_method = 'poisson'
        interactive = True
        
        for arg in args:
            if arg.isdigit():
                max_points = int(arg)
            elif arg == '--no-enhance':
                enhance = False
            elif arg == '--no-comparison':
                comparison = False
            elif arg == '--surface':
                surface_reconstruction = True
            elif arg.startswith('--method='):
                reconstruction_method = arg.split('=')[1]
            elif arg == '--no-interactive':
                interactive = False
        
        # Choose visualization method
        if surface_reconstruction:
            visualize_surface_reconstruction(ply_file, max_points=max_points, 
                                           method=reconstruction_method, interactive=interactive)
        else:
            visualize_ply(ply_file, max_points=max_points, enhance=enhance, comparison=comparison)
    finally:
        # Clean up temp file after matplotlib viewing
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"\n🗑️  Cleaned up temporary file")
            except:
                pass
