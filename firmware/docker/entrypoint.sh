#!/usr/bin/env bash
# Sources the ESP-IDF environment (puts idf.py, esptool.py, the compiler,
# etc. on PATH) before running whatever command was passed to `docker run`.
set -euo pipefail

# shellcheck disable=SC1091
if [ -f "$IDF_PATH/export.sh" ]; then
    source "$IDF_PATH/export.sh" > /dev/null
else
    echo "Error: ESP-IDF export script not found at $IDF_PATH/export.sh" >&2
    exit 1
fi

exec "$@"