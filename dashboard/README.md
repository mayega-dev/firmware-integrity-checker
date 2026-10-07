# Firmware Integrity Monitor (PySide6 Dashboard)

Desktop companion app for the ESP32 firmware integrity checker. Listens on
the device's dedicated **alert UART** (see `firmware/main/serial_comm.c` -
a separate port from the board's console/programming UART) and renders
live integrity status, an alert log, a raw console, and connection
settings.

![Dashboard screenshot](docs/screenshot.png)

```
┌───────────────┬──────────────────────────────────────────────────┐
│ Integrity      │  Dashboard                                        │
│ Monitor        │  ┌──────────────────────────────────────────┐    │
│                │  │ ● SYSTEM SECURE             ESP32-S3      │    │
│ ▣ Dashboard    │  │   Last event: STATUS_SAFE @ 14:32:07  fw 1.0.0│
│ ⚗ Alert Log    │  └──────────────────────────────────────────┘    │
│ ⌘ Console      │  [Total Checks] [Critical Alerts] [Uptime] [FW]   │
│ ⚙ Settings     │  ┌──────────────────────────────────────────┐    │
│                │  │  INTEGRITY CHECK TIMELINE  ▂▂▂▂▂█▂▂▂▂▂▂▂  │    │
│ ● CONNECTED    │  └──────────────────────────────────────────┘    │
│                │  RECENT EVENTS  [table: time | severity | ...]   │
└───────────────┴──────────────────────────────────────────────────┘
```

(`docs/screenshot.png` above is a placeholder path for you to fill in -
this sandbox has no network access to install real PySide6 and render an
actual screenshot. Run `python main.py` with Simulation mode on to see
the real thing within a minute of install, then drop a screenshot in
`docs/` and the image link above will pick it up.)

## Install & run

**Prefer Docker?** If you have the full project (this folder plus the
sibling `firmware/` folder and a root `docker-compose.yml`), run
`docker compose up --build dashboard` from the project root instead - see
the root `DOCKER.md`. If you only have this `dashboard/` folder on its
own, `scripts/run-with-device.sh` here still works standalone - see this
folder's own `DOCKER.md`. Either way, note the one genuine complication:
this is a GUI app, so Docker needs X11 window forwarding set up in
addition to the usual container plumbing - the one-line `xhost` step trips
people up most.

```
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

No hardware yet? Check **Simulation mode** on the Settings page and hit
Connect - it generates realistic synthetic `STATUS`/`ALERT` traffic locally
so you can explore the whole UI without a board attached.

## Standalone executable (no Python needed to run it)

See `PACKAGING.md` - builds a Linux executable via Docker (or natively),
and covers building the Windows one (which has to actually run on
Windows - PyInstaller can't cross-compile that from here).

## Exporting logs

The Alert Log page's **Export CSV** button saves into `exports/` at the
project root by default. Matters specifically when running via Docker:
`docker-compose.yml` mounts that folder into the container at
`/data/exports`, so files you export are still there after the container
exits - without that mount, anything saved to the container's own
filesystem would vanish the moment `--rm` cleans it up. Running natively
(no Docker), it defaults to your home folder instead, same as any normal
desktop app - the exports/ default is a container-specific fallback, not a
hardcoded location either way.

## Finding the right port

The Settings page's port dropdown groups what your OS reports into two
sections:
- **ESP32 devices detected** - ports whose USB vendor/product ID matches a
  known ESP32 USB-UART bridge chip (Silicon Labs CP210x, WCH CH340/CH343,
  FTDI) or Espressif's own native-USB VID (S2/S3/C3/C6/H2 in USB-CDC or
  USB-Serial-JTAG mode). The first one found is auto-selected.
- **Other serial ports** - everything else the OS lists: Bluetooth virtual
  COM ports, an internal modem, anything not recognized as ESP32 hardware.
  Still selectable manually (e.g. an unlisted/generic USB-serial adapter
  wired to the alert UART pins in the two-cable setup), just not
  auto-picked.

The list re-scans every 2 seconds while disconnected, so plugging in a
board gets it listed without clicking Refresh. This logic (`app/device_link.py`'s
`available_ports()`) uses pyserial's cross-platform port enumeration -
identical behavior on Windows (`COM3`, etc.) and Linux/macOS
(`/dev/ttyUSB0`, `/dev/ttyACM0`, etc.), nothing OS-specific to configure.

## Wiring a real device

The alert UART is **not** the same port your board enumerates as a
programming/console COM port over its onboard USB. Per
`firmware/PORTING_NOTES.md` and `Kconfig.projbuild`, it's a second UART
you configure via `idf.py menuconfig` → **Firmware Integrity Checker**,
and you'll need an external USB-to-TTL adapter wired to those GPIO pins
(TX→RX, RX→TX, GND→GND) unless your board exposes a second USB port
already tied to that UART (some S3 devkits do). See
`firmware/VM_TESTING.md` for driver names and VM/WSL2 passthrough if
you're testing from inside a virtual machine.

Protocol (see `app/protocol.py`, mirrors `firmware/main/serial_comm.c` exactly):
```
::STATUS:<fw_version>:<hardware_revision>::   (sent once, at boot)
::ALERT:<LEVEL>:<EVENT_CODE>::                (sent per security event)
```
Outgoing commands the device understands (`integrity_checker.c`):
```
::POLL::      trigger an immediate verification sweep
::TAMPER::    debug builds only (ENABLE_TAMPER_SIMULATION=1) - injects a
              simulated tamper event for testing the alert path end-to-end
