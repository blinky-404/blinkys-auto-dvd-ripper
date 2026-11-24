#!/bin/bash
# ============================================================================
# Wrapper script invoked by cron & the Web UI 'Run Organizer Now' button
# ============================================================================
exec python3 "$(dirname "$0")/organize-rips.py" "$@"
