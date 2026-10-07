Running the Firmware Integrity Checker on Any OS

This guide matches the project's docker-compose.yml and the fixed firmware/dashboard. All commands run from the project root (the folder containing docker-compose.yml, firmware/ and dashboard/).

- How the pieces talk to each other
ESP32 --(USB cable, /dev/ttyUSB0 or COMx)--> Dashboard
        ::STATUS:<fw>:<hw>::
        ::REHASH:<PASS|FAIL>:<64-char sha256>::
        ::ALERT:<LEVEL>:<CODE>[|ORIG:<hash>|CURR:<hash>]::
Dashboard --> ESP32:  ::POLL::  ::REHASH::  ::RECALIBRATE_BASELINE::  ::RESET_FIRMWARE::  ::TAMPER::

The firmware's default Alert transport = Console sends these frames over the same USB port you flash through, so one USB cable is enough. Only one program can hold the port at a time: flash first, close the monitor, then start the dashboard.

- Compose services used
Service	Profile	Purpose
dashboard	none	Dashboard in Simulation mode (no hardware)
dashboard-hw	hw	Dashboard with the serial device passed through
firmware-menuconfig-slim / firmware-menuconfig	tools	Configure firmware options
firmware-build-slim / firmware-build	tools	Build firmware
firmware-flash-slim / firmware-flash	hw	Flash the board
firmware-monitor-slim / firmware-monitor	hw	View the board's serial output

docker compose run / up <service> auto-enables the service's profile, so you do not need --profile. Do not run docker compose --profile hw up without a service name: it would start the flasher and monitor too, and they would fight over the port.

The -slim services build ESP-IDF v5.3.1 from firmware/docker/Dockerfile.slim (first build is slow, then cached). The non-slim ones pull espressif/idf:v5.3.1 (a few GB, one time). Use either family consistently.

- One-time prep (all platforms)
mkdir -p exports
# Ensure the firmware requires the app_update component (fixes the esp_ota_ops.h error)
grep -q app_update firmware/main/CMakeLists.txt || \
  sed -i 's/        esp_partition/        esp_partition\n        app_update/' firmware/main/CMakeLists.txt
# If you ever built natively, remove that build dir (host paths break the container build)
sudo rm -rf firmware/build

- Optional: choose firmware options (the default is already correct):
docker compose run --rm firmware-menuconfig-slim

- Build and flash the firmware (Linux and Windows/WSL2)
# 1. Build (override the command: the default one runs set-target, which cleans every time)
docker compose run --rm firmware-build-slim idf.py build

# 2. Flash (adjust PORT if the board is /dev/ttyACM0)
PORT=/dev/ttyUSB0 docker compose run --rm firmware-flash-slim

# 3. Optional: confirm the board is emitting frames, then press Ctrl+] to exit
PORT=/dev/ttyUSB0 docker compose run --rm firmware-monitor-slim

- If flashing hangs at Connecting......, hold the board's BOOT button until writing starts. Expected monitor output (repeats every 10 s):
::STATUS:1.0.0:ESP32::
::REHASH:PASS:<64 hex characters>::
::ALERT:INFO:STATUS_SAFE::

- Linux (native Docker)
# Allow containers to open windows on your display
xhost +local:docker

# Simulation mode (no board needed)
docker compose up dashboard

# Hardware mode
PORT=/dev/ttyUSB0 docker compose up dashboard-hw

- If you get "permission denied" on the port: sudo usermod -aG dialout $USER and log out/in, or temporarily sudo chmod 666 /dev/ttyUSB0.

Windows (via WSL2)
Step 1: Attach the ESP32 to WSL2

In Windows PowerShell (Administrator):
winget install --interactive --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>

- Use the BUSID of the CP210x / CH340 entry. Verify inside WSL2:
ls /dev/ttyUSB* /dev/ttyACM*

You must run usbipd attach again each time the board is unplugged, WSL restarts or the host reboots.

Step 2: Display (Windows 11 / recent Windows 10 with WSLg)

Do not override DISPLAY with the old resolv.conf trick; WSLg already sets it. Check:

echo $DISPLAY                 # should print :0
ls /mnt/wslg/.X11-unix        # should list X0

If those are empty: run wsl --update then wsl --shutdown in PowerShell.

WSLg keeps its display socket at /mnt/wslg/.X11-unix, so create docker-compose.wslg.yml next to docker-compose.yml:
services:
  dashboard:
    volumes:
      - /mnt/wslg/.X11-unix:/tmp/.X11-unix:rw
      - ./exports:/data/exports
  dashboard-hw:
    volumes:
      - /mnt/wslg/.X11-unix:/tmp/.X11-unix:rw
      - ./exports:/data/exports

Step 3: Run
# Simulation mode
docker compose -f docker-compose.yml -f docker-compose.wslg.yml up dashboard

# Hardware mode
PORT=/dev/ttyUSB0 docker compose -f docker-compose.yml -f docker-compose.wslg.yml up dashboard-hw

macOS

Docker Desktop on macOS cannot pass USB devices through, so flashing and hardware mode must run natively.

Simulation mode (GUI in Docker via XQuartz):

bash
xhost + localhost
DISPLAY=host.docker.internal:0 docker compose up dashboard

Real hardware (native dashboard):

bash
cd dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

- Using the dashboard
Settings -> choose the port (/dev/ttyUSB0 or COMx), baud 115200, Connect Device (or tick Simulation mode to test the UI with no board).
Within a few seconds the Baseline Threshold, Latest Rehash (full 64-char SHA-256), Firmware Version and Total Checks populate, and rows appear in the audit log.
Device Console shows every raw line received. If no frames arrive within 6 seconds it prints a checklist.
Re-calibrate Baseline Hash sends ::RECALIBRATE_BASELINE::; the device re-baselines in RAM only (a provisioned NVS golden hash is not modified).
::RESET_FIRMWARE:: cannot restore an image; the device answers with a fresh status and verification sweep.
