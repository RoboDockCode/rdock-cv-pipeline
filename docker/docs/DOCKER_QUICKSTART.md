# 🐋 Docker Quick Start - MAST3R 3D Reconstruction

> **Note**: Run all commands from the project root directory.

## Build

```bash
docker-compose -f docker/docker-compose.yml build
```

## Run

### Process Captures
```bash
# Process latest capture automatically
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python process_captures.py"
```

### Interactive Shell
```bash
docker-compose -f docker/docker-compose.yml run --rm reconstruction bash
```

### Python Shell
```bash
docker-compose -f docker/docker-compose.yml run --rm reconstruction python
```

### Custom Script
```bash
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python scripts/realistic_reconstruction_simple.py"
```

## Add Images

```bash
# Create new capture folder
mkdir -p captures/my_capture
cp /path/to/images/*.jpg captures/my_capture/

# Process them
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python process_captures.py"
```

## AWS S3 Setup

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python process_captures.py"
```

## Verify GPU

```bash
docker-compose -f docker/docker-compose.yml run --rm reconstruction nvidia-smi
```

## 📖 Full Documentation

See [README_DOCKER.md](README_DOCKER.md) for complete usage guide.

