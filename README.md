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


## Screenshots

### Web Control Center Dashboard
<img width="1910" height="678" alt="Screenshot 2026-11-23 165249" src="https://github.com/user-attachments/assets/f426cb43-9f70-49ca-bdfe-a5e332784030" />
### Universal Media Test Player & Logs
<img width="1883" height="701" alt="Screenshot 2026-11-23 165343" src="https://github.com/user-attachments/assets/01b02c7d-32fc-4e33-9737-d5a4b7df1f01" />
<img width="1918" height="726" alt="Screenshot 2026-11-23 165326" src="https://github.com/user-attachments/assets/f2481901-7a6a-4377-93fc-080e07b4a113" />


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

## Hardware & Prerequisites

* **Optical Drives:** Any USB or SATA DVD/Blu-ray drive supported by Linux (`/dev/sr*` + `/dev/sg*`). For 4K UHD Blu-rays, a **LibreDrive-compatible** drive is required.
* **Powered USB Hub (Recommended for Multi-Drive):** Dual external USB optical drives draw high spin-up current. Use a **powered USB 3.0 hub**—the Web Control Center monitors `dmesg` for USB voltage/reset brownouts and alerts you automatically.
* **MakeMKV Key:** MakeMKV includes a free beta key (updated periodically on the MakeMKV forums) or accepts a lifetime license key in the Web UI under **Setup & Toggles** (`MAKEMKV_KEY`).
* **CPU & RAM for Local AI Vision (`moondream`):** Optional. Runs on CPU on demand (`~1.8 GB` RAM only during the ~15–25s identification step, then drops back to **`0 MB` idle RAM**).

## Troubleshooting FAQ

* **My optical drive isn't showing up in MakeMKV or the Dashboard:**
  Ensure the SCSI generic kernel module is loaded (`sudo modprobe sg`) and check `ls -l /dev/sr* /dev/sg*`.
* **DVD fails immediately with `COPY PROTECTION KEY EXCHANGE FAILURE`:**
  New or replacement DVD drives often ship with Region `0` (unset) or a non-matching region. Install `regionset` (`sudo apt install regionset`) and set your drive region (e.g., `sudo regionset /dev/sr0` -> `1` for North America).
* **Where do I enter my MakeMKV registration key or TMDB API key?**
  Open the Web Control Center (`http://<SERVER-IP>:8090`), click **Setup & Toggles**, paste your keys, and click **Save Settings**.
* **Why did my video go to `short_videos/`, `low_quality_quarantine/`, or `no_audio/`?**
  * `short_videos/`: Valid videos shorter than `MIN_RUNTIME_MINS` (default `45m`, such as behind-the-scenes featurettes; trailers under `10m` are skipped at rip time).
  * `low_quality_quarantine/`: Videos below your minimum resolution/bitrate threshold.
  * `no_audio/`: Broken rips containing `0` audio streams.

## Uninstall / Clean Reset

To cleanly stop all containers, remove the scheduled organizer cron job, and wipe `/DATA/ripper_system` (while preserving your ripped videos in `/DATA/ripper_media`):

```bash
chmod +x install.sh && ./install.sh --uninstall
```
