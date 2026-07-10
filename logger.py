# logger.py - Logging with colors and file rotation 📝
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
import config

# Create log directory if not exists
Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)

# Define ANSI color codes for terminal output
COLORS = {
    'DEBUG': '\033[94m',    # Blue
    'INFO': '\033[96m',     # Cyan
    'WARNING': '\033[93m',  # Yellow
    'ERROR': '\033[91m',    # Red
    'SUCCESS': '\033[92m',  # Green
    'RESET': '\033[0m'      # Reset
}

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to console output."""
    def format(self, record):
        # For console, add color based on level
        if record.levelname == 'SUCCESS':
            color = COLORS['SUCCESS']
        else:
            color = COLORS.get(record.levelname, COLORS['RESET'])
        record.colored_levelname = f"{color}{record.levelname}{COLORS['RESET']}"
        record.colored_message = f"{color}{record.getMessage()}{COLORS['RESET']}"
        return super().format(record)

# Create main logger
logger = logging.getLogger("hunter")
logger.setLevel(logging.DEBUG)

# --- File handler (detailed, no colors) ---
file_handler = RotatingFileHandler(
    config.LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8"
)
file_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)-8s] %(message)s",
    "%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# --- Console handler (with colors) ---
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = ColoredFormatter(
    "[%(asctime)s] [%(colored_levelname)s] %(colored_message)s",
    "%H:%M:%S"
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Add custom SUCCESS level
SUCCESS_LEVEL = 25  # Between WARNING (30) and INFO (20)
logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")

def success(msg, *args, **kwargs):
    """Log a success message."""
    logger.log(SUCCESS_LEVEL, msg, *args, **kwargs)

# Convenience functions
def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

# Make success available as function
success = success
