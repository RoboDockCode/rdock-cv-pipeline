# RoboDock MAST3R RunPod Architecture

## Overview

Distributed 3D reconstruction pipeline using local capture + cloud processing.

## Architecture Diagram

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Laptop    │         │   AWS S3     │         │   RunPod    │
│  (Capture)  │────────▶│  (Storage)   │────────▶│ (GPU Proc)  │
│             │         │              │         │             │
│  - Camera   │   1     │ - Input imgs │   2     │ - MAST3R    │
│  - Uploader │  Upload │ - Metadata   │  Fetch  │ - Inference │
└─────────────┘         └──────────────┘         └─────────────┘
       ▲                       │                         │
       │                       │                         │
       │                       ▼                         │
       │                ┌──────────────┐                 │
       │                │   AWS S3     │◀────────────────┘
       │                │  (Results)   │        3
       │                │              │      Upload
       │                │ - PLY files  │
       │                │ - Stats      │
       └────────────────│ - Viz        │
              4         └──────────────┘
            Download
```

## Components

### 1. Local Capture Script (`capture_and_upload.py`)
**Purpose:** Capture images from laptop camera and upload to S3

**Features:**
- Capture video frames with camera
- Bundle images with metadata
- Upload to S3 input bucket
- Create job manifest

**Output:**
```
s3://rdock-reconstruction-input/jobs/job_<timestamp>/
├── images/
│   ├── img_001.jpg
│   ├── img_002.jpg
│   └── ...
├── metadata.json
└── manifest.json
```

**Metadata Format:**
```json
{
  "job_id": "job_20251003_203045",
  "capture_date": "2025-10-03T20:30:45Z",
  "num_frames": 7,
  "capture_duration": 15.0,
  "interval": 2.0,
  "camera": {
    "resolution": [1920, 1080],
    "fps": 30
  },
  "reconstruction_params": {
    "mode": "realistic",
    "global_alignment": true,
    "conf_threshold": 3.0
  }
}
```

### 2. S3 Storage Structure

**Input Bucket: `rdock-reconstruction-input`**
```
jobs/
├── job_20251003_203045/
│   ├── images/
│   │   ├── img_001.jpg
│   │   ├── img_002.jpg
│   │   └── ...
│   ├── metadata.json
│   └── status.json (updated by RunPod)
```

**Output Bucket: `rdock-reconstruction-output`**
```
jobs/
└── job_20251003_203045/
    ├── reconstruction.ply
    ├── visualization.png
    ├── stats.json
    └── logs.txt
