#!/bin/bash
# ============================================================
# 02-mount-ssd.sh
# Raspberry Pi NAS — Step 2: Detect and Mount USB SSD
#
# This script:
#   1. Lists connected USB storage devices
#   2. Asks you to confirm which one is the SSD
#   3. Detects the filesystem type
#   4. Creates a mount point at /mnt/ssd1
#   5. Adds an entry to /etc/fstab for auto-mount on boot
#   6. Mounts the drive and verifies
#
# Usage: sudo bash scripts/02-mount-ssd.sh
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

if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root. Use: sudo bash $0"
fi

echo ""
echo "=============================================="
echo "  Raspberry Pi NAS — Mount USB SSD"
echo "=============================================="
echo ""

# ---- Step 1: Show all block devices ----
step "Detecting storage devices..."
echo ""
lsblk -o NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT
echo ""

# Filter to only show removable/USB storage partitions (exclude mmcblk = SD card)
USB_PARTS=$(lsblk -rno NAME,TYPE,TRAN | awk '$2=="part" && $3=="usb" {print $1}')

if [ -z "$USB_PARTS" ]; then
    warn "No USB partitions detected automatically."
    info "All partitions (excluding SD card):"
    lsblk -rno NAME,SIZE,TYPE,FSTYPE | grep -v "mmcblk" | grep "part" || true
    echo ""
    read -rp "Enter the device partition manually (e.g. sda1, sdb1): " PARTITION
else
    echo "Detected USB partitions:"
    i=1
    declare -a PART_LIST=()
    while IFS= read -r part; do
        SIZE=$(lsblk -rno SIZE "/dev/$part" 2>/dev/null || echo "?")
        FSTYPE=$(lsblk -rno FSTYPE "/dev/$part" 2>/dev/null || echo "unknown")
        echo "  $i) /dev/$part  (${SIZE}, ${FSTYPE})"
        PART_LIST+=("$part")
        ((i++))
    done <<< "$USB_PARTS"
    echo ""
    read -rp "Enter the number of your SSD partition (or type the name manually, e.g. sda1): " SELECTION

    if [[ "$SELECTION" =~ ^[0-9]+$ ]] && [ "$SELECTION" -ge 1 ] && [ "$SELECTION" -le "${#PART_LIST[@]}" ]; then
        PARTITION="${PART_LIST[$((SELECTION-1))]}"
    else
        PARTITION="$SELECTION"
    fi
fi

DEVICE="/dev/$PARTITION"

if [ ! -b "$DEVICE" ]; then
    error "Device $DEVICE does not exist. Check the device name and try again."
fi

# ---- Step 2: Get filesystem type and UUID ----
step "Reading filesystem information for $DEVICE..."
FSTYPE=$(lsblk -rno FSTYPE "$DEVICE" 2>/dev/null || true)
UUID=$(blkid -s UUID -o value "$DEVICE" 2>/dev/null || true)

if [ -z "$FSTYPE" ]; then
    warn "No filesystem detected. The drive may be unformatted."
    echo ""
    echo "Would you like to format it as ext4? (All data will be ERASED)"
    read -rp "Type YES to format, or NO to exit: " CONFIRM_FORMAT
    if [ "$CONFIRM_FORMAT" = "YES" ]; then
        info "Formatting $DEVICE as ext4..."
        mkfs.ext4 -L "NAS_SSD" "$DEVICE"
        FSTYPE="ext4"
        UUID=$(blkid -s UUID -o value "$DEVICE")
        success "Formatted as ext4. UUID: $UUID"
    else
        error "Cannot continue without a filesystem. Exiting."
    fi
fi

if [ -z "$UUID" ]; then
    error "Could not read UUID from $DEVICE. Try: sudo blkid $DEVICE"
fi

info "Device   : $DEVICE"
info "UUID     : $UUID"
info "Filesystem: $FSTYPE"

