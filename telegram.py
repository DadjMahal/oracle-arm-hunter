# telegram.py - Telegram notifications for hunter events 📬
import requests
from datetime import datetime
import config
from logger import logger

class TelegramNotifier:
    """
    Sends notifications via Telegram bot.
    Messages are sent on start, success, and critical errors.
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
        msg = f"""🚀 <b>Oracle ARM Hunter Started</b>

<b>Version:</b> {config.VERSION}
<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
<b>Target:</b> {config.SHAPE} ({config.OCPUS} OCPU, {config.MEMORY} GB)
<b>Instance:</b> {config.INSTANCE_NAME}
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

<i>Hunter completed successfully.</i>"""
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

# Create a global notifier instance
notifier = TelegramNotifier()
