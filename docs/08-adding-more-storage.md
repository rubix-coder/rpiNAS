# Adding More Storage

When your first SSD fills up, or you want to separate different types of data across drives, you can add more USB drives. Each drive gets its own mount point and its own Samba share (or you can add them all to one share).

---

## Method 1 — Add a Second SSD (Recommended)

This is the cleanest approach: each SSD is independent, gets its own mount point, and can be added or removed without affecting the others.

### Step 1 — Plug In the New Drive

Plug the new USB SSD into any free USB port on the Pi. The blue USB 3.0 ports give better performance.

### Step 2 — Identify the New Drive

```bash
lsblk
```

You will see a new device, likely `sdb` (since `sda` is your first SSD):
```
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINT
sda           8:0    0 931.5G  0 disk
└─sda1        8:1    0 931.5G  0 part /mnt/ssd1
sdb           8:16   0 931.5G  0 disk
└─sdb1        8:17   0 931.5G  0 part
mmcblk0     179:0    0  29.7G  0 disk
```

### Step 3 — Get the New Drive's UUID

```bash
sudo blkid /dev/sdb1
```

Copy the UUID (it will be different from your first SSD's UUID).

### Step 4 — Create a New Mount Point

```bash
sudo mkdir -p /mnt/ssd2
```

### Step 5 — Add to fstab

```bash
sudo nano /etc/fstab
```

Add a new line for the second drive (adjust UUID and filesystem type):

```
UUID=XXXXXXXX-XXXX  /mnt/ssd2  ext4  defaults,nofail  0  2
```

Save and exit, then mount:

```bash
sudo mount -a
df -h | grep ssd2
```

### Step 6 — Set Permissions

```bash
sudo chown -R bmp:bmp /mnt/ssd2
sudo chmod -R 0775 /mnt/ssd2
```

### Step 7 — Add a New Samba Share

```bash
sudo nano /etc/samba/smb.conf
```

Add a new share block at the bottom:

```ini
[Storage2]
   comment = Second SSD
   path = /mnt/ssd2
   browseable = yes
   read only = no
   writable = yes
   create mask = 0775
   directory mask = 0775
   valid users = bmp
   force user = bmp
```

Restart Samba:
```bash
sudo systemctl restart smbd
```

Your second drive is now accessible as `\\100.67.250.22\Storage2`.

---

## Method 2 — Use a Powered USB Hub

The Pi's USB ports can provide up to ~1.2A total across all USB ports. Multiple bus-powered SSDs may cause issues. Use a **powered USB hub** (one with its own power adapter) to safely connect multiple drives.

Recommended: any 4-port USB 3.0 hub with an external power adapter (e.g. Anker, Sabrent, TP-Link). Cost: ~$15–$30.

Connection:
```
Pi USB 3.0 port
      │
  [Powered USB Hub]
      ├── SSD 1 (sda)
      ├── SSD 2 (sdb)
      └── SSD 3 (sdc)
```

The setup process for each drive is identical to Method 1.

---

## Method 3 — Merge Drives into a Single Share

If you want all drives to appear as one large pool under a single Samba share, you can use `mergerfs` to combine them into a single virtual mount point.

> This is more advanced. Only do this if you specifically want one giant pool.

### Install mergerfs

```bash
sudo apt-get update
sudo apt-get install -y mergerfs
```

### Create a Pool Mount Point

```bash
sudo mkdir -p /mnt/pool
```

### Add to fstab

```bash
sudo nano /etc/fstab
```

Add after your individual SSD entries:
```
/mnt/ssd1:/mnt/ssd2  /mnt/pool  fuse.mergerfs  defaults,allow_other,use_ino,cache.files=off,moveoneexisting=preexisting  0  0
```

Mount:
```bash
sudo mount -a
df -h | grep pool
```

### Point Samba at the Pool

In `/etc/samba/smb.conf`, change the `Kingston` share path to:
```ini
[NAS]
   path = /mnt/pool
   ...
```

Now `\\100.67.250.22\NAS` shows all drives as one combined share. Files are distributed across the physical drives based on available space.

---

## Drive Naming Reference

| Device | Typical Mount Point | Samba Share Name |
|--------|--------------------|--------------------|
| First SSD | `/mnt/ssd1` | `Kingston` or `Storage1` |
| Second SSD | `/mnt/ssd2` | `Storage2` |
| Third SSD | `/mnt/ssd3` | `Storage3` |
| Pool (merged) | `/mnt/pool` | `NAS` |

---

## Capacity Planning

| Drives | Total Storage | Cost Estimate |
|--------|--------------|---------------|
| 1 × 1TB SSD | 1 TB | ~$70–$100 |
| 2 × 1TB SSD | 2 TB | ~$140–$200 |
| 1 × 2TB SSD | 2 TB | ~$120–$160 |
| 4 × 1TB SSD | 4 TB | ~$280–$400 |

> For redundancy (surviving drive failure), consider a RAID setup. The simplest option for Pi is `mdadm` RAID 1 (mirror). This is an advanced topic not covered in this guide.

---

## Removing a Drive Safely

Always unmount before physically disconnecting:

```bash
# Unmount the drive:
sudo umount /mnt/ssd2

# Then remove from fstab to prevent boot errors:
sudo nano /etc/fstab
# Delete or comment out the line for ssd2

# Then it is safe to unplug
```
