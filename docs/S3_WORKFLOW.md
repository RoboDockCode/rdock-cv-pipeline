# S3-Based Decoupled Workflow

This document describes the decoupled capture and inference workflow using S3 as the data pipeline.

## Architecture Overview

```
┌──────────────────┐
│  Local Machine   │
│  (with camera)   │
└────────┬─────────┘
         │ capture_to_s3.py
         ▼
┌─────────────────────────────────┐
│          S3 Bucket              │
│  ┌─────────────────────────┐   │
│  │   input/frames/         │   │
│  │   └── session_id/       │   │
│  │       ├── frame_000.jpg │   │
│  │       ├── frame_001.jpg │   │
│  │       └── metadata.json │   │
│  └─────────────────────────┘   │
└────────┬────────────────────────┘
         │ infer_from_s3.py
         ▼
┌──────────────────┐
│ Digital Ocean    │
│ GPU Droplet      │
│ (MAST3R model)   │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────────┐
│          S3 Bucket              │
│  ┌─────────────────────────┐   │
│  │ output/reconstructions/ │   │
│  │   └── session_id/       │   │
│  │       └── result.ply    │   │
│  └─────────────────────────┘   │
└─────────────────────────────────┘
```

## Benefits of This Architecture

1. **Decoupled Processing**: Capture and inference are completely independent
2. **Scalable**: Multiple GPU workers can process different sessions in parallel
3. **Flexible**: Capture on edge devices, process in cloud
4. **Persistent Storage**: All data stored in S3 for reprocessing or auditing
5. **Async Processing**: Capture can continue while inference runs on previous sessions

## Setup

### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://your-bucket-name --region us-east-2

# Or use AWS Console
```

### 2. Set Bucket Structure (automatically created)

```
your-bucket-name/
├── input/
│   └── frames/
│       ├── 20231010_143000/
│       ├── 20231010_144500/
│       └── ...
└── output/
    └── reconstructions/
        ├── 20231010_143000/
        ├── 20231010_144500/
        └── ...
```

### 3. Configure AWS Credentials

On both local machine and GPU server:

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-2
# Default output format: json
```

## Usage

### Step 1: Capture Frames (Local Machine or Edge Device)

```bash
# Basic capture (30 seconds, one frame every 2 seconds)
python scripts/capture_to_s3.py --bucket your-bucket-name

# Custom duration and interval
python scripts/capture_to_s3.py --bucket your-bucket-name --duration 60 --interval 1.5

# With custom session ID
python scripts/capture_to_s3.py --bucket your-bucket-name --session robot_capture_001
```

**Output:**
```
📸 FRAME CAPTURE TO S3
============================================================
🪣  Bucket: your-bucket-name
📁 Prefix: input/frames/20231010_143000
⏱️  Duration: 30s
📷 Interval: 2.0s
============================================================
✅ S3 connection established
✅ Camera opened

🎥 Capturing... Press 'q' to stop early
------------------------------------------------------------
📸 Frame   1 captured ( 6.7% complete)
📸 Frame   2 captured (13.3% complete)
...

============================================================
☁️  UPLOADING TO S3
============================================================
📦 Uploading 15 frames...
✅ Uploaded: input/frames/20231010_143000/frame_000000.jpg
...

============================================================
✅ CAPTURE COMPLETE
============================================================
📋 Session ID: 20231010_143000
📸 Frames uploaded: 15
📁 S3 location: s3://your-bucket-name/input/frames/20231010_143000/

🔄 Next step: Run inference with this session ID
   python scripts/infer_from_s3.py --bucket your-bucket-name --session 20231010_143000
```

### Step 2: Run Inference (GPU Server)

```bash
# Process latest session automatically
python scripts/infer_from_s3.py --bucket your-bucket-name

# Process specific session
python scripts/infer_from_s3.py --bucket your-bucket-name --session 20231010_143000

# Keep local copy of result
python scripts/infer_from_s3.py --bucket your-bucket-name --keep-local

# List available sessions
python scripts/infer_from_s3.py --bucket your-bucket-name --list
```

**Output:**
```
🧠 MAST3R INFERENCE FROM S3
============================================================
🪣  Bucket: your-bucket-name
📥 Input: input/frames
📤 Output: output/reconstructions
✅ S3 connection established
📋 Session ID: 20231010_143000

🔍 Looking for frames...
✅ Found 15 frames

📥 DOWNLOADING FRAMES
------------------------------------------------------------
📥 Downloading 15 frames...
   Downloaded 5/15
   Downloaded 10/15
   Downloaded 15/15
✅ Downloaded 15/15 frames

============================================================
🧠 RUNNING INFERENCE
============================================================
Loading MAST3R for realistic reconstruction...
✅ Model loaded
📖 Loading images...
🔗 Creating pairs...
🧠 Running inference...
🌍 Global alignment...
⚙️  Optimizing...
Final loss: 0.002341
🎨 Extracting point cloud...
✅ Saved: reconstruction_20231010_143000.ply (125,432 points)

============================================================
☁️  UPLOADING RESULT
============================================================
✅ Uploaded: output/reconstructions/20231010_143000/reconstruction_20231010_143000.ply

============================================================
✅ INFERENCE COMPLETE
============================================================
📋 Session ID: 20231010_143000
📸 Frames processed: 15
📁 Result location: s3://your-bucket-name/output/reconstructions/20231010_143000/reconstruction_20231010_143000.ply
```

