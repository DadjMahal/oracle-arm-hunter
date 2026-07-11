# telegram.py - Telegram notifications and interactive command listener 📬
import requests
import threading
import time
from datetime import datetime
import config
from logger import logger

class TelegramNotifier:
    """
    Sends notifications via Telegram bot and runs a background listener
    to respond to interactive commands like /status, /pause, /resume, /stop.
    """
    def __init__(self):
        self.enabled = config.TELEGRAM_ENABLED
        self.token = config.TELEGRAM_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        if self.enabled and (not self.token or not self.chat_id):
            logger.warning("⚠️ Telegram enabled but token/chat_id missing. Disabling notifications.")
            self.enabled = False
        if self.enabled:
            logger.info("📬 Telegram notifications are active.")

    def send_message(self, text, parse_mode="HTML"):
        """Send a message to the configured Telegram chat."""
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.debug("📤 Telegram message sent.")
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")

    def notify_start(self, state):
        """Send a startup notification with details."""
        instance_list = "\n".join(
            f"• {inst['name']} ({inst['ocpus']} OCPU, {inst['memory']} GB)"
            for inst in config.INSTANCES
        )
        msg = f"""🚀 <b>Oracle ARM Hunter Started</b>

<b>Version:</b> {config.VERSION}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>Shape:</b> {config.SHAPE}
<b>Target instances:</b>
{instance_list}
<b>Region:</b> eu-frankfurt-1

<i>Searching for available capacity…</i>"""
        self.send_message(msg)

    def notify_success(self, instance_id, public_ip, state):
        """Send a success message with instance details."""
        attempts = state.get("attempt", 0)
        cycles = state.get("cycle", 0)
        msg = f"""✅ <b>Oracle ARM Instance Created!</b>

<b>Instance ID:</b> <code>{instance_id}</code>
<b>Public IP:</b> <code>{public_ip or 'N/A'}</code>
<b>Total Attempts:</b> {attempts}
<b>Total Cycles:</b> {cycles}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

<i>Hunter continues for remaining instances if any.</i>"""
        self.send_message(msg)

    def notify_error(self, error_message, state):
        """Send a critical error notification."""
        msg = f"""❌ <b>Oracle ARM Hunter Error</b>

<b>Error:</b> {error_message}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>Attempt:</b> {state.get("attempt", 0)}
<b>Cycle:</b> {state.get("cycle", 0)}

<i>Hunter will retry. Check logs for details.</i>"""
        self.send_message(msg)

    def start_listener(self, state, retry):
        """Starts the background long-polling thread for commands."""
        if not self.enabled:
            return
        listener_thread = threading.Thread(target=self._command_loop, args=(state, retry), daemon=True)
        listener_thread.start()
        logger.info("🤖 Telegram command listener activated (/status, /pause, /resume, /stop).")

    def _command_loop(self, state, retry):
        """Internal loop to catch and process commands."""
        offset = 0
        # Drop old messages
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            resp = requests.get(url, params={"limit": 1, "timeout": 1}, timeout=5)
            if resp.status_code == 200:
                results = resp.json().get("result", [])
                if results:
                    offset = results[0]["update_id"] + 1
        except Exception as e:
            logger.debug(f"Telegram offset initialization skipped: {e}")

        while True:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates"
                resp = requests.get(url, params={"offset": offset, "timeout": 20}, timeout=25)
                if resp.status_code != 200:
                    time.sleep(5)
                    continue

                updates = resp.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if chat_id != str(self.chat_id):
                        continue

                    if text == "/status":
                        self._send_status_reply(state, retry)
                    elif text == "/pause":
                        state.pause()
                        self.send_message("⏸️ Hunter paused. Use /resume to continue.")
                    elif text == "/resume":
                        state.resume()
                        self.send_message("▶️ Hunter resumed.")
                    elif text == "/stop":
                        state.request_stop()
                        self.send_message("🛑 Stop request received. Hunter will exit after current cycle.")

            except Exception as e:
                logger.debug(f"Telegram listener temporary error: {e}")
                time.sleep(5)

    def _send_status_reply(self, state, retry):
        """Compiles accurate hunting telemetry metrics and replies to user."""
        s_data = state.data
        r_data = retry.data

        # Gather per-instance status
        instance_lines = []
        for inst in s_data.get("instances", []):
            status = "✅" if inst["success"] else "⏳"
            instance_lines.append(f"{status} {inst['name']} ({inst['ocpus']} OCPU, {inst['memory']} GB)")
        instances_str = "\n".join(instance_lines) if instance_lines else "None configured"

        status_label = "🎉 ALL DONE" if s_data.get("success") else "🎮 HUNTING"
        if s_data.get("paused"):
            status_label = "⏸️ PAUSED"
        if s_data.get("stop_requested"):
            status_label = "🛑 STOPPING"

        started_clean = s_data.get("started_at", "N/A")[:19].replace("T", " ")
        next_ts = r_data.get("next_retry", time.time())
        next_check = datetime.fromtimestamp(next_ts).strftime('%H:%M:%S')

        msg = f"""🤖 <b>Oracle ARM Hunter Status</b>
──────────────────
ℹ️ <b>Status:</b> <code>{status_label}</code>
🔄 <b>Current Cycle:</b> #{s_data.get("cycle", 0)}
🎯 <b>Current Attempt:</b> #{s_data.get("attempt", 0)}
📍 <b>Last AD:</b> <code>{s_data.get("current_ad", "None") or "None"}</code>
──────────────────
<b>Instances:</b>
{instances_str}
──────────────────
📊 <b>Statistics:</b>
├ 🔁 <b>Total Requests:</b> {r_data.get("total_retries", 0)}
├ 📅 <b>Retries Today:</b> {r_data.get("retries_today", 0)}
└ ⏱️ <b>Last Sleep:</b> {r_data.get("last_delay", 0)}s
🕒 <b>Started:</b> <code>{started_clean}</code>
🔮 <b>Next Wakeup:</b> <code>{next_check}</code>
"""
        self.send_message(msg)

# Global notifier instance
notifier = TelegramNotifier()
