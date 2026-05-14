#!/bin/bash
# ============================================================
# 05-verify-setup.sh
# Raspberry Pi NAS — Step 5: Verify the Complete Setup
#
# Checks every component and reports pass/fail.
# Run without sudo (though some checks may show less info).
#
# Usage: bash scripts/05-verify-setup.sh
# ============================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "  ${GREEN}[PASS]${NC} $*"; ((PASS++)) || true; }
fail() { echo -e "  ${RED}[FAIL]${NC} $*"; ((FAIL++)) || true; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $*"; ((WARN++)) || true; }
section() { echo -e "\n${BOLD}${BLUE}$*${NC}"; echo "$(printf '%0.s-' {1..50})"; }

echo ""
echo "=============================================="
echo "  Raspberry Pi NAS — Setup Verification"
echo "  $(date)"
echo "=============================================="

# ============================================================
section "1. System"
# ============================================================

# OS version
OS=$(grep PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "Unknown")
pass "OS: $OS"

# Architecture
ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" ]]; then
    pass "Architecture: $ARCH (64-bit — correct for Pi 4)"
else
    warn "Architecture: $ARCH (expected aarch64 for Pi 4 with 64-bit OS)"
fi

# Internet
if ping -c 1 -W 3 8.8.8.8 &>/dev/null 2>&1; then
    pass "Internet connectivity: OK"
else
    fail "Internet connectivity: UNREACHABLE (check Wi-Fi/Ethernet)"
fi

# Uptime
UPTIME=$(uptime -p 2>/dev/null || uptime)
pass "Uptime: $UPTIME"

# Memory
MEM_FREE=$(free -m | awk '/^Mem/{print $4}')
MEM_TOTAL=$(free -m | awk '/^Mem/{print $2}')
if [ "$MEM_FREE" -gt 50 ]; then
    pass "Memory: ${MEM_FREE}MB free of ${MEM_TOTAL}MB"
else
    warn "Memory: only ${MEM_FREE}MB free of ${MEM_TOTAL}MB — very low"
fi

# ============================================================
section "2. SSH Service"
# ============================================================

if systemctl is-active --quiet ssh 2>/dev/null || systemctl is-active --quiet sshd 2>/dev/null; then
    pass "SSH service: running"
else
    fail "SSH service: NOT running (run: sudo systemctl start ssh)"
fi

if systemctl is-enabled --quiet ssh 2>/dev/null || systemctl is-enabled --quiet sshd 2>/dev/null; then
    pass "SSH on boot: enabled"
else
    warn "SSH on boot: not enabled (run: sudo systemctl enable ssh)"
fi

# ============================================================
section "3. SSD / Storage"
# ============================================================

MOUNT_POINT="/mnt/ssd1"

if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    pass "SSD mounted at $MOUNT_POINT"

    # Check disk usage
    DISK_INFO=$(df -h "$MOUNT_POINT" | tail -1)
    SIZE=$(echo "$DISK_INFO" | awk '{print $2}')
    USED=$(echo "$DISK_INFO" | awk '{print $3}')
    AVAIL=$(echo "$DISK_INFO" | awk '{print $4}')
    PCT=$(echo "$DISK_INFO" | awk '{print $5}')
    pass "Disk: ${USED} used / ${SIZE} total / ${AVAIL} available (${PCT} full)"

    # Check writable
    TEST_FILE="$MOUNT_POINT/.verify_test_$$"
    if echo "test" > "$TEST_FILE" 2>/dev/null; then
        rm -f "$TEST_FILE"
        pass "SSD is writable"
    else
        fail "SSD is NOT writable (check permissions: sudo chown -R \$USER:$USER $MOUNT_POINT)"
    fi
else
    fail "SSD not mounted at $MOUNT_POINT (run: sudo bash scripts/02-mount-ssd.sh)"
fi

# Check fstab entry
if [ -f /etc/fstab ] && grep -q "$MOUNT_POINT" /etc/fstab; then
    pass "fstab entry found for $MOUNT_POINT (will auto-mount on reboot)"
else
    fail "No fstab entry for $MOUNT_POINT (SSD will NOT auto-mount after reboot)"
fi

# ============================================================
section "4. Samba File Sharing"
# ============================================================

if command -v samba &>/dev/null || dpkg -l samba &>/dev/null 2>&1; then
    pass "Samba: installed ($(samba --version 2>/dev/null | head -1 || echo 'version unknown'))"
else
    fail "Samba: NOT installed (run: sudo bash scripts/03-samba-setup.sh)"
fi

if systemctl is-active --quiet smbd 2>/dev/null; then
    pass "smbd service: running"
else
    fail "smbd service: NOT running (run: sudo systemctl start smbd)"
fi

if systemctl is-active --quiet nmbd 2>/dev/null; then
    pass "nmbd service: running"
else
    warn "nmbd service: NOT running (run: sudo systemctl start nmbd)"
fi

if systemctl is-enabled --quiet smbd 2>/dev/null; then
    pass "smbd on boot: enabled"
else
    warn "smbd on boot: not enabled (run: sudo systemctl enable smbd)"
fi

# Check shares
if command -v testparm &>/dev/null; then
    SHARES=$(testparm -s 2>/dev/null | grep -E '^\[' | grep -v '\[global\]' | tr -d '[]' | tr '\n' ' ')
    if [ -n "$SHARES" ]; then
        pass "Samba shares configured: $SHARES"
    else
        fail "No Samba shares configured (run: sudo bash scripts/03-samba-setup.sh)"
    fi

    if testparm -s 2>/dev/null | grep -q "path = $MOUNT_POINT"; then
        pass "Samba share points to $MOUNT_POINT"
    else
        warn "Samba share path may not point to $MOUNT_POINT — check smb.conf"
    fi
fi

# ============================================================
section "5. Tailscale VPN"
# ============================================================

if command -v tailscale &>/dev/null; then
    pass "Tailscale: installed ($(tailscale version | head -1))"

    if systemctl is-active --quiet tailscaled 2>/dev/null; then
        pass "Tailscale daemon: running"
    else
        fail "Tailscale daemon: NOT running (run: sudo systemctl start tailscaled)"
    fi

    if systemctl is-enabled --quiet tailscaled 2>/dev/null; then
        pass "Tailscale on boot: enabled"
    else
        warn "Tailscale on boot: not enabled (run: sudo systemctl enable tailscaled)"
    fi

    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "")
    if [ -n "$TAILSCALE_IP" ]; then
        pass "Tailscale IP: $TAILSCALE_IP"
    else
        fail "Tailscale: not authenticated (run: sudo tailscale up)"
    fi
