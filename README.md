# Raspberry Pi 4 NAS — Complete Setup Guide

> Turn a Raspberry Pi 4 and a USB SSD into a home NAS with remote access via Tailscale, accessible from Windows, Linux, and Android. No experience required.

---

## Table of Contents

| Step | Guide |
|------|-------|
| 0 | [Hardware Requirements & Costs](docs/01-hardware-requirements.md) |
| 1 | [OS Installation (Raspberry Pi OS)](docs/02-os-setup.md) |
| 2 | [SSD Mounting](docs/03-ssd-mounting.md) |
| 3 | [Samba File Sharing (SMB)](docs/04-samba-setup.md) |
| 4 | [Tailscale — Remote Access from Anywhere](docs/05-tailscale-setup.md) |
| 5 | [Windows Client Setup](docs/06-windows-access.md) |
| 6 | [Android Client Setup](docs/07-android-setup.md) |
| 7 | [Adding More Storage Later](docs/08-adding-more-storage.md) |

---

## What This Builds

A **home NAS (Network Attached Storage)** that:
- Stores files on a USB SSD plugged into a Raspberry Pi 4
- Shares files over your local network and the internet via SMB (same protocol Windows uses for network drives)
- Lets you access your files securely from **anywhere** using Tailscale VPN — no port forwarding needed
- Works from Windows, Linux, macOS, and Android
- Costs under **$5/year** to run in electricity

```
[USB SSD] ──USB3──▶ [Raspberry Pi 4] ──Tailscale VPN──▶ [Any Device Anywhere]
                           │
                         Samba
                           │
              ┌────────────┴────────────┐
          Windows / Linux / macOS    Android
          (File Explorer / Nautilus)  (Solid Explorer)
```

---

## Cost Summary

| Item | Approx Cost (USD) |
|------|-------------------|
| Raspberry Pi 4 Model B (4GB) | $55 – $75 |
| Official Raspberry Pi power supply (5V 3A, USB-C) | $8 – $12 |
| MicroSD card (32GB+, Class 10) | $8 – $15 |
| USB SSD 1TB (any brand, USB 3.0+) | $70 – $100 |
| USB cable (if not included with SSD) | $0 – $10 |
| **Total hardware** | **~$141 – $212** |
| All software (Pi OS, Samba, Tailscale) | **Free** |

> Prices vary by region and retailer. Check Amazon, PiShop, and Micro Center.

---

## Power Consumption

| Scenario | Power Draw |
|----------|-----------|
| Pi 4 idle (no SSD) | ~2.7 W |
| Pi 4 + USB SSD idle | ~5 – 6 W |
| Pi 4 + USB SSD active file transfer | ~7 – 10 W |
| **Per day** (idle 24 h) | ~0.12 – 0.14 kWh |
| **Per month** (idle) | ~3.6 – 4.2 kWh |
| **Monthly electricity cost** at $0.12/kWh | **~$0.43 – $0.50** |
| **Annual electricity cost** | **~$5 – $6** |

> Compare to a commercial NAS (Synology/QNAP): ~15–25 W idle, ~$15–$25/year.

---

## Quick Start (Scripts)

After completing [OS setup](docs/02-os-setup.md) and SSHing into your Pi, clone this repo and run the scripts in order:

```bash
# On the Raspberry Pi — clone this repo
git clone https://github.com/rubix-coder/rpinas.git
cd rpinas

# Step 1 — Update system
sudo bash scripts/01-initial-setup.sh

# Step 2 — Detect and mount your SSD
sudo bash scripts/02-mount-ssd.sh

# Step 3 — Install and configure Samba file sharing
sudo bash scripts/03-samba-setup.sh

# Step 4 — Install Tailscale for remote access
sudo bash scripts/04-tailscale-setup.sh

# Step 5 — Verify everything works
bash scripts/05-verify-setup.sh
```

> Each script is self-contained and tells you what it's doing at every step.

---

## Prerequisites

### You Need to Know
- How to open a terminal (Linux/macOS) or Command Prompt / PowerShell (Windows)
- How to copy and paste commands
- Nothing else — every step is explained from scratch

### Hardware Checklist
- [ ] Raspberry Pi 4 Model B (2GB RAM minimum, 4GB recommended)
- [ ] Official Raspberry Pi power supply (5V 3A USB-C) — **do not use phone chargers**
- [ ] MicroSD card — 32GB or larger, Class 10 or better
- [ ] USB SSD or USB HDD (any size, any brand)
- [ ] A spare computer (Windows, Linux, or macOS) to flash the SD card
- [ ] Your home Wi-Fi password OR an Ethernet cable to your router

### Software Checklist (all free)
- [ ] [Raspberry Pi Imager](https://www.raspberrypi.com/software/) — flashes the OS onto the SD card
- [ ] [Tailscale](https://tailscale.com/) — free account for remote access
- [ ] **Windows:** File Explorer (built-in) or [FolderSync Desktop](https://foldersync.io/) for auto-sync
- [ ] **Android:** [Solid Explorer](https://play.google.com/store/apps/details?id=pl.solidexplorer2) + [FolderSync](https://play.google.com/store/apps/details?id=dk.tacit.android.foldersync.lite)

---

## Example Hardware Used

- Raspberry Pi 4 Model B
- 1TB portable USB SSD (USB 3.0)
- Linux laptop — used to SSH into the Pi
- Tailscale for remote access across all devices

---

## License

MIT — free to use, adapt, and share.