```

### 3. RunPod Processing Script (`runpod_processor.py`)

**Purpose:** Poll S3, process jobs, upload results

**Workflow:**
1. Poll S3 input bucket for new jobs
2. Download images and metadata
3. Run MAST3R reconstruction
4. Upload PLY and visualizations to output bucket
5. Update job status

**Key Features:**
- Automatic job discovery
- GPU acceleration
- Error handling and retry
- Progress reporting
- Memory management for large reconstructions

**Environment Variables:**
```bash
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
S3_INPUT_BUCKET=rdock-reconstruction-input
S3_OUTPUT_BUCKET=rdock-reconstruction-output
RUNPOD_GPU_TYPE=RTX4090
```

### 4. Local Visualizer (`download_and_visualize.py`)

**Purpose:** Download and visualize results

**Features:**
- Poll output bucket for completed jobs
- Download PLY files
- Launch interactive visualizer
- Cache results locally

## Workflow Details

### Step 1: Capture and Upload
```bash
# On laptop
python scripts/capture_and_upload.py --duration 15 --interval 2 --upload
```

**What happens:**
1. Opens camera and captures frames
2. Saves frames to temp directory
3. Creates metadata.json
4. Uploads to S3 input bucket
5. Prints job ID for tracking

### Step 2: RunPod Processing
```bash
# On RunPod instance (runs continuously)
python scripts/runpod_processor.py --watch
```

**What happens:**
1. Watches S3 input bucket
2. Detects new job directory
3. Downloads images and metadata
4. Runs MAST3R reconstruction based on metadata params
5. Uploads results to output bucket
6. Updates status file

### Step 3: Download and Visualize
```bash
# On laptop
python scripts/download_and_visualize.py --job-id job_20251003_203045
```

**What happens:**
1. Checks job status in output bucket
2. Downloads reconstruction.ply
3. Launches interactive viewer
4. Caches locally for offline viewing

## Implementation Plan

### Phase 1: Basic Pipeline ✓ (Current)
- [x] Local reconstruction working with GPU
- [x] PLY visualization working
- [x] Frame capture working

### Phase 2: S3 Integration (Next)
- [ ] Create `capture_and_upload.py`
- [ ] Create S3 bucket structure
- [ ] Create `download_and_visualize.py`
- [ ] Test upload → download flow

### Phase 3: RunPod Processing
- [ ] Create `runpod_processor.py`
- [ ] Set up RunPod template
- [ ] Test end-to-end pipeline
- [ ] Add error handling

### Phase 4: Improvements
- [ ] Add job queue/status tracking
- [ ] Add web interface
- [ ] Add batch processing
- [ ] Add cost tracking

## Cost Estimates

### RunPod GPU Options
| GPU | VRAM | Cost (spot) | Use Case |
|-----|------|-------------|----------|
| RTX 3090 | 24GB | $0.30/hr | Good for most jobs |
| RTX 4090 | 24GB | $0.40/hr | Faster processing |
| A40 | 48GB | $0.50/hr | Large reconstructions |

### Example Cost Calculation
**Scenario:** 20 reconstruction jobs per month, 2 minutes each

```
20 jobs × 2 min/job = 40 minutes/month
40 min ÷ 60 = 0.67 hours/month
0.67 hours × $0.40/hr = $0.27/month
```

**Compare to:**
- Running 24/7: $0.40/hr × 720hr = $288/month
- AWS g5.xlarge: ~$40/month for same usage
- **Savings: 99%** by using on-demand RunPod

## Security Considerations

1. **S3 Bucket Permissions:**
   - Input bucket: Laptop write, RunPod read
   - Output bucket: RunPod write, Laptop read
   - Use IAM roles, not root credentials

2. **API Keys:**
   - Store in environment variables
   - Never commit to git
   - Use RunPod secrets management

3. **Data Privacy:**
   - Enable S3 encryption at rest
   - Use HTTPS for all transfers
   - Consider private VPC for sensitive data

## Monitoring & Debugging

### Job Status File
```json
{
  "job_id": "job_20251003_203045",
  "status": "processing",
  "started_at": "2025-10-03T20:35:00Z",
  "progress": 0.45,
  "current_step": "global_alignment",
  "estimated_completion": "2025-10-03T20:37:00Z"
}
```

### Logging
- Local: `logs/capture_<timestamp>.log`
- RunPod: `logs/processing_<job_id>.log` (uploaded to S3)
- Errors: Captured in status.json

### Monitoring Dashboard (Future)
- Job queue length
- Processing time per job
- Cost per job
- Error rate
- GPU utilization

## Future Enhancements

### Web Interface
Replace local download script with web dashboard:
```
https://rdock-reconstruction.com
- Upload images via browser
- Monitor job status
- View/download results
- Gallery of past reconstructions
```

### Batch Processing
```bash
# Process multiple captures in one job
python scripts/batch_upload.py --directory captures/
# RunPod processes all in sequence
```

### Real-time Streaming
- Stream video from laptop to RunPod
- Process frames in real-time
- Stream back depth maps/point clouds

### Mobile App
- Capture from phone camera
- Upload to S3
- View results on phone

## Branch Strategy

```
main (production)
└── architecture/gpu-processing-pipeline (current feature branch)
    ├── feature/s3-upload (implement capture and upload)
    ├── feature/s3-download (implement download and viz)
    ├── feature/runpod-processor (implement cloud processing)
    └── feature/job-management (add status tracking)
```

**Workflow:**
1. Create sub-branch for each component
2. Develop and test in isolation
3. Merge to `architecture/gpu-processing-pipeline`
4. Once complete, merge to `main`

## Getting Started

### Prerequisites
```bash
# AWS CLI
aws configure

# Create S3 buckets
aws s3 mb s3://rdock-reconstruction-input
aws s3 mb s3://rdock-reconstruction-output

# Install dependencies
pip install boto3 tqdm
```

### Quick Start
```bash
# 1. Capture and upload
python scripts/capture_and_upload.py --duration 15 --interval 2

# 2. Wait for processing (or check status)
python scripts/check_status.py --job-id <job_id>

# 3. Download and visualize
python scripts/download_and_visualize.py --job-id <job_id>
```

## References

- [RunPod Documentation](https://docs.runpod.io/)
- [AWS S3 SDK (boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [MAST3R Paper](https://arxiv.org/abs/2406.09756)

