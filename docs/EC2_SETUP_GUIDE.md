# EC2 Setup Guide for MAST3R Pipeline

## Memory Issue Analysis

Your local machine is likely running out of VRAM when loading the MAST3R ViTLarge model. The `MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric` model requires significant GPU memory.

## Recommended EC2 Instances

### Option 1: Cost-Effective Development (Recommended for Testing)
**Instance Type:** `g4dn.xlarge` or `g4dn.2xlarge`
- **GPU:** NVIDIA T4 (16GB VRAM)
- **vCPUs:** 4-8
- **RAM:** 16-32 GB
- **Cost:** ~$0.526-$0.752/hour (on-demand)
- **Use Case:** Development, testing, small-scale reconstructions
- **Note:** May struggle with very large reconstructions or high-resolution inputs

### Option 2: Production-Ready (Best Balance)
**Instance Type:** `g5.xlarge` or `g5.2xlarge`
- **GPU:** NVIDIA A10G (24GB VRAM)
- **vCPUs:** 4-8
- **RAM:** 16-32 GB
- **Cost:** ~$1.006-$1.212/hour (on-demand)
- **Use Case:** Production workloads, high-quality reconstructions
- **Recommended:** ✅ Best choice for your pipeline

### Option 3: High-Performance (For Large-Scale)
**Instance Type:** `g5.4xlarge` or `p3.2xlarge`
- **GPU:** NVIDIA A10G 24GB or V100 16GB
- **vCPUs:** 16-8
- **RAM:** 64-61 GB
- **Cost:** ~$1.624-$3.06/hour (on-demand)
- **Use Case:** Very large reconstructions, batch processing

### Option 4: Maximum Power
**Instance Type:** `p4d.24xlarge` or `g5.12xlarge`
- **GPU:** A100 40GB or 4x A10G
- **Cost:** $32.77/hour or $4.89/hour
- **Use Case:** Only if you need extreme performance

## Quick Start: Launch EC2 Instance

### 1. Create EC2 Instance via AWS Console

```bash
# AMI: Deep Learning AMI (Ubuntu 20.04 or 22.04)
# Instance Type: g5.xlarge (recommended)
# Storage: 100GB GP3 (for models and data)
# Security Group: Allow SSH (port 22) and optionally Jupyter (8888)
```

### 2. Connect to Instance

```bash
# Save your key pair as rdock-cv.pem
chmod 400 rdock-cv.pem
ssh -i rdock-cv.pem ubuntu@<instance-public-ip>
```

### 3. Setup Environment

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Check GPU
nvidia-smi

# Install conda (if not already on Deep Learning AMI)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b
echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Clone your repository
git clone https://github.com/<your-repo>/rdock-cv-pipeline.git
cd rdock-cv-pipeline

# Initialize submodules
git submodule update --init --recursive

# Create conda environment
conda env create -f environment.yml
conda activate rdock-cv

# Install additional dependencies if needed
pip install pillow
```

### 4. Run Your Pipeline

```bash
# Test modules
python scripts/test_modules.py

# Run realistic reconstruction (with camera/video input)
python scripts/realistic_reconstruction_simple.py --duration 30 --interval 2

# Run auto reconstruction
python scripts/auto_reconstruction_simple.py --duration 60 --interval 30
```

## Cost Optimization Tips

### 1. Use Spot Instances
- Save up to 90% vs on-demand pricing
- Good for non-critical workloads
- Enable spot instance when launching

### 2. Use Reserved Instances
- If using regularly, commit to 1-year reserved instance
- Save ~40% vs on-demand

### 3. Stop Instance When Not In Use
```bash
# From AWS Console or CLI
aws ec2 stop-instances --instance-ids i-1234567890abcdef0
```
**Important:** Stopping (not terminating) preserves your data while not charging for compute

### 4. Use EBS Snapshots
- Take snapshots of your configured instance
- Launch new instances from snapshot when needed
- Only pay for storage (~$0.05/GB-month)

### 5. Use EC2 Instance Scheduler
- Automatically start/stop instances on schedule
- Great for development workflows

## Performance Expectations on g5.xlarge

Based on MAST3R requirements:
- **Model Loading:** 10-30 seconds
- **Frame Pair Processing:** 1-3 seconds per pair
- **30-second capture (15 images):** ~5-10 minutes total
- **GPU Memory Usage:** 8-12GB VRAM
- **System Memory:** 8-16GB RAM

## Accessing Your Instance via Jupyter (Optional)

```bash
# On EC2 instance
conda activate rdock-cv
pip install jupyter notebook

# Start jupyter with public access
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser

# Note the token from output
```

Then access via browser: `http://<instance-public-ip>:8888`

**Security:** Make sure port 8888 is open in your security group, or use SSH tunneling:
```bash
# From your local machine
ssh -i rdock-cv.pem -L 8888:localhost:8888 ubuntu@<instance-ip>
# Access at http://localhost:8888
```

## Working with Video Files

If you don't have a camera on EC2, you can:

### Option 1: Process Pre-recorded Videos
```bash
# Upload video from local machine
scp -i rdock-cv.pem video.mp4 ubuntu@<instance-ip>:~/rdock-cv-pipeline/

# Create script to extract frames from video and process
```

### Option 2: Use Sample Images
```bash
# Process existing point cloud files
python scripts/test_simplified_pipeline.py
```

### Option 3: Forward Camera over Network
```bash
# From local machine with camera
# Stream video to EC2 (more advanced setup)
```

## S3 Integration for Results

```bash
# Install AWS CLI (usually pre-installed on Deep Learning AMI)
aws configure

# Upload results to S3
aws s3 cp outputs/ s3://your-bucket/rdock-cv-outputs/ --recursive

# Download to local machine
aws s3 sync s3://your-bucket/rdock-cv-outputs/ ./local_outputs/
```

## Monitoring GPU Usage

```bash
# Watch GPU in real-time
watch -n 1 nvidia-smi

# Or use htop for CPU/RAM
htop
```

## Troubleshooting

### Out of Memory on g4dn.xlarge
- Upgrade to g5.xlarge (24GB VRAM)
- Process fewer images at once
- Reduce image resolution

### Slow Network Transfer
- Use AWS Transfer Family for large files
- Consider running entirely in cloud with S3

### Instance Costs Too High
- Use spot instances
- Schedule start/stop times
- Consider using smaller instance for development

## Quick Launch Script

Save this as `launch_ec2.sh`:

```bash
#!/bin/bash
# Quick launch script for EC2 instance

INSTANCE_TYPE="g5.xlarge"
AMI_ID="ami-0c55b159cbfafe1f0"  # Deep Learning AMI (update for your region)
KEY_NAME="rdock-cv"
SECURITY_GROUP="sg-xxxxxxxx"

aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SECURITY_GROUP \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=rdock-cv-pipeline}]'
```

## Next Steps

1. **Launch g5.xlarge instance** (recommended starting point)
2. **Clone your repo and setup environment**
3. **Test with `test_modules.py`** to verify everything works
4. **Run reconstruction pipeline**
5. **Download results or push to S3**
6. **Stop instance when done** to save costs

## Cost Calculator Example

**g5.xlarge usage:**
- 2 hours/day development
- 20 days/month
- Cost: ~$40/month

**g5.xlarge + spot pricing:**
- Same usage with 70% spot discount
- Cost: ~$12/month

Much more economical than buying a dedicated GPU workstation!


