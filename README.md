# Blinky's Auto DVD Ripper (v2.0)

A hands-free, self-hosted **DVD & Blu-ray auto-ripping, encoding, quality-auditing, and AI-assisted media organization appliance** with a unified **Web Control Center**. Works on **Ubuntu/Debian**, **CasaOS**, **ZimaOS**, or any Docker host.

## Key Features
* **Unified Web Control Center (`:8090`):** Live **CPU Load & Storage Capacity RPM Tachometer Gauges**, optical drive hardware detection, USB brownout alerts, container controls, and embedded **MakeMKV (`:5800`)**, **HandBrake (`:5801`)**, and **File Manager (`:8091`)** views.
* **Universal Media Test Player:** Stream both `.mkv` and `.mp4` rips directly inside your browser (with automatic live audio/video transcoding for `.mkv` files) before moving them to Jellyfin/Plex.
* **Audio Safety & Quality Quarantine:**
  * Quarantines 0-audio files to `no_audio/` so silent rips never break encodes.
  * Auto-converts **DTS / PCM** tracks to universal **AAC** while saving untouched `.mkv` audio backups.
  * Routes low-resolution or low-bitrate rips to `low_quality_quarantine/`.
* **Multi-Database + On-Demand AI Vision Identification:**
  * Supports **TMDB** (Movies/TV), **TVmaze** (TV Series — no API key required), and **MusicBrainz** (Concerts — no API key required).
  * Optional **On-Demand Local Ollama (`moondream`)** or **Google Gemini** fallback that captures a `2x2` frame grid on unmatched discs (using **0 MB idle RAM** when not actively identifying a disc).
* **2x2 Logs & `.TXT` Report Exporter:** View MakeMKV sector alerts, audio audits, HandBrake encodes, and organizer logs side by side or export custom `.TXT` diagnostic reports.

## Quick Start (One-Command Install)
```bash
git clone https://github.com
cd blinkys-auto-dvd-ripper
chmod +x install.sh && ./install.sh
```

Once installed, open **`http://<YOUR-SERVER-IP>:8090`** in your browser.
