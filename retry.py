# retry.py - Intelligent retry logic with exponential backoff & jitter 🔄
import json
import random
import time
from pathlib import Path
from datetime import datetime
import config
from logger import logger

class RetryManager:
    """
    Manages retry delays for different error types.
    Uses exponential backoff for 429 errors, random delays for capacity/5xx.
    """
    def __init__(self):
        self.backoff = config.INITIAL_BACKOFF
        self.state_file = config.RETRY_STATE_FILE
        self.data = {
            "last_delay": 0,
            "next_retry": 0,
            "last_error": "",
            "total_retries": 0,
            "retries_today": 0,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "last_retry_time": None
        }
        self.load()

    def load(self):
        """Load retry state from JSON."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logger.debug("🔄 Retry state loaded.")
            except (json.JSONDecodeError, IOError):
                logger.debug("🆕 Starting fresh retry state.")
                self.save()
        else:
            self.save()

    def save(self):
        """Save retry statistics to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.data, f, indent=4)
        except IOError as e:
            logger.warning(f"⚠️ Failed to save retry state: {e}")

    def _update_stats(self, delay, error):
        """Record new retry info and daily counters."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.data["date"] != today:
            self.data["retries_today"] = 0
            self.data["date"] = today
        self.data["last_delay"] = delay
        self.data["next_retry"] = int(time.time()) + delay
        self.data["last_error"] = error
        self.data["total_retries"] += 1
        self.data["retries_today"] += 1
        self.data["last_retry_time"] = datetime.now().isoformat()
        self.save()

    def wait_capacity(self):
        """Random short delay when no capacity in any AD."""
        delay = random.randint(config.MIN_DELAY, config.MAX_DELAY)
        self._update_stats(delay, "Out of host capacity")
        return delay

    def wait_429(self):
        """Exponential backoff for rate limiting."""
        delay = self.backoff
        self.backoff = min(self.backoff * 2, config.MAX_BACKOFF)
        self._update_stats(delay, "429 Too Many Requests")
        return delay

    def wait_server_error(self):
        """Random delay after a 5xx server error."""
        delay = random.randint(config.SERVER_ERROR_MIN, config.SERVER_ERROR_MAX)
        self._update_stats(delay, "5xx Server Error")
        return delay

    def success(self):
        """Reset backoff after a successful operation."""
        self.backoff = config.INITIAL_BACKOFF
        self._update_stats(0, "")
