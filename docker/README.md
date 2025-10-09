# Docker Configuration

This directory contains all Docker-related files for the MAST3R 3D reconstruction pipeline.

## 📁 Directory Structure

```
docker/
├── Dockerfile              # Main Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore          # Files to exclude from build
├── docs/                   # Documentation
│   ├── README_DOCKER.md       # Complete usage guide
│   ├── DOCKER_QUICKSTART.md   # Quick reference
│   └── DOCKERIZATION_SUMMARY.md  # Technical overview
└── scripts/                # Helper scripts
    ├── entrypoint.sh          # Container entrypoint
    └── test_docker.sh         # Automated tests
```

## 🚀 Quick Start

**Run all commands from the project root directory** (parent of this `docker/` folder).

### Build
```bash
docker-compose -f docker/docker-compose.yml build
```

### Run
```bash
# Process captures
docker-compose -f docker/docker-compose.yml run --rm reconstruction "python process_captures.py"

# Interactive shell
docker-compose -f docker/docker-compose.yml run --rm reconstruction bash
```

### Test
```bash
./docker/scripts/test_docker.sh
```

## 📖 Documentation

- **[Quick Start](docs/DOCKER_QUICKSTART.md)** - Essential commands
- **[Full Guide](docs/README_DOCKER.md)** - Complete documentation
- **[Technical Summary](docs/DOCKERIZATION_SUMMARY.md)** - Implementation details

## 🔧 Configuration Files

### `Dockerfile`
- Base: NVIDIA CUDA 11.8 with cuDNN 8
- Python 3.9 with PyTorch (GPU enabled)
- Auto-downloads MAST3R model weights
- Creates `/app` working directory

### `docker-compose.yml`
- GPU passthrough configuration
- Volume mounts for data persistence
- Environment variables for AWS/Python
- Port 8000 exposed for future API

### `.dockerignore`
Excludes unnecessary files from build context:
- Cache files (`__pycache__`, `*.pyc`)
- Output files (already volume-mounted)
- Development files (`.git`, IDE configs)

## 🎯 Design Goals

1. **No API lock-in** - Use existing scripts as-is
2. **Portable** - Works anywhere with Docker + NVIDIA drivers
3. **Future-ready** - Easy to add API layer later
4. **Clean separation** - Docker files isolated from code

## 💡 Tips

### Shorter Commands
You can create an alias:
```bash
alias dc='docker-compose -f docker/docker-compose.yml'
dc build
dc run --rm reconstruction bash
```

### Development Mode
Uncomment volume mounts in `docker-compose.yml` to live-edit code:
```yaml
volumes:
  # ... existing ...
  - ../scripts:/app/scripts
  - ../frame_processing_pipeline:/app/frame_processing_pipeline
```

### Without Docker Compose
```bash
# Build
docker build -f docker/Dockerfile -t rdock-cv-pipeline .

# Run
docker run --rm --gpus all -v $(pwd)/captures:/app/captures rdock-cv-pipeline python process_captures.py
```

## 🆘 Troubleshooting

See the [full documentation](docs/README_DOCKER.md#-troubleshooting) for detailed troubleshooting steps.

Common issues:
- **GPU not detected**: Check nvidia-docker2 installation
- **Permission errors**: Use `--user $(id -u):$(id -g)` flag
- **Build fails**: Ensure good internet for model download

