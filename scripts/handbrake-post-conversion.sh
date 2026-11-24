#!/bin/sh
CONVERSION_STATUS="$1"
OUTPUT_FILE="$2"
SOURCE_FILE="$3"

if [ "$CONVERSION_STATUS" = "0" ] && [ -n "$OUTPUT_FILE" ] && [ -f "$OUTPUT_FILE" ]; then
  PARENT_DIR=$(basename "$(dirname "$SOURCE_FILE")")
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

  echo "[post_conversion] Encode complete: $OUTPUT_FILE — running organizer before next encode..."
  wget -qO- --post-data="" http://ripper-ui:8090/api/run-organizer >/dev/null 2>&1 || true
  sleep 3
  while wget -qO- http://ripper-ui:8090/api/status 2>/dev/null | grep -q '"busy": true'; do
    sleep 2
  done
  echo "[post_conversion] Organizer finished — resuming HandBrake queue."
fi
