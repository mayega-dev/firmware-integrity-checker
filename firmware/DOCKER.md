# Building & flashing via Docker

This replaces installing ESP-IDF locally entirely - `espressif/idf:v5.3.1`
is Espressif's official image with the full toolchain already built in.
Docker only needs to pull that one image (a few GB, one time, cached
afterward), instead of the git-clone-plus-30-submodules process.

## Prerequisites

- Docker installed (`docker --version` to check). On Ubuntu:
  `sudo apt install docker.io docker-compose-v2`, then
  `sudo usermod -aG docker $USER` and log out/in so you don't need `sudo`
  for every command below.

## Build

```
./scripts/docker-build.sh
```
First run pulls the image (a few minutes depending on connection) and sets
the target to `esp32`; later runs are much faster (cached image + ccache
volume for incremental builds). Output lands in `build/` exactly like a
native `idf.py build` would.

**Ownership note:** the container runs as root by default (this is
Espressif's own documented pattern for this image), so files under
`build/` will show up root-owned on your host afterward. That's harmless
for reading/reflashing, but if you ever need to `rm -rf build/` or edit
generated files as your normal user:
```
sudo chown -R "$(id -u):$(id -g)" build/
```

## Flash

```
./scripts/docker-flash.sh              # defaults to /dev/ttyUSB0
./scripts/docker-flash.sh /dev/ttyACM0 # or specify the port
```
Works natively on Linux - Docker on Linux can bind a host device node
straight into the container, no extra layer involved.

## Configure (menuconfig) / View logs (monitor) / Ad-hoc shell

```
./scripts/docker-menuconfig.sh   # e.g. set ALERT_UART pins, or disable
                                  # console output for the single-cable
                                  # quick-test setup from earlier
./scripts/docker-monitor.sh      # live console output (only shows
                                  # anything if you kept the console on)
./scripts/docker-shell.sh        # drop into bash with idf.py on PATH
```

## Windows (WSL2)

Docker Desktop on Windows runs its Linux containers through WSL2. Device
passthrough works the same way it does for native WSL2 (see
`VM_TESTING.md`'s usbipd-win section):
```powershell
# Windows PowerShell, admin:
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```
Then run the exact same `./scripts/docker-*.sh` commands from inside your
WSL2 terminal (where Docker Desktop's `docker` CLI is also available) -
`/dev/ttyUSB0` will show up there once attached, and the scripts work
identically to the Linux case above.

## macOS

Docker Desktop for Mac does **not** support USB device passthrough - this
is a Docker Desktop limitation, not something a Dockerfile/compose config
can work around. `./scripts/docker-build.sh` works fine (building doesn't
need a device). For flashing/monitoring against real hardware on a Mac,
install ESP-IDF natively instead (`brew install cmake ninja`, then follow
Espressif's standard macOS install docs) - Docker isn't the right tool for
that specific step on this OS.
