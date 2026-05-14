# Tailscale — Secure Remote Access from Anywhere

Tailscale creates a private VPN network between your devices. Once set up:
- You can access your NAS from anywhere in the world — office, coffee shop, abroad
- No port forwarding on your router needed
- No public IP required
- Traffic is encrypted end-to-end
- **Free for personal use** (up to 3 users, 100 devices)

**You can run this manually (guide below) or use the script:**
```bash
sudo bash scripts/04-tailscale-setup.sh
```

---

## How Tailscale Works (Simple Explanation)

Tailscale assigns each of your devices a private IP in the `100.x.x.x` range (called a "Tailscale IP"). All your devices — Pi, laptop, phone — can talk to each other using these IPs, even through firewalls and NAT, as if they were on the same local network.

```
[Pi at home]  ←── Tailscale VPN ──→  [Your laptop at work]
100.67.250.22                          100.x.x.x
```

---

## Prerequisites

- You have a free Tailscale account at https://tailscale.com (sign up with Google/GitHub/email)
- You are SSH'd into the Pi

---

## Step 1 — Install Tailscale on the Pi

Tailscale provides an official install script:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

This script:
1. Detects your OS (Raspberry Pi OS / Debian)
2. Adds the Tailscale apt repository
3. Installs the `tailscale` package
4. Starts the Tailscale service

Verify it installed:
```bash
tailscale version
```

---

## Step 2 — Authenticate the Pi with Tailscale

```bash
sudo tailscale up
```

This will print a URL like:
```
To authenticate, visit:

        https://login.tailscale.com/a/xxxxxxxxxxxxxxxxxx
```

**Copy that URL and open it in a browser on any device** (your laptop, phone — anything with internet access).

Log in with your Tailscale account. You will see a page saying "Device connected." The Pi is now part of your Tailscale network.

---

## Step 3 — Find Your Pi's Tailscale IP

```bash
tailscale ip -4
```

Example output:
```
100.67.250.22
```

This is the Pi's permanent Tailscale IP. It stays the same even if the Pi's local IP changes. Write it down.

You can also see all your Tailscale devices at: **https://login.tailscale.com/admin/machines**

---

## Step 4 — Enable Tailscale to Start on Boot

```bash
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
```

Verify it is running:
```bash
sudo systemctl status tailscaled
```

You should see `active (running)`.

---

## Step 5 — Test the Connection

From another device that has Tailscale installed (see Step 6 below), try:

```bash
# Ping the Pi over Tailscale:
ping 100.67.250.22

# SSH over Tailscale:
ssh bmp@100.67.250.22

# Access the Samba share over Tailscale:
# Windows: \\100.67.250.22\Kingston
# Linux: smb://100.67.250.22/Kingston
```

---

## Step 6 — Install Tailscale on Your Other Devices

Install Tailscale on every device that needs remote access to the NAS:

### Windows
1. Go to https://tailscale.com/download
2. Download and install Tailscale for Windows
3. Sign in with the same Tailscale account you used on the Pi
4. The Pi (and its Tailscale IP) will appear in the Tailscale menu

**Firewall note for Windows with Norton/antivirus:**
Some antivirus suites (e.g. Norton) block the Tailscale subnet. Add a firewall exception for `100.64.0.0/10`.

### Android
1. Install **Tailscale** from the Play Store
2. Open it and sign in with the same account
3. Toggle on the VPN

### Linux (Ubuntu/Debian)
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

### macOS
1. Install Tailscale from the Mac App Store
2. Open and sign in

---

## Step 7 — Access the NAS Remotely

Once Tailscale is running on both the Pi and your device, use the Pi's Tailscale IP everywhere you would normally use the local IP:

| What | Local (home only) | Remote (Tailscale) |
|------|-------------------|--------------------|
| SSH | `ssh bmp@192.168.1.105` | `ssh bmp@100.67.250.22` |
| Windows SMB | `\\192.168.1.105\Kingston` | `\\100.67.250.22\Kingston` |
| Linux SMB | `smb://192.168.1.105/Kingston` | `smb://100.67.250.22/Kingston` |

---

## Optional — Key Expiry

By default, Tailscale authentication keys expire after 90 days and you need to re-authenticate. For a NAS (server that should stay connected), disable key expiry:

1. Go to https://login.tailscale.com/admin/machines
2. Find your Pi, click the **...** menu
3. Click **"Disable key expiry"**

This way your Pi stays connected indefinitely without needing to re-authenticate.

---

## Troubleshooting

**`curl: command not found`**
```bash
sudo apt-get install -y curl
```
Then re-run the Tailscale install command.

**Tailscale says "not connected" after reboot**
```bash
sudo tailscale up
sudo systemctl enable tailscaled
```

**Can't reach the Pi's Tailscale IP from another device**
- Make sure Tailscale is running on BOTH devices: `sudo systemctl status tailscaled`
- Both devices must be signed into the **same** Tailscale account
- Check the Tailscale admin page to confirm both devices are listed as "Connected"

**SMB share not reachable over Tailscale but SSH works**
- The Windows firewall or antivirus may be blocking SMB. Add a rule allowing traffic from `100.64.0.0/10` on port 445.
- Try temporarily disabling the Windows firewall to test.

**Tailscale IP changed**
- Tailscale IPs are persistent — they don't change unless you remove and re-add the device. If it changed, re-authenticate: `sudo tailscale up`
