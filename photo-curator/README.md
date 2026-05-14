# Photo Curator — Digital to Physical

Turn your digital photo library into a physical album. This app uses AI running on your GPU to find your best photos from thousands of images, then exports them print-ready (300 DPI) so you can hand them to any print shop.

## What it does

1. **Scans** your photo folder (supports JPG, PNG, HEIC, WEBP)
2. **Scores** every photo with AI — checking beauty, sharpness, lighting, and faces
3. **Ranks** them best-first so the good ones bubble to the top
4. **Lets you keep, skip, or remove** photos with a single click (or keyboard shortcut)
5. **Exports** your chosen photos as 300 DPI JPEGs, smart-cropped to your chosen print size, with descriptive filenames like `2024-07-04_beach_sunset_0001_4x6.jpg`

---

## Requirements

| What | Details |
|---|---|
| Docker | Version 20.10 or later |
| NVIDIA GPU | Any CUDA-capable GPU with ≥ 4 GB VRAM (e.g. RTX 3060, RTX 4070) |
| NVIDIA Container Toolkit | For GPU passthrough into Docker |
| RAM | 8 GB minimum, 16 GB recommended |
| Disk space | ~12 GB for the Docker image (CLIP model is ~1.5 GB) |

**No GPU?** Set `DEVICE=cpu` in your `.env` file. Scoring will be slower (~10× slower per batch) but everything works.

---

## Setup (first time)

### Step 1 — Install NVIDIA Container Toolkit (GPU passthrough)

Run these commands on the machine that has the GPU:

```bash
# Install the toolkit
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit

# Register NVIDIA as a Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify it works
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

You should see your GPU listed in the output.

### Step 2 — Mount your NAS photos

Your photos need to be accessible as a directory on the GPU machine.

**If your NAS is a Samba share (Windows-style):**
```bash
# Install cifs-utils
sudo apt-get install cifs-utils

# Mount the share (replace with your NAS IP, share name, and credentials)
sudo mkdir -p /mnt/nas/photos
sudo mount -t cifs //192.168.1.100/photos /mnt/nas/photos -o username=YOUR_USER,password=YOUR_PASS,uid=$(id -u),gid=$(id -g)

# To auto-mount on boot, add to /etc/fstab:
# //192.168.1.100/photos /mnt/nas/photos cifs username=user,password=pass,uid=1000,gid=1000 0 0
```

**On macOS:** Open Finder → Go → Connect to Server → `smb://192.168.1.100/photos`  
Photos will appear at `/Volumes/photos`

**On Windows:** Map the network drive (e.g. as `Z:\`), then enter `Z:\` in the app.

### Step 3 — Configure the app

```bash
cd photo-curator

# Copy the example config
cp .env.example .env

# Edit .env with your paths:
#   PHOTO_DIR=/mnt/nas/photos      ← where your photos are
#   EXPORT_DIR=/mnt/nas/exports    ← where print files will be saved
nano .env
```

### Step 4 — Build and run

```bash
# Build the Docker image (takes 10–20 minutes first time — downloads AI model)
docker compose build

# Start the app
docker compose up -d

# Check it's running
docker compose logs -f photo-curator
```

Open your browser at: **http://localhost:8000** (or replace `localhost` with your machine's IP address for access from other devices on your network).

---

## Using the App

The app walks you through 4 steps:

### Step 1 — Choose Folder
Select whether your photos are on a **local folder** or a **network folder (NAS)**. Enter the path, click **Test Access** to confirm it's reachable, then click **Start Scanning**.

### Step 2 — Scan & Score
The AI analyses every photo. A progress bar shows how many have been checked. For a library of 5,000 photos, expect 5–15 minutes on a GPU (or 30–60 minutes on CPU).

Scores explained:
- **✨ Beauty (50%)** — AI-assessed overall aesthetic appeal
- **🔍 Sharpness (25%)** — whether the photo is in focus
- **💡 Lighting (15%)** — exposure and brightness quality
- **😊 Faces (10%)** — bonus for portraits with people

### Step 3 — Pick Your Best
Photos appear best-first. For each one you can:
- **✓ Keep** (green) — this photo goes into your album
- **– Skip** — undecided, come back later
- **✗ Remove** — hide this photo

**Keyboard shortcuts** (click a photo first to open it):
| Key | Action |
|---|---|
| `K` | Keep (approve) |
| `S` | Skip |
| `R` | Remove |
| `→` | Next photo |
| `←` | Previous photo |
| `Esc` | Close |

### Step 4 — Build & Export Album
Create an album, add your kept photos, choose a print size for each, then click **Export for Printing**.

**Print sizes:**
| Size | Pixels | Use for |
|---|---|---|
| 4×6" | 1800×1200 | Standard prints, most affordable |
| 5×7" | 2100×1500 | Slightly larger, great for portraits |
| 8×10" | 3000×2400 | Statement prints, framing |
| A4 grid | 2480×3508 | 4 photos per page, photo book style |

Exported files are named like: `2024-07-04_beach_sunset_0001_4x6.jpg`  
→ Date, scene type (AI-detected), sequence number, print size.

Take the export folder to any print shop (Costco, Walmart, Boots, or local labs) or upload to Shutterfly, Snapfish, etc.

---

## Troubleshooting

**"GPU not found" / scoring is very slow**
- Make sure `nvidia-container-toolkit` is installed and Docker was restarted after setup
- Run `docker compose logs photo-curator | grep "CLIP model"` — should say "loaded successfully"
- Set `DEVICE=cpu` in `.env` as a fallback

**"Path not found" on Step 1**
- The path must be accessible **inside the Docker container**, not just on your machine
- Check `docker-compose.yml` → the `volumes:` section maps your host path into the container
- Update `PHOTO_DIR` in `.env` to match your host path

**HEIC photos (iPhone) not loading**
- HEIC support requires `libheif` in the container — it's included in the Dockerfile
- If you see errors, rebuild: `docker compose build --no-cache`

**Out of GPU memory**
- Reduce batch size: set `BATCH_SIZE=8` in `.env` and restart
- Or switch to `DEVICE=cpu`

**Rebuild after code changes**
```bash
docker compose down
docker compose build
docker compose up -d
```

---

## File Structure

```
photo-curator/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + GPU worker startup
│   │   ├── config.py            # Settings
│   │   ├── database.py          # SQLite schema (SQLAlchemy async)
│   │   ├── models/scorer.py     # CLIP aesthetic model + CPU metrics
│   │   ├── routers/             # API endpoints
│   │   └── services/            # Scan, scoring, export logic
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html               # 4-step wizard UI
│   ├── app.js                   # All UI logic (vanilla JS)
│   └── styles.css               # Custom CSS
├── docker-compose.yml
├── .env.example                 # Copy to .env and fill in your paths
└── README.md                    # This file
```

---

## Privacy

All processing happens **on your own machine**. Your photos are never uploaded anywhere. The AI model (CLIP) runs entirely locally on your GPU.
