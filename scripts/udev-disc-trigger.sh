#!/bin/bash
DEV="${1:-/dev/sr0}"
CONF="/DATA/ripper_system/config/organizer.conf"
MODE=$(grep -E '^DRIVE_MODE=' "$CONF" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "sequential")
if [ "$MODE" = "sequential" ]; then
  exec 200>/tmp/blinky_ripper_seq.lock
  flock -x 200
fi
docker restart makemkv >/dev/null 2>&1
