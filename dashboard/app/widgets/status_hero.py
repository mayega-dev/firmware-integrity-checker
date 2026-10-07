from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.models import Severity

# Color & Label Mappings per Severity State
_STATE_TEXT = {
    Severity.INFO: ("SYSTEM NORMAL", "Firmware hash matched baseline.", QColor("#10B981")),
    Severity.WARNING: ("WARNING DETECTED", "Non-critical telemetry event.", QColor("#F59E0B")),
    Severity.CRITICAL: ("CRITICAL ALERT", "Firmware hash tamper detected!", QColor("#EF4444")),
    Severity.UNKNOWN: ("INITIALIZING", "Waiting for telemetry status frame...", QColor("#64748B")),
}


class StatusHero(QFrame):
    """
    Hero banner displaying real-time integrity status and device parameters with high-visibility typography.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)

        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(24, 18, 24, 18)

        # Status text column
        text_lay = QVBoxLayout()
        text_lay.setSpacing(6)

        self.lbl_status = QLabel("INITIALIZING")
        self.lbl_status.setFont(QFont("JetBrains Mono", 18, QFont.Weight.Bold))

        self.lbl_subtext = QLabel("Waiting for telemetry status frame...")
        self.lbl_subtext.setWordWrap(True)
        self.lbl_subtext.setStyleSheet(
            "color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600;"
        )

        text_lay.addWidget(self.lbl_status)
        text_lay.addWidget(self.lbl_subtext)
        main_lay.addLayout(text_lay, 1)

        # Device info badge on the right
        self.lbl_device = QLabel("")
        self.lbl_device.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_device.setStyleSheet("""
            color: #94A3B8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 600;
        """)
        main_lay.addWidget(self.lbl_device)

        self.set_severity(Severity.UNKNOWN)

    def set_severity(self, severity: Severity, custom_subtext: str | None = None) -> None:
        title, default_sub, color = _STATE_TEXT.get(
            severity,
            ("UNKNOWN", "Status unknown", QColor("#64748B"))
        )

        subtext = custom_subtext if custom_subtext is not None else default_sub
        hex_color = color.name()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #0B0F19;
                border: 2px solid {hex_color};
                border-radius: 10px;
            }}
        """)

        self.lbl_status.setText(title)
        self.lbl_status.setStyleSheet(
            f"color: {hex_color}; border: none; background: transparent; font-size: 18px; font-weight: 800;"
        )

        self.lbl_subtext.setText(subtext)
        self.lbl_subtext.setStyleSheet(
            "color: #F8FAFC; font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; border: none; background: transparent;"
        )

    def set_device_info(self, info: str) -> None:
        self.lbl_device.setText(info)