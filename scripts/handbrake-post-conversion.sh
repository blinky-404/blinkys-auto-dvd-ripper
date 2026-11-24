#!/bin/sh
# jlesage/handbrake post_conversion.sh hook
# Pauses HandBrake between encodes while ripper-ui renames, verifies, and organizes the finished MP4.
CONVERSION_STATUS="$1"
OUTPUT_FILE="$2"
SOURCE_FILE="$3"

if [ "$CONVERSION_STATUS" = "0" ] && [ -n "$OUTPUT_FILE" ]; then
  echo "[post_conversion] Encode complete: $OUTPUT_FILE — running organizer before next encode..."
  if command -v curl >/dev/null 2>&1; then
    curl -s -X POST http://ripper-ui:8090/api/run-organizer >/dev/null 2>&1 || true
  else
    wget -qO- --post-data="" http://ripper-ui:8090/api/run-organizer >/dev/null 2>&1 || true
  fi
  # Wait until ripper-ui finishes organizing (and any AI Vision scan) before HandBrake starts the next file
  sleep 3
  while wget -qO- http://ripper-ui:8090/api/status 2>/dev/null | grep -q '"busy": true'; do
    sleep 2
  done
  echo "[post_conversion] Organizer finished — resuming HandBrake queue."
fi
