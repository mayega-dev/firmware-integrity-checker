from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Serial protocol commands
CMD_POLL = "::POLL::"
CMD_TAMPER = "::TAMPER::"
CMD_REHASH = "::REHASH::"
CMD_RESET_FIRMWARE = "::RESET_FIRMWARE::"


class ConsolePage(QWidget):
    """
    Professional-grade raw UART traffic viewer and command execution terminal
    supporting live stream inspection, manual rehash triggers, and firmware reset commands.
    """

    command_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

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

        title = QLabel("Device Console & Serial Command Dispatcher")
        title.setObjectName("pageTitle")
        title.setStyleSheet("""
            color: #F8FAFC;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 20px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)

        subtitle = QLabel(
            "Live raw UART stream telemetry inspection, manual firmware rehashing, and firmware restoration controls."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setStyleSheet("""
            color: #94A3B8;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            background: transparent;
            border: none;
        """)
        header_lay.addWidget(title)
        header_lay.addWidget(subtitle)
        root.addWidget(header_card)

        # ── Console View Card ────────────────────────────────────────────────
        console_container = QFrame()
        console_container.setStyleSheet("""
            QFrame {
                background: #0B0F19;
                border: 1px solid #1E293B;
                border-radius: 10px;
            }
        """)
        cc_layout = QVBoxLayout(console_container)
        cc_layout.setContentsMargins(20, 20, 20, 20)
        cc_layout.setSpacing(12)

        console_header = QLabel("UART STREAM OUTPUT & HASH TELEMETRY")
        console_header.setStyleSheet("""
            color: #94A3B8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.2px;
            background: transparent;
            border: none;
        """)
        cc_layout.addWidget(console_header)

        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(10000)
        self.console.setStyleSheet("""
            QPlainTextEdit {
                background-color: #040609;
                color: #38BDF8;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 12px;
                font-family: 'JetBrains Mono', monospace;
                font-size: 12px;
                selection-background-color: #38BDF8;
                selection-color: #040609;
            }
        """)
        cc_layout.addWidget(self.console, 1)

        # ── Controls Bottom Bar ──────────────────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.autoscroll_check = QCheckBox("Auto-scroll")
        self.autoscroll_check.setChecked(True)
        self.autoscroll_check.setCursor(Qt.PointingHandCursor)
        self.autoscroll_check.setStyleSheet("""
            QCheckBox {
                color: #F8FAFC;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 13px;
                font-weight: 600;
                background: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #334155;
                border-radius: 4px;
                background: #070A10;
            }
            QCheckBox::indicator:checked {
                background: #38BDF8;
                border-color: #38BDF8;
            }
        """)

        clear_btn = QPushButton("Clear Console")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                border-color: #38BDF8;
            }
        """)
        clear_btn.clicked.connect(self.console.clear)

        rehash_btn = QPushButton("Send ::REHASH::")
        rehash_btn.setCursor(Qt.PointingHandCursor)
        rehash_btn.setToolTip("Triggers an immediate ESP32 firmware rehash calculation over serial.")
        rehash_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #10B981;
            }
        """)
        rehash_btn.clicked.connect(self._send_rehash_command)

        poll_btn = QPushButton("Send ::POLL::")
        poll_btn.setCursor(Qt.PointingHandCursor)
        poll_btn.setToolTip("Trigger an immediate verification sweep on the connected ESP32 device.")
        poll_btn.setStyleSheet("""
            QPushButton {
                background: #0284C7;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #38BDF8;
                color: #070A10;
            }
        """)
        poll_btn.clicked.connect(self._send_poll_command)

        tamper_btn = QPushButton("Send ::TAMPER:: (Debug)")
        tamper_btn.setCursor(Qt.PointingHandCursor)
        tamper_btn.setToolTip("Triggers a simulated hardware tampering event on debug builds.")
        tamper_btn.setStyleSheet("""
            QPushButton {
                background: #450A0A;
                color: #F87171;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 8px 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #7F1D1D;
                border-color: #F87171;
                color: #FFFFFF;
            }
        """)
        tamper_btn.clicked.connect(self._confirm_and_send_tamper)

        reset_btn = QPushButton("Reset Firmware")
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setToolTip("Dispatches ::RESET_FIRMWARE:: to restore baseline hardware image.")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #DC2626;
                color: #FFFFFF;
                border: 1px solid #EF4444;
                border-radius: 6px;
                padding: 8px 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #EF4444;
            }
        """)
        reset_btn.clicked.connect(self._confirm_and_send_reset)

        bottom.addWidget(self.autoscroll_check)
        bottom.addStretch(1)
        bottom.addWidget(clear_btn)
        bottom.addWidget(rehash_btn)
        bottom.addWidget(poll_btn)
        bottom.addWidget(tamper_btn)
        bottom.addWidget(reset_btn)

        cc_layout.addLayout(bottom)
        root.addWidget(console_container, 1)

    def _send_rehash_command(self) -> None:
        self.command_requested.emit(CMD_REHASH)

    def _send_poll_command(self) -> None:
        self.command_requested.emit(CMD_POLL)

    def _confirm_and_send_tamper(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Send ::TAMPER::",
            "Inject a simulated tamper signal into the serial stream?\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.command_requested.emit(CMD_TAMPER)

    def _confirm_and_send_reset(self) -> None:
        reply = QMessageBox.critical(
            self,
            "Reset ESP32 Firmware",
            "This will dispatch the ::RESET_FIRMWARE:: command to restore the golden firmware "
            "image on the connected device and reset baseline hashes.\n\nAre you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.command_requested.emit(CMD_RESET_FIRMWARE)

    def append_line(self, line: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.console.appendPlainText(f"[{timestamp}] {line}")
        if self.autoscroll_check.isChecked():
            scrollbar = self.console.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())