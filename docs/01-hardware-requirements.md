# Hardware Requirements & Cost Estimates

## Minimum Hardware

| Component | What to Buy | Why | Approx Cost |
|-----------|-------------|-----|-------------|
| **Raspberry Pi 4 Model B** | 4GB RAM version | More RAM = smoother under load. 2GB works but 4GB is better. | $55 – $75 |
| **Power Supply** | Official Raspberry Pi 15W USB-C (5V/3A) | The Pi 4 draws up to 3A peak. Underpowered supplies cause random crashes and data corruption. **Do not skip this.** | $8 – $12 |
| **MicroSD Card** | 32GB, Class 10 / A1 or better | This is the Pi's "hard drive" for the OS. The SSD holds your data. SanDisk and Samsung are reliable brands. | $8 – $15 |
| **USB SSD or HDD** | Any USB 3.0 SSD (1TB+ recommended) | SSD is faster and more durable than HDD. A USB 3.0 drive plugged into the Pi's USB 3.0 port gives best performance. | $70 – $120 |
| **USB cable** | Usually included with the SSD | USB-A to USB-A, or USB-A to USB-C depending on your drive | $0 – $10 |

**Total: approximately $141 – $232 USD**

---

## Recommended Parts (Example Setup)

- **Pi:** Raspberry Pi 4 Model B 4GB
- **SSD:** Any 1TB portable USB SSD (USB 3.0/3.2, bus-powered) — compact and needs no separate power brick
- **Power:** Official Raspberry Pi 27W USB-C power supply
- **SD Card:** Any 32GB MicroSD (Class 10, A1) — SanDisk and Samsung are reliable choices

---

## Optional / Nice to Have

| Component | Use | Cost |
|-----------|-----|------|
| USB 3.0 hub (powered) | Connect multiple SSDs | $15 – $30 |
| Raspberry Pi case with fan | Keeps Pi cool, prevents throttling | $10 – $25 |
| Ethernet cable (Cat 5e or better) | Wired is faster and more stable than Wi-Fi for a NAS | $5 – $15 |
| UPS (Uninterruptible Power Supply) | Prevents filesystem corruption during power cuts | $30 – $80 |

---

## What You Do NOT Need

- Monitor or keyboard — the Pi runs headless (SSH only)
- A router with special settings — Tailscale works through any NAT
- A static IP from your ISP — Tailscale handles dynamic IPs
- Any paid software or subscriptions

---

## Power Consumption Details

The Raspberry Pi 4 is very efficient. Here is what to expect:

| State | Pi 4 alone | Pi 4 + 1TB USB SSD |
|-------|-----------|---------------------|
| Idle | ~2.7 W | ~5 – 6 W |
| Light file transfer | ~4 W | ~7 – 8 W |
| Heavy file transfer | ~6 W | ~9 – 10 W |
| Peak (boot, USB enumeration) | ~6.4 W | ~10 – 12 W |

### Monthly Electricity Cost

Using idle average of 5.5 W running 24 hours a day, 30 days a month:

```
5.5 W × 24 h × 30 days = 3,960 Wh = 3.96 kWh per month
```

At **$0.12 per kWh** (US average):
```
3.96 kWh × $0.12 = ~$0.48 per month = ~$5.76 per year
```

At **£0.28 per kWh** (UK average):
```
3.96 kWh × £0.28 = ~£1.11 per month = ~£13.30 per year
```

### Comparison to Alternatives

| Device | Idle Power | Annual Cost (@ $0.12/kWh) |
|--------|-----------|--------------------------|
| **Raspberry Pi 4 NAS** | 5–6 W | **~$5–$6** |
| Synology DS223 (2-bay NAS) | ~12 W | ~$12–$13 |
| Synology DS923+ (4-bay NAS) | ~20 W | ~$21 |
| Old desktop PC as NAS | ~60–120 W | ~$63–$126 |

The Pi is the most energy-efficient option for a home NAS.

---

## Before You Buy — Checklist

- [ ] Do you have a computer to flash the SD card? (Windows, Linux, or macOS — any will work)
- [ ] Is your home router accessible? (You need to connect the Pi to your network)
- [ ] Do you have a Tailscale account? (Free at tailscale.com — sign up before starting)
- [ ] Do you know your Wi-Fi network name (SSID) and password?

If yes to all — you're ready. Continue to [OS Installation](02-os-setup.md).
