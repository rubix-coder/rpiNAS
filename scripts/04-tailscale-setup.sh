#!/bin/bash
# ============================================================
# 04-tailscale-setup.sh
# Raspberry Pi NAS — Step 4: Install Tailscale
#
# Tailscale creates a secure private network between your
# devices so you can access the NAS from anywhere without
# port forwarding.
#
# Prerequisites:
#   - A free Tailscale account at https://tailscale.com
#   - Internet access on the Pi
#
# Usage: sudo bash scripts/04-tailscale-setup.sh
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

if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root. Use: sudo bash $0"
fi

echo ""
echo "=============================================="
echo "  Raspberry Pi NAS — Tailscale Setup"
echo "=============================================="
echo ""
echo "Before continuing, make sure you have:"
echo "  - A free Tailscale account (tailscale.com)"
echo "  - Internet access on this Pi"
echo ""
read -rp "Press Enter to continue (or Ctrl+C to cancel)..."

# ---- Step 1: Check internet ----
step "Checking internet connectivity..."
if ! ping -c 1 -W 5 8.8.8.8 &>/dev/null; then
    error "No internet connection. Connect and try again."
fi
success "Internet is reachable"

# ---- Step 2: Check if already installed ----
if command -v tailscale &>/dev/null; then
    EXISTING_VER=$(tailscale version | head -1)
    warn "Tailscale is already installed: $EXISTING_VER"
    read -rp "Reinstall / update? [y/N]: " REINSTALL
    REINSTALL="${REINSTALL:-N}"
    if [[ ! "$REINSTALL" =~ ^[Yy]$ ]]; then
        info "Skipping installation."
        SKIP_INSTALL=true
    else
        SKIP_INSTALL=false
    fi
else
    SKIP_INSTALL=false
fi

# ---- Step 3: Install Tailscale ----
if [ "$SKIP_INSTALL" = false ]; then
    step "Downloading and installing Tailscale..."
    info "This runs the official Tailscale install script from tailscale.com"
    curl -fsSL https://tailscale.com/install.sh | sh
    success "Tailscale installed: $(tailscale version | head -1)"
fi

# ---- Step 4: Enable and start the service ----
step "Enabling Tailscale service..."
systemctl enable tailscaled
systemctl start tailscaled

# Wait for daemon to be ready
for i in {1..10}; do
    if tailscale status &>/dev/null 2>&1; then
        break
    fi
    sleep 1
done
success "Tailscale daemon is running"

# ---- Step 5: Authenticate ----
step "Authenticating with Tailscale..."
echo ""

# Check if already authenticated
if tailscale status 2>/dev/null | grep -q "logged in"; then
    CURRENT_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    success "Already authenticated! Tailscale IP: $CURRENT_IP"
else
    echo "Running 'tailscale up' will display a login URL."
    echo "Open that URL in a browser on any of your devices and"
    echo "log in with your Tailscale account to authenticate this Pi."
    echo ""
    echo "After authenticating in the browser, come back here."
    echo ""

    # Run tailscale up — this blocks and shows the auth URL
    tailscale up --accept-routes

    echo ""
    # Wait for authentication
    for i in {1..60}; do
        if tailscale status 2>/dev/null | grep -q -v "not logged in"; then
            break
        fi
        sleep 2
    done
fi

# ---- Step 6: Get and display the Tailscale IP ----
step "Getting Tailscale IP..."
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || "")

if [ -z "$TAILSCALE_IP" ]; then
    error "Could not get Tailscale IP. Authentication may have failed. Try: sudo tailscale up"
fi

success "Tailscale IP: $TAILSCALE_IP"

# ---- Step 7: Verify connectivity ----
step "Verifying Tailscale status..."
tailscale status
echo ""

# ---- Step 8: Show next steps ----
# Get share name from smb.conf if available
SHARE_NAME=$(grep -oP '(?<=^\[)[^\]]+' /etc/samba/smb.conf 2>/dev/null | grep -v global | head -1 || echo "NAS")

echo ""
echo "=============================================="
echo -e "  ${GREEN}Tailscale setup complete!${NC}"
echo "=============================================="
echo ""
echo "  Tailscale IP : $TAILSCALE_IP"
echo "  (This IP stays the same even when your home IP changes)"
echo ""
echo "  Install Tailscale on your other devices:"
echo "    Windows  : https://tailscale.com/download"
echo "    Android  : Install 'Tailscale' from Play Store"
echo "    Linux    : curl -fsSL https://tailscale.com/install.sh | sh"
echo ""
echo "  Then access your NAS from anywhere:"
echo "    Windows  : \\\\${TAILSCALE_IP}\\${SHARE_NAME}"
echo "    Linux    : smb://${TAILSCALE_IP}/${SHARE_NAME}"
echo "    SSH      : ssh $(logname 2>/dev/null || echo '<your-username>')@${TAILSCALE_IP}"
echo ""
echo "  IMPORTANT: Disable key expiry for persistent access:"
echo "    1. Go to https://login.tailscale.com/admin/machines"
echo "    2. Find this Pi, click '...', click 'Disable key expiry'"
echo ""
echo "Next step: Verify everything is working"
echo "  bash scripts/05-verify-setup.sh"
echo ""