### Step 3: Download Results

```bash
# Download specific reconstruction
aws s3 cp s3://your-bucket-name/output/reconstructions/20231010_143000/reconstruction_20231010_143000.ply ./

# Download all reconstructions
aws s3 sync s3://your-bucket-name/output/reconstructions/ ./local_results/

# Visualize
python scripts/view_ply.py reconstruction_20231010_143000.ply
```

## Advanced Usage

### Batch Processing

Process multiple sessions in parallel on GPU server:

```bash
# List sessions
python scripts/infer_from_s3.py --bucket your-bucket-name --list

# Process each in separate terminals or background jobs
python scripts/infer_from_s3.py --bucket your-bucket-name --session 20231010_143000 &
python scripts/infer_from_s3.py --bucket your-bucket-name --session 20231010_144500 &
```

### Continuous Capture

Capture multiple sessions in sequence:

```bash
# Capture session 1
python scripts/capture_to_s3.py --bucket your-bucket-name --session capture_01

# Wait or immediately start session 2
python scripts/capture_to_s3.py --bucket your-bucket-name --session capture_02
```

### Automated Workflow

Create a workflow script:

```bash
#!/bin/bash
# workflow.sh

BUCKET="your-bucket-name"
SESSION=$(date +%Y%m%d_%H%M%S)

# Step 1: Capture
echo "Starting capture for session: $SESSION"
python scripts/capture_to_s3.py --bucket $BUCKET --session $SESSION

# Step 2: Trigger inference (can be on different machine)
echo "Triggering inference..."
ssh gpu-server "cd rdock-cv-pipeline && python scripts/infer_from_s3.py --bucket $BUCKET --session $SESSION"

# Step 3: Download result
echo "Downloading result..."
aws s3 cp s3://$BUCKET/output/reconstructions/$SESSION/ ./results/$SESSION/ --recursive

echo "Complete! Result in ./results/$SESSION/"
```

## S3 Bucket Policies

### Recommended IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

### Lifecycle Rules (Optional Cost Optimization)

Delete old input frames after processing:

```bash
# AWS Console: S3 → Bucket → Management → Lifecycle rules
# Rule: Delete objects in input/frames/ after 7 days
```

## Cost Estimation

### S3 Storage
- **Frames**: ~15 frames × 200KB = ~3MB per session
- **Reconstruction**: ~5-10MB per session
- **Monthly (100 sessions)**: ~1GB = $0.023/month

### S3 Requests
- **PUT requests**: 15 frames + 1 PLY = 16 requests = $0.00008
- **GET requests**: 15 frames = 15 requests = $0.00006
- **Per session**: ~$0.00014

### Data Transfer
- **Upload (free from internet)**: $0
- **Download to internet**: ~10MB × $0.09/GB = $0.0009
- **Within AWS**: Free if same region

**Total cost per session**: < $0.01

## Monitoring

### Check Session Status

```bash
# List all sessions
python scripts/infer_from_s3.py --bucket your-bucket-name --list

# Check specific session
aws s3 ls s3://your-bucket-name/input/frames/20231010_143000/
aws s3 ls s3://your-bucket-name/output/reconstructions/20231010_143000/
```

### Session Metadata

Each session includes a `metadata.json` file:

```json
{
  "session_id": "20231010_143000",
  "timestamp": "2023-10-10T14:30:00.123456",
  "frame_count": 15,
  "frames": [
    "input/frames/20231010_143000/frame_000000.jpg",
    "input/frames/20231010_143000/frame_000001.jpg",
    ...
  ]
}
```

## Troubleshooting

### Issue: "No sessions found in S3"
- Check bucket name is correct
- Verify AWS credentials are configured
- Check S3 prefix matches (default: `input/frames`)

### Issue: "Not enough frames found"
- Check frames were actually uploaded: `aws s3 ls s3://bucket/input/frames/session/`
- Verify session ID is correct
- Ensure at least 2 frames exist

### Issue: "Failed to upload result to S3"
- Check IAM permissions include `s3:PutObject`
- Verify network connectivity to S3
- Check disk space for temporary files

### Issue: "Model loading failed"
- Ensure you're on the GPU server
- Check CUDA is available: `python -c "import torch; print(torch.cuda.is_available())"`
- Verify submodules initialized: `git submodule update --init --recursive`

## Migration from Old Workflow

### Old (Coupled):
```bash
python scripts/realistic_reconstruction_simple.py --duration 30
```

### New (Decoupled):
```bash
# On capture device
python scripts/capture_to_s3.py --bucket my-bucket --duration 30

# On GPU server
python scripts/infer_from_s3.py --bucket my-bucket
```

Both achieve the same result, but the new workflow is more flexible and scalable.

