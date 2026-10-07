#!/usr/bin/env bash
# Run the dashboard against a real board: X11 window forwarding AND serial
# device passthrough together (docker-compose.yml deliberately omits the
# device mapping so Simulation Mode always works - this script is for when
# you actually have hardware plugged in).
#
# Usage: ./scripts/run-with-device.sh [/dev/ttyUSB0]
#
# Linux only as written. Windows/WSL2: attach the board via usbipd first
# (see ../firmware/VM_TESTING.md), then run this same script from inside
# WSL2 with a Windows X server (e.g. VcXsrv) running and DISPLAY pointed at
# it. macOS: Docker Desktop doesn't support USB passthrough at all - run
# the dashboard natively (python main.py) instead of through Docker when
# you need real hardware on a Mac; Docker there is fine for
# Simulation-Mode-only use.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p exports

PORT="${1:-/dev/ttyUSB0}"

if [ ! -e "$PORT" ]; then
    echo "Error: $PORT does not exist. Is the board plugged in?" >&2
    echo "Check with: ls /dev/ttyUSB* /dev/ttyACM*" >&2
    exit 1
fi

# Authorize the container to connect to your X server. This is the
# "quick, fine for a personal dev machine" version - see DOCKER.md for a
# tighter alternative (mounting .Xauthority instead of opening xhost to
# all local users).
xhost +local:docker >/dev/null 2>&1 || {
    echo "Warning: 'xhost' command not found or failed - the GUI window may not appear." >&2
    echo "Install it with: sudo apt install x11-xserver-utils" >&2
}

docker build -t firmware-integrity-dashboard:latest .

docker run --rm -it \
    -e DISPLAY="$DISPLAY" \
    -e QT_X11_NO_MITSHM=1 \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$PWD/exports":/data/exports \
    --device="$PORT":"$PORT" \
    firmware-integrity-dashboard:latest
