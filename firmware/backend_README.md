# Firmware Integrity Checker (ESP32 family)

Runtime firmware integrity + anti-rollback checker for ESP32-family
microcontrollers (ESP32, ESP32-S2/S3, ESP32-C2/C3/C6, ESP32-H2), built on
ESP-IDF. See `PORTING_NOTES.md` for what changed to generalize this beyond
the original ESP32-S3-only build, and `VM_TESTING.md` for connecting a real
board from Windows, Linux, or inside a VM.

## Build

**Prefer Docker?** If you have the full project (this folder plus the
sibling `dashboard/` folder and a root `docker-compose.yml`), run
`docker compose run --rm firmware-build` from the project root instead -
see the root `DOCKER.md`. If you only have this `firmware/` folder on its
own, `scripts/docker-*.sh` here still work standalone (each uses plain
`docker run`, no compose file needed) - see this folder's own `DOCKER.md`.

```
idf.py set-target esp32s3      # or esp32 / esp32s2 / esp32c3 / esp32c6 / esp32h2
idf.py menuconfig              # → "Firmware Integrity Checker" → set alert
                                #   UART pins to ones free on your board
idf.py -p <PORT> flash monitor
```

## What's implemented vs. what the full proposal describes

This repo currently implements the **on-device firmware/main only**:
- SHA-256 hashing of the monitored app partition (`crypto.c`)
- Reference-hash loading from NVS with a self-established fallback (`integrity_checker.c`)
- Persistent, monotonic anti-rollback floor in NVS (`rollback.c`)
- A wear-aware NVS ring-buffer secure event log (`logger.c`)
- A framed UART alert protocol for a host-side listener (`serial_comm.c`)

**Not yet implemented** (referenced in the proposal / in code comments, but
no code exists for these anywhere in this repo):
- A provisioning path that actually calls `crypto_store_reference_hash()` —
  right now nothing writes the trusted golden hash, so devices always fall
  back to the weaker self-established baseline. Needs either a UART
  command handler + host-side signer script, or a manufacturing-time NVS
  provisioning tool.
- The MQTT/CoAP alert transport described in the proposal (current
  transport is a raw framed string over UART, not MQTT/CoAP over Wi-Fi).
- The desktop/mobile dashboard, backend CRUD API, and database described
  in Chapter 3 of the proposal — no host-side application code exists yet.
- The Signer/CI pipeline (build → test → sign → SBOM → OTA publish).

## Testing

`test/` contains Unity test skeletons (`test_crypto.c`, `test_logger.c`,
`test_rollback.c`) that exercise the hardware-dependent paths and therefore
require a real board — see `test/CMakeLists.txt` for how to build/run them.
`crypto_hash_to_str()`'s tests are the one exception and can be pulled into
a plain host-side Unity/CMock build if you want something runnable without
hardware today.

## Layout

```
main/     - firmware source (this is what idf.py builds by default)
test/     - Unity test sources (hardware-dependent, see test/CMakeLists.txt)
```
