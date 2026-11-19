# CasaOS Automated Dual-Drive DVD Ripper

> **Note:** This project's architecture, Docker Compose configuration, HandBrake hook scripts, and `systemd`/`udev` hot-swap automation were created with AI assistance.

A turnkey, hot-swappable DVD ripping and encoding pipeline for **CasaOS**, **Debian**, and **Ubuntu** servers using **MakeMKV** and **HandBrake**.

## Features
* **Plug-and-Play Multi-Drive Support:** Automatically detects 1 or 2+ USB optical drives on boot (`systemd`) and when hot-swapped (`udev`), queueing discs sequentially and auto-ejecting each tray when finished.
* **Unlabelled Audio Protection:** Pre-configures MakeMKV to capture both preferred-language and unlabelled (`nolang`) audio tracks so studio discs with missing language metadata are never skipped.
* **Silent-Track Gatekeeper (`pre_conversion.sh`):** Scans `.mkv` rips with `ffprobe` before encoding and quarantines silent bonus titles to `/DATA/ripper/no_audio`.
* **Automatic Disc-Based Naming (`post_conversion.sh`):** Names finished `.mp4` files after the DVD's disc label and adds timestamp protection for multi-version discs.
* **Temp-File Filtering:** Prevents HandBrake from touching `.mkv.tmp` files while MakeMKV is still ripping.

## Hardware Recommendations
* **Wall-Powered USB Hub:** Recommended when running 1–2 external USB optical drives to prevent voltage drops during high-speed disc spin-up.
* **Scratch Storage:** Uses `/DATA/ripper` on your local SSD for fast ripping and encoding before transferring finished `.mp4` files to your NAS.

## Quick One-Line Install
Plug in your USB DVD drive(s) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/blinky-404/casaos-auto-dvd-ripper/main/install.sh | bash
```

## Web Interfaces & Directories
* **MakeMKV Web UI:** `http://<SERVER-IP>:5800`
* **HandBrake Web UI:** `http://<SERVER-IP>:5801`
* **Raw Rips:** `/DATA/ripper/raw`
* **Finished Encodes:** `/DATA/ripper/finished`
* **Quarantined Silent Files:** `/DATA/ripper/no_audio`

## Attribution
Designed, debugged, and packaged with AI assistance.
