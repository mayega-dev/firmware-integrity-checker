from __future__ import annotations

import json
import re
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.models import AlertEvent, AlertLogModel, Severity
from app.protocol import DeviceStatus
from app.widgets.stat_card import StatCard
from app.widgets.status_hero import StatusHero
from app.widgets.timeline import IntegrityTimeline

SHA256_REGEX = re.compile(r"\b[a-fA-F0-9]{64}\b")


class DashboardPage(QWidget):
    """
    Telemetry C2 dashboard displaying full 64-character SHA-256 hashes on every continuous check.
    Handles parsed AlertEvent/DeviceStatus objects, SimulatorLink, and raw serial line strings.
    """

    navigate_requested = Signal(str)
    reset_firmware_requested = Signal()
    send_command_requested = Signal(str)

    def __init__(self, log_model: AlertLogModel, parent=None):
        super().__init__(parent)
        self._log_model = log_model
        self._total_checks = 0
        self._critical_count = 0
        self._session_start: datetime | None = None
        self._device_status: DeviceStatus | None = None
        self._connected_port: str = ""
        self._connected_baud: int = 115200

        self._baseline_hash: str | None = None
        self._latest_hash: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        # ── Header Card ──────────────────────────────────────────────────────
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: #0B0F19;
                border: 1px solid #1E293B;
                border-left: 4px solid #38BDF8;
                border-radius: 10px;
            }
        """)
        header_lay = QVBoxLayout(header_card)
        header_lay.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Telemetry Command & Control — Firmware Integrity Monitor")
        title.setStyleSheet("color: #F8FAFC; font-size: 20px; font-weight: 800; border: none;")

        subtitle = QLabel(
            "Continuous automated firmware rehashing displaying complete untruncated 64-character baseline vs runtime SHA-256 hashes."
        )
        subtitle.setStyleSheet("color: #94A3B8; font-size: 13px; border: none;")

        header_lay.addWidget(title)
        header_lay.addWidget(subtitle)
        root.addWidget(header_card)

        # ── Hero Status Banner ───────────────────────────────────────────────
        self.hero = StatusHero()
        root.addWidget(self.hero)

        # ── Full Baseline & Current Hash Monitor Panel ───────────────────────
        hash_panel = QFrame()
        hash_panel.setStyleSheet("QFrame { background: #0B0F19; border: 1px solid #1E293B; border-radius: 10px; }")
        hash_lay = QVBoxLayout(hash_panel)
        hash_lay.setContentsMargins(20, 16, 20, 16)
        hash_lay.setSpacing(10)

        hash_header_lay = QHBoxLayout()
        hash_title = QLabel("FIRMWARE HASH THRESHOLD MONITOR (FULL 64-CHAR SHA-256)")
        hash_title.setStyleSheet("color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 700;")
        hash_header_lay.addWidget(hash_title)
        hash_header_lay.addStretch(1)

        self.btn_reset_baseline = QPushButton("Re-calibrate Baseline Hash")
        self.btn_reset_baseline.setCursor(Qt.PointingHandCursor)
        self.btn_reset_baseline.setStyleSheet("""
            QPushButton {
                background: #1E293B; color: #94A3B8; border: 1px solid #334155;
                border-radius: 5px; padding: 4px 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #334155; color: #F8FAFC; border-color: #38BDF8; }
        """)
        self.btn_reset_baseline.clicked.connect(self.recalibrate_baseline)
        hash_header_lay.addWidget(self.btn_reset_baseline)
        hash_lay.addLayout(hash_header_lay)

        # Baseline Hash Row
        baseline_row = QHBoxLayout()
        lbl_base = QLabel("Baseline Threshold:")
        lbl_base.setFixedWidth(160)
        lbl_base.setStyleSheet("color: #94A3B8; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;")

        self.lbl_baseline_hash = QLabel("NOT ESTABLISHED (Awaiting initial ESP32 rehash)")
        self.lbl_baseline_hash.setWordWrap(True)
        self.lbl_baseline_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_baseline_hash.setStyleSheet("""
            color: #10B981; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
            background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
        """)
        baseline_row.addWidget(lbl_base)
        baseline_row.addWidget(self.lbl_baseline_hash, 1)
        hash_lay.addLayout(baseline_row)

        # Current Hash Row
        current_row = QHBoxLayout()
        lbl_curr = QLabel("Latest Rehash:")
        lbl_curr.setFixedWidth(160)
        lbl_curr.setStyleSheet("color: #94A3B8; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;")

        self.lbl_current_hash = QLabel("–")
        self.lbl_current_hash.setWordWrap(True)
        self.lbl_current_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_current_hash.setStyleSheet("""
            color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
            background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
        """)
        current_row.addWidget(lbl_curr)
        current_row.addWidget(self.lbl_current_hash, 1)
        hash_lay.addLayout(current_row)

        root.addWidget(hash_panel)

        # ── Stat Cards ───────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self.card_checks = StatCard("Total Checks", "0")
        self.card_alerts = StatCard("Critical Alerts", "0")
        self.card_uptime = StatCard("Session Uptime", "00:00:00")
        self.card_firmware = StatCard("Firmware Version", "–")
        for card in (self.card_checks, self.card_alerts, self.card_uptime, self.card_firmware):
            stats_row.addWidget(card)
        root.addLayout(stats_row)

        self.timeline = IntegrityTimeline()
        root.addWidget(self.timeline)

        # ── Table View ───────────────────────────────────────────────────────
        table_container = QFrame()
        table_container.setStyleSheet("QFrame { background: #0B0F19; border: 1px solid #1E293B; border-radius: 10px; }")
        tc_layout = QVBoxLayout(table_container)
        tc_layout.setContentsMargins(20, 20, 20, 20)

        recent_label = QLabel("RECENT SECURITY EVENTS & REHASH AUDIT LOG")
        recent_label.setStyleSheet("color: #94A3B8; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 700;")
        tc_layout.addWidget(recent_label)

        self.recent_table = QTableView()
        self.recent_table.setModel(log_model)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QTableView.SelectRows)
        self.recent_table.setEditTriggers(QTableView.NoEditTriggers)
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.recent_table.setMinimumHeight(220)

        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.recent_table.setColumnWidth(0, 90)
        self.recent_table.setColumnWidth(1, 100)
        self.recent_table.setColumnWidth(2, 180)

        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #1E293B; color: #F8FAFC; font-family: 'JetBrains Mono', monospace;
                font-size: 12px; font-weight: 700; padding: 8px; border: none; border-bottom: 1px solid #334155;
            }
        """)

        self.recent_table.setStyleSheet("""
            QTableView {
                background-color: #070A10; alternate-background-color: #0B0F19; color: #F8FAFC;
                gridline-color: #1E293B; border: 1px solid #334155; border-radius: 6px;
                font-family: 'JetBrains Mono', monospace; font-size: 12px;
            }
        """)

        tc_layout.addWidget(self.recent_table)
        root.addWidget(table_container, 1)

        # ── Footer ───────────────────────────────────────────────────────────
        footer_card = QFrame()
        footer_card.setStyleSheet("QFrame { background: #0B0F19; border: 1px solid #1E293B; border-radius: 8px; }")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(20, 14, 20, 14)

        self.footer_info = QLabel("Disconnected — No Active Telemetry Feed")
        self.footer_info.setStyleSheet("color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 600;")

        self.btn_reset_firmware = QPushButton("Reset / Restore ESP32 Firmware")
        self.btn_reset_firmware.setCursor(Qt.PointingHandCursor)
        self.btn_reset_firmware.setStyleSheet("""
            QPushButton {
                background: #DC2626; color: #FFFFFF; border: 1px solid #EF4444;
                border-radius: 6px; padding: 6px 14px; font-weight: 700; font-size: 12px;
            }
            QPushButton:hover { background: #EF4444; }
        """)
        self.btn_reset_firmware.clicked.connect(self.on_reset_firmware_clicked)

        view_log_btn = QPushButton("View Complete Audit Log →")
        view_log_btn.setCursor(Qt.PointingHandCursor)
        view_log_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B; color: #F8FAFC; border: 1px solid #334155;
                border-radius: 6px; padding: 6px 14px; font-weight: 700; font-size: 12px;
            }
            QPushButton:hover { background: #334155; border-color: #38BDF8; color: #38BDF8; }
        """)
        view_log_btn.clicked.connect(lambda: self.navigate_requested.emit("log"))

        footer_layout.addWidget(self.footer_info)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_reset_firmware)
        footer_layout.addWidget(view_log_btn)
        root.addWidget(footer_card)

        self._uptime_timer = QTimer(self)
        self._uptime_timer.setInterval(1000)
        self._uptime_timer.timeout.connect(self.tick_uptime)
        self._uptime_timer.start()

    def tick_uptime(self) -> None:
        if self._session_start is None:
            return
        elapsed = datetime.now() - self._session_start
        total_seconds = int(elapsed.total_seconds())
        h, rem = divmod(total_seconds, 3600)
        m, s = divmod(rem, 60)
        self.card_uptime.set_value(f"{h:02d}:{m:02d}:{s:02d}")

    def reset_session_stats(self) -> None:
        self._total_checks = 0
        self._critical_count = 0
        self._baseline_hash = None
        self._latest_hash = None
        self.card_checks.set_value("0")
        self.card_alerts.set_value("0")
        self.card_firmware.set_value("–")
        self.lbl_baseline_hash.setText("NOT ESTABLISHED (Awaiting initial ESP32 rehash)")
        self.lbl_baseline_hash.setStyleSheet("""
            color: #10B981; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
            background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
        """)
        self.lbl_current_hash.setText("–")
        self.lbl_current_hash.setStyleSheet("""
            color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
            background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
        """)
        self.timeline.clear()

    def on_connected(self, port: str = "", baud: int = 115200) -> None:
        self._session_start = datetime.now()
        self._connected_port = port
        self._connected_baud = baud

        if port == "__SIMULATE__":
            self.footer_info.setText("Simulation Mode Active — Generating Synthetic Telemetry")
            self.hero.set_severity(Severity.INFO, "Simulation Mode Active - listening for telemetry stream.")
        else:
            port_str = f"{port} @ {baud} baud" if port else "Serial UART"
            self.footer_info.setText(f"Secure UART Telemetry Feed Active on {port_str}")
            self.hero.set_severity(Severity.INFO, "Connected - listening for ESP32 telemetry frames...")

    def on_disconnected(self, reason: str = "") -> None:
        self._session_start = None
        self._device_status = None
        self._connected_port = ""
        self.footer_info.setText("Disconnected — No Active Telemetry Feed")
        self.hero.set_severity(Severity.UNKNOWN, reason or "Disconnected.")
        self.hero.set_device_info("")

    def on_line_received(self, line: str) -> None:
        self.process_raw_telemetry(line)

    def process_raw_telemetry(self, raw_input: str) -> None:
        """
        Handles NON-frame lines only. ::STATUS::/::ALERT::/::REHASH:: frames are
        parsed once in DeviceLink and delivered through on_status / on_alert /
        on_hash_frame, so they are skipped here (otherwise every check would be
        counted twice, and ESP_LOG lines that happen to print a hash would
        masquerade as extra checks).
        """
        if not raw_input or not raw_input.strip():
            return

        text = raw_input.strip()

        if "::STATUS:" in text or "::ALERT:" in text or "::REHASH:" in text:
            return

        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
            except Exception:
                return
            fw = data.get("fw_version") or data.get("version") or data.get("fw")
            if fw:
                self.card_firmware.set_value(str(fw))
                self.hero.set_device_info(f"ESP32 Hardware\nfw {fw}")
            curr_hash = data.get("hash") or data.get("curr_hash") or data.get("sha256")
            orig_hash = data.get("orig_hash") or data.get("baseline")
            if curr_hash:
                self.on_rehash(str(curr_hash), str(orig_hash) if orig_hash else None)

    def on_hash_frame(self, hash_val: str, status: str) -> None:
        """::REHASH:<PASS|FAIL>:<hash>:: - refresh the hash panel only."""
        self.on_rehash(hash_val, None, record_event=False)

    def on_status(self, status: DeviceStatus) -> None:
        self._device_status = status
        fw_ver = getattr(status, "fw_version", "1.0.0")
        self.card_firmware.set_value(fw_ver)
        mode_prefix = "[Simulated] " if self._connected_port == "__SIMULATE__" else ""
        hw_rev = getattr(status, "hardware_revision", "ESP32")
        self.hero.set_device_info(f"{mode_prefix}{hw_rev}\nfw {fw_ver}")

    def on_alert(self, event: AlertEvent) -> None:
        try:
            sev = getattr(event, "severity", Severity.INFO)
            self._total_checks += 1
            if sev == Severity.CRITICAL:
                self._critical_count += 1

            self.card_checks.set_value(str(self._total_checks))
            self.card_alerts.set_value(str(self._critical_count))
            self.timeline.add_point(sev)

            orig = getattr(event, "orig_hash", None)
            curr = getattr(event, "curr_hash", None)
            if curr and curr != "N/A" and SHA256_REGEX.fullmatch(curr.strip()):
                self.on_rehash(curr, orig, record_event=False)
            elif sev == Severity.CRITICAL:
                self.hero.set_severity(Severity.CRITICAL, event.description)

            if hasattr(self._log_model, 'add_event'):
                self._log_model.add_event(event)

            QTimer.singleShot(0, self.recent_table.scrollToBottom)
        except Exception as e:
            print(f"[ERROR] Processing alert: {e}")

    def on_rehash(self, current_hash: str, orig_hash: str | None = None, record_event: bool = True) -> None:
        if not current_hash:
            return

        current_hash = current_hash.strip()
        if not SHA256_REGEX.fullmatch(current_hash):
            return
        self._latest_hash = current_hash
        self.lbl_current_hash.setText(current_hash)

        if self._baseline_hash is None:
            self._baseline_hash = orig_hash.strip() if orig_hash and orig_hash != "N/A" else current_hash
            self.lbl_baseline_hash.setText(self._baseline_hash)
            self.hero.set_severity(
                Severity.INFO,
                f"Baseline Established: {self._baseline_hash}"
            )

        if current_hash != self._baseline_hash:
            self.lbl_current_hash.setStyleSheet("""
                color: #EF4444; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
                background: #2A0808; border: 1px solid #EF4444; border-radius: 4px; padding: 6px 10px;
            """)
            self.hero.set_severity(
                Severity.CRITICAL,
                f"FIRMWARE MISMATCH! Baseline: {self._baseline_hash} != Current: {current_hash}"
            )
            if record_event:
                self._record_rehash_event(Severity.CRITICAL, "Firmware hash mismatch detected during runtime check.")
        else:
            self.lbl_current_hash.setStyleSheet("""
                color: #10B981; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
                background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
            """)
            self.hero.set_severity(
                Severity.INFO,
                f"Integrity Normal — Baseline: {self._baseline_hash} | Current: {current_hash}"
            )
            if record_event:
                self._record_rehash_event(Severity.INFO, "Routine firmware SHA-256 integrity rehash verified.")

    def _record_rehash_event(self, severity: Severity, message: str) -> None:
        try:
            self._total_checks += 1
            if severity == Severity.CRITICAL:
                self._critical_count += 1

            self.card_checks.set_value(str(self._total_checks))
            self.card_alerts.set_value(str(self._critical_count))
            self.timeline.add_point(severity)

            sev_name = severity.name if hasattr(severity, 'name') else 'INFO'
            code = "FIRMWARE_TAMPERED" if severity == Severity.CRITICAL else "STATUS_SAFE"
            raw_line = f"::ALERT:{sev_name}:{code}|ORIG:{self._baseline_hash or 'N/A'}|CURR:{self._latest_hash or 'N/A'}::"

            event = None
            if hasattr(AlertEvent, 'parse_raw_line'):
                event = AlertEvent.parse_raw_line(raw_line)

            if event is None:
                event = AlertEvent(
                    severity=severity,
                    event_code=code,
                    description=message,
                    orig_hash=self._baseline_hash or "N/A",
                    curr_hash=self._latest_hash or "N/A",
                    raw_line=raw_line,
                )

            if event and hasattr(self._log_model, 'add_event'):
                self._log_model.add_event(event)

            QTimer.singleShot(0, self.recent_table.scrollToBottom)
        except Exception as e:
            print(f"[ERROR] Failed to record rehash event: {e}")

    def recalibrate_baseline(self) -> None:
        try:
            if not self._latest_hash:
                return

            self._baseline_hash = self._latest_hash
            self.lbl_baseline_hash.setText(self._baseline_hash)
            self.lbl_baseline_hash.setStyleSheet("""
                color: #10B981; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
                background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
            """)
            self.lbl_current_hash.setStyleSheet("""
                color: #10B981; font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 700;
                background: #070A10; border: 1px solid #1E293B; border-radius: 4px; padding: 6px 10px;
            """)

            msg = f"[BASELINE RE-CALIBRATED] Threshold Hash set to: {self._baseline_hash}"
            self.hero.set_severity(Severity.INFO, f"Baseline re-calibrated to: {self._baseline_hash}")

            self.send_command_requested.emit("::RECALIBRATE_BASELINE::")
            self._record_rehash_event(Severity.INFO, msg)
        except Exception as e:
            print(f"[ERROR] Failed during recalibrate_baseline: {e}")

    def on_reset_firmware_clicked(self) -> None:
        try:
            self.send_command_requested.emit("::RESET_FIRMWARE::")
            self.reset_firmware_requested.emit()

            reset_msg = f"[FIRMWARE RESET INITIATED] Previous Baseline: {self._baseline_hash or 'None'}"
            self._baseline_hash = None
            self.lbl_baseline_hash.setText("RESETTING... Awaiting new baseline hash")
            self._record_rehash_event(Severity.WARNING, reset_msg)
            self.hero.set_severity(Severity.WARNING, "Firmware Reset Initiated - Waiting for hardware baseline...")
        except Exception as e:
            print(f"[ERROR] Failed during on_reset_firmware_clicked: {e}")