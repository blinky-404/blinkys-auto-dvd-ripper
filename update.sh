#!/bin/bash
# ==============================================================================
# Blinky's Auto DVD Ripper — Safe In-Place Updater
# Preserves existing .env, organizer.conf API keys, Ollama models, and media.
# ==============================================================================
set -e

echo "=== Updating Blinky's Auto DVD Ripper ==="
git pull origin main

# Load existing paths from .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

SYSTEM_DIR="${SYSTEM_DIR:-/DATA/ripper_system}"
MEDIA_DIR="${MEDIA_DIR:-/DATA/ripper_media}"

# Ensure new folders & hooks exist without overwriting organizer.conf
sudo mkdir -p "$MEDIA_DIR/ai_hold"
sudo mkdir -p "$SYSTEM_DIR/handbrake/hooks"
sudo cp -f scripts/handbrake-post-conversion.sh "$SYSTEM_DIR/handbrake/hooks/post_conversion.sh"
sudo chmod +x "$SYSTEM_DIR/handbrake/hooks/post_conversion.sh"

if [ -f scripts/udev-disc-trigger.sh ]; then
  sudo cp -f scripts/udev-disc-trigger.sh /usr/local/bin/blinky-udev-trigger.sh
  sudo chmod +x /usr/local/bin/blinky-udev-trigger.sh
fi

sudo docker compose up -d --build
echo "=== Update Complete! Your settings, API keys, and media were preserved. ==="
