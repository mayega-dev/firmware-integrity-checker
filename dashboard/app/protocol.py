"""
Wire protocol parser and definitions for the ESP32 Firmware Integrity Checker's
alert UART interface.

Supported incoming frames (newline-terminated):
    ::STATUS:<fw_version>:<hardware_revision>::
    ::ALERT:<LEVEL>:<EVENT_CODE>[|ORIG:<hash>|CURR:<hash>]::
    ::REHASH:<STATUS>:<HASH_VAL>::

Supported outgoing commands:
    ::POLL::                 -> Trigger an immediate verification sweep
    ::TAMPER::               -> Debug builds only: inject simulated tamper event
    ::RESET_FIRMWARE::       -> Reset baseline and restore ESP32 firmware state
    ::RECALIBRATE_BASELINE:: -> Re-calibrate baseline hash to current device state
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_STATUS_RE = re.compile(r"::STATUS:([^:]*):([^:]*)::")
_ALERT_RE = re.compile(r"::ALERT:([A-Za-z0-9_]+):([A-Za-z0-9_]+)(?:\|(.*))?::")
_REHASH_RE = re.compile(r"::REHASH:([A-Za-z0-9_]*)(?::([^:]*))?::")


class Severity(str, Enum):
    """Normalized severity level for integrity events."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_level(cls, level: str) -> Severity:
        level = (level or "").strip().upper()
        if level == "CRITICAL":
            return cls.CRITICAL
        if level in ("WARNING", "WARN"):
            return cls.WARNING
        if level in ("INFO", "PASS", "SAFE", "SUCCESS"):
            return cls.INFO
        return cls.UNKNOWN


EVENT_CATALOG: dict[str, str] = {
    "STATUS_SAFE": "Runtime integrity check passed — firmware matches the trusted baseline.",
    "FIRMWARE_TAMPERED": "CRITICAL MISMATCH! Running firmware hash no longer matches the golden baseline.",
    "SYSTEM_RESTORED": "Firmware restored to baseline golden state.",
    "ROLLBACK_ATTEMPT_BLOCKED": "Boot halted: firmware version is older than the anti-rollback floor.",
    "REHASH_PASS": "Manual re-hash check completed successfully.",
    "REHASH_FAIL": "Manual re-hash check failed baseline integrity verification.",
}


@dataclass
class DeviceStatus:
    """Parsed payload from a device status frame (::STATUS:...::)."""

    fw_version: str
    hardware_revision: str
    received_at: datetime = field(default_factory=datetime.now)


@dataclass
class AlertEvent:
    """Parsed payload from a device alert frame (::ALERT:...::)."""

    level_raw: str
    event_code: str
    severity: Severity
    description: str
    orig_hash: str = "N/A"
    curr_hash: str = "N/A"
    received_at: datetime = field(default_factory=datetime.now)
    raw_line: str = ""


@dataclass
class RehashAlertEvent(AlertEvent):
    """
    Parsed result of a firmware rehash / re-verification event.
    Inherits all fields from AlertEvent so UI models can read description,
    severity, event_code, received_at, and raw_line transparently.
    """

    hash_val: str = ""


def parse_line(line: str) -> DeviceStatus | AlertEvent | RehashAlertEvent | None:
    """
    Parse a single incoming line from the device UART.
    
    Returns DeviceStatus, AlertEvent, RehashAlertEvent, or None if unrecognized.
    """
    cleaned = _ANSI_RE.sub("", line).strip()
    if not cleaned:
        return None

    # 1. Parse Status Frame
    status_match = _STATUS_RE.search(cleaned)
    if status_match:
        fw_version, hw_revision = status_match.group(1), status_match.group(2)
        return DeviceStatus(
            fw_version=fw_version or "unknown",
            hardware_revision=hw_revision or "unknown",
        )

    # 2. Parse Alert Frame (Supports pipe-delimited metadata like |ORIG:<hash>|CURR:<hash>)
    alert_match = _ALERT_RE.search(cleaned)
    if alert_match:
        level_raw, event_code, metadata_str = (
            alert_match.group(1),
            alert_match.group(2),
            alert_match.group(3),
        )
        severity = Severity.from_level(level_raw)

        kv_pairs: dict[str, str] = {}
        if metadata_str:
            for item in metadata_str.split("|"):
                if ":" in item:
                    k, v = item.split(":", 1)
                    kv_pairs[k] = v

        orig_hash = kv_pairs.get("ORIG", "N/A")
        curr_hash = kv_pairs.get("CURR", "N/A")

        base_desc = EVENT_CATALOG.get(
            event_code, f"Unrecognized event code '{event_code}'."
        )

        if orig_hash != "N/A" or curr_hash != "N/A":
            description = f"{base_desc} [Baseline: {orig_hash} | Current: {curr_hash}]"
        else:
            description = base_desc

        return AlertEvent(
            level_raw=level_raw or "UNKNOWN",
            event_code=event_code or "UNKNOWN",
            severity=severity,
            description=description,
            orig_hash=orig_hash,
            curr_hash=curr_hash,
            raw_line=cleaned,
        )

    # 3. Parse Legacy Rehash Frame
    rehash_match = _REHASH_RE.search(cleaned)
    if rehash_match:
        status_raw = rehash_match.group(1) or "UNKNOWN"
        hash_val = rehash_match.group(2) or ""

        is_ok = status_raw.upper() in ("OK", "PASS", "SUCCESS", "INFO")
        severity = Severity.INFO if is_ok else Severity.CRITICAL
        event_code = "REHASH_PASS" if is_ok else "REHASH_FAIL"

        desc = EVENT_CATALOG.get(
            event_code, f"Rehash finished with status '{status_raw}'."
        )
        if hash_val:
            desc = f"{desc} [Hash: {hash_val}]"

        return RehashAlertEvent(
            level_raw=status_raw,
            event_code=event_code,
            severity=severity,
            description=desc,
            orig_hash=hash_val if is_ok else "N/A",
            curr_hash=hash_val,
            raw_line=cleaned,
            hash_val=hash_val,
        )

    return None


# Control Protocol Command Constants
CMD_POLL = "::POLL::\n"
CMD_TAMPER = "::TAMPER::\n"
CMD_RESET_FIRMWARE = "::RESET_FIRMWARE::\n"
CMD_RECALIBRATE = "::RECALIBRATE_BASELINE::\n"