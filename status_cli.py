#!/usr/bin/env python3
# status_cli.py - Self-refreshing native terminal dashboard 📊
import json
import os
import subprocess
import time
from datetime import datetime

import config

# ANSI Terminal Colors
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
RESET = "\033[0m"

STATE_FILE = "/opt/oracle-arm-hunter/state/hunter.json"
RETRY_FILE = "/opt/oracle-arm-hunter/state/retry.json"

def check_service_status():
    """Checks if the systemd service is actively running."""
    try:
        cmd = ["systemctl", "is-active", "oracle-arm-hunter"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        status = result.stdout.strip()
        if status == "active":
            return f"{GREEN}{BOLD}● ACTIVE (HUNTING){RESET}"
        return f"{RED}{BOLD}○ INACTIVE (STOPPED){RESET}"
    except Exception:
        return f"{YELLOW}UNKNOWN{RESET}"

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def colorize_error(error_text):
    """Applies contextual colors to different Oracle response types."""
    if not error_text:
        return f"{GREEN}None (Clean Start){RESET}"
    
    error_text_str = str(error_text)
    if "capacity" in error_text_str.lower():
        return f"{YELLOW}⚠️  Out of host capacity{RESET}"
    elif "429" in error_text_str or "rate" in error_text_str.lower():
        return f"{RED}{BOLD}🛑 429 Too Many Requests{RESET}"
    elif "5xx" in error_text_str or "server" in error_text_str.lower():
        return f"{RED}💥 Server Error ({error_text_str}){RESET}"
    return f"{CYAN}{error_text_str}{RESET}"

def render_dashboard():
    state = load_json(STATE_FILE)
    retry = load_json(RETRY_FILE)
    service = check_service_status()

    # Time calculations
    now_ts = time.time()
    next_ts = retry.get("next_retry", now_ts)
    seconds_left = int(next_ts - now_ts)
    
    if seconds_left > 0:
        countdown = f"{YELLOW}{seconds_left}s{RESET}"
    else:
        countdown = f"{GREEN}Processing...{RESET}"

    started_at = state.get("started_at", "N/A")[:19].replace("T", " ")
    
    # Adaptive settings
    ad_min = retry.get("adaptive_min", config.MIN_DELAY)
    ad_max = retry.get("adaptive_max", config.MAX_DELAY)
    clean_streak = retry.get("consecutive_clean_requests", 0)
    micro_delay = retry.get("micro_delay", 2)
    total_429s = retry.get("total_429s", 0)
    
    # Clean up AD visualization
    raw_ad = str(state.get('current_ad', 'None'))
    clean_ad = raw_ad.split(":")[-1] if ":" in raw_ad else raw_ad

    # Clear screen natively before printing fresh block
    print("\033[H\033[J", end="")

    print(f"{CYAN}{BOLD}" + "="*55 + f"{RESET}")
    print(f"⚡ {BOLD}ORACLE ARM HUNTER REAL-TIME TELEMETRY{RESET} ⚡")
    print(f"{CYAN}" + "="*55 + f"{RESET}")
    
    print(f"📌 {BOLD}Service Status:{RESET}  {service}")
    print(f"🕒 {BOLD}Current Time:{RESET}    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🚀 {BOLD}Started At:{RESET}      {started_at}")
    print(f"{CYAN}" + "-"*55 + f"{RESET}")

    print(f"🔄 {BOLD}Current Cycle:{RESET}   {BLUE}#{state.get('cycle', 0)}{RESET}")
    print(f"🎯 {BOLD}Current Attempt:{RESET} {BLUE}#{state.get('attempt', 0)}{RESET}")
    print(f"🗺️  {BOLD}Last Active AD:{RESET}  {YELLOW}{clean_ad}{RESET}")
    print(f"{CYAN}" + "-"*55 + f"{RESET}")

    print(f"⚙️  {BOLD}AI Pacing Optimizer:{RESET}")
    print(f" ├ ⏱️  Cycle Windows:       {GREEN}{ad_min}s - {ad_max}s{RESET}")
    print(f" ├ ⏱️  AD Micro-Delay:      {YELLOW}{micro_delay}s{RESET}")
    print(f" └ 📈 Clean Streak:         {GREEN}{clean_streak}{RESET} requests")
    print(f"{CYAN}" + "-"*55 + f"{RESET}")

    print(f"📊 {BOLD}Request Metrics:{RESET}")
    print(f" ├ 🔁 Total API Requests:  {CYAN}{retry.get('total_retries', 0)}{RESET}")
    print(f" ├ 📅 Retries Today:       {CYAN}{retry.get('retries_today', 0)}{RESET}")
    print(f" ├ 🛑 Total 429 Blocks:    {RED}{BOLD}{total_429s}{RESET}")
    print(f" ├ ⏱️  Last Sleep Delay:   {CYAN}{retry.get('last_delay', 0)}s{RESET}")
    print(f" ├ ⏳ Next Wakeup In:      {countdown}")
    print(f" └ 💬 {BOLD}Last API Response:{RESET} {colorize_error(retry.get('last_error', ''))}")
    print(f"{CYAN}" + "="*55 + f"{RESET}")

    if state.get("success"):
        print(f"\n{GREEN}{BOLD}🎉 SUCCESS! SERVER INSTANCE CAPTURED!{RESET}")
        print(f"🌐 IP: {GREEN}{state.get('public_ip', 'N/A')}{RESET}")
        print(f"🆔 ID: {state.get('instance_id', 'N/A')}")
        print(f"{CYAN}" + "="*55 + f"{RESET}")
    else:
        print(f"ℹ️  {UNDERLINE}Tip:{RESET} Press {BOLD}Ctrl + C{RESET} to exit. Hunter runs safely in background.")

if __name__ == "__main__":
    try:
        # Loop infinitely every 1 second natively
        while True:
            render_dashboard()
            time.sleep(1)
    except KeyboardInterrupt:
        # Clear screen cleanly on exit
        print("\033[H\033[J", end="")
        print("👋 Телеметрію закрито. Мисливець продовжує працювати!")
