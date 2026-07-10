# retry.py - Smart Adaptive Pacing Engine with Dynamic Micro-Delays 🔄
import json
import random
import time
from pathlib import Path
from datetime import datetime
import config
from logger import logger

class RetryManager:
    """
    Manages retry delays with dynamic self-tuning.
    Tracks 429 history and automatically adjusts micro-pacing to achieve 0 errors.
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
            "total_429s": 0,                  # 📊 New 429 Counter
            "micro_delay": 2,                 # ⏱️ Dynamic micro-delay between ADs
            "date": datetime.now().strftime("%Y-%m-%d"),
            "last_retry_time": None,
            "adaptive_min": config.MIN_DELAY,
            "adaptive_max": config.MAX_DELAY,
            "consecutive_clean_requests": 0
        }
        self.load()

    def load(self):
        """Load retry state from JSON."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logger.debug("🔄 Adaptive retry state loaded.")
            except (json.JSONDecodeError, IOError):
                logger.debug("🆕 Starting fresh retry state.")
                self.save()
        else:
            self.save()

    def save(self):
        """Save retry statistics and tuned limits to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.data, f, indent=4)
        except IOError as e:
            logger.warning(f"⚠️ Failed to save retry state: {e}")

    def get_micro_delay(self):
        """Returns the current dynamically optimized micro-delay."""
        return self.data.get("micro_delay", 2)

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
        """Standard capacity check loop. Gradually speeds up if safe."""
        current_min = self.data.get("adaptive_min", config.MIN_DELAY)
        current_max = self.data.get("adaptive_max", config.MAX_DELAY)

        self.data["consecutive_clean_requests"] = self.data.get("consecutive_clean_requests", 0) + 1
        clean_streak = self.data["consecutive_clean_requests"]

        # 🚀 If we have a massive clean streak (100 cycles), try to optimize micro-delay down
        if clean_streak % 100 == 0 and self.data.get("micro_delay", 2) > 2:
            self.data["micro_delay"] -= 1
            logger.info(f"⚡ Stability High! Lowering micro-delay to {self.data['micro_delay']}s")

        if clean_streak >= 30:
            if current_min > 16:
                current_min -= 1
                current_max -= 1
                self.data["adaptive_min"] = current_min
                self.data["adaptive_max"] = current_max
                logger.info(f"🔥 Optimization: 30 clean requests. Speeding up baseline to {current_min}-{current_max}s!")
            self.data["consecutive_clean_requests"] = 0

        delay = random.randint(current_min, current_max)
        self._update_stats(delay, "Out of host capacity")
        return delay

    def wait_429(self):
        """Oracle is angry. Instantly slow down base pace and increase micro-delays."""
        self.data["total_429s"] = self.data.get("total_429s", 0) + 1
        
        # 🛡️ Anti-DDoS Action: Increase micro-delay between AD requests to prevent burst triggers
        current_micro = self.data.get("micro_delay", 2)
        if current_micro < 5:
            self.data["micro_delay"] = current_micro + 1
            logger.warning(f"🛡️ Smart Defense: Adjusting micro-delay between ADs to {self.data['micro_delay']}s to kill 429s.")

        current_min = self.data.get("adaptive_min", config.MIN_DELAY)
        current_max = self.data.get("adaptive_max", config.MAX_DELAY)

        if current_min < 61:
            current_min += 3
            current_max += 3
            self.data["adaptive_min"] = current_min
            self.data["adaptive_max"] = current_max
            logger.warning(f"📉 Optimization: 429 detected. Slowing down baseline to {current_min}-{current_max}s.")

        self.data["consecutive_clean_requests"] = 0

        base_delay = min(self.backoff, config.MAX_BACKOFF)
        jitter_range = base_delay * config.JITTER_FACTOR
        delay = int(base_delay + random.uniform(-jitter_range, jitter_range))
        delay = max(config.INITIAL_BACKOFF, delay)
        
        self.backoff = min(self.backoff * 2, config.MAX_BACKOFF)
        self._update_stats(delay, "429 Too Many Requests")
        return delay

    def wait_server_error(self):
        """Random delay after a 5xx server error."""
        self.data["consecutive_clean_requests"] = 0
        delay = random.randint(config.SERVER_ERROR_MIN, config.SERVER_ERROR_MAX)
        self._update_stats(delay, "5xx Server Error")
        return delay

    def success(self):
        """Reset backoff after a successful operation."""
        self.backoff = config.INITIAL_BACKOFF
        self.data["consecutive_clean_requests"] = 0
        self._update_stats(0, "")
