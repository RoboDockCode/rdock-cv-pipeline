# Docker Usage Guide - MAST3R 3D Reconstruction Pipeline

This guide explains how to use the dockerized MAST3R 3D reconstruction pipeline.

> **Important**: All commands should be run from the **project root directory**, not from inside the `docker/` folder.

## 📋 Prerequisites

1. **Docker** (v20.10+) and **Docker Compose** (v2.0+)
2. **NVIDIA Docker runtime** (for GPU support)
   ```bash
   # Install nvidia-docker2
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   sudo apt-get update && sudo apt-get install -y nvidia-docker2
   sudo systemctl restart docker
   ```

3. **NVIDIA GPU** with CUDA 11.8+ support (recommended, but CPU-only mode works too)

## 🚀 Quick Start

### 1. Build the Docker Image

```bash
# Build using docker-compose (recommended)
docker-compose -f docker/docker-compose.yml build

# Or build directly with docker
docker build -t rdock-cv-pipeline .
```

**Note**: First build will take ~15-20 minutes as it downloads:
- CUDA base image (~3GB)
- Python dependencies
- MAST3R model weights from HuggingFace (~2GB)

### 2. Verify Installation

```bash
# Check GPU is accessible
docker-compose run --rm reconstruction nvidia-smi

# Check Python environment
docker-compose run --rm reconstruction "python -c 'import torch; print(f\"CUDA available: {torch.cuda.is_available()}\")'"
```

## 📸 Usage Examples

### Process Existing Captures

Process images from the `captures/` directory:

```bash
# Process the latest capture automatically
docker-compose run --rm reconstruction "python process_captures.py"

# Process specific capture
docker-compose run --rm reconstruction "python process_captures.py --capture captures/capture_20251004_211506"
```

**Output**: Creates `.ply` file in the project root and uploads to S3 (if configured).

### Run Realistic Reconstruction

Use the realistic reconstruction script directly with custom images:

```bash
# Interactive shell - then run commands
docker-compose run --rm reconstruction bash
>>> python scripts/realistic_reconstruction_simple.py --help

# Or one-liner
docker-compose run --rm reconstruction "python -c '
from scripts.realistic_reconstruction_simple import RealisticReconstructor
import glob
images = sorted(glob.glob(\"captures/capture_20251004_211506/*.jpg\"))
rec = RealisticReconstructor()
rec.reconstruct(images, \"outputs/my_reconstruction.ply\")
'"
```

### Use as Python Library

```bash
# Start interactive Python shell in container
docker-compose run --rm reconstruction python

# Then in Python:
>>> from scripts.realistic_reconstruction_simple import RealisticReconstructor
>>> reconstructor = RealisticReconstructor()
>>> 
>>> # Load and process images
>>> import glob
>>> images = sorted(glob.glob('captures/capture_*/img_*.jpg'))
>>> result = reconstructor.reconstruct(images, 'outputs/result.ply')
>>> print(f"Created: {result}")
```

### View PLY Files

```bash
# Visualize a reconstruction
docker-compose run --rm reconstruction "python scripts/view_ply.py outputs/reconstruction.ply"

# Note: For GUI visualization, you'll need X11 forwarding or copy the file to host:
docker cp rdock-cv-reconstruction:/app/outputs/reconstruction.ply ./
python scripts/view_ply.py reconstruction.ply  # Run on host
```

## 🗂️ Volume Mounts

The Docker setup includes several volume mounts for data persistence:

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `./captures` | `/app/captures` | Input image sequences |
| `./outputs` | `/app/outputs` | Output PLY files |
| `./point_clouds` | `/app/point_clouds` | Intermediate point clouds |
| `model-cache` | `/root/.cache` | Cached model weights (persistent) |

### Adding Custom Images

```bash
# Create a new capture directory
mkdir -p captures/my_capture
cp /path/to/images/*.jpg captures/my_capture/

# Process them
docker-compose run --rm reconstruction "python -c '
from scripts.realistic_reconstruction_simple import RealisticReconstructor
import glob
images = sorted(glob.glob(\"captures/my_capture/*.jpg\"))
rec = RealisticReconstructor()
rec.reconstruct(images, \"outputs/my_output.ply\")
'"
```

