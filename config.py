# config.py - All settings for Oracle ARM Hunter 🛠️
import os
from pathlib import Path

# Version of the hunter
VERSION = "2.1.0"

# Base directory of the project
BASE_DIR = Path("/opt/oracle-arm-hunter")

# Directories for logs and state (created automatically)
LOG_DIR = BASE_DIR / "logs"
STATE_DIR = BASE_DIR / "state"
LOCK_FILE = "/tmp/oracle-arm-hunter.lock"  # Prevent multiple instances

# Create directories if they don't exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

# --- Oracle Cloud settings ---
OCI_CONFIG_FILE = Path.home() / ".oci" / "config"  # Default OCI config
OCI_PROFILE = "DEFAULT"  # Profile name in OCI config

# Target instance configuration
INSTANCE_NAME = "retry-vm"          # Display name of the VM
SHAPE = "VM.Standard.A1.Flex"      # ARM shape
OCPUS = 2                          # Number of OCPUs (Always Free max)
MEMORY = 12                        # Memory in GB (Always Free max)
BOOT_VOLUME_SIZE_GB = 100          # Boot volume size

# Image selection criteria
IMAGE_OS = "Canonical Ubuntu"
IMAGE_VERSION = "24.04"

# Timing parameters (seconds)
MIN_DELAY = 10                     # Min wait between AD cycles
MAX_DELAY = 30                     # Max wait between AD cycles
INITIAL_BACKOFF = 30               # Starting backoff for 429 errors
MAX_BACKOFF = 900                  # Maximum backoff (15 min)
SERVER_ERROR_MIN = 30              # Min wait after 5xx errors
SERVER_ERROR_MAX = 90              # Max wait after 5xx errors
LOOP_SLEEP = 60                    # Sleep between full cycles

# SSH key file
SSH_KEY_PATH = Path.home() / ".ssh" / "authorized_keys"

# State and log files
STATE_FILE = STATE_DIR / "hunter.json"
RETRY_STATE_FILE = STATE_DIR / "retry.json"
LOG_FILE = LOG_DIR / "hunter.log"

# Telegram configuration (loaded from environment variables)
TELEGRAM_ENABLED = os.environ.get("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
