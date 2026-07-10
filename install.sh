#!/bin/bash
# install.sh - One-command setup for Oracle ARM Hunter 🛠️
set -e

echo "========================================="
echo " Oracle ARM Hunter - Auto Installer"
echo "========================================="
echo ""

# Must be run as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo or as root."
    exit 1
fi

# --- Configuration prompts ---
echo "🔑 Enter your OCI Compartment OCID (tenancy):"
read -r COMPARTMENT_ID
echo "🌐 Enter your OCI Subnet OCID:"
read -r SUBNET_ID

echo ""
echo "📬 Enable Telegram notifications? (y/n)"
read -r enable_telegram

TELEGRAM_ENABLED="false"
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
if [[ "$enable_telegram" =~ ^[Yy]$ ]]; then
    TELEGRAM_ENABLED="true"
    read -p "Enter Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    read -p "Enter Telegram Chat ID: " TELEGRAM_CHAT_ID
fi

# --- Create project directory ---
PROJECT_DIR="/opt/oracle-arm-hunter"
echo "📁 Creating project directory: $PROJECT_DIR"
mkdir -p "$PROJECT_DIR"/{logs,state}

# --- Copy files from current directory ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES=("config.py" "logger.py" "lock.py" "state.py" "retry.py" "oracle_client.py" "telegram.py" "hunter.py" "requirements.txt")
for file in "${FILES[@]}"; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        cp "$SCRIPT_DIR/$file" "$PROJECT_DIR/"
        echo "  ✅ $file"
    else
        echo "  ⚠️  $file not found, skipping"
    fi
done

# Set proper ownership
chown -R ubuntu:ubuntu "$PROJECT_DIR"

# --- Setup Python virtual environment ---
echo ""
echo "🐍 Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- Environment file for systemd ---
cat > /etc/oracle-arm-hunter.env <<EOF
OCI_COMPARTMENT_ID=$COMPARTMENT_ID
OCI_SUBNET_ID=$SUBNET_ID
TELEGRAM_ENABLED=$TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
EOF
chmod 600 /etc/oracle-arm-hunter.env

# --- Install systemd service ---
if [ -f "$SCRIPT_DIR/oracle-arm-hunter.service" ]; then
    cp "$SCRIPT_DIR/oracle-arm-hunter.service" /etc/systemd/system/
    systemctl daemon-reload
    echo "📦 Systemd service installed."
else
    echo "⚠️  oracle-arm-hunter.service not found, skipping service setup."
fi

echo ""
echo "========================================="
echo " ✅ Installation complete!"
echo "========================================="
echo ""
echo "To run manually:"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo "  python hunter.py"
echo ""
echo "To start as a service:"
echo "  sudo systemctl enable oracle-arm-hunter"
echo "  sudo systemctl start oracle-arm-hunter"
echo ""
echo "View logs:"
echo "  tail -f $PROJECT_DIR/logs/hunter.log"
echo "  sudo journalctl -u oracle-arm-hunter -f"