## ☁️ AWS S3 Integration

### Configure AWS Credentials

```bash
# Option 1: Environment variables in shell
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
docker-compose run --rm reconstruction "python process_captures.py"

# Option 2: Create .env file
cat > .env << EOF
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1
EOF
docker-compose run --rm reconstruction "python process_captures.py"

# Option 3: Mount AWS credentials
docker-compose run --rm -v ~/.aws:/root/.aws reconstruction "python process_captures.py"
```

### S3 Upload Example

The `process_captures.py` script automatically uploads to S3 if credentials are configured:
- Bucket: `frame-storage`
- Path: `output/{job_id}/reconstruction.ply`

## 🔧 Advanced Usage

### Run as Background Service

```bash
# Start container in background
docker-compose up -d

# Execute commands in running container
docker-compose exec reconstruction python process_captures.py

# Stop service
docker-compose down
```

### Development Mode (Live Code Changes)

Uncomment volume mounts in `docker-compose.yml`:

```yaml
volumes:
  # ... existing mounts ...
  - ./scripts:/app/scripts
  - ./frame_processing_pipeline:/app/frame_processing_pipeline
```

Now changes to Python files are immediately reflected in the container.

### GPU Memory Management

```bash
# Limit GPU memory for multiple containers
docker-compose run --rm -e CUDA_VISIBLE_DEVICES=0 reconstruction "python process_captures.py"

# Monitor GPU usage
watch -n 1 "docker exec rdock-cv-reconstruction nvidia-smi"
```

### Custom Python Scripts

```bash
# Create custom script
cat > my_script.py << 'EOF'
import sys
sys.path.append('/app')
from scripts.realistic_reconstruction_simple import RealisticReconstructor
# ... your code ...
EOF

# Run it in container
docker-compose run --rm -v $(pwd)/my_script.py:/app/my_script.py reconstruction "python my_script.py"
```

## 🐛 Troubleshooting

### GPU Not Detected

```bash
# Verify nvidia-docker is installed
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check GPU in container
docker-compose run --rm reconstruction nvidia-smi
```

If this fails:
- Ensure nvidia-docker2 is installed
- Check NVIDIA drivers are up to date
- Restart Docker daemon: `sudo systemctl restart docker`

### Out of Memory

```bash
# Reduce batch size or image resolution
# Edit scripts to use smaller images or process fewer at once

# Or use CPU mode (slower)
docker-compose run --rm -e CUDA_VISIBLE_DEVICES="" reconstruction "python process_captures.py"
```

### Model Download Fails

If HuggingFace download fails during build:

```bash
# Build with network debugging
docker build --progress=plain --no-cache -t rdock-cv-pipeline .

# Or manually download after container starts
docker-compose run --rm reconstruction "python -c '
from mast3r.model import AsymmetricMASt3R
model = AsymmetricMASt3R.from_pretrained(\"naver/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric\")
'"
```

### Permission Issues

```bash
# If output files have wrong permissions
docker-compose run --rm --user $(id -u):$(id -g) reconstruction "python process_captures.py"

# Or fix after processing
sudo chown -R $USER:$USER outputs/ point_clouds/
```

## 📊 Performance Notes

- **GPU (RTX 3090)**: ~30-60 seconds for 10-15 images
- **GPU (T4)**: ~1-2 minutes for 10-15 images  
- **CPU Only**: ~10-20 minutes for 10-15 images (not recommended)

More images = longer processing but better reconstruction quality.

## 🔮 Future API Layer

The Docker setup is ready for adding a REST API:

```bash
# When API is added, start server:
docker-compose up -d

# API will be available at:
# http://localhost:8000
```

Port 8000 is already exposed in the docker-compose configuration.

## 📝 Notes

- Model weights are cached in a Docker volume (`model-cache`) so they persist across container rebuilds
- First run will be slower as the model initializes
- Reconstruction quality improves with more diverse viewpoints
- For best results, use 10-20 images with good overlap between views

## 🆘 Support

For issues:
1. Check logs: `docker-compose logs`
2. Run with verbose output: `docker-compose run --rm reconstruction "python -u process_captures.py"`
3. Check GPU status: `docker-compose run --rm reconstruction nvidia-smi`

