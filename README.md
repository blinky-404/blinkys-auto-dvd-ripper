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

## Automated Daily TMDB Organizer & Quality Auditor (`organize-rips.sh`)

After HandBrake finishes encoding `.mp4` files into `/DATA/ripper/finished`, `scripts/organize-rips.sh` automatically verifies, renames, and organizes them into standard `Movie Title (Year)` folders—either on a **3:00 AM daily cron schedule** or on-demand via a **one-click CasaOS dashboard button** (`rip-organizer-btn`).

### Features
- **Simple Config File (`/DATA/ripper/organizer.conf`):** Store your free TMDB Read Access Token, destination root path, and minimum runtime threshold once (template provided in `organizer.conf.example`).
- **Audio & Runtime Gatekeeper:** Uses `ffprobe` to quarantine silent tracks or clips shorter than `MIN_RUNTIME_MINS` (default: `45` minutes) into `/DATA/ripper/no_audio`.
- **DVD-Calibrated Quality Tiering:** Routes clean rips (`300p+` height and `400+ kbps` bitrate) into `movies full quality/` and flags ultra-low-resolution or heavily pixelated rips into `movies low quality/`.
- **TMDB Matching & Notepad Reports:** Renames matched titles to `Movie Title (Year)/Movie Title (Year).mp4`, writes an individual `Movie Title (Year)_info.txt` file inside each movie folder, and refreshes a master `ripper_daily_report.txt` summary on every run.

### One-Click CasaOS Dashboard Trigger
Create a lightweight on-demand button tile on your CasaOS home screen:
```bash
sudo docker run -d --name rip-organizer-btn --restart no \
  -v /DATA/ripper:/DATA/ripper \
  -v /usr/local/bin/organize-rips.sh:/organize-rips.sh:ro \
  alpine sh -c "apk add --no-cache bash curl jq ffmpeg python3 && bash /organize-rips.sh"
```
Click **three dots (`...`) > Start** (or **Restart**) on `rip-organizer-btn` anytime to run the organizer immediately.

### Setting Up Your Free TMDB API Token & Organizer
1. Create a free account at [themoviedb.org](https://themoviedb.org) and go to **Settings > API** to generate an **API Read Access Token** (starts with `eyJ...`) or **API Key**.
2. Copy the example config file into your ripper directory and install the organizer script:
   ```bash
   sudo cp organizer.conf.example /DATA/ripper/organizer.conf
   sudo cp scripts/organize-rips.sh /usr/local/bin/organize-rips.sh
   sudo chmod +x /usr/local/bin/organize-rips.sh
   ```
3. Open `/DATA/ripper/organizer.conf` and paste your TMDB token inside `TMDB_TOKEN="..."`.
4. *(Optional)* Schedule the organizer to run automatically every night at 3:00 AM via `sudo crontab -e`:
   ```cron
   0 3 * * * /usr/local/bin/organize-rips.sh
   ```

## Beginner's Quick Reference & Troubleshooting

New to Linux or CasaOS? You do not need to memorize commands—use this quick guide to see where your files go and how to check if everything is healthy.

### Where Do My Movies Go? (Folder Map)
Every folder lives inside **`DATA > ripper`** in your CasaOS **Files** app:
- **`raw/`** — Temporary landing zone while MakeMKV reads your DVD.
- **`watch/`** — Holding area where movies wait in line for HandBrake to compress them.
- **`finished/`** — Completed `.mp4` movies ready to be renamed and sorted.
- **`organized_movies/`** — Your final, cleanly named `Movie Title (Year)` folders and Notepad `_info.txt` reports.
- **`no_audio/`** — Quarantined bonus clips, silent tracks, or incomplete rips under 45 minutes.

### One-Command Health Check
If a disc isn't ripping or you want to verify your setup, open the **CasaOS Terminal** (`>_` icon in the top-left of CasaOS) and paste this single line:
```bash
echo "=== Containers ===" && sudo docker ps --format "table {{.Names}}\t{{.Status}}" && echo "=== DVD Drives ===" && ls -l /dev/sr* 2>/dev/null || echo "No DVD drives detected" && echo "=== Recent Rip Report ===" && cat /DATA/ripper/organized_movies/ripper_daily_report.txt 2>/dev/null || echo "No report generated yet"
```

### Need Help? Copy-Paste This Into Any AI Assistant
If something gets stuck, run the **Health Check** command above, copy the output, and paste it into an AI assistant with this prompt:
> *"I am using the `blinky-404/casaos-auto-dvd-ripper` setup on CasaOS. Here is my health check output—can you tell me what is wrong and give me the exact command to fix it?"*

### Raw Audio Audit Log & One-Click Ripper Restart
- **Raw Audio Notepad Log (`/DATA/ripper/no_audio/raw_audio_audit.txt`):** Before HandBrake encodes any `.mkv`, `scripts/pre_conversion.sh` records all detected audio tracks (`index`, `codec`, `channels`, `language`) and automatically converts DTS/PCM streams to AAC so HandBrake never outputs a silent `.mp4`.
- **One-Click Restart Button (`ripper-restart-btn`):** If a scratched disc ever causes MakeMKV or HandBrake to hang at 100%, create an on-demand restart tile on your CasaOS dashboard:
  ```bash
  sudo docker run -d --name ripper-restart-btn --restart no -v /var/run/docker.sock:/var/run/docker.sock alpine sh -c "apk add --no-cache docker-cli && docker restart makemkv handbrake"
  ```
