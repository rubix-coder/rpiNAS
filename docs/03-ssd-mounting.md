# SSD Mounting

This guide detects your USB SSD, formats it if needed, mounts it permanently, and ensures it re-mounts automatically on every reboot.

**You can run this manually (guide below) or use the script:**
```bash
sudo bash scripts/02-mount-ssd.sh
```

---

## Prerequisites

- You are SSH'd into the Pi as your user (e.g. `nasuser`)
- The USB SSD is plugged into one of the **blue USB 3.0 ports** on the Pi
- You have run `scripts/01-initial-setup.sh` or manually updated the system

---

## Step 1 — Identify the SSD

List all connected storage devices:
```bash
lsblk
```

You will see output like:
```
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda           8:0    0 931.5G  0 disk
└─sda1        8:1    0 931.5G  0 part
mmcblk0     179:0    0  29.7G  0 disk
├─mmcblk0p1 179:1    0   256M  0 part /boot
└─mmcblk0p2 179:2    0  29.5G  0 part /
```

- `mmcblk0` is your MicroSD card (the Pi's OS). **Do not touch this.**
- `sda` is your USB SSD. `sda1` is its first partition.

> If you see `sdb` instead of `sda`, that just means a different device letter was assigned. Use whatever letter appears for your drive.

To confirm it is the SSD and not something else:
```bash
sudo fdisk -l /dev/sda
```

Look for the size matching your SSD (e.g. 1TB shows as ~931.5 GB).

---

## Step 2 — Check the Filesystem Type

```bash
lsblk -f
```

Look at the `FSTYPE` column for your SSD partition (`sda1`). Common values:

| FSTYPE | What it means |
|--------|--------------|
| `exfat` | Windows-formatted portable drive — works fine, needs `exfatprogs` |
| `ntfs` | Windows NTFS — works, needs `ntfs-3g` |
| `ext4` | Linux native — best performance on Linux |
| `vfat` | FAT32 — works but 4GB file size limit |
| _(blank)_ | Unformatted — needs formatting |

---

## Step 3 — Install Required Filesystem Tools

Depending on your filesystem type, install the appropriate tools:

**For exFAT (most portable USB drives):**
```bash
sudo apt-get update
sudo apt-get install -y exfatprogs
```

**For NTFS:**
```bash
sudo apt-get update
sudo apt-get install -y ntfs-3g
```

**For ext4 (Linux-native, no extra tools needed):**
```bash
# Nothing to install — ext4 is built into the kernel
echo "ext4 is natively supported"
```

---

## Step 4 — (Optional) Format to ext4 for Best Performance

> **WARNING: Formatting erases ALL data on the drive. Only do this if the drive is empty or you have backed up your data.**

If you want the best Linux performance, format the drive as ext4:
```bash
# Unmount first if it auto-mounted:
sudo umount /dev/sda1

# Format (THIS ERASES EVERYTHING):
sudo mkfs.ext4 -L "NAS_SSD" /dev/sda1
```

If you want to keep it as exFAT (so it also works on Windows directly), skip this step.

---

## Step 5 — Create the Mount Point

A mount point is just an empty folder where the SSD's contents will appear:
```bash
sudo mkdir -p /mnt/ssd1
```

---

## Step 6 — Get the UUID

We mount by UUID (a unique identifier) instead of device name (`sda1`), because device names can change between reboots if you have multiple drives. UUID never changes.

```bash
sudo blkid /dev/sda1
```

Output example:
```
/dev/sda1: UUID="XXXX-XXXX" TYPE="exfat" PARTUUID="xxxxxxxx-01"
```

Copy the UUID value — you need it in the next step. In this example it is `XXXX-XXXX`.

---

## Step 7 — Add to fstab for Automatic Mounting

`/etc/fstab` is the file that tells Linux what to mount at boot. We will add a line for the SSD.

First, make a backup of your current fstab:
```bash
sudo cp /etc/fstab /etc/fstab.backup
```

Open fstab in the nano text editor:
```bash
sudo nano /etc/fstab
```

Add this line at the bottom (replace `XXXX-XXXX` with your actual UUID and `exfat` with your filesystem type):

**For exFAT:**
```
UUID=XXXX-XXXX  /mnt/ssd1  exfat  defaults,nofail,uid=1000,gid=1000,umask=000  0  0
```

**For NTFS:**
```
UUID=XXXX-XXXX  /mnt/ssd1  ntfs-3g  defaults,nofail,uid=1000,gid=1000,umask=000  0  0
```

**For ext4:**
```
UUID=XXXX-XXXX  /mnt/ssd1  ext4  defaults,nofail  0  2
```

> **Explanation of options:**
> - `nofail` — if the SSD is missing at boot, the Pi still boots normally (very important!)
> - `uid=1000,gid=1000` — your user owns the files (user `nasuser` is usually uid 1000)
> - `umask=000` — everyone can read/write (needed for Samba sharing)

Save and exit nano: press `Ctrl+X`, then `Y`, then `Enter`.

---

## Step 8 — Mount and Verify

Test your fstab entry without rebooting:
```bash
sudo mount -a
```

If there is no error output, the mount worked. Verify:
```bash
df -h | grep ssd1
```

You should see something like:
```
/dev/sda1       932G   1.2G   931G   1% /mnt/ssd1
```

Also check you can write to it:
```bash
echo "test" | sudo tee /mnt/ssd1/test.txt
cat /mnt/ssd1/test.txt
sudo rm /mnt/ssd1/test.txt
```

---

## Step 9 — Test Reboot Persistence

Reboot the Pi and check the drive is still mounted:
```bash
sudo reboot
```

Wait 60–90 seconds, then SSH back in:
```bash
df -h | grep ssd1
```

If the drive appears — you are done with mounting. Continue to [Samba Setup](04-samba-setup.md).

---

## Troubleshooting

**`mount: /mnt/ssd1: can't read superblock`**
The filesystem may be corrupted or the wrong type was specified. Check the FSTYPE again with `lsblk -f`.

**Drive not showing in `lsblk`**
- Check the physical USB connection
- Try a different USB port (use the blue USB 3.0 ports)
- Check if the drive needs its own power (some 3.5" HDDs do — use a powered USB hub)

**Permission denied writing to the SSD**
- For ext4, run: `sudo chown -R nasuser:nasuser /mnt/ssd1`
- For exFAT/NTFS, make sure `uid=1000,gid=1000,umask=000` is in your fstab entry

**`fstab` entry broke — Pi won't boot**
- Boot with the SD card, edit fstab from another computer, or restore the backup:
  - From a working Pi: `sudo cp /etc/fstab.backup /etc/fstab`
  - From your computer: mount the SD card and edit `rootfs/etc/fstab`
