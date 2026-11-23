#!/bin/bash
# Blinky's Auto DVD Ripper - Modular Pre-Conversion Audio Gatekeeper

INPUT_FILE="$1"
[ -f "$INPUT_FILE" ] || exit 0

SYSTEM_DIR="${SYSTEM_DIR:-/DATA/ripper_system}"
MEDIA_DIR="${MEDIA_DIR:-/DATA/ripper_media}"
CONF_FILE="$SYSTEM_DIR/config/organizer.conf"
LOG_FILE="$SYSTEM_DIR/logs/audio_audit.log"

mkdir -p "$SYSTEM_DIR/logs" "$MEDIA_DIR/no_audio" "$MEDIA_DIR/raw_audio_backups"

# Load modular settings
[ -f "$CONF_FILE" ] && source "$CONF_FILE"
ENABLE_SILENT_QUARANTINE="${ENABLE_SILENT_QUARANTINE:-true}"
ENABLE_DTS_CONVERSION="${ENABLE_DTS_CONVERSION:-true}"
ENABLE_RAW_AUDIO_BACKUP="${ENABLE_RAW_AUDIO_BACKUP:-true}"
LOG_MAX_LINES="${LOG_MAX_LINES:-500}"

log_msg() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt "$LOG_MAX_LINES" ]; then
        tail -n "$LOG_MAX_LINES" "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
}

BASENAME=$(basename "$INPUT_FILE")
FOLDER_TAG=$(basename "$(dirname "$INPUT_FILE")")
[ "$FOLDER_TAG" = "raw" ] && TAG_PREFIX="$BASENAME" || TAG_PREFIX="${FOLDER_TAG}_${BASENAME}"

TRACKS=$(ffprobe -v error -select_streams a -show_entries stream=index,codec_name,channels:stream_tags=language -of csv=p=0 "$INPUT_FILE" 2>/dev/null)
FLAT_TRACKS=$(echo "$TRACKS" | tr '\n' ' | ' | sed 's/ | $//')
log_msg "${TAG_PREFIX} -> Audio Streams: ${FLAT_TRACKS:-NONE}"

# 1. Silent File Quarantine Check
if [ -z "$TRACKS" ]; then
    if [ "$ENABLE_SILENT_QUARANTINE" = "true" ]; then
        mv "$INPUT_FILE" "$MEDIA_DIR/no_audio/${TAG_PREFIX%.mkv}_NO_AUDIO.mkv"
        log_msg "   -> QUARANTINED to no_audio/ (0 audio tracks detected)"
        exit 1
    else
        log_msg "   -> WARNING: 0 audio tracks detected, but silent quarantine is disabled"
        exit 0
    fi
fi

# 2. All-Tracks DTS / PCM Detection & Optional Backup + AAC Conversion
if echo "$TRACKS" | grep -Eiq ",(dts|pcm)"; then
    if [ "$ENABLE_DTS_CONVERSION" = "true" ]; then
        if [ "$ENABLE_RAW_AUDIO_BACKUP" = "true" ]; then
            cp "$INPUT_FILE" "$MEDIA_DIR/raw_audio_backups/${TAG_PREFIX}"
            log_msg "   -> Saved untouched backup to raw_audio_backups/${TAG_PREFIX}"
        fi
        TMP_FILE="${INPUT_FILE%.mkv}_aac_fixed.mkv"
        if ffmpeg -hide_banner -loglevel error -y -i "$INPUT_FILE" -map 0:v:0 -map 0:a -c:v copy -c:a aac -b:a 192k "$TMP_FILE"; then
            mv "$TMP_FILE" "$INPUT_FILE"
            log_msg "   -> Converted DTS/PCM audio tracks to AAC (192k)"
        else
            rm -f "$TMP_FILE"
            log_msg "   -> ERROR: ffmpeg AAC conversion failed; passing original MKV to HandBrake"
        fi
    else
        log_msg "   -> DTS/PCM track detected, but auto-conversion is disabled in Setup"
    fi
fi
