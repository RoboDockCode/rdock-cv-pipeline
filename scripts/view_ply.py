#!/usr/bin/env python3
"""
Simple PLY viewer using matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import struct
import sys

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

def visualize_ply(filename, max_points=10000):
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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python view_ply.py <ply_file>")
        print("Example: python view_ply.py point_clouds/frame_000001.ply")
        sys.exit(1)
    
    ply_file = sys.argv[1]
    visualize_ply(ply_file)
