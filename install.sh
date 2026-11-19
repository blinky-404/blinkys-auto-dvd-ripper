#!/bin/bash
# CasaOS Automated Dual-Drive DVD Ripper
# Upstream Containers: Built on jlesage/docker-makemkv and jlesage/docker-handbrake by Jocelyn Le Sage (https://github.com/jlesage).
# Upstream Containers: Built on jlesage/docker-makemkv and jlesage/docker-handbrake by Jocelyn Le Sage (https://github.com/jlesage).
# Attribution: Architecture, Docker Compose setup, HandBrake hooks, and udev/systemd rules were created with AI assistance.
set -e

echo "=== 1. Creating Ripper Directories ==="
sudo mkdir -p /DATA/ripper/{raw,finished,no_audio,makemkv/config,handbrake/config/hooks}
sudo chown -R 1000:1000 /DATA/ripper

echo "=== 2. Pre-configuring MakeMKV Unlabelled-Audio Rule ==="
sudo tee /DATA/ripper/makemkv/config/settings.conf > /dev/null << 'EOF'
app_DefaultSelectionString = "-sel:all,+sel:(favlang|nolang|single),-sel:mvcvideo,=100:all,-10:favlang"
app_ExpertMode = "true"
EOF
sudo chown 1000:1000 /DATA/ripper/makemkv/config/settings.conf

echo "=== 3. Installing HandBrake Audio Check & Auto-Naming Hooks ==="
sudo tee /DATA/ripper/handbrake/config/hooks/pre_conversion.sh > /dev/null << 'EOF'
#!/bin/sh
SOURCE_FILE="$1"
if [ -f "$SOURCE_FILE" ]; then
    AUDIO_COUNT=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$SOURCE_FILE" | wc -l)
    if [ "$AUDIO_COUNT" -eq 0 ]; then
        FOLDER_NAME=$(basename "$(dirname "$SOURCE_FILE")")
        CLEAN_NAME=$(echo "$FOLDER_NAME" | sed 's/__*/ /g; s/_/ /g' | xargs)
        [ -z "$CLEAN_NAME" ] || [ "$CLEAN_NAME" = "watch" ] && CLEAN_NAME=$(basename "${SOURCE_FILE%.*}")
        mv "$SOURCE_FILE" "/no_audio/${CLEAN_NAME}_NO_AUDIO.mkv"
        rmdir "$(dirname "$SOURCE_FILE")" 2>/dev/null || true
    fi
fi
EOF
sudo chmod +x /DATA/ripper/handbrake/config/hooks/pre_conversion.sh

sudo tee /DATA/ripper/handbrake/config/hooks/post_conversion.sh > /dev/null << 'EOF'
#!/bin/sh
STATUS="$1"
OUTPUT_FILE="$2"
SOURCE_FILE="$3"
if [ "$STATUS" -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
    FOLDER_NAME=$(basename "$(dirname "$SOURCE_FILE")")
    if [ "$FOLDER_NAME" != "watch" ] && [ -n "$FOLDER_NAME" ]; then
        CLEAN_NAME=$(echo "$FOLDER_NAME" | sed 's/__*/ /g; s/_/ /g' | xargs)
        NEW_PATH="/output/${CLEAN_NAME}.mp4"
        [ -e "$NEW_PATH" ] && NEW_PATH="/output/${CLEAN_NAME}_$(date +%s).mp4"
        mv "$OUTPUT_FILE" "$NEW_PATH"
        rmdir "$(dirname "$OUTPUT_FILE")" 2>/dev/null || true
    fi
fi
EOF
sudo chmod +x /DATA/ripper/handbrake/config/hooks/post_conversion.sh

echo "=== 4. Writing Docker Compose Configuration ==="
cat << 'EOF' > /tmp/dc.yml
services:
  makemkv:
    image: jlesage/makemkv
    container_name: makemkv
    ports:
      - "5800:5800"
    environment:
      - USER_ID=1000
      - GROUP_ID=1000
      - TZ=America/Los_Angeles
      - AUTO_DISC_RIPPER=1
      - AUTO_DISC_RIPPER_EJECT=1
      - AUTO_DISC_RIPPER_MIN_TITLE_LENGTH=1800
      - AUTO_DISC_RIPPER_FORCE_UNIQUE_OUTPUT_DIR=1
      - AUTO_DISC_RIPPER_MAKEMKV_PROFILE=default
    volumes:
      - "/DATA/ripper/makemkv/config:/config:rw"
      - "/DATA/ripper/raw:/output:rw"
    devices:
EOF
for d in /dev/sr* /dev/sg*; do [ -e "$d" ] && echo "      - \"$d:$d\"" >> /tmp/dc.yml; done
cat << 'EOF' >> /tmp/dc.yml
    restart: unless-stopped

  handbrake:
    image: jlesage/handbrake
    container_name: handbrake
    ports:
      - "5801:5800"
    environment:
      - USER_ID=1000
      - GROUP_ID=1000
      - TZ=America/Los_Angeles
      - AUTOMATED_CONVERSION_PRESET=General/HQ 480p30 Surround
      - AUTOMATED_CONVERSION_FORMAT=mp4
      - AUTOMATED_CONVERSION_KEEP_SOURCE=0
      - AUTOMATED_CONVERSION_WATCH_DIR_FILTER=*.mkv
    volumes:
      - "/DATA/ripper/handbrake/config:/config:rw"
      - "/DATA/ripper/raw:/watch:rw"
      - "/DATA/ripper/finished:/output:rw"
      - "/DATA/ripper/no_audio:/no_audio:rw"
    restart: unless-stopped
EOF
sudo mv /tmp/dc.yml /DATA/ripper/docker-compose.yml

echo "=== 5. Installing Plug-and-Play Drive Sync Service & Hot-Swap Rule ==="
sudo tee /usr/local/bin/sync-ripper-drives.sh > /dev/null << 'EOF'
#!/bin/bash
sleep 5
DEVS=$(for d in /dev/sr* /dev/sg*; do [ -e "$d" ] && echo "      - \"$d:$d\""; done)
if [ -n "$DEVS" ]; then
  awk -v devs="$DEVS" '/devices:/{print; print devs; skip=1; next} skip && /restart:/{skip=0; print; next} !skip{print}' /DATA/ripper/docker-compose.yml > /tmp/dc.yml && mv /tmp/dc.yml /DATA/ripper/docker-compose.yml
  cd /DATA/ripper && docker compose up -d
fi
EOF
sudo chmod +x /usr/local/bin/sync-ripper-drives.sh

sudo tee /etc/systemd/system/sync-ripper-drives.service > /dev/null << 'EOF'
[Unit]
Description=Auto-detect DVD drives for MakeMKV on boot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/sync-ripper-drives.sh

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/udev/rules.d/99-ripper-drives.rules > /dev/null << 'EOF'
SUBSYSTEM=="block", KERNEL=="sr*", ACTION=="add|remove", RUN+="/bin/systemctl start --no-block sync-ripper-drives.service"
EOF

sudo systemctl daemon-reload
sudo systemctl enable sync-ripper-drives.service
sudo udevadm control --reload-rules

echo "=== 6. Starting MakeMKV & HandBrake ==="
cd /DATA/ripper && sudo docker compose up -d
echo "=== Done! MakeMKV is at :5800 and HandBrake is at :5801 ==="
