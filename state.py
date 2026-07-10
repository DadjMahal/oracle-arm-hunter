# state.py - Persistent state tracking for the hunter 📊
import json
from pathlib import Path
from datetime import datetime
import config
from logger import logger

class State:
    """
    Stores and updates the hunter's state in a JSON file.
    Includes attempt, cycle, AD, instance ID, public IP, etc.
    """
    def __init__(self):
        self.state_file = config.STATE_FILE
        self.data = {
            "attempt": 0,
            "cycle": 0,
            "current_ad": "",
            "instance_id": "",
            "public_ip": "",
            "success": False,
            "started_at": datetime.now().isoformat(),
            "last_error": None,
            "last_updated": None
        }
        self.load()

    def load(self):
        """Load state from file, falling back to defaults."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logger.debug("📂 State loaded.")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"⚠️ Failed to load state: {e}. Starting fresh.")
                self.save()
        else:
            self.save()

    def save(self):
        """Persist current state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.data["last_updated"] = datetime.now().isoformat()
            with open(self.state_file, "w") as f:
                json.dump(self.data, f, indent=4)
            logger.debug("💾 State saved.")
        except IOError as e:
            logger.error(f"❌ Failed to save state: {e}")

    def next_attempt(self):
        """Increment attempt counter."""
        self.data["attempt"] += 1
        self.save()

    def next_cycle(self):
        """Increment cycle counter and reset attempt."""
        self.data["cycle"] += 1
        self.save()

    def set_ad(self, ad):
        """Record current availability domain."""
        self.data["current_ad"] = ad
        self.save()

    def success(self, instance_id, public_ip):
        """Mark hunting as successful."""
        self.data["success"] = True
        self.data["instance_id"] = instance_id
        self.data["public_ip"] = public_ip
        self.save()

    def set_error(self, error_message):
        """Record the last error encountered."""
        self.data["last_error"] = error_message
        self.save()

    def get(self, key, default=None):
        """Safely get a state value."""
        return self.data.get(key, default)
