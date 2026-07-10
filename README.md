# 🦾 Oracle ARM Hunter

Automatically provision an **Oracle Cloud Always Free ARM instance** the moment capacity becomes available.  
No more manual clicking – set it, forget it, and let the hunter do the work.

---

## 💢 Why this exists

Oracle Cloud’s “Always Free” tier includes up to **2 OCPUs and 12 GB of RAM** on ARM architecture.  
In reality, you’re often greeted with *“Out of host capacity”* for days or weeks.  
This tool automates the retry process until the instance is created.

## 🎭 Oracle UX: a small friendly rant

Let’s be honest – Oracle has the resources to build a truly world‑class user experience.  
A company of this calibre could easily hire a few more UX engineers and designers **without letting go of the talented people already on board**.  

Instead, the current OCI console often feels like a maze built by engineers who never had to actually use it.  
Buttons are hidden, menus multiply like rabbits, and finding a simple virtual machine can turn into an archaeological dig.  

We’re not asking for much – just a UI that doesn’t require 17 clicks to launch an instance, and perhaps a dash of modern design.  
Oracle, if you’re reading this: we love your Always Free tier. Now please give your existing team the tools (and maybe a couple extra hands) to make the console as generous as the compute offer.

---

## ✨ Features

- 🔁 **Automatic AD cycling** – tries all availability domains in a loop.
- ⏳ **Smart retries** – exponential backoff on 429 errors, random delays on capacity.
- 📊 **State persistence** – resumes where it left off after restarts.
- 🔒 **Process lock** – prevents duplicate instances.
- 📬 **Telegram notifications** – start, success, and critical errors.
- 🎨 **Colored console output** – easy to spot success/errors.
- 📦 **systemd service** – runs as a background daemon.
- 🛠️ **One‑command install** – just run `install.sh`.

---

## 📋 Prerequisites (prepare your server)

> All steps are performed on the server where the hunter will run.  
> Recommended OS: **Ubuntu 20.04 / 22.04 LTS**.

### 1. Install Python and basic tools
sudo apt update
sudo apt install -y python3 python3-pip python3-venv curl git

### 2. Install and configure Oracle Cloud CLI
pip3 install oci-cli
oci setup config

Follow the prompts – you’ll need your user OCID, tenancy OCID, and region (e.g., eu-frankfurt-1).  
Verify the CLI works:
oci iam availability-domain list

### 3. Prepare SSH public key
The hunter injects your public key into the new instance.  
It reads the file ~/.ssh/authorized_keys.  
Make sure it exists and contains your public key:
cat ~/.ssh/authorized_keys

If it doesn’t exist, create it:
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys   # paste your public key

### 4. Ensure a VCN and subnet exist
The hunter uses the first VCN and subnet it finds in your tenancy.  
Make sure you have at least one public subnet in the target region.

### 5. Always Free limits
The maximum free ARM resources are: **2 OCPUs, 12 GB RAM**.  
The hunter is preconfigured with these values – you don’t need to change anything.

---

## 🚀 Quick Start

### Clone and install
git clone https://github.com/yourusername/oracle-arm-hunter.git
cd oracle-arm-hunter
chmod +x install.sh
sudo ./install.sh

The installer will ask for:
- **OCI Compartment OCID** (your tenancy)
- **Subnet OCID**
- **Telegram bot token & chat ID** (optional)

All files will be placed in /opt/oracle-arm-hunter/.

### Manual test run
cd /opt/oracle-arm-hunter
source venv/bin/activate
python hunter.py

### Run as a service (recommended)
sudo systemctl enable oracle-arm-hunter
sudo systemctl start oracle-arm-hunter

Check status:
systemctl status oracle-arm-hunter

View logs:
tail -f /opt/oracle-arm-hunter/logs/hunter.log
sudo journalctl -u oracle-arm-hunter -f

---

## 📬 Telegram Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Get your chat ID by sending a message to your bot, then run:
   curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
3. During install.sh answer y when asked about Telegram, then provide the token and chat ID.
   Alternatively, manually edit /etc/oracle-arm-hunter.env.

---

## ⚙️ Configuration (config.py)

All settings are in one file. Usually no changes are needed.

| Parameter         | Default                  | Description |
|-------------------|--------------------------|-------------|
| INSTANCE_NAME     | retry-vm                 | VM display name |
| SHAPE             | VM.Standard.A1.Flex      | ARM shape |
| OCPUS             | 2                        | Number of OCPUs |
| MEMORY            | 12                       | RAM in GB |
| IMAGE_OS          | Canonical Ubuntu         | Operating system |
| IMAGE_VERSION     | 24.04                    | Ubuntu version |
| TELEGRAM_ENABLED  | true / false             | Enable notifications |

---

## 🧱 Project Structure

oracle-arm-hunter/
├── hunter.py               # Main loop
├── oracle_client.py        # OCI SDK wrapper
├── config.py               # All settings
├── state.py                # Persistent state
├── retry.py                # Retry manager
├── logger.py               # Colored logging
├── lock.py                 # Process lock
├── telegram.py             # Telegram notifications
├── requirements.txt        # Dependencies
├── install.sh              # One‑command installer
├── oracle-arm-hunter.service  # systemd unit
└── README.md

---

## ❓ FAQ

**Will I be charged?**  
No. The hunter uses only Always Free resources (2 OCPUs, 12 GB). It cannot exceed the free limit.

**What if the instance already exists?**  
The hunter will detect it, print the public IP, and exit.

**How long does it take?**  
Anywhere from a few minutes to several days, depending on regional capacity.

**How do I stop it?**  
sudo systemctl stop oracle-arm-hunter or press Ctrl+C if running manually.

**Is it safe to reboot the server?**  
Yes, the systemd service will start the hunter automatically after a reboot.

---

## 📝 License

MIT
