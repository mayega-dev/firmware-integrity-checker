#!/usr/bin/env bash
# Builds a standalone Linux executable natively (no Docker) - use this if
# you already have Python 3.11+ on this machine and would rather not spin
# up a container just to build. See build_linux_docker.sh for the
# container-based alternative (matches the rest of this project's workflow
# more closely and avoids "works on my machine" dependency drift).
set -euo pipefail
cd "$(dirname "$0")/.."   # dashboard/ directory

python3 -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip
pip install --timeout 180 --retries 15 -r requirements.txt -r packaging/requirements-build.txt

pyinstaller --noconfirm --clean packaging/dashboard.spec

deactivate

echo ""
echo "Built: dist/FirmwareIntegrityMonitor/"
echo "Run it directly:  ./dist/FirmwareIntegrityMonitor/FirmwareIntegrityMonitor"
echo "Or zip the whole dist/FirmwareIntegrityMonitor/ folder to share it -"
echo "everything needed is inside, no Python install required on the target machine."
