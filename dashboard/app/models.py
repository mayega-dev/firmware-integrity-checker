from __future__ import annotations

from datetime import datetime
from enum import Enum
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


SEVERITY_COLORS = {
    Severity.INFO: "#10B981",       # Emerald Green
    Severity.WARNING: "#F59E0B",    # Amber Yellow
    Severity.CRITICAL: "#EF4444",   # Crimson Red
    Severity.UNKNOWN: "#64748B",    # Slate Gray
}


class AlertEvent:
    """Represents a single parsed security alert / rehash event with full untruncated hashes."""

    def __init__(
        self,
        severity: Severity,
        event_code: str,
        description: str,
        orig_hash: str = "N/A",
        curr_hash: str = "N/A",
        raw_line: str = "",
    ):
        self.received_at = datetime.now()
        self.severity = severity
        self.event_code = event_code
        self.orig_hash = orig_hash
        self.curr_hash = curr_hash
        self.description = description
        self.raw_line = raw_line

    @classmethod
    def parse_raw_line(cls, raw_line: str) -> AlertEvent | None:
        """
        Parses serial telemetry protocol:
        ::ALERT:<SEVERITY>:<EVENT_CODE>|ORIG:<64_CHAR_HASH>|CURR:<64_CHAR_HASH>::
        """
        cleaned = raw_line.strip()
        if not (cleaned.startswith("::") and cleaned.endswith("::")):
            return None

        content = cleaned[2:-2]
        parts = content.split("|")
        meta = parts[0].split(":")

        if len(meta) < 2:
            return None

        sev_str = meta[1].upper()
        try:
            severity = Severity[sev_str]
        except KeyError:
            severity = Severity.UNKNOWN

        event_code = meta[2] if len(meta) > 2 else "UNKNOWN"

        kv_pairs = {}
        for part in parts[1:]:
            if ":" in part:
                k, v = part.split(":", 1)
                kv_pairs[k] = v

        orig_hash = kv_pairs.get("ORIG", "N/A")
        curr_hash = kv_pairs.get("CURR", "N/A")

        if event_code == "STATUS_SAFE":
            description = f"Pass | Baseline: {orig_hash} | Current: {curr_hash}"
        elif event_code == "FIRMWARE_TAMPERED":
            description = f"CRITICAL MISMATCH! Baseline: {orig_hash} != Current: {curr_hash}"
        elif event_code == "SYSTEM_RESTORED":
            description = f"Firmware Restored | Baseline: {orig_hash} | Current: {curr_hash}"
        else:
            description = f"{event_code} | Baseline: {orig_hash} | Current: {curr_hash}"

        return cls(
            severity=severity,
            event_code=event_code,
            description=description,
            orig_hash=orig_hash,
            curr_hash=curr_hash,
            raw_line=raw_line,
        )


class AlertLogModel(QAbstractTableModel):
    """Qt Table Model storing session audit logs with complete SHA-256 strings."""

    HEADERS = ["Time", "Severity", "Event", "Description"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[AlertEvent] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._events)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._events)):
            return None

        event = self._events[index.row()]
        col = index.column()
        role_val = int(role)

        if role_val == int(Qt.DisplayRole):
            if col == 0:
                return event.received_at.strftime("%H:%M:%S")
            elif col == 1:
                return event.severity.value
            elif col == 2:
                return event.event_code
            elif col == 3:
                return event.description

        elif role_val == int(Qt.ToolTipRole):
            return (
                f"Event: {event.event_code}\n"
                f"Baseline Hash: {event.orig_hash}\n"
                f"Current Hash:  {event.curr_hash}\n"
                f"Raw Protocol:  {event.raw_line}"
            )

        elif role_val == int(Qt.TextAlignmentRole):
            if col in (0, 1):
                return int(Qt.AlignCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)

        elif role_val == int(Qt.ForegroundRole):
            if col == 1:
                from PySide6.QtGui import QColor
                return QColor(SEVERITY_COLORS.get(event.severity, "#64748B"))

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and int(role) == int(Qt.DisplayRole):
            return self.HEADERS[section]
        return None

    def add_event(self, event: AlertEvent) -> None:
        self.beginInsertRows(QModelIndex(), len(self._events), len(self._events))
        self._events.append(event)
        self.endInsertRows()

    def append_raw_line(self, raw_line: str) -> AlertEvent | None:
        event = AlertEvent.parse_raw_line(raw_line)
        if event:
            self.add_event(event)
        return event

    def events(self) -> list[AlertEvent]:
        return list(self._events)

    def clear(self) -> None:
        self.beginResetModel()
        self._events.clear()
        self.endResetModel()