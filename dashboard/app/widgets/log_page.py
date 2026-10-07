from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.models import AlertLogModel

_CONTAINER_EXPORTS_DIR = Path("/data/exports")


class LogPage(QWidget):
    """
    Alert log view displaying full, un-truncated 64-character SHA-256 hashes in all table rows and CSV exports.
    """

    def __init__(self, log_model: AlertLogModel, parent=None):
        super().__init__(parent)
        self._log_model = log_model

        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(log_model)
        self._proxy.setFilterKeyColumn(-1)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        # ── Header Card ──────────────────────────────────────────────────────
        header_card = QFrame()
        header_card.setObjectName("headerCard")
        header_card.setStyleSheet("""
            QFrame#headerCard {
                background: #0B0F19;
                border: 1px solid #1E293B;
                border-left: 4px solid #38BDF8;
                border-radius: 10px;
            }
        """)
        header_lay = QVBoxLayout(header_card)
        header_lay.setContentsMargins(24, 20, 24, 20)
        header_lay.setSpacing(6)

        title = QLabel("Device Alert Log & Firmware Audit Trail")
        title.setStyleSheet("color: #F8FAFC; font-size: 20px; font-weight: 800; border: none;")

        subtitle = QLabel(
            "Complete immutable audit log recording complete 64-character baseline threshold SHA-256 hashes vs continuous runtime rehashes."
        )
        subtitle.setStyleSheet("color: #94A3B8; font-size: 15px; border: none;")
        header_lay.addWidget(title)
        header_lay.addWidget(subtitle)
        root.addWidget(header_card)

        # ── Content Card (Toolbar + Table) ───────────────────────────────────
        content_card = QFrame()
        content_card.setStyleSheet("QFrame { background: #0B0F19; border: 1px solid #1E293B; border-radius: 10px; }")
        cc_layout = QVBoxLayout(content_card)
        cc_layout.setContentsMargins(20, 20, 20, 20)
        cc_layout.setSpacing(16)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by complete 64-character hash, event code, or severity…")
        self.search_box.textChanged.connect(self._proxy.setFilterFixedString)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #070A10; color: #F8FAFC; border: 1px solid #334155;
                border-radius: 6px; padding: 8px 12px; font-size: 15px;
            }
            QLineEdit:focus { border-color: #38BDF8; }
        """)

        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All severities", "CRITICAL", "WARNING", "INFO"])
        self.severity_filter.currentTextChanged.connect(self._apply_severity_filter)
        self.severity_filter.setStyleSheet("""
            QComboBox {
                background: #070A10; color: #F8FAFC; border: 1px solid #334155;
                border-radius: 6px; padding: 8px 12px; font-size: 15px;
            }
        """)

        export_btn = QPushButton("Export CSV")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B; color: #F8FAFC; border: 1px solid #334155;
                border-radius: 6px; padding: 8px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #334155; border-color: #38BDF8; }
        """)
        export_btn.clicked.connect(self._export_csv)

        clear_btn = QPushButton("Clear Log")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #450A0A; color: #F87171; border: 1px solid #7F1D1D;
                border-radius: 6px; padding: 8px 16px; font-weight: 700;
            }
            QPushButton:hover { background: #7F1D1D; color: #FFFFFF; }
        """)
        clear_btn.clicked.connect(self._clear_log)

        toolbar.addWidget(self.search_box, 1)
        toolbar.addWidget(self.severity_filter)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(clear_btn)
        cc_layout.addLayout(toolbar)

        # ── QTableView Setup with Horizontal Scrolling for Full Hashes ───────
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #1E293B; color: #F8FAFC; font-family: 'JetBrains Mono', monospace;
                font-size: 15px; font-weight: 700; padding: 8px; border: none; border-bottom: 1px solid #334155;
            }
        """)

        self.table.setStyleSheet("""
            QTableView {
                background-color: #070A10; alternate-background-color: #0B0F19; color: #F8FAFC;
                gridline-color: #1E293B; border: 1px solid #334155; border-radius: 6px;
                font-family: 'JetBrains Mono', 'Courier New', monospace; font-size: 10px;
            }
            QTableView::item:selected { background-color: #1E293B; color: #38BDF8; }
        """)
        cc_layout.addWidget(self.table, 1)
        root.addWidget(content_card, 1)

    def _apply_severity_filter(self, text: str) -> None:
        if text == "All severities":
            self._proxy.setFilterRegularExpression("")
            self._proxy.setFilterKeyColumn(-1)
        else:
            self._proxy.setFilterKeyColumn(1)
            self._proxy.setFilterFixedString(text)

    def _clear_log(self) -> None:
        if QMessageBox.question(
            self, "Clear Log", "Clear all logged rehash events?", QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._log_model.clear()

    def _export_csv(self) -> None:
        events = self._log_model.events()
        if not events:
            QMessageBox.information(self, "Export CSV", "No log events available to export.")
            return

        default_name = f"firmware_audit_log_full_hashes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        default_dir = _CONTAINER_EXPORTS_DIR if _CONTAINER_EXPORTS_DIR.is_dir() else Path.home()
        default_path = str(default_dir / default_name)

        path, _ = QFileDialog.getSaveFileName(self, "Export Full Hashes", default_path, "CSV Files (*.csv)")
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "severity", "event_code", "baseline_hash", "current_hash", "description", "raw_payload"])
            for e in events:
                writer.writerow([
                    getattr(e, "received_at", datetime.now()).isoformat(timespec="seconds"),
                    getattr(e.severity, "value", str(e.severity)),
                    getattr(e, "event_code", "REHASH"),
                    getattr(e, "orig_hash", "N/A"),
                    getattr(e, "curr_hash", "N/A"),
                    getattr(e, "description", ""),
                    getattr(e, "raw_line", "")
                ])

        QMessageBox.information(self, "Export CSV", f"Exported {len(events)} events with complete 64-char hashes to:\n{path}")