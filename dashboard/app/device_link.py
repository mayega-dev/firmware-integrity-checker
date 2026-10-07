from __future__ import annotations

import queue
import re
import time
from dataclasses import dataclass
from PySide6.QtCore import QThread, Signal

try:
    import serial
    import serial.tools.list_ports
    HAS_PYSERIAL = True
except ImportError:
    HAS_PYSERIAL = False

from app.models import AlertEvent
from app.protocol import DeviceStatus, RehashAlertEvent, parse_line


@dataclass
class PortInfo:
    device: str
    description: str
    is_likely_esp32: bool = False
    match_reason: str = ""


def available_ports() -> list[PortInfo]:
    """Scans system for serial ports and identifies ESP32 silicon bridges."""
    results: list[PortInfo] = []
    if not HAS_PYSERIAL:
        return results

    try:
        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = p.description or ""
            hwid = p.hwid or ""
            device = p.device or ""

            is_esp = False
            reason = ""

            if any(vid in hwid.upper() for vid in ["10C4:EA60", "1A86:7523", "0403:6001", "303A:"]):
                is_esp = True
                reason = "USB UART Bridge (CP210x / CH340 / FTDI / ESP USB)"
            elif "CP210" in desc or "CH340" in desc or "ESP32" in desc:
                is_esp = True
                reason = desc

            results.append(
                PortInfo(
                    device=device,
                    description=desc,
                    is_likely_esp32=is_esp,
                    match_reason=reason,
                )
            )
    except Exception:
        pass

    return results


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class DeviceLink(QThread):
    """
    Base class for every telemetry source. Subclasses push each complete text
    line they receive into `_ingest_line()`, which is the ONE place where wire
    frames are parsed and turned into Qt signals - so real hardware and the
    simulator exercise exactly the same code path.
    """

    connected = Signal()
    disconnected = Signal(str)
    status_received = Signal(DeviceStatus)
    alert_received = Signal(AlertEvent)
    hash_received = Signal(str, str)      # (sha256_hex, "PASS" | "FAIL")
    raw_line_received = Signal(str)
    link_error = Signal(str)
    diagnostic = Signal(str)              # human-readable hints for the console

    def __init__(self, parent=None):
        super().__init__(parent)
        self._baseline_hash: str | None = None
        self._last_hash: str | None = None
        self.frames_seen = 0

    def stop(self) -> None:
        pass

    def send_command(self, command: str) -> None:
        pass

    # ------------------------------------------------------------------
    def _ingest_line(self, raw_line: str) -> None:
        line = _ANSI_RE.sub("", raw_line).strip()
        if not line:
            return

        # Always show the raw text in the console page (including log noise).
        self.raw_line_received.emit(line)

        parsed = parse_line(line)
        if parsed is None:
            return
        self.frames_seen += 1

        # ::STATUS:<fw>:<hw>::
        if isinstance(parsed, DeviceStatus):
            self.status_received.emit(parsed)
            return

        # ::REHASH:<PASS|FAIL>:<hash>::  -> hash panel only (no log row; the
        # firmware follows every REHASH with an ::ALERT:: that is logged).
        if isinstance(parsed, RehashAlertEvent):
            if parsed.hash_val:
                self._last_hash = parsed.hash_val
                is_pass = parsed.event_code == "REHASH_PASS"
                if is_pass and self._baseline_hash is None:
                    self._baseline_hash = parsed.hash_val
                self.hash_received.emit(parsed.hash_val, "PASS" if is_pass else "FAIL")
            return

        # ::ALERT:<LEVEL>:<CODE>[|ORIG:..|CURR:..]::
        orig = parsed.orig_hash
        curr = parsed.curr_hash
        if orig in ("", "N/A"):
            orig = self._baseline_hash or "N/A"
        if curr in ("", "N/A"):
            curr = self._last_hash or "N/A"

        normalized = f"::ALERT:{parsed.level_raw.upper()}:{parsed.event_code}|ORIG:{orig}|CURR:{curr}::"
        event = AlertEvent.parse_raw_line(normalized)
        if event is not None:
            event.raw_line = line
            self.alert_received.emit(event)


