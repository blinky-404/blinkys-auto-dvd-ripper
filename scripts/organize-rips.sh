#!/bin/bash
source /DATA/ripper/organizer.conf
FINISHED_DIR="/DATA/ripper/finished"
QUARANTINE_DIR="/DATA/ripper/no_audio"
FULL_DIR="$DEST_MOVIES_DIR/movies full quality"
LOW_DIR="$DEST_MOVIES_DIR/movies low quality"
REPORT_FILE="$DEST_MOVIES_DIR/ripper_daily_report.txt"
mkdir -p "$FULL_DIR" "$LOW_DIR" "$QUARANTINE_DIR"
shopt -s nullglob
FILES=("$FINISHED_DIR"/*.mp4 "$FINISHED_DIR"/*.mkv)
[ ${#FILES[@]} -eq 0 ] && exit 0
echo "Latest Rip & Quality Audit - $(date '+%Y-%m-%d %H:%M:%S')" > "$REPORT_FILE"
for FILE in "${FILES[@]}"; do
    [ -f "$FILE" ] || continue
    BASENAME=$(basename "${FILE%.*}"); EXT="${FILE##*.}"
    AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 "$FILE" 2>/dev/null | head -n 1)
    HEIGHT=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$FILE" 2>/dev/null | head -n 1)
    DUR_SEC=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FILE" 2>/dev/null | cut -d. -f1)
    MINS=$(( ${DUR_SEC:-0} / 60 ))
    if [ -z "$AUDIO" ] || [ "$MINS" -lt "$MIN_RUNTIME_MINS" ]; then
        mv "$FILE" "$QUARANTINE_DIR/${BASENAME}_FLAGGED.${EXT}"
        echo "[QUARANTINED] $BASENAME | Mins: $MINS | Audio: ${AUDIO:-none}" >> "$REPORT_FILE"
        continue
    fi
    CLEAN_QUERY=$(echo "$BASENAME" | sed -E 's/\(Unmatched\)//Ig; s/#[A-Za-z0-9]+//g; s/\b169\b//g; s/[._-]+/ /g' | xargs | sed -E 's/ [a-zA-Z0-9]{6}$//')
    ENCODED=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv.pop()))" "$CLEAN_QUERY")
    H="api.themoviedb.org"; P="3/search/movie"
    if [ ${#TMDB_TOKEN} -gt 60 ]; then
        RES=$(curl -s -H "Authorization: Bearer $TMDB_TOKEN" "https://$H/$P?query=$ENCODED")
    else
        RES=$(curl -s "https://$H/$P?api_key=$TMDB_TOKEN&query=$ENCODED")
    fi
    TITLE=$(echo "$RES" | jq -r '.results | first | .title // empty')
    REL=$(echo "$RES" | jq -r '.results | first | .release_date // empty')
    if [ -n "$TITLE" ] && [ -n "${REL:0:4}" ]; then
        FINAL="$(echo "$TITLE" | tr -d '\\/:*?"<>|') (${REL:0:4})"; STATUS="Matched via TMDB"
    else
        FINAL="$CLEAN_QUERY (Unmatched)"; STATUS="Unmatched"
    fi
    BASE="$LOW_DIR"; TIER="Low Quality (${HEIGHT:-0}p)"
    BITRATE=$(ffprobe -v error -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$FILE" 2>/dev/null | head -n 1); KBPS=$(( ${BITRATE:-1000000} / 1000 )); [ "${HEIGHT:-0}" -ge 300 ] && [ "$KBPS" -ge 400 ] && BASE="$FULL_DIR" && TIER="Full Quality (${HEIGHT:-0}p)"
    MF="$BASE/$FINAL"; mkdir -p "$MF"
    DEST="$MF/${FINAL}.${EXT}"; [ -e "$DEST" ] && DEST="$MF/${FINAL}_$(date +%s).${EXT}"
    mv "$FILE" "$DEST"
    printf "Title: %s\nStatus: %s\nQuality: %s\nRuntime: %s mins\nAudio: %s\nSource: %s.%s\nDate: %s\n" "$FINAL" "$STATUS" "$TIER" "$MINS" "$AUDIO" "$BASENAME" "$EXT" "$(date '+%Y-%m-%d %H:%M:%S')" > "$MF/${FINAL}_info.txt"
    chown -R 1000:1000 "$MF"
    echo "[PASSED] $FINAL | $TIER | ${MINS}m | $AUDIO | Source: $BASENAME" >> "$REPORT_FILE"
done
chown -R 1000:1000 "$DEST_MOVIES_DIR"
