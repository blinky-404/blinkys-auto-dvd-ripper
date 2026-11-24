#!/bin/sh
# jlesage/handbrake post_conversion.sh hook
# Prefixes descriptive parent disc folder name onto finished MP4 and pauses HandBrake
# while ripper-ui organizes the file and cleans up raw/<DISC_FOLDER>.
CONVERSION_STATUS="$1"
OUTPUT_FILE="$2"
SOURCE_FILE="$3"

if [ "$CONVERSION_STATUS" = "0" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  RAW_PARENT=$(basename "$(dirname "$SOURCE_FILE")")
  PARENT_DIR=$(echo "$RAW_PARENT" | tr -cd '[:alnum:] ._-' | sed 's/^ *//;s/ *$//')
  LOWER_DIR=$(echo "$PARENT_DIR" | tr '[:upper:]' '[:lower:]' | tr -d ' _-')
  case "$LOWER_DIR" in
    ""|watch|dvd|dvdvideo|videots|bdmv|disc|disc1|disc2|disk|untitled|unknown|unidentified|volume|movie|video|main)
      ;;
    *)
      OUT_DIR=$(dirname "$OUTPUT_FILE")
      OUT_BASE=$(basename "$OUTPUT_FILE")
      case "$OUT_BASE" in
        "$PARENT_DIR"*) ;;
        *)
          NEW_OUT="$OUT_DIR/${PARENT_DIR} - ${OUT_BASE}"
          mv -f "$OUTPUT_FILE" "$NEW_OUT" && OUTPUT_FILE="$NEW_OUT"
          echo "[post_conversion] Renamed with disc folder: $OUTPUT_FILE"
          ;;
      esac
      ;;
  esac

  HOST_IP=$(ip route 2>/dev/null | awk '/default/ {print $3}')
  [ -z "$HOST_IP" ] && HOST_IP="172.17.0.1"
  UI_URL="http://${HOST_IP}:${UI_PORT:-8090}"

  echo "[post_conversion] Encode complete: $OUTPUT_FILE — triggering organizer at $UI_URL..."
  wget -qO- --post-data="" "$UI_URL/api/run-organizer" >/dev/null 2>&1 || true
  sleep 3
  TRIES=0
  while wget -qO- "$UI_URL/api/status" 2>/dev/null | grep -q '"busy": true' && [ "$TRIES" -lt 300 ]; do
    TRIES=$((TRIES + 1))
    sleep 2
  done
  echo "[post_conversion] Organizer step complete (polls=$TRIES) — resuming HandBrake queue."
fi
