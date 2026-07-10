# 🦾 Oracle ARM Hunter

![Screenshot](https://s6.imgcdn.dev/YFkkoo.png)

Automatically provision an **Oracle Cloud Always Free ARM instance** the moment capacity becomes available.
No more refreshing the OCI Console every few minutes — just start the hunter and let it work until your VM is created.

---

# 💢 Why this exists

Oracle Cloud offers an excellent **Always Free** ARM tier:

- 2 OCPUs
- 12 GB RAM
- Fast Ampere A1 processors

Unfortunately, in popular regions you'll often see:

> **Out of host capacity**

for hours, days or even weeks.

This project continuously retries instance creation until capacity becomes available.

---

# 🎭 Oracle UX: a small friendly rant

Let's be honest — Oracle has all the resources needed to build one of the best cloud platforms on the market.

Instead, the OCI Console sometimes feels like a maze.

Finding one Virtual Machine can become an archaeological expedition through dozens of menus and hidden buttons.

The Always Free program is amazing.

The UI... could use a little love. ❤️

---

# ✨ Features

| Feature | Status |
|----------|:------:|
| Automatic Availability Domain rotation | ✅ |
| Automatic Ubuntu ARM image detection | ✅ |
| Smart retry logic | ✅ |
| Exponential backoff for API limits | ✅ |
| Adaptive Anti-DDoS Pacing (Dynamic 429 evasion) | ✅ |
| Random retry delays for capacity errors | ✅ |
| Persistent state | ✅ |
| Process lock | ✅ |
| Colored console logging | ✅ |
| Log file | ✅ |
| Native Telemetry Dashboard CLI | ✅ |
| Public IP detection | ✅ |
| Telegram notifications | ✅ |
| systemd service | ✅ |
| One-command installation | ✅ |

---

# 📋 Prerequisites

Recommended OS:

- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS

---

## 1. Install Python

```bash
sudo apt update

sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git
```

---

## 2. Install Oracle Cloud CLI

```bash
pip3 install oci-cli

oci setup config
```

Verify configuration:

```bash
oci iam availability-domain list
```

---

## 3. Configure SSH

Hunter injects your SSH public key into the created VM.

Verify:

```bash
cat ~/.ssh/authorized_keys
```

If the file doesn't exist:

```bash
mkdir -p ~/.ssh

nano ~/.ssh/authorized_keys
```

Paste your public key and save.

---

## 4. Create a VCN

The hunter automatically uses the first available:

- VCN
- Public Subnet

Make sure they already exist inside your OCI tenancy.

---

## 5. Always Free limits

Oracle currently allows:

| Resource | Value |
|-----------|------:|
| OCPUs | 2 |
| RAM | 12 GB |

The default configuration already matches these limits.

---

# 🚀 Installation

Clone repository:

```bash
git clone https://github.com/DadjMahal/oracle-arm-hunter.git

cd oracle-arm-hunter
```

Run installer:

```bash
chmod +x install.sh

sudo ./install.sh
```

Installer will ask for:

- OCI Compartment OCID
- Subnet OCID
- Telegram Bot Token (optional)
- Telegram Chat ID (optional)

Everything will be installed into:

```text
/opt/oracle-arm-hunter
```

---

# ▶ Manual Run

```bash
cd /opt/oracle-arm-hunter

source venv/bin/activate

python hunter.py
```

---

# ⚙ Run as a Service

Enable:

```bash
sudo systemctl enable oracle-arm-hunter
```

Start:

```bash
sudo systemctl start oracle-arm-hunter
```

Status:

```bash
systemctl status oracle-arm-hunter
```

Logs:

```bash
tail -f /opt/oracle-arm-hunter/logs/hunter.log
```

System journal:

```bash
sudo journalctl -u oracle-arm-hunter -f
```

---

# 📊 Real-Time Telemetry Dashboard

To monitor your hunting process, auto-tuned windows, clean streaks, and total 429 tracking natively without interrupting the background daemon:

```bash
python3 /opt/oracle-arm-hunter/status_cli.py
```

*Tip: You can safely exit this screen anytime using `Ctrl + C`. The hunter will remain running in the background.*

---

# 📬 Telegram Notifications

Create a bot:

> https://t.me/BotFather

Get updates:

```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Provide the token and Chat ID during installation or edit:

```text
/etc/oracle-arm-hunter.env
```

---

# ⚙ Configuration

Main configuration lives in:

```text
config.py
```

Example:

```python
INSTANCE_NAME = "retry-vm"

SHAPE = "VM.Standard.A1.Flex"

OCPUS = 2

MEMORY = 12

IMAGE_OS = "Canonical Ubuntu"

IMAGE_VERSION = "24.04"

TELEGRAM_ENABLED = True
```

---

# 🔄 Retry Algorithm

The hunter cycles through every Availability Domain with smart micro-pacing between them to bypass Oracle burst rate-limits.

```text
AD-1
 │
 ▼
[Micro-Delay]
 │
 ▼
AD-2
 │
 ▼
[Micro-Delay]
 │
 ▼
AD-3
 │
 ▼
Out of capacity?
 │
 ▼
Base Sleep (Adaptive)
 │
 ▼
Repeat
```

As soon as one Availability Domain has capacity:

```text
Create VM
      │
      ▼
Get Public IP
      │
      ▼
Save State
      │
      ▼
Exit
```

---

# 🏗 Architecture

```text
                    hunter.py
                        │
      ┌─────────────────┼─────────────────┐
      │                 │                 │
      ▼                 ▼                 ▼
oracle_client.py     retry.py          state.py   ◄── status_cli.py
      │                 │                 │
      └─────────────────┼─────────────────┘
                        │
                        ▼
                    logger.py
                        │
                        ▼
                     logs/
```

---

# 📂 Project Structure

```text
oracle-arm-hunter/
│
├── hunter.py                 # Main application loop
├── oracle_client.py          # Oracle Cloud SDK wrapper
├── config.py                 # Configuration
├── retry.py                  # Retry manager with anti-429 dynamic buffers
├── state.py                  # Persistent state
├── logger.py                 # Logging
├── lock.py                   # Process lock
├── telegram.py               # Telegram notifications
├── status_cli.py             # Native real-time telemetry control panel
│
├── requirements.txt
├── install.sh
├── oracle-arm-hunter.service
├── README.md
│
├── logs/
│   └── hunter.log
│
└── state/
    ├── hunter.json
    └── retry.json
```

---

# 📄 Log Files

Application log:

```text
logs/hunter.log
```

State:

```text
state/hunter.json
```

Retry metadata:

```text
state/retry.json
```

---

# ❓ FAQ

### Will I be charged?

No.

The default configuration uses Oracle Always Free resources only.

---

### What happens if the VM already exists?

The hunter detects the instance, prints its Public IP, and exits immediately.

---

### How long can it take?

Anything from a few minutes to several days depending on Oracle's available capacity.

---

### Can I reboot the server?

Yes.

If installed as a systemd service, the hunter starts automatically after reboot.

---

### How do I stop it?

```bash
sudo systemctl stop oracle-arm-hunter
```

Or simply press:

```text
Ctrl + C
```

when running manually.

---

# ❤️ Contributing

Pull requests, bug reports and feature suggestions are always welcome.

If this project saved you hours of clicking through the OCI Console, consider giving it a ⭐ on GitHub.

---

# 📜 License

MIT License
