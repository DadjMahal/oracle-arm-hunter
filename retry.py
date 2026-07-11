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
    Aggressively speeds up when clean, slows down only when 429 appears.
    Goal: maximum request speed without triggering 429 errors.
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
            "total_429s": 0,
            "micro_delay": 3,                 # Default micro-delay: 3s (middle of 2-5 range)
            "date": datetime.now().strftime("%Y-%m-%d"),
            "last_retry_time": None,
            "adaptive_min": 25,               # Start at optimal 25s
            "adaptive_max": 35,               # Start at optimal 35s
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
        """
        Returns a RANDOMIZED micro-delay between 2 and current micro_delay value.
        This prevents predictable patterns that Oracle can detect.
        """
        current_max = self.data.get("micro_delay", 3)
        delay = random.randint(2, max(2, current_max))
        return delay

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
        """
        Standard capacity check loop.
        Quickly speeds up to optimal 25-35s range when environment is clean.
        """
        current_min = self.data.get("adaptive_min", 25)
        current_max = self.data.get("adaptive_max", 35)

        self.data["consecutive_clean_requests"] = self.data.get("consecutive_clean_requests", 0) + 1
        clean_streak = self.data["consecutive_clean_requests"]

        # 🚀 FAST OPTIMIZATION: reduce delays after just 12 clean cycles (~6 min)
        if clean_streak >= 12:
            if current_min > 25:
                # Move 2 seconds closer to optimal per 12 clean cycles
                current_min = max(25, current_min - 2)
                current_max = max(35, current_max - 2)
                self.data["adaptive_min"] = current_min
                self.data["adaptive_max"] = current_max
                logger.info(f"🔥 Speed boost: {clean_streak} clean cycles. Accelerating to {current_min}-{current_max}s!")
            self.data["consecutive_clean_requests"] = 0

            # ⚡ After 60 total clean requests, reduce micro-delay to absolute minimum
            if self.data.get("total_retries", 0) > 0 and self.data.get("total_retries", 0) % 60 == 0:
                if self.data.get("micro_delay", 3) > 3:
                    self.data["micro_delay"] = max(2, self.data["micro_delay"] - 1)
                    logger.info(f"⚡ Micro-optimization: micro-delay now 2-{self.data['micro_delay']}s!")

        delay = random.randint(current_min, current_max)
        self._update_stats(delay, "Out of host capacity")
        return delay

    def wait_429(self):
        """
        Oracle rate-limited us. Temporarily slow down, then quickly recover.
        """
        self.data["total_429s"] = self.data.get("total_429s", 0) + 1

        # 🛡️ Increase micro-delay to maximum 5s during 429 storms
        current_micro = self.data.get("micro_delay", 3)
        if current_micro < 5:
            self.data["micro_delay"] = min(5, current_micro + 1)
            logger.warning(f"🛡️ 429 detected! Micro-delay increased to 2-{self.data['micro_delay']}s range.")

        # Slow down main cycle to 60-70s range during active 429 errors
        current_min = self.data.get("adaptive_min", 25)
        current_max = self.data.get("adaptive_max", 35)

        if current_min < 61:
            current_min = min(61, current_min + 3)
            current_max = min(71, current_max + 3)
            self.data["adaptive_min"] = current_min
            self.data["adaptive_max"] = current_max
            logger.warning(f"📉 429 slow-down: baseline increased to {current_min}-{current_max}s.")

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
