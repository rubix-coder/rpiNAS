# OS Installation — Raspberry Pi OS Lite

This guide installs **Raspberry Pi OS Lite (64-bit)** on your MicroSD card. "Lite" means no desktop — the Pi runs as a headless server, which is exactly what we want for a NAS. It uses less RAM, less CPU, and starts faster.

---

## What You Need

- MicroSD card (32GB+)
- Your computer (Windows, Linux, or macOS)
- Raspberry Pi Imager (download below)
- Your Wi-Fi name (SSID) and password, OR an Ethernet cable

---

## Step 1 — Download Raspberry Pi Imager

Go to the official page and download the version for your OS:

**https://www.raspberrypi.com/software/**

- Windows: download the `.exe` installer
- macOS: download the `.dmg` file
- Ubuntu/Debian Linux: run this in a terminal:
  ```bash
  sudo apt-get install rpi-imager
  ```
- Other Linux: download the `.deb` or `.AppImage` from the page above

Install and open Raspberry Pi Imager.

---

## Step 2 — Insert the MicroSD Card

Plug your MicroSD card into your computer. If your computer does not have a MicroSD slot, you need a USB card reader (very cheap, ~$5).

---

## Step 3 — Flash the OS

1. Open **Raspberry Pi Imager**
2. Click **"CHOOSE DEVICE"** → select **Raspberry Pi 4**
3. Click **"CHOOSE OS"**
   - Select **"Raspberry Pi OS (other)"**
   - Then select **"Raspberry Pi OS Lite (64-bit)"**
   - _(Do NOT choose the Desktop version — you don't need it)_
4. Click **"CHOOSE STORAGE"** → select your MicroSD card
   - **Double-check you selected the SD card, not your own hard drive!**

---

## Step 4 — Configure SSH and Wi-Fi (Critical!)

Before flashing, click the **gear icon** (or "EDIT SETTINGS" button) to pre-configure the Pi. This lets the Pi connect to your network automatically on first boot.

Fill in these settings:

### General tab
| Setting | What to Enter |
|---------|--------------|
| Set hostname | `raspberrypi` (or anything you like, e.g. `nas`) |
| Set username and password | Username: `nasuser` (or your name) / choose a strong password |
| Configure wireless LAN | Enter your Wi-Fi name and password |
| Wireless LAN country | Select your country |
| Set locale settings | Set your timezone and keyboard layout |

### Services tab
| Setting | Value |
|---------|-------|
| Enable SSH | Checked |
| Use password authentication | Selected |

Click **"SAVE"** then click **"YES"** when asked to apply the customisation.

---

## Step 5 — Write the Image

Click **"WRITE"**. You will be warned that all data on the SD card will be erased. Click **"YES"** to confirm.

The write and verification process takes **3–10 minutes** depending on your card speed. Do not remove the card until it says "Write Successful."

---

## Step 6 — First Boot

1. Remove the MicroSD card from your computer and insert it into the Raspberry Pi (slot is on the underside)
2. Plug your USB SSD into one of the **blue USB 3.0 ports** on the Pi (the blue ports are faster)
3. Plug in the power supply last — the Pi boots immediately when power is connected
4. Wait **60–90 seconds** for first boot (it expands the filesystem on first run)

---

## Step 7 — Find the Pi's IP Address

You need the Pi's IP address to SSH into it. There are three ways to find it:

### Option A — Use the hostname (easiest)
Most home networks support mDNS. Try:
```bash
# From your Linux/macOS computer:
ping raspberrypi.local
# or whatever hostname you set:
ping nas.local
```
If you get replies, use `raspberrypi.local` as the address.

### Option B — Check your router
Log into your home router's admin page (usually `192.168.1.1` or `192.168.0.1` in a browser). Look for a "Connected devices" or "DHCP clients" list. Find `raspberrypi` in the list.

### Option C — Scan the network
```bash
# Install nmap if not installed:
sudo apt-get install nmap       # Ubuntu/Debian
# Then scan (replace 192.168.1 with your network prefix):
nmap -sn 192.168.1.0/24 | grep -i raspberry
```

---

## Step 8 — SSH into the Pi

Once you have the IP address (e.g. `192.168.x.x`):

### From Linux or macOS:
```bash
ssh nasuser@192.168.x.x
# or using hostname:
ssh nasuser@raspberrypi.local
```

### From Windows:
Open **Command Prompt** or **PowerShell** (press Win+R, type `cmd`, press Enter):
```
ssh nasuser@192.168.x.x
```
> Windows 10 and 11 include SSH by default. If the command is not found, go to Settings → Apps → Optional Features → Add a feature → OpenSSH Client.

When asked "Are you sure you want to continue connecting?" type `yes` and press Enter.

Enter your password when prompted. The password will not appear as you type — that is normal.

---

## Step 9 — You're In!

You should see a prompt like:
```
nasuser@raspberrypi:~ $
```

Congratulations — you are now connected to your Raspberry Pi. Continue to [SSD Mounting](03-ssd-mounting.md) or run the scripts:

```bash
# Clone this repo on the Pi first:
git clone https://github.com/rubix-coder/rpinas.git
cd rpinas

# Then run the initial setup script:
sudo bash scripts/01-initial-setup.sh
```

---

## Troubleshooting

**Cannot connect via SSH — "Connection refused"**
- Wait another 60 seconds and try again. The Pi may still be booting.
- Check that SSH was enabled in the Imager settings (Step 4).
- Verify the Pi is connected to your network — check your router's device list.

**Cannot find the Pi on the network**
- Make sure you entered the Wi-Fi credentials correctly in Step 4.
- Try connecting the Pi via Ethernet cable directly to your router instead.
- Re-flash the SD card and try again.

**Wrong password**
- The password you set in Step 4 is the one to use. If you forgot it, re-flash the SD card.

**"WARNING: Remote host identification has changed"**
- This happens if you re-flashed and SSH sees a different key. Run:
  ```bash
  ssh-keygen -R raspberrypi.local
  # or:
  ssh-keygen -R 192.168.x.x
  ```
  Then try SSHing again.
