#!/bin/bash
set -e
echo "=== Blinky's Auto DVD Ripper v2.0 Installer ==="
DEFAULT_BASE=$([ -d "/DATA" ] && echo "/DATA" || echo "/opt/blinky-ripper")
read -p "Install base directory [$DEFAULT_BASE]: " BASE_DIR
BASE_DIR="${BASE_DIR:-$DEFAULT_BASE}"
read -p "Control Center Web UI Port: " UI_PORT
UI_PORT="${UI_PORT:-8090}"
read -p "MakeMKV Port: " MAKEMKV_PORT
MAKEMKV_PORT="${MAKEMKV_PORT:-5800}"
read -p "HandBrake Port: " HANDBRAKE_PORT
HANDBRAKE_PORT="${HANDBRAKE_PORT:-5801}"
read -p "File Manager Port: " FILEBROWSER_PORT
FILEBROWSER_PORT="${FILEBROWSER_PORT:-8091}"

sudo mkdir -p "$BASE_DIR/ripper_system/"{config,logs,makemkv,handbrake,filebrowser,ollama}
sudo mkdir -p "$BASE_DIR/ripper_media/"{raw,finished,organized_movies,low_quality_quarantine,raw_audio_backups,no_audio}
sudo chmod -R 777 "$BASE_DIR/ripper_system" "$BASE_DIR/ripper_media"
[ -f "$BASE_DIR/ripper_system/config/organizer.conf" ] || cp config/organizer.conf.example "$BASE_DIR/ripper_system/config/organizer.conf"

cat << ENV > .env
SYSTEM_DIR=$BASE_DIR/ripper_system
MEDIA_DIR=$BASE_DIR/ripper_media
UI_PORT=$UI_PORT
MAKEMKV_PORT=$MAKEMKV_PORT
HANDBRAKE_PORT=$HANDBRAKE_PORT
FILEBROWSER_PORT=$FILEBROWSER_PORT
PUID=$(id -u)
PGID=$(id -g)
ENV

sudo cp scripts/udev-disc-trigger.sh /usr/local/bin/blinky-udev-trigger.sh && sudo chmod +x /usr/local/bin/blinky-udev-trigger.sh
echo 'SUBSYSTEM=="block", KERNEL=="sr[0-9]*", ACTION=="add", RUN+="/usr/bin/systemd-run --no-block /usr/local/bin/blinky-udev-trigger.sh /dev/%k"' | sudo tee /etc/udev/rules.d/99-blinky-dvd-ripper.rules >/dev/null
sudo udevadm control --reload-rules
sudo docker compose up -d --build
echo "Done! Open http://$(hostname -I | awk '{print $1}'):$UI_PORT"
