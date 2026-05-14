#!/bin/bash
# ============================================================
# 03-samba-setup.sh
# Raspberry Pi NAS — Step 3: Install & Configure Samba
#
# This script:
#   1. Installs Samba
#   2. Backs up the default smb.conf
#   3. Adds a share for /mnt/ssd1
#   4. Creates a Samba user (same as your Linux user)
#   5. Starts and enables Samba services
#   6. Verifies the config
#
# Usage: sudo bash scripts/03-samba-setup.sh
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

MOUNT_POINT="/mnt/ssd1"
SMB_CONF="/etc/samba/smb.conf"

if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root. Use: sudo bash $0"
fi

echo ""
echo "=============================================="
echo "  Raspberry Pi NAS — Samba Setup"
echo "=============================================="
echo ""

# ---- Prompt for configuration ----
echo "Configuration:"
echo ""

# Get share name
read -rp "Share name (what it appears as on the network) [NAS]: " SHARE_NAME
SHARE_NAME="${SHARE_NAME:-NAS}"

# Validate share name (no spaces or special chars)
if [[ "$SHARE_NAME" =~ [^a-zA-Z0-9_-] ]]; then
    error "Share name must only contain letters, numbers, underscores, and hyphens."
fi

# Get username
CURRENT_SUDO_USER="${SUDO_USER:-$(logname 2>/dev/null || echo 'nasuser')}"
read -rp "Linux username to share with [$CURRENT_SUDO_USER]: " SAMBA_USER
SAMBA_USER="${SAMBA_USER:-$CURRENT_SUDO_USER}"

# Verify the user exists
if ! id "$SAMBA_USER" &>/dev/null; then
    error "User '$SAMBA_USER' does not exist on this system."
fi

# Get mount point
read -rp "Path to share [$MOUNT_POINT]: " SHARE_PATH
SHARE_PATH="${SHARE_PATH:-$MOUNT_POINT}"

if [ ! -d "$SHARE_PATH" ]; then
    error "Directory $SHARE_PATH does not exist. Run 02-mount-ssd.sh first."
fi

echo ""
info "Share name  : $SHARE_NAME"
info "Linux user  : $SAMBA_USER"
info "Share path  : $SHARE_PATH"
echo ""
read -rp "Proceed? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# ---- Step 1: Install Samba ----
step "Installing Samba..."
apt-get update -y
apt-get install -y samba samba-common-bin
success "Samba installed: $(samba --version)"

# ---- Step 2: Backup smb.conf ----
step "Backing up Samba config..."
if [ -f "$SMB_CONF" ]; then
    BACKUP="${SMB_CONF}.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$SMB_CONF" "$BACKUP"
    success "Backed up to $BACKUP"
fi

# ---- Step 3: Add the share to smb.conf ----
step "Adding share [$SHARE_NAME] to $SMB_CONF..."

# Remove any existing block for this share name (idempotent)
if grep -q "^\[$SHARE_NAME\]" "$SMB_CONF" 2>/dev/null; then
    warn "Share [$SHARE_NAME] already exists in smb.conf — updating it."
    # Remove existing block (from [SHARE_NAME] to the next blank line before a new [section])
    python3 -c "
import re, sys
content = open('$SMB_CONF').read()
pattern = r'\[$SHARE_NAME\][^\[]*'
content = re.sub(pattern, '', content)
open('$SMB_CONF', 'w').write(content.rstrip() + '\n')
" 2>/dev/null || true
fi

# Append the new share block
cat >> "$SMB_CONF" << EOF

[$SHARE_NAME]
   comment = NAS Storage - $SHARE_NAME
   path = $SHARE_PATH
   browseable = yes
   read only = no
   writable = yes
   create mask = 0775
   directory mask = 0775
   valid users = $SAMBA_USER
   force user = $SAMBA_USER
EOF

success "Share [$SHARE_NAME] added to smb.conf"

# ---- Step 4: Set permissions on share path ----
step "Setting permissions on $SHARE_PATH..."
chown -R "$SAMBA_USER:$SAMBA_USER" "$SHARE_PATH" 2>/dev/null || warn "chown failed (normal for exFAT/NTFS — permissions handled via fstab)"
chmod -R 0775 "$SHARE_PATH" 2>/dev/null || true
success "Permissions updated"

# ---- Step 5: Set Samba password ----
step "Setting Samba password for user '$SAMBA_USER'..."
echo ""
echo "You need to set a Samba password for '$SAMBA_USER'."
echo "This is the password you'll use from Windows/Android to connect."
echo "It can be the same as or different from your Linux login password."
echo ""

smbpasswd -a "$SAMBA_USER"
smbpasswd -e "$SAMBA_USER"
success "Samba user '$SAMBA_USER' configured"

# ---- Step 6: Validate config ----
step "Validating Samba configuration..."
if testparm -s "$SMB_CONF" &>/dev/null; then
    success "smb.conf is valid"
else
    error "smb.conf has errors. Run 'testparm' to see details."
fi

# ---- Step 7: Enable and restart Samba ----
step "Starting Samba services..."
systemctl enable smbd nmbd
systemctl restart smbd nmbd
success "Samba is running"

# ---- Step 8: Allow Samba through UFW if active ----
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    step "Allowing Samba through UFW firewall..."
    ufw allow samba
    success "UFW rule added for Samba"
fi

# ---- Step 9: Show connection info ----
step "Getting connection details..."
LAN_IP=$(hostname -I | awk '{print $1}')
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "Not configured (run 04-tailscale-setup.sh)")

echo ""
echo "=============================================="
echo -e "  ${GREEN}Samba setup complete!${NC}"
echo "=============================================="
echo ""
echo "  Share name     : $SHARE_NAME"
echo "  Share path     : $SHARE_PATH"
echo "  Samba user     : $SAMBA_USER"
echo ""
echo "  Access from the same Wi-Fi network:"
echo "    Windows   : \\\\${LAN_IP}\\${SHARE_NAME}"
echo "    Linux     : smb://${LAN_IP}/${SHARE_NAME}"
echo ""
echo "  Access from anywhere (after Tailscale setup):"
echo "    Windows   : \\\\${TAILSCALE_IP}\\${SHARE_NAME}"
echo "    Linux     : smb://${TAILSCALE_IP}/${SHARE_NAME}"
echo ""
echo "Next step: Set up Tailscale for remote access"
echo "  sudo bash scripts/04-tailscale-setup.sh"
echo ""
