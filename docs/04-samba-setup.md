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

Scroll to the very bottom of the file and add this block (replace `NAS` with whatever share name you want, and adjust the path if you mounted your SSD elsewhere):

```ini
[NAS]
   comment = NAS Storage
   path = /mnt/ssd1
   browseable = yes
   read only = no
   writable = yes
   create mask = 0775
   directory mask = 0775
   valid users = nasuser
   force user = nasuser
```

> **Explanation:**
> - `[NAS]` — the share name users will see on the network (change to anything you like)
> - `path` — where the SSD is mounted
> - `valid users = nasuser` — replace `nasuser` with your actual Linux username
> - `force user = nasuser` — files created via Samba are owned by that user

Save and exit: `Ctrl+X`, `Y`, `Enter`.

---

## Step 4 — Create a Samba Password for Your User

Samba has its own separate password database. Set a password for your user (replace `nasuser` with your actual username):

```bash
sudo smbpasswd -a nasuser
```

You will be asked to enter and confirm a password. This is the password you'll use to connect from Windows/Android. It can be different from your SSH/Linux password.

Enable the account:
```bash
sudo smbpasswd -e nasuser
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

Make sure your user can read and write to the SSD (replace `nasuser` with your username):
```bash
sudo chown -R nasuser:nasuser /mnt/ssd1
sudo chmod -R 0775 /mnt/ssd1
```

> If your SSD is exFAT or NTFS, the `chown` command may say "Operation not supported" — that is OK. The `uid=1000` option in fstab handles this.

---

## Step 8 — Test from the Pi Itself

You can test the share from the Pi before going to another device (replace `nasuser` with your username):
```bash
smbclient -L localhost -U nasuser
```

Enter your Samba password. You should see the `NAS` share listed:
```
Sharename    Type    Comment
---------    ----    -------
NAS          Disk    NAS Storage
```

---

## Step 9 — Access from Another Device on the Same Network

Replace `192.168.x.x` with your Pi's actual local IP address (found during [OS setup](02-os-setup.md)).

### From Linux:
Open your file manager (Nautilus, Dolphin) and type in the address bar:
```
smb://192.168.x.x/NAS
```
Enter your username and Samba password.

Or mount from terminal:
```bash
sudo apt-get install -y cifs-utils
sudo mkdir -p /mnt/nas
sudo mount -t cifs //192.168.x.x/NAS /mnt/nas -o username=nasuser,uid=$(id -u),gid=$(id -g)
```

### From Windows:
1. Open **File Explorer**
2. In the address bar type: `\\192.168.x.x\NAS`
3. Press Enter — enter your Samba username and password
4. To map as a permanent drive: right-click "This PC" → "Map network drive"

### From macOS:
1. Open **Finder**
2. Menu → **Go → Connect to Server** (`Cmd+K`)
3. Enter: `smb://192.168.x.x/NAS`
4. Enter your Samba username and password

---

## Firewall Notes

If you have a firewall running on the Pi (UFW), allow Samba:
```bash
sudo ufw allow samba
```

---

## Troubleshooting

**"Access denied" or "Incorrect password"**
- Make sure you ran `sudo smbpasswd -a <username>` and `sudo smbpasswd -e <username>`
- The Samba password is separate from your Linux login password

**Share not visible in network browser**
- Try connecting directly by IP: `\\192.168.x.x\NAS` instead of browsing
- Check Samba is running: `sudo systemctl status smbd`

**Can see share but can't write files**
- Check SSD permissions: `ls -la /mnt/ssd1`
- Run: `sudo chown -R <username>:<username> /mnt/ssd1 && sudo chmod -R 0775 /mnt/ssd1`

**`testparm` shows errors**
- Check indentation in smb.conf — the lines under `[NAS]` must be indented with spaces or tabs
- Make sure there are no typos in option names