else
    fail "Tailscale: NOT installed (run: sudo bash scripts/04-tailscale-setup.sh)"
    TAILSCALE_IP=""
fi

# ============================================================
section "6. Network"
# ============================================================

LAN_IP=$(hostname -I | awk '{print $1}' || echo "unknown")
HOSTNAME=$(hostname)

pass "Hostname: $HOSTNAME"
pass "LAN IP: $LAN_IP"

# Port 445 (SMB)
if command -v ss &>/dev/null; then
    if ss -tlnp 2>/dev/null | grep -q ':445'; then
        pass "Port 445 (SMB): listening"
    else
        fail "Port 445 (SMB): NOT listening (check Samba)"
    fi
elif command -v netstat &>/dev/null; then
    if netstat -tlnp 2>/dev/null | grep -q ':445'; then
        pass "Port 445 (SMB): listening"
    else
        fail "Port 445 (SMB): NOT listening"
    fi
fi

# Port 22 (SSH)
if command -v ss &>/dev/null && ss -tlnp 2>/dev/null | grep -q ':22'; then
    pass "Port 22 (SSH): listening"
fi

# ============================================================
section "7. Summary"
# ============================================================

echo ""
TOTAL=$((PASS + FAIL + WARN))
echo -e "  Total checks : $TOTAL"
echo -e "  ${GREEN}Passed${NC}       : $PASS"
if [ "$WARN" -gt 0 ]; then
    echo -e "  ${YELLOW}Warnings${NC}     : $WARN"
fi
if [ "$FAIL" -gt 0 ]; then
    echo -e "  ${RED}Failed${NC}       : $FAIL"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}All critical checks passed! Your NAS is ready.${NC}"
    echo ""

    echo "  Access your NAS:"
    echo "    Windows  : \\\\${LAN_IP}\\$(testparm -s 2>/dev/null | grep -E '^\[' | grep -v '\[global\]' | tr -d '[]' | head -1 || echo 'NAS') (local)"
    if [ -n "${TAILSCALE_IP:-}" ]; then
        echo "    Windows  : \\\\${TAILSCALE_IP}\\$(testparm -s 2>/dev/null | grep -E '^\[' | grep -v '\[global\]' | tr -d '[]' | head -1 || echo 'NAS') (anywhere)"
        echo "    SSH      : ssh $(logname 2>/dev/null || echo '<your-username>')@${TAILSCALE_IP} (anywhere)"
    fi
else
    echo -e "  ${RED}${BOLD}$FAIL check(s) failed. Review the [FAIL] items above and fix them.${NC}"
    echo "  Run this script again after fixing to re-verify."
fi

echo ""