class SerialLink(DeviceLink):
    """Hardware serial link reading from a physical USB UART device."""

    NO_DATA_HINT_AFTER_S = 6.0
    POLL_RETRY_S = 2.0

    def __init__(self, port: str, baud: int = 115200, parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self._running = False
        self._serial = None
        self._write_queue: queue.Queue[str] = queue.Queue()

    def stop(self) -> None:
        self._running = False

    def send_command(self, command: str) -> None:
        if not command.endswith("\n"):
            command += "\n"
        self._write_queue.put(command)

    def _open(self):
        ser = serial.Serial()
        ser.port = self.port
        ser.baudrate = self.baud
        ser.timeout = 0.2
        ser.write_timeout = 1.0
        # Opening a port normally pulses DTR/RTS, which resets most ESP32
        # boards (and makes you miss the boot-time frames). Keep both low.
        ser.dtr = False
        ser.rts = False
        ser.open()
        return ser

    def run(self) -> None:
        if not HAS_PYSERIAL:
            self.link_error.emit("pyserial is not installed in the Python environment.")
            self.disconnected.emit("pyserial missing.")
            return

        try:
            self._serial = self._open()
            self._running = True
            self.connected.emit()
        except Exception as e:  # noqa: BLE001
            self.link_error.emit(f"Failed to open port {self.port}: {e}")
            self.disconnected.emit("Connection failed.")
            return

        buf = bytearray()
        started = time.monotonic()
        last_poll = 0.0
        hinted = False

        try:
            # Drop whatever the OS buffered before we attached.
            self._serial.reset_input_buffer()

            while self._running and self._serial and self._serial.is_open:
                now = time.monotonic()

                # Until the first valid frame arrives, keep asking the device
                # for one - the firmware only sends its boot-time STATUS/REHASH
                # frames once, usually before the dashboard was connected.
                if self.frames_seen == 0 and now - last_poll >= self.POLL_RETRY_S and now - started >= 0.4:
                    self._write_queue.put("::POLL::\n")
                    last_poll = now

                while not self._write_queue.empty():
                    cmd = self._write_queue.get_nowait()
                    self._serial.write(cmd.encode("utf-8"))
                    self._serial.flush()

                chunk = self._serial.read(self._serial.in_waiting or 1)
                if chunk:
                    buf.extend(chunk)
                    while True:
                        nl = buf.find(b"\n")
                        if nl < 0:
                            break
                        line = bytes(buf[:nl]).decode("utf-8", errors="ignore")
                        del buf[: nl + 1]
                        self._ingest_line(line)
                    # A frame is never longer than ~256 bytes; don't let a
                    # newline-less stream grow without bound.
                    if len(buf) > 4096:
                        self._ingest_line(bytes(buf).decode("utf-8", errors="ignore"))
                        buf.clear()

                if not hinted and self.frames_seen == 0 and now - started > self.NO_DATA_HINT_AFTER_S:
                    hinted = True
                    self.diagnostic.emit(
                        f"[HINT] Port {self.port} opened but no ::STATUS::/::ALERT::/::REHASH:: frames "
                        f"received after {int(self.NO_DATA_HINT_AFTER_S)}s. Check: (1) firmware built with "
                        f"'Alert transport = console' (default) or your adapter is wired to the alert UART "
                        f"pins; (2) baud matches ({self.baud}); (3) no other program (idf.py monitor, "
                        f"Arduino IDE) is holding the port."
                    )

        except Exception as e:  # noqa: BLE001
            self.link_error.emit(f"Serial communications error: {e}")
        finally:
            try:
                if self._serial and self._serial.is_open:
                    self._serial.close()
            except Exception:  # noqa: BLE001
                pass
            self.disconnected.emit("Port closed.")


class SimulatorLink(DeviceLink):
    """
    In-process synthetic ESP32. It emits the *exact* wire frames the real
    firmware emits (STATUS, REHASH, ALERT) as text lines through the same
    `_ingest_line()` path as hardware, so Simulation Mode is a true test of
    the parser + dashboard wiring.
    """

    BASELINE_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    TAMPERED_HASH = "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._cmd_queue: queue.Queue[str] = queue.Queue()

    def stop(self) -> None:
        self._running = False

    def send_command(self, command: str) -> None:
        self._cmd_queue.put(command)

    def _emit_check(self, level: str, code: str, curr_hash: str) -> None:
        ok = curr_hash == self.BASELINE_HASH
        self._ingest_line(f"::REHASH:{'PASS' if ok else 'FAIL'}:{curr_hash}::")
        if ok:
            self._ingest_line(f"::ALERT:{level}:{code}::")
        else:
            self._ingest_line(
                f"::ALERT:{level}:{code}|ORIG:{self.BASELINE_HASH}|CURR:{curr_hash}::"
            )

    def run(self) -> None:
        self._running = True
        self.connected.emit()

        self._ingest_line("::STATUS:1.0.0-sim:ESP32-S3 (Simulated)::")
        self._ingest_line(f"::REHASH:PASS:{self.BASELINE_HASH}::")

        sequence = [
            ("INFO", "STATUS_SAFE", self.BASELINE_HASH, 3.0),
            ("INFO", "STATUS_SAFE", self.BASELINE_HASH, 3.0),
            ("CRITICAL", "FIRMWARE_TAMPERED", self.TAMPERED_HASH, 3.5),
            ("CRITICAL", "FIRMWARE_TAMPERED", self.TAMPERED_HASH, 3.0),
            ("WARNING", "SYSTEM_RESTORED", self.BASELINE_HASH, 3.0),
            ("INFO", "STATUS_SAFE", self.BASELINE_HASH, 3.0),
        ]
        idx = 0

        while self._running:
            while not self._cmd_queue.empty():
                cmd = self._cmd_queue.get_nowait().strip()
                if "RESET" in cmd or "RECALIBRATE" in cmd:
                    idx = 0
                    self._emit_check("WARNING", "SYSTEM_RESTORED", self.BASELINE_HASH)

            level, code, curr_hash, interval = sequence[idx]
            self._emit_check(level, code, curr_hash)
            idx = (idx + 1) % len(sequence)

            slept = 0.0
            while slept < interval and self._running:
                if not self._cmd_queue.empty():
                    break
                time.sleep(0.1)
                slept += 0.1

        self.disconnected.emit("Simulation Stopped.")
