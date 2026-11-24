#!/bin/sh
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

  TRIGGER="/output/.trigger_organizer"
  touch "$TRIGGER"
  echo "[post_conversion] Encode complete: $OUTPUT_FILE — waiting for ripper-ui organizer..."
  TRIES=0
  while [ -f "$TRIGGER" ] && [ "$TRIES" -lt 300 ]; do
    TRIES=$((TRIES + 1))
    sleep 2
  done
  echo "[post_conversion] Organizer finished (polls=$TRIES) — resuming HandBrake queue."
fi
