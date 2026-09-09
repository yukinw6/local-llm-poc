import os

_project = os.environ.get("GCP_PROJECT")
if not _project:
    raise SystemExit("Error: GCP_PROJECT environment variable is not set.\n  export GCP_PROJECT=your-project-id")

PROJECT = _project
ZONE = os.environ.get("GCP_ZONE", "us-central1-b")
DISK_SIZE_GB = 100
IMAGE_PROJECT = "deeplearning-platform-release"
IMAGE_FAMILY = "common-cu129-ubuntu-2204-nvidia-580"

PROFILES = {
    "t4": {
        "machine_type": "n1-standard-4",
        "gpu_type": "nvidia-tesla-t4",
        "gpu_count": 1,
        "vram_gb": 16,
        "default_model": "qwen3:8b",
    },
    "l4": {
        "machine_type": "g2-standard-4",
        "gpu_type": "nvidia-l4",
        "gpu_count": 1,
        "vram_gb": 24,
        "default_model": "qwen3:14b",
    },
    "a100-40": {
        "machine_type": "a2-highgpu-1g",
        "gpu_type": "nvidia-tesla-a100",
        "gpu_count": 1,
        "vram_gb": 40,
        "default_model": "qwen3:32b",
    },
}

_profile_name = os.environ.get("GCP_GPU_PROFILE", "t4")
if _profile_name not in PROFILES:
    raise SystemExit(f"Error: Unknown GCP_GPU_PROFILE={_profile_name!r}. Choose from: {list(PROFILES)}")

PROFILE = PROFILES[_profile_name]
MACHINE_TYPE = PROFILE["machine_type"]
GPU_TYPE = PROFILE["gpu_type"]
GPU_COUNT = PROFILE["gpu_count"]
DEFAULT_MODEL = PROFILE["default_model"]
VM_NAME = f"local-llm-poc-{_profile_name}"
