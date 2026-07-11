# config.py - All settings for Oracle ARM Hunter 🛠️
import os
import json
from pathlib import Path

VERSION = "2.3.0"  # Multi-instance + Telegram commands

BASE_DIR = Path(os.environ.get("HUNTER_BASE_DIR", "/opt/oracle-arm-hunter"))
LOG_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"
LOCK_FILE = "/tmp/oracle-arm-hunter.lock"

LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

OCI_CONFIG_FILE = Path.home() / ".oci" / "config"
OCI_PROFILE = os.environ.get("OCI_PROFILE", "DEFAULT")

SHAPE = "VM.Standard.A1.Flex"
BOOT_VOLUME_SIZE_GB = 100

IMAGE_OS = "Canonical Ubuntu"
IMAGE_VERSION = os.environ.get("HUNTER_IMAGE_VERSION", "24.04")

# --- Multi-instance configuration ---
# By default a single instance from environment (backward compatible)
_default_name = os.environ.get("HUNTER_INSTANCE_NAME", "retry-vm")
_default_ocpus = int(os.environ.get("HUNTER_OCPUS", "2"))
_default_memory = int(os.environ.get("HUNTER_MEMORY_GB", "12"))

# HUNTER_INSTANCES env var can contain a JSON list of instance configs
instances_env = os.environ.get("HUNTER_INSTANCES")
if instances_env:
    try:
        INSTANCES = json.loads(instances_env)
    except json.JSONDecodeError:
        INSTANCES = [{"name": _default_name, "ocpus": _default_ocpus, "memory": _default_memory}]
else:
    INSTANCES = [{"name": _default_name, "ocpus": _default_ocpus, "memory": _default_memory}]

# Legacy single-instance accessors (used by telegram notifications for display)
INSTANCE_NAME = INSTANCES[0]["name"] if INSTANCES else "retry-vm"
OCPUS = INSTANCES[0]["ocpus"] if INSTANCES else 2
MEMORY = INSTANCES[0]["memory"] if INSTANCES else 12

# Timing (unchanged)
MIN_DELAY = 25
MAX_DELAY = 35
INITIAL_BACKOFF = 60
MAX_BACKOFF = 100
SERVER_ERROR_MIN = 60
SERVER_ERROR_MAX = 100
JITTER_FACTOR = 0.10

SSH_KEY_PATH = Path(os.environ.get("HUNTER_SSH_KEY_PATH", Path.home() / ".ssh" / "authorized_keys"))

STATE_FILE = STATE_DIR / "hunter.json"
RETRY_STATE_FILE = STATE_DIR / "retry.json"
LOG_FILE = LOG_DIR / "hunter.log"

TELEGRAM_ENABLED = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
