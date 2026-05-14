# Samba File Sharing Setup

Samba lets the Pi share files using the **SMB protocol** — the same protocol Windows uses for network drives. Once configured, you can access your NAS from:
- Windows (File Explorer, map as network drive)
- Linux (Nautilus, Dolphin, or `mount -t cifs`)
- macOS (Finder → Go → Connect to Server)
- Android (Solid Explorer, FX File Explorer, etc.)

**You can run this manually (guide below) or use the script:**
```bash
sudo bash scripts/03-samba-setup.sh
```

---

## Prerequisites

- SSD is mounted at `/mnt/ssd1` (completed [SSD Mounting](03-ssd-mounting.md))
- You are SSH'd into the Pi

---

## Step 1 — Install Samba

```bash
sudo apt-get update
sudo apt-get install -y samba samba-common-bin
```

Verify it installed:
```bash
samba --version
```

You should see something like `Version 4.17.x`.

---

## Step 2 — Back Up the Default Config

Before editing, save the original Samba config:
```bash
sudo cp /etc/samba/smb.conf /etc/samba/smb.conf.backup
```

---

## Step 3 — Configure the Samba Share

Open the Samba configuration file:
```bash
sudo nano /etc/samba/smb.conf
```

Scroll to the very bottom of the file and add this block (replace `Kingston` with whatever share name you want, and adjust the path if you mounted your SSD elsewhere):

```ini
[Kingston]
   comment = NAS Storage
   path = /mnt/ssd1
   browseable = yes
   read only = no
   writable = yes
   create mask = 0775
   directory mask = 0775
   valid users = bmp
   force user = bmp
```

> **Explanation:**
> - `[Kingston]` — the share name users will see on the network
> - `path` — where the SSD is mounted
> - `valid users = bmp` — only user `bmp` can access this share
> - `force user = bmp` — files created via Samba are owned by `bmp`

Save and exit: `Ctrl+X`, `Y`, `Enter`.

---

## Step 4 — Create a Samba Password for Your User

Samba has its own separate password database. Set a password for your user:

```bash
sudo smbpasswd -a bmp
```

You will be asked to enter and confirm a password. This is the password you'll use to connect from Windows/Android. It can be different from your SSH/Linux password.

Enable the account:
```bash
sudo smbpasswd -e bmp
```

---

## Step 5 — Verify the Config

Check the config file for syntax errors:
```bash
testparm
```

You should see `Loaded services file OK.` at the end. Press `Ctrl+C` to exit.

---

## Step 6 — Restart Samba

Apply your changes by restarting the Samba services:
```bash
sudo systemctl restart smbd nmbd
```

Enable them to start automatically on boot:
```bash
sudo systemctl enable smbd nmbd
```

Check they are running:
```bash
sudo systemctl status smbd
```

You should see `active (running)` in green.

---

## Step 7 — Set Correct Permissions on the SSD

Make sure your user can read and write to the SSD:
```bash
sudo chown -R bmp:bmp /mnt/ssd1
sudo chmod -R 0775 /mnt/ssd1
```

> If your SSD is exFAT or NTFS, the `chown` command may say "Operation not supported" — that is OK. The `uid=1000` option in fstab handles this.

---

## Step 8 — Test from the Pi Itself

You can test the share from the Pi before going to another device:
```bash
smbclient -L localhost -U bmp
```

Enter your Samba password. You should see the `Kingston` share listed:
```
Sharename    Type    Comment
---------    ----    -------
Kingston     Disk    NAS Storage
```

---

## Step 9 — Access from Another Device on the Same Network

### From Linux:
Open your file manager (Nautilus, Dolphin) and type in the address bar:
```
smb://192.168.1.105/Kingston
```
Replace `192.168.1.105` with your Pi's IP address. Enter username `bmp` and your Samba password.

Or mount from terminal:
```bash
sudo apt-get install -y cifs-utils
sudo mkdir -p /mnt/nas
sudo mount -t cifs //192.168.1.105/Kingston /mnt/nas -o username=bmp,uid=$(id -u),gid=$(id -g)
```

### From Windows:
1. Open **File Explorer**
2. In the address bar type: `\\192.168.1.105\Kingston`
3. Press Enter — enter username `bmp` and your Samba password
4. To map as a permanent drive: right-click "This PC" → "Map network drive"

### From macOS:
1. Open **Finder**
2. Menu → **Go → Connect to Server** (`Cmd+K`)
3. Enter: `smb://192.168.1.105/Kingston`
4. Enter username `bmp` and Samba password

---

## Firewall Notes

If you have a firewall running on the Pi (UFW), allow Samba:
```bash
sudo ufw allow samba
```

---

## Troubleshooting

**"Access denied" or "Incorrect password"**
- Make sure you ran `sudo smbpasswd -a bmp` and `sudo smbpasswd -e bmp`
- The Samba password is separate from your Linux login password

**Share not visible in network browser**
- Try connecting directly by IP: `\\192.168.1.x\Kingston` instead of browsing
- Check Samba is running: `sudo systemctl status smbd`

**Can see share but can't write files**
- Check SSD permissions: `ls -la /mnt/ssd1`
- Run: `sudo chown -R bmp:bmp /mnt/ssd1 && sudo chmod -R 0775 /mnt/ssd1`

**`testparm` shows errors**
- Check indentation in smb.conf — the lines under `[Kingston]` must be indented with spaces or tabs
- Make sure there are no typos in option names
