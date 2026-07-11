# state.py - Persistent state tracking for the hunter 📊
import json
from pathlib import Path
from datetime import datetime
import config
from logger import logger

class State:
    """
    Stores and updates the hunter's state in a JSON file.
    Supports multiple instances and interactive commands (pause/resume/stop).
    """
    def __init__(self):
        self.state_file = config.STATE_FILE
        self.data = {
            "attempt": 0,
            "cycle": 0,
            "current_ad": "",
            "success": False,          # overall success (all instances)
            "started_at": datetime.now().isoformat(),
            "last_error": None,
            "last_updated": None,
            "instances": [],           # list of per-instance state
            "paused": False,
            "stop_requested": False
        }
        self.load()
        self._init_instances()

    def _init_instances(self):
        """Ensure state contains entries for all configured instances."""
        existing_names = {inst["name"] for inst in self.data["instances"]}
        for cfg in config.INSTANCES:
            if cfg["name"] not in existing_names:
                self.data["instances"].append({
                    "name": cfg["name"],
                    "ocpus": cfg["ocpus"],
                    "memory": cfg["memory"],
                    "success": False,
                    "instance_id": None,
                    "public_ip": None
                })
        self.save()

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

    # --- Instance-level operations ---
    def get_pending_instances(self):
        """Return list of instance dicts that are not yet created."""
        return [inst for inst in self.data["instances"] if not inst["success"]]

    def mark_instance_success(self, name, instance_id, public_ip):
        """Mark a specific instance as successfully created."""
        for inst in self.data["instances"]:
            if inst["name"] == name:
                inst["success"] = True
                inst["instance_id"] = instance_id
                inst["public_ip"] = public_ip
                break
        # Update overall success flag
        self.data["success"] = all(inst["success"] for inst in self.data["instances"])
        self.save()

    def set_existing_instance(self, name, instance_id, public_ip):
        """Mark an already-existing instance as done (used at startup)."""
        self.mark_instance_success(name, instance_id, public_ip)

    # --- Global controls ---
    def pause(self):
        self.data["paused"] = True
        self.save()

    def resume(self):
        self.data["paused"] = False
        self.save()

    def request_stop(self):
        self.data["stop_requested"] = True
        self.save()

    # --- Legacy helpers (kept for backward compatibility) ---
    def next_attempt(self):
        self.data["attempt"] += 1
        self.save()

    def next_cycle(self):
        self.data["cycle"] += 1
        self.save()

    def set_ad(self, ad):
        self.data["current_ad"] = ad
        self.save()

    def set_error(self, error_message):
        self.data["last_error"] = error_message
        self.save()

    def get(self, key, default=None):
        return self.data.get(key, default)
