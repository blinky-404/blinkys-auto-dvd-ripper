#!/bin/sh
INPUT_FILE="$1"
[ -f "$INPUT_FILE" ] || exit 0

LOG_FILE="/output/.pending_audio_audit.log"
CONF_FILE="/output/.organizer.conf"
[ -f "$CONF_FILE" ] && . "$CONF_FILE"
ENABLE_SILENT_QUARANTINE="${ENABLE_SILENT_QUARANTINE:-true}"
ENABLE_DTS_CONVERSION="${ENABLE_DTS_CONVERSION:-true}"

log_msg() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

BASENAME=$(basename "$INPUT_FILE")
FOLDER_TAG=$(basename "$(dirname "$INPUT_FILE")")
[ "$FOLDER_TAG" = "watch" ] && TAG_PREFIX="$BASENAME" || TAG_PREFIX="${FOLDER_TAG}_${BASENAME}"

TRACKS=$(ffprobe -v error -select_streams a -show_entries stream=index,codec_name,channels:stream_tags=language -of csv=p=0 "$INPUT_FILE" 2>/dev/null)
FLAT_TRACKS=$(echo "$TRACKS" | tr '\n' '|' | sed 's/|$//;s/|/ | /g')
log_msg "[MKV Pre-Check] ${TAG_PREFIX} -> Audio Streams: ${FLAT_TRACKS:-NONE}"

if [ -z "$TRACKS" ]; then
  if [ "$ENABLE_SILENT_QUARANTINE" = "true" ]; then
    mkdir -p /output/quarantine/no_audio
    mv "$INPUT_FILE" "/output/quarantine/no_audio/${TAG_PREFIX%.mkv}_NO_AUDIO.mkv"
    log_msg "   -> QUARANTINED to quarantine/no_audio/ (0 audio tracks detected)"
    exit 1
  else
    log_msg "   -> WARNING: 0 audio tracks detected, silent quarantine disabled"
    exit 0
  fi
fi

if echo "$TRACKS" | grep -Eiq ",(dts|pcm)"; then
  if [ "$ENABLE_DTS_CONVERSION" = "true" ]; then
    TMP_FILE="${INPUT_FILE%.mkv}_aac_tmp.mkv"
    if ffmpeg -hide_banner -loglevel error -y -i "$INPUT_FILE" -map 0:v:0 -map 0:a -c:v copy -c:a aac -b:a 192k "$TMP_FILE"; then
      mv "$TMP_FILE" "$INPUT_FILE"
      log_msg "   -> Converted DTS/PCM audio tracks to AAC (192k) via atomic temp copy"
    else
      rm -f "$TMP_FILE"
      log_msg "   -> ERROR: ffmpeg AAC conversion failed; kept original MKV intact"
    fi
  else
    log_msg "   -> DTS/PCM track detected, auto-conversion disabled in Setup"
  fi
fi