```

## Architecture

```
main.py                    - entry point, loads the QSS theme, shows MainWindow
app/
  protocol.py               - wire format parser (pure Python, no Qt - unit tested)
  device_link.py             - QThread workers: SerialLink (real hw), SimulatorLink (demo)
  models.py                   - AlertLogModel (QAbstractTableModel) + severity colors
  main_window.py                - sidebar + page stack + device-link lifecycle wiring
  widgets/
    sidebar.py                   - left nav rail + connection pill
    dashboard_page.py             - status hero, stat cards, timeline, recent events
    log_page.py                    - full alert log: filter, sort, CSV export
    console_page.py                 - raw traffic feed + manual ::POLL::/::TAMPER::
    settings_page.py                 - port/baud selection, simulation toggle, connect
    status_hero.py                    - big pulsing status indicator widget
    timeline.py                        - custom-painted rolling event strip (no QtCharts dep)
    stat_card.py                        - small metric tile
  resources/theme.qss                   - dark theme shared by every widget
test_protocol.py           - real, runnable unit tests for app/protocol.py (pytest or `python test_protocol.py`)
```

**One thread owns the serial port.** `SerialLink` does all reads *and*
writes from inside its own `run()` loop via an internal command queue,
rather than having the UI thread write directly - pyserial doesn't
guarantee `Serial.write()`/`.readline()` are safe to call concurrently
from two threads, so this avoids that whole class of bug.

**No QtCharts dependency.** The integrity timeline is a small
custom-painted `QWidget` (`widgets/timeline.py`) instead of pulling in
`PySide6.QtCharts`, since that addon module isn't guaranteed present on
every PySide6 install/platform. One less thing that can fail to import.

## Testing

`test_protocol.py` is real, dependency-free (no PySide6 needed) and
verifies the parser against the exact frames `serial_comm.c` emits,
including edge cases (unknown event codes from a future firmware version,
stray console/log noise leaking onto the wire, trailing `\r\n`). Run it
directly - `python test_protocol.py` - or with `pytest`.

The rest of the app (widgets, main window, device link threading) was
verified with a full offline smoke test during development: constructing
every page, driving simulated `STATUS`/`ALERT` traffic through the real
`MainWindow` handlers, exercising navigation/filter/export/command-send
code paths, and running `SimulatorLink`'s and `SerialLink`'s actual
background thread loops (including `SerialLink`'s graceful
"pyserial not installed" error path) - all against a structural PySide6
API stub, since this sandbox has no network access to install real
PySide6. **You should still do one real run** (`python main.py` with
actual PySide6 installed, Simulation mode is enough) before treating this
as final - a structural stub confirms the code *calls* the right methods
in the right order, not that the real Qt paint/event system behaves
identically pixel-for-pixel.

## Known limitations / next steps

- Only the alert UART's structured frames are modeled; nothing here
  parses OTA, MQTT/CoAP, or the desktop backend/database described in the
  UTAMU proposal's Chapter 3 - none of that exists yet (see the firmware
  package's `README.md` for the full gap list).
- Reconnection is manual (no auto-retry on cable unplug) - a nice next
  addition if this becomes a long-running kiosk-style deployment.
- Log persistence is in-memory only per session; use **Export CSV** on the
  Alert Log page before closing the app if you need to keep a record.
