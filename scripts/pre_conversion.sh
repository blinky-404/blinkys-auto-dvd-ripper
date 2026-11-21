#!/bin/bash
INPUT_FILE="$1"
[ -f "$INPUT_FILE" ] || exit 0
BASENAME=$(basename "$INPUT_FILE")
FOLDER_TAG=$(basename "$(dirname "$INPUT_FILE")")
BACKUP_DIR="/output/../raw_audio_backups"
LOG_FILE="/output/../no_audio/raw_audio_audit.txt"
mkdir -p "$BACKUP_DIR"

TRACKS=$(ffprobe -v error -select_streams a -show_entries stream=index,codec_name,channels:stream_tags=language -of csv=p=0 "$INPUT_FILE" 2>/dev/null)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${FOLDER_TAG}/${BASENAME} -> Tracks: ${TRACKS:-NONE}" >> "$LOG_FILE"

if [ -z "$TRACKS" ]; then
    mv "$INPUT_FILE" "/output/../no_audio/${FOLDER_TAG}_${BASENAME}_NO_AUDIO.mkv"
    exit 1
fi

FIRST_CODEC=$(echo "$TRACKS" | head -n 1 | cut -d',' -f2)
if [[ "$FIRST_CODEC" == "dts"* || "$FIRST_CODEC" == "pcm"* ]]; then
    cp "$INPUT_FILE" "$BACKUP_DIR/${FOLDER_TAG}_${BASENAME}"
    TMP_FILE="${INPUT_FILE%.mkv}_fixed.mkv"
    if ffmpeg -hide_banner -loglevel error -y -i "$INPUT_FILE" -map 0:v:0 -map 0:a -c:v copy -c:a aac -b:a 192k "$TMP_FILE"; then
        mv "$TMP_FILE" "$INPUT_FILE"
        echo "   -> Backed up untouched MKV to raw_audio_backups/ and converted $FIRST_CODEC to AAC" >> "$LOG_FILE"
    fi
fi
