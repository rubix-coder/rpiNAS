# Windows Client Setup

This guide sets up access to the NAS from a Windows PC — both on the local network and remotely via Tailscale.

---

## Prerequisites

- Samba is configured on the Pi ([Samba Setup](04-samba-setup.md))
- Tailscale is installed on the Pi ([Tailscale Setup](05-tailscale-setup.md))
- You know the Pi's Tailscale IP (e.g. `100.67.250.22`) or local IP (e.g. `192.168.1.105`)

---

## Option A — Access Directly (No Installation Needed)

Windows has built-in SMB support. No extra software required.

### One-time Access via File Explorer

1. Open **File Explorer** (Win+E)
2. Click in the address bar at the top
3. Type the path to your NAS share and press Enter:
   ```
   \\100.67.250.22\Kingston
   ```
   _(Use Tailscale IP to access from anywhere, or local IP if on the same Wi-Fi)_
4. A login box will appear:
   - **Username:** `bmp`
   - **Password:** your Samba password (set in [Samba Setup](04-samba-setup.md))
   - Check "Remember my credentials" so you don't have to type it every time
5. The NAS share opens — you can now copy, paste, and manage files

### Map as a Permanent Network Drive

Mapping creates a drive letter (like `Z:`) that always points to your NAS:

1. Open **File Explorer**
2. Right-click **"This PC"** in the left sidebar
3. Click **"Map network drive..."**
4. Set:
   - **Drive:** any letter (e.g. `Z:`)
   - **Folder:** `\\100.67.250.22\Kingston`
   - Check **"Reconnect at sign-in"** — this remounts the drive every time you log in
   - Check **"Connect using different credentials"** if your Windows username differs from `bmp`
5. Click **Finish**, enter your Samba username and password
6. The drive `Z:` now appears in File Explorer alongside your local drives

---

## Option B — Install Tailscale for Remote Access

If you are not at home and want to reach the NAS from outside your network, you need Tailscale on your Windows PC too.

### Install Tailscale on Windows

1. Go to: https://tailscale.com/download
2. Download the **Windows** installer (`.exe`)
3. Run the installer — follow the prompts
4. Tailscale appears in the system tray (bottom-right corner, near the clock)
5. Click the Tailscale icon → **Sign in**
6. Log in with the **same account** you used to set up Tailscale on the Pi
7. Tailscale connects — you can now reach the Pi at its Tailscale IP (`100.67.250.22`)

### Firewall Exception for Tailscale (Norton / McAfee / Windows Defender)

Some security software blocks traffic to `100.x.x.x` addresses. If SMB over Tailscale doesn't work, add a firewall exception:

**Windows Defender Firewall:**
1. Open **Windows Security** → **Firewall & network protection** → **Advanced settings**
2. Click **Inbound Rules** → **New Rule**
3. Choose **Port** → TCP → Specific ports: `445`
4. Choose **Allow the connection**
5. Apply to Domain, Private, and Public
6. Name it "Tailscale SMB"

**Norton:**
1. Open Norton → **Settings** → **Firewall**
2. Go to **Traffic Rules** → **Add**
3. Allow TCP traffic from source `100.64.0.0/10` on port `445`

**McAfee:**
1. Open McAfee → **PC Security** → **Firewall** → **Internet Connections for Programs**
2. Or add an exception for the Tailscale IP range `100.64.0.0/10`

---

## Option C — FolderSync Desktop (Auto Sync)

FolderSync Desktop automatically syncs folders between your PC and the NAS — like a self-hosted Dropbox.

### Install FolderSync Desktop

1. Download from: https://foldersync.io/
2. Install and open it

### Add the NAS as an Account

1. Open FolderSync Desktop
2. Go to **Accounts** → **Add account**
3. Select **SMB / CIFS / Windows Share**
4. Fill in:
   - **Host:** `100.67.250.22` (Tailscale IP for remote, or local IP for home only)
   - **Share:** `Kingston`
   - **Username:** `bmp`
   - **Password:** your Samba password
   - **Domain:** (leave blank)
5. Click **Test connection** — should say "Connection successful"
6. Click **Save**

### Create a Sync Pair (Folder Pair)

1. Go to **Folderpairs** → **Add folderpair**
2. Set:
   - **Local folder:** e.g. `C:\Users\YourName\Documents\NAS Sync`
   - **Remote folder:** browse to your desired folder on the NAS
   - **Sync type:** choose one:
     - **Two-way** — changes on either side sync to the other
     - **To remote** — PC → NAS only (good for backup)
     - **To local** — NAS → PC only (good for reading)
3. Set a **sync schedule** (e.g. every hour, or manually)
4. Click **Save** then **Sync now** to test

---

## Verify Everything Works

Open File Explorer and navigate to your mapped drive (e.g. `Z:`). Try:
- Creating a new folder
- Copying a file in
- Deleting a file

If all three work, your Windows NAS access is fully set up.

---

## Troubleshooting

**"Windows cannot access \\100.67.250.22\Kingston"**
- Check Tailscale is connected on your Windows PC (system tray icon)
- Check Tailscale is running on the Pi: SSH in and run `sudo systemctl status tailscaled`
- Try pinging the Pi: open Command Prompt and run `ping 100.67.250.22`

**Login dialog loops (keeps asking for password)**
- Make sure you are using Samba username `bmp` (not your Windows username)
- In credential manager: Start → type "Credential Manager" → Windows Credentials → remove any old entries for the Pi's IP

**Mapped drive shows disconnected / red X after reboot**
- Make sure Tailscale starts before File Explorer tries to reconnect
- Try right-clicking the drive and clicking "Reconnect"
- Alternatively, use a login script to mount the drive after Tailscale connects

**SMB1 protocol error (older Windows versions)**
- Windows 10/11 disables SMBv1. Samba uses SMBv2/v3 by default, so this should not occur. If it does:
  ```
  # On the Pi, check smb.conf has:
  min protocol = SMB2
  ```
