import os

_project = os.environ.get("GCP_PROJECT")
if not _project:
    raise SystemExit("Error: GCP_PROJECT environment variable is not set.\n  export GCP_PROJECT=your-project-id")

PROJECT = _project
ZONE = os.environ.get("GCP_ZONE", "us-central1-b")
VM_NAME = "local-llm-poc-vm"
# GPU options (MACHINE_TYPE / GPU_TYPE / VRAM / approx SPOT price):
#   T4  16GB: n1-standard-4  / nvidia-tesla-t4   / ~$0.20/h SPOT  ← default (us-central1確認済み)
#   L4  24GB: g2-standard-4  / nvidia-l4          / SPOT価格未確認
#   A100 40GB: a2-highgpu-1g / nvidia-tesla-a100  / SPOT価格未確認
MACHINE_TYPE = "n1-standard-4"
GPU_TYPE = "nvidia-tesla-t4"
GPU_COUNT = 1
DISK_SIZE_GB = 100
IMAGE_PROJECT = "deeplearning-platform-release"
IMAGE_FAMILY = "common-cu129-ubuntu-2204-nvidia-580"
