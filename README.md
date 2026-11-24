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
git clone https://github.com/blinky-404/blinkys-auto-dvd-ripper.git
cd blinkys-auto-dvd-ripper
chmod +x install.sh && ./install.sh
```

Once installed, open **`http://<YOUR-SERVER-IP>:8090`** in your browser.

## Multi-Platform Server Setup (TrueNAS SCALE, Unraid, OMV, Proxmox)

> **⚠️ Untested Platforms Notice:** This stack is actively tested and verified on **CasaOS / Debian 12+**. The setup instructions below for **TrueNAS SCALE**, **Unraid**, **OpenMediaVault**, and **Proxmox / Portainer** are provided as community starting guides and **have not yet been tested end-to-end on those platforms**. Back up existing media and test on a staging dataset first!

By default, all media and system folders live under `/DATA` (`DATA_DIR=/DATA` in `.env`). On platforms that mount storage pools elsewhere, set `DATA_DIR` in your `.env` file before starting the stack.

### 1. TrueNAS SCALE 24.10+ (Electric Eel / Fangtooth) — *Untested*
* **Requirements:** TrueNAS SCALE 24.10+ (uses native Docker Compose). *(TrueNAS CORE / FreeBSD is not supported.)*
* **Steps:**
  1. Create a dataset for the ripper (e.g., `/mnt/tank/ripper`) and clone the repo there so it survives OS upgrades.
  2. Copy `.env.example` to `.env` and set `DATA_DIR=/mnt/tank/ripper`.
  3. Ensure the SCSI generic kernel module is loaded (`sudo modprobe sg`) and add `modprobe sg` under **System -> Advanced -> Init/Shutdown Scripts** so MakeMKV detects `/dev/sr*` and `/dev/sg*`.
  4. Bring up the stack with `docker compose up -d --build`.
  5. *(Optional)* TrueNAS resets root crontabs on OS updates—add `/mnt/tank/ripper/scripts/organize-rips.sh` under **System -> Advanced -> Cron Jobs** in the TrueNAS UI (or trigger **Run Organizer Now** from the Web UI).

### 2. Unraid — *Untested*
* **Requirements:** Unraid 6.12+ with the **Compose Manager** plugin from Community Applications.
* **Steps:**
  1. Create a share (e.g., `/mnt/user/ripper`) and place the repository files there.
  2. Set `DATA_DIR=/mnt/user/ripper` in `.env`.
  3. Add `modprobe sg` to `/boot/config/go` (and run `modprobe sg` via SSH) so optical drives expose `/dev/sg*` to MakeMKV.
  4. Import `docker-compose.yml` in **Compose Manager** and click **Compose Up**.

### 3. OpenMediaVault (OMV 7+) — *Untested*
* **Steps:**
  1. Install the **openmediavault-compose** plugin via OMV-Extras.
  2. Set `DATA_DIR=/srv/dev-disk-by-uuid-<YOUR-UUID>/ripper` in `.env`.
  3. Run `chmod +x install.sh && ./install.sh` (or deploy via the OMV Compose UI) and ensure `sg` is loaded (`modprobe sg`).

### 4. Proxmox VE (LXC / VM) & Portainer — *Untested*
* **Proxmox VM (Recommended):** Create a Debian 12 / Ubuntu 24.04 VM, pass through your USB controller or SATA optical drives (`qm set <VMID> -usb0 host=...`), and run `./install.sh` normally.
* **Proxmox LXC:** Requires a privileged container with `/dev/sr*` and `/dev/sg*` bind-mounted in `/etc/pve/lxc/<CTID>.conf`.
* **Portainer:** Add this repository as a **Stack** (`docker-compose.yml`), define `DATA_DIR` in Portainer's environment variables, and deploy.