# ---- Step 3: Install filesystem tools if needed ----
step "Checking filesystem support..."
case "$FSTYPE" in
    exfat)
        if ! command -v mkfs.exfat &>/dev/null && ! dpkg -l exfatprogs &>/dev/null 2>&1; then
            info "Installing exfatprogs for exFAT support..."
            apt-get install -y exfatprogs
        fi
        MOUNT_OPTS="defaults,nofail,uid=1000,gid=1000,umask=000"
        ;;
    ntfs|ntfs-3g)
        if ! command -v ntfs-3g &>/dev/null; then
            info "Installing ntfs-3g for NTFS support..."
            apt-get install -y ntfs-3g
        fi
        FSTYPE="ntfs-3g"
        MOUNT_OPTS="defaults,nofail,uid=1000,gid=1000,umask=000"
        ;;
    ext4|ext3|ext2)
        MOUNT_OPTS="defaults,nofail"
        ;;
    vfat|fat32)
        MOUNT_OPTS="defaults,nofail,uid=1000,gid=1000,umask=000"
        ;;
    *)
        warn "Unknown filesystem type: $FSTYPE. Attempting generic mount options."
        MOUNT_OPTS="defaults,nofail"
        ;;
esac
success "Filesystem support OK"

# ---- Step 4: Create mount point ----
step "Creating mount point at $MOUNT_POINT..."
mkdir -p "$MOUNT_POINT"
success "Mount point created: $MOUNT_POINT"

# ---- Step 5: Check if already in fstab ----
step "Updating /etc/fstab..."
if grep -q "$UUID" /etc/fstab; then
    warn "UUID $UUID is already in /etc/fstab. Skipping fstab update."
else
    # Backup fstab first
    cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)
    info "Backed up /etc/fstab"

    # Add new entry
    FSTAB_LINE="UUID=$UUID  $MOUNT_POINT  $FSTYPE  $MOUNT_OPTS  0  0"
    echo "" >> /etc/fstab
    echo "# NAS SSD - added by 02-mount-ssd.sh" >> /etc/fstab
    echo "$FSTAB_LINE" >> /etc/fstab
    success "Added to /etc/fstab: $FSTAB_LINE"
fi

# ---- Step 6: Mount the drive ----
step "Mounting $DEVICE at $MOUNT_POINT..."

# Unmount if currently mounted elsewhere
if mountpoint -q "$MOUNT_POINT"; then
    warn "$MOUNT_POINT is already mounted. Remounting..."
    umount "$MOUNT_POINT"
fi

mount -a
if mountpoint -q "$MOUNT_POINT"; then
    success "Drive mounted at $MOUNT_POINT"
else
    error "Mount failed. Check the fstab entry and try: sudo mount -a"
fi

# ---- Step 7: Set permissions ----
step "Setting permissions..."
if [ "$FSTYPE" = "ext4" ] || [ "$FSTYPE" = "ext3" ] || [ "$FSTYPE" = "ext2" ]; then
    chown -R 1000:1000 "$MOUNT_POINT" || warn "chown failed (may be OK for exFAT/NTFS)"
    chmod -R 0775 "$MOUNT_POINT" || true
fi
success "Permissions set"

# ---- Step 8: Verify ----
step "Verifying mount..."
echo ""
df -h "$MOUNT_POINT"
echo ""

# Write test
TEST_FILE="$MOUNT_POINT/.nas_mount_test"
if echo "mount test OK" > "$TEST_FILE" 2>/dev/null; then
    rm -f "$TEST_FILE"
    success "Read/write test passed"
else
    warn "Could not write to $MOUNT_POINT. Check permissions."
fi

echo ""
echo "=============================================="
echo -e "  ${GREEN}SSD mounted successfully!${NC}"
echo "=============================================="
echo ""
echo "  Mount point : $MOUNT_POINT"
echo "  UUID        : $UUID"
echo "  Filesystem  : $FSTYPE"
echo ""
echo "Next step: Set up Samba file sharing"
echo "  sudo bash scripts/03-samba-setup.sh"
echo ""
