# CasaOS Automated Dual-Drive DVD Ripper

> **Note:** This project's architecture, Docker Compose configuration, HandBrake hook scripts, and `systemd`/`udev` hot-swap automation were created with AI assistance.

A turnkey, hot-swappable DVD ripping and encoding pipeline for **CasaOS**, **Debian**, and **Ubuntu** servers using **MakeMKV** and **HandBrake**.

## Features
* **Plug-and-Play Multi-Drive Support:** Automatically detects 1 or 2+ USB optical drives on boot (`systemd`) and when hot-swapped (`udev`), queueing discs sequentially and auto-ejecting each tray when finished.
* **Unlabelled Audio Protection:** Pre-configures MakeMKV to capture both preferred-language and unlabelled (`nolang`) audio tracks so studio discs with missing language metadata are never skipped.
* **Silent-Track Gatekeeper (`pre_conversion.sh`):** Scans `.mkv` rips with `ffprobe` before encoding and quarantines silent bonus titles to `no_audio/`.
* **Automatic Disc-Based Naming (`post_conversion.sh`):** Names finished `.mp4` files after the DVD's disc label and adds timestamp protection for multi-version discs.
* **Temp-File Filtering:** Prevents HandBrake from touching `.mkv.tmp` files while MakeMKV is still ripping.

## Hardware Recommendations
* **Wall-Powered USB Hub:** Recommended when running 1–2 external USB optical drives to prevent voltage drops during high-speed disc spin-up.
* **Scratch Storage:** Uses a local SSD directory (`/DATA/ripper` by default) for fast ripping and encoding before transferring finished `.mp4` files to your NAS.

## Quick One-Line Install

### Default Install (`/DATA/ripper`)
Plug in your USB DVD drive(s) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/blinky-404/casaos-auto-dvd-ripper/main/install.sh | bash
```

### Custom Storage Drive / Folder Path
To install onto a different drive or mount point (such as a secondary SSD at `/mnt/ssd/ripper`), pass `RIPPER_DIR` before `bash`:

```bash
curl -fsSL https://raw.githubusercontent.com/blinky-404/casaos-auto-dvd-ripper/main/install.sh | RIPPER_DIR="/mnt/ssd/ripper" bash
```

### Changing the Storage Path After Installation
If you already installed and want to move your ripper folder to a different drive later:
1. Stop the containers: `cd /DATA/ripper && sudo docker compose down`
2. Move the folder to your new drive: `sudo mv /DATA/ripper /mnt/newdrive/ripper`
3. Re-run the installer pointing to the new path: `curl -fsSL https://raw.githubusercontent.com/blinky-404/casaos-auto-dvd-ripper/main/install.sh | RIPPER_DIR="/mnt/newdrive/ripper" bash`

## Web Interfaces & Directories
* **MakeMKV Web UI:** `http://<SERVER-IP>:5800`
* **HandBrake Web UI:** `http://<SERVER-IP>:5801`
* **Raw Rips:** `<RIPPER_DIR>/raw`
* **Finished Encodes:** `<RIPPER_DIR>/finished`
* **Quarantined Silent Files:** `<RIPPER_DIR>/no_audio`

## Upstream Projects & Credits
This automation wrapper relies on the excellent work of the following upstream developers and projects:
* **jlesage/docker-makemkv** & **jlesage/docker-handbrake** by **Jocelyn Le Sage (`jlesage`)** — for maintaining the containerized web-UI builds, auto-ripper daemon, and conversion hook framework that power this pipeline.
* **MakeMKV** (`makemkv.com`) — for disc decryption and MKV extraction.
* **HandBrake** (`handbrake.fr`) — for open-source video transcoding.

## Attribution
Designed, debugged, and packaged with AI assistance.
