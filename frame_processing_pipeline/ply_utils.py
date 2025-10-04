"""Utilities for PLY file I/O operations"""
import struct
import numpy as np
import os


def write_ply(filename, points, colors, confidences=None):
    """
    Write points to PLY file with colors and optional confidence values
    
    Args:
        filename: Output PLY file path
        points: Nx3 array of 3D points
        colors: Nx3 array of RGB colors (0-255)
        confidences: Optional N array of confidence values
    """
    n_points = len(points)
    
    with open(filename, 'wb') as f:
        # Build header
        header_lines = [
            "ply",
            "format binary_little_endian 1.0",
            f"element vertex {n_points}",
            "property float x",
            "property float y",
            "property float z",
            "property uchar red",
            "property uchar green",
            "property uchar blue",
        ]
        
        if confidences is not None:
            header_lines.append("property float confidence")
        
        header_lines.append("end_header")
        header = '\n'.join(header_lines) + '\n'
        f.write(header.encode('ascii'))
        
        # Write vertex data
        for i in range(n_points):
            f.write(struct.pack('<fff', points[i, 0], points[i, 1], points[i, 2]))
            f.write(struct.pack('<BBB', colors[i, 0], colors[i, 1], colors[i, 2]))
            if confidences is not None:
                f.write(struct.pack('<f', confidences[i]))


def read_ply(filename):
    """
    Read PLY file and return points, colors, and optional confidences
    
    Returns:
        (points, colors, confidences) tuple where confidences may be None
    """
    points = []
    colors = []
    confidences = []
    has_confidence = False
    
    with open(filename, 'rb') as f:
        # Parse header
        while True:
            line = f.readline()
            if b'property float confidence' in line:
                has_confidence = True
            if line.strip() == b'end_header':
                break
        
        # Determine byte size per vertex
        bytes_per_vertex = 19 if has_confidence else 15  # xyz(12) + rgb(3) + conf(4)
        
        # Read vertex data
        while True:
            data = f.read(bytes_per_vertex)
            if len(data) < bytes_per_vertex:
                break
            
            if has_confidence:
                x, y, z, r, g, b, conf = struct.unpack('<fffBBBf', data)
                confidences.append(conf)
            else:
                x, y, z, r, g, b = struct.unpack('<fffBBB', data)
            
            points.append([x, y, z])
            colors.append([r, g, b])
    
    points = np.array(points)
    colors = np.array(colors)
    confidences = np.array(confidences) if has_confidence else None
    
    return points, colors, confidences


def get_ply_point_count(filename):
    """Get the number of points in a PLY file from its header"""
    try:
        with open(filename, 'rb') as f:
            while True:
                line = f.readline().decode('ascii').strip()
                if line.startswith('element vertex'):
                    return int(line.split()[-1])
                elif line == 'end_header':
                    break
        return 0
    except Exception as e:
        print(f"Error reading PLY header: {e}")
        return 0


def merge_ply_files(ply_files, output_file):
    """
    Merge multiple PLY files into a single file
    
    Args:
        ply_files: List of PLY file paths to merge
        output_file: Output merged PLY file path
        
    Returns:
        output_file path if successful, None otherwise
    """
    all_points = []
    all_colors = []
    all_confidences = []
    has_confidence = False
    valid_files = 0
    
    for ply_file in ply_files:
        if not os.path.exists(ply_file):
            continue
            
        points, colors, confs = read_ply(ply_file)
        
        if len(points) > 0:
            all_points.append(points)
            all_colors.append(colors)
            
            if confs is not None:
                all_confidences.append(confs)
                has_confidence = True
            
            valid_files += 1
            print(f"  ✅ Loaded {len(points):,} points from {os.path.basename(ply_file)}")
        else:
            print(f"  ⚠️  Skipping empty file: {os.path.basename(ply_file)}")
    
    if len(all_points) < 2:
        print(f"❌ Need at least 2 valid point clouds, found {len(all_points)}")
        return None
    
    # Merge arrays
    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    merged_confs = np.concatenate(all_confidences) if has_confidence else None
    
    # Write merged file
    write_ply(output_file, merged_points, merged_colors, merged_confs)
    print(f"✅ Merged {valid_files} point clouds into {output_file}")
    
    return output_file

