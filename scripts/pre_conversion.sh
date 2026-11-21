#!/bin/bash
INPUT_FILE="$1"
[ -f "$INPUT_FILE" ] || exit 0
BASENAME=$(basename "$INPUT_FILE")
LOG_FILE="/output/../no_audio/raw_audio_audit.txt"
mkdir -p "/output/../no_audio"

TRACKS=$(ffprobe -v error -select_streams a -show_entries stream=index,codec_name,channels:stream_tags=language -of csv=p=0 "$INPUT_FILE" 2>/dev/null)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $BASENAME -> Tracks: ${TRACKS:-NONE}" >> "$LOG_FILE"

if [ -z "$TRACKS" ]; then
    mv "$INPUT_FILE" "/output/../no_audio/${BASENAME}_NO_AUDIO.mkv"
    exit 1
fi

FIRST_CODEC=$(echo "$TRACKS" | head -n 1 | cut -d',' -f2)
if [[ "$FIRST_CODEC" == "dts"* || "$FIRST_CODEC" == "pcm"* ]]; then
    TMP_FILE="${INPUT_FILE%.mkv}_fixed.mkv"
    if ffmpeg -hide_banner -loglevel error -y -i "$INPUT_FILE" -map 0:v:0 -map 0:a -c:v copy -c:a aac -b:a 192k "$TMP_FILE"; then
        mv "$TMP_FILE" "$INPUT_FILE"
        echo "   -> Converted $FIRST_CODEC audio to AAC" >> "$LOG_FILE"
    fi
fi
