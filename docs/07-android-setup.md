# Android Client Setup

This guide sets up your Android phone or tablet to access the NAS for browsing files and auto-syncing.

You will install two apps:
- **Solid Explorer** — for browsing and managing files on the NAS
- **FolderSync** — for automatically syncing folders between your phone and the NAS

---

## Prerequisites

- Samba is set up on the Pi ([Samba Setup](04-samba-setup.md))
- Tailscale is set up on the Pi ([Tailscale Setup](05-tailscale-setup.md))
- You know the Pi's Tailscale IP (run `tailscale ip -4` on the Pi to find it)

---

## Part 1 — Tailscale on Android (Remote Access)

If you only want to access the NAS from home (same Wi-Fi), you can skip this. For access from anywhere, install Tailscale:

1. Install **Tailscale** from the Play Store (free):
   - Search for "Tailscale" or find it directly in the Play Store

2. Open Tailscale → tap **Sign In**

3. Sign in with the **same account** you used to set up Tailscale on the Pi

4. Toggle the VPN on (the switch at the top)

5. Your Pi will appear in the device list with its Tailscale IP

The Pi is now reachable from your phone from anywhere with internet.

---

## Part 2 — Solid Explorer (File Browser)

Solid Explorer is a two-panel file manager that natively supports SMB network shares.

### Install
- Search "Solid Explorer" in the Play Store
- Free to try; one-time purchase (~$2.99) after a 14-day trial

### Connect to the NAS

1. Open **Solid Explorer**

2. Tap the **+** button (bottom right) or the hamburger menu

3. Tap **"New cloud connection"** or **"Add storage"**

4. Select **"LAN / SMB"** or **"Windows / Samba share"**

5. Fill in:
   | Field | Value |
   |-------|-------|
   | Host / IP | your Pi's Tailscale IP (e.g. `100.x.x.x`) |
   | Share | `NAS` (or whatever share name you set) |
   | Username | your Samba username |
   | Password | your Samba password |
   | Domain | (leave blank) |

6. Tap **Connect** / **Test** — if successful, tap **Save**

7. The `NAS` share appears as a bookmark in Solid Explorer

You can now browse, copy, move, and open files on your NAS directly from your phone.

---

## Part 3 — FolderSync (Auto Backup / Sync)

FolderSync automatically syncs selected phone folders to the NAS on a schedule — great for photo backup.

### Install
- Search "FolderSync" in the Play Store
- **FolderSync Lite** is free (with ads, limited to 2 sync pairs)
- **FolderSync Pro** is a one-time purchase (~$3.49) for unlimited pairs

### Add the NAS as an Account

1. Open **FolderSync**

2. Tap **"Accounts"** → tap **"+"** to add a new account

3. Select **"SMB/CIFS"** (also labeled "Samba" in some versions)

4. Fill in:
   | Field | Value |
   |-------|-------|
   | Account name | `Home NAS` (anything you like) |
   | Server | your Pi's Tailscale IP |
   | Share | `NAS` (or whatever share name you set) |
   | Username | your Samba username |
   | Password | your Samba password |
   | SMB version | SMB2 (or Auto) |

5. Tap **"Test"** — should say "Connection OK"

6. Tap **"Save"**

### Create a Sync Pair for Photo Backup

1. Tap **"Folderpairs"** → tap **"+"**

2. Configure:
   | Setting | Value |
   |---------|-------|
   | Folderpair name | `Photo Backup` |
   | Account | `Home NAS` |
   | Sync type | **"To remote folder"** (phone → NAS only, for backup) |
   | Local folder | `/sdcard/DCIM/Camera` (your camera folder) |
   | Remote folder | Browse to `NAS/Phone Backup/Photos` |

3. **Scheduling** (optional):
   - Tap **"Scheduling"**
   - Enable **"Scheduled sync"**
   - Set interval: e.g. **"Every 1 hour"** or **"When connected to Wi-Fi"**

4. **Advanced options** (recommended):
   - Enable **"Use WiFi only"** to avoid mobile data charges
   - Enable **"Use existing if file size is same"** to skip already-synced files

5. Tap **"Save"**

6. Tap **"Sync now"** to do the first sync immediately

### Suggested Folder Pairs

| What | Local Folder | Remote Folder | Sync Type |
|------|-------------|---------------|-----------|
| Photo backup | `/sdcard/DCIM` | `NAS/Phone/Photos` | To remote |
| WhatsApp backup | `/sdcard/WhatsApp` | `NAS/Phone/WhatsApp` | To remote |
| Documents sync | `/sdcard/Documents` | `NAS/Documents` | Two-way |
| Music download | `/sdcard/Music` | `NAS/Music` | To local |

---

## Troubleshooting

**Cannot connect — "Connection failed"**
- Make sure Tailscale VPN is on and connected (check the Tailscale app)
- Ping test: install "Ping" app, ping your Pi's Tailscale IP
- Try connecting on local Wi-Fi first using your Pi's home IP to isolate the issue

**Solid Explorer shows share but files are empty**
- The share path may be wrong. Check you have the right share name (`NAS` not `ssd1`)
- Try browsing to the Pi IP without specifying the share name to see what shares are visible

**FolderSync shows "No network available"**
- Tailscale VPN must be enabled before FolderSync tries to sync
- In FolderSync → Account settings, make sure it is set to allow the VPN interface

**Sync is very slow**
- Tailscale over mobile data is limited by your connection speed. On home Wi-Fi over Tailscale it should be fast.
- For large first syncs, connect to home Wi-Fi first.

**FolderSync keeps re-uploading the same files**
- Set "Use existing if file size is same" and "Use modified date" in advanced sync settings
- Make sure the NAS and phone clocks are in sync (they usually are)
