#!/bin/bash
# ============================================================
# 01-initial-setup.sh
# Raspberry Pi NAS — Step 1: System Update & Prerequisites
#
# Run this first, on a fresh Raspberry Pi OS Lite install.
# Usage: sudo bash scripts/01-initial-setup.sh
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
step()    { echo -e "\n${BLUE}===>${NC} $*"; }

# ---- Guards ----
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root. Use: sudo bash $0"
fi

echo ""
echo "=============================================="
echo "  Raspberry Pi NAS — Initial Setup"
echo "=============================================="
echo ""

# ---- Step 1: Check internet ----
step "Checking internet connectivity..."
if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
    error "No internet connection. Connect the Pi to your network and try again."
fi
success "Internet is reachable"

# ---- Step 2: Update package list ----
step "Updating package list..."
apt-get update -y
success "Package list updated"

# ---- Step 3: Upgrade packages ----
step "Upgrading installed packages (this may take several minutes)..."
apt-get upgrade -y
success "Packages upgraded"

# ---- Step 4: Install essential tools ----
step "Installing essential tools..."
apt-get install -y \
    curl \
    wget \
    git \
    htop \
    lsof \
    usbutils \
    util-linux \
    exfatprogs \
    ntfs-3g \
    cifs-utils \
    net-tools
success "Essential tools installed"

# ---- Step 5: Ensure SSH is enabled ----
step "Enabling SSH service..."
systemctl enable ssh
systemctl start ssh
success "SSH is enabled and running"

# ---- Step 6: Show system info ----
step "System information:"
echo ""
echo "  Hostname : $(hostname)"
echo "  OS       : $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"')"
echo "  Kernel   : $(uname -r)"
echo "  Arch     : $(uname -m)"
echo "  IP (LAN) : $(hostname -I | awk '{print $1}')"
echo "  Uptime   : $(uptime -p)"
echo ""

echo "=============================================="
echo -e "  ${GREEN}Initial setup complete!${NC}"
echo "=============================================="
echo ""
echo "Next step: Mount your SSD"
echo "  sudo bash scripts/02-mount-ssd.sh"
echo ""
