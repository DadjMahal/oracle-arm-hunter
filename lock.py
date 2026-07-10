# lock.py - Process lock to prevent multiple instances 🔒
import os
import sys
import atexit
import fcntl
import config
from logger import logger

class ProcessLock:
    """
    Ensures only one hunter process runs at a time.
    Uses a lock file with fcntl for atomicity.
    """
    def __init__(self):
        self.lock_file = config.LOCK_FILE
        self.fd = None

    def acquire(self):
        """Acquire exclusive lock or exit if already locked."""
        try:
            self.fd = open(self.lock_file, 'w')
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.fd.write(str(os.getpid()))
            self.fd.flush()
            atexit.register(self.release)
            logger.debug(f"🔒 Lock acquired. PID: {os.getpid()}")
            return True
        except IOError:
            logger.error("❌ Another hunter instance is already running. Exiting.")
            sys.exit(1)

    def release(self):
        """Release the lock and remove lock file."""
        if self.fd:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                self.fd.close()
                if os.path.exists(self.lock_file):
                    os.remove(self.lock_file)
                logger.debug("🔓 Lock released.")
            except Exception as e:
                logger.warning(f"⚠️ Failed to release lock: {e}")

    def __enter__(self):
        """Enable use as context manager."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock on context exit."""
        self.release()
