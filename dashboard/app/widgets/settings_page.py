from __future__ import annotations

import glob
import os
import platform
import subprocess
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.device_link import available_ports

COMMON_BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
PORT_REFRESH_INTERVAL_MS = 2500


class SettingsPage(QWidget):
    """
    Hardware serial configuration panel supporting dropdown selection and custom manual entry
    of hardware ports (USB/UART), virtual socat pseudo-terminals (/dev/pts, /tmp/vser*),
    and simulation mode across Linux, WSL, macOS, and Windows.
    """

    connect_requested = Signal(str, int)  # port, baud ("__SIMULATE__" for simulation)
    disconnect_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_connected = False

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

        title = QLabel("Hardware & Connection Settings")
        title.setObjectName("pageTitle")
        title.setStyleSheet("""
            color: #F8FAFC;
            font-size: 20px;
            font-weight: 800;
            background: transparent;
            border: none;
        """)

        subtitle = QLabel(
            "Select or type the active serial port from detected ESP32 hardware, USB serial bridges, "
            "Docker mounts, virtual terminals, or simulation scripts."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            color: #94A3B8;
            font-size: 13px;
            background: transparent;
            border: none;
        """)
        header_lay.addWidget(title)
        header_lay.addWidget(subtitle)
        root.addWidget(header_card)

        # ── Configuration Form Card ──────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("""
            QFrame#card {
                background: #0B0F19;
                border: 1px solid #1E293B;
                border-radius: 10px;
            }
        """)
        form_wrap = QVBoxLayout(card)
        form_wrap.setContentsMargins(24, 24, 24, 24)
        form_wrap.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        form_label_style = """
            color: #F8FAFC;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            background: transparent;
            border: none;
        """

        input_widget_style = """
            QComboBox {
                background: #070A10;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                border-color: #38BDF8;
            }
            QComboBox QAbstractItemView {
                background-color: #0B0F19;
                color: #F8FAFC;
                selection-background-color: #1E293B;
                selection-color: #38BDF8;
                border: 1px solid #334155;
            }
            QComboBox::drop-down {
                border: none;
            }
        """

        # Serial Port Selection Row (Editable dropdown allows custom typed paths)
        port_row = QHBoxLayout()
        port_row.setSpacing(10)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(340)
        self.port_combo.setStyleSheet(input_widget_style)
        self.port_combo.currentIndexChanged.connect(self._on_port_changed)
        if self.port_combo.lineEdit():
            self.port_combo.lineEdit().textChanged.connect(self._on_port_changed)

        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #334155;
                border-color: #38BDF8;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(refresh_btn)

        port_label = QLabel("Serial Port")
        port_label.setStyleSheet(form_label_style)
        form.addRow(port_label, port_row)

        # Port Status Summary Label
        self.port_summary_label = QLabel("")
        self.port_summary_label.setWordWrap(True)
        self.port_summary_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: none;")
        form.addRow("", self.port_summary_label)

        # Baud Rate Row
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(b) for b in COMMON_BAUD_RATES])
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setStyleSheet(input_widget_style)

        baud_label = QLabel("Baud Rate")
        baud_label.setStyleSheet(form_label_style)
        form.addRow(baud_label, self.baud_combo)

        # Simulation Mode Checkbox
        self.simulate_check = QCheckBox("Simulation mode (standalone UI testing)")
        self.simulate_check.setCursor(Qt.PointingHandCursor)
        self.simulate_check.setStyleSheet("""
            QCheckBox {
                color: #38BDF8;
                font-size: 13px;
                font-weight: 700;
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
        self.simulate_check.toggled.connect(self._on_simulate_toggled)
        form.addRow("", self.simulate_check)

        form_wrap.addLayout(form)

        # ── Action Buttons Row ───────────────────────────────────────────────
        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.connect_btn = QPushButton("Connect Device")
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #0284C7;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #38BDF8;
                color: #070A10;
            }
            QPushButton:disabled {
                background: #1E293B;
                color: #64748B;
            }
        """)
        self.connect_btn.clicked.connect(self._on_connect_clicked)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setCursor(Qt.PointingHandCursor)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #F87171;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #7F1D1D;
                border-color: #F87171;
                color: #FFFFFF;
            }
            QPushButton:disabled {
                background: #0B0F19;
                color: #334155;
                border-color: #1E293B;
            }
        """)
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)

        button_row.addWidget(self.connect_btn)
        button_row.addWidget(self.disconnect_btn)
        button_row.addStretch(1)
        form_wrap.addLayout(button_row)

        root.addWidget(card)
        root.addStretch(1)

        self.refresh_ports()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(PORT_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start()

    def _get_clean_port_path(self) -> str:
        """Extracts and cleans the currently selected or custom-entered port path."""
        data = self.port_combo.currentData()
        if data and isinstance(data, str) and not data.startswith("──"):
            return data.strip()

        text = self.port_combo.currentText().strip()
        if not text or text.startswith("──"):
            return ""

        if " (" in text:
            text = text.split(" (")[0].strip()

        if text.startswith("──"):
            return ""

        return text

    def _add_category_header(self, text: str) -> None:
        """Adds an unselectable section header item."""
        self.port_combo.addItem(text, None)
        model = self.port_combo.model()
        item = model.item(self.port_combo.count() - 1)
        if isinstance(item, QStandardItem):
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)

    def refresh_ports(self) -> None:
        """
        Scans for physical serial ports, USB-to-serial adapters, Docker mounts,
        and virtual simulation terminals across Linux, WSL, macOS, and Windows.
        Filters out dummy unbacked Linux kernel ttyS ports.
        """
        if self._is_connected:
            return

        previous_device = self._get_clean_port_path()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()

        # 1. Fetch hardware serial ports
        ports = available_ports()
        known_devices = {p.device for p in ports}

        # 2. Additional platform-specific virtual and USB serial scans
        extra_candidates = set()
        sys_platform = platform.system().lower()

        if "linux" in sys_platform or "wsl" in platform.release().lower():
            extra_candidates.update(
                glob.glob("/dev/ttyUSB*")
                + glob.glob("/dev/ttyACM*")
                + glob.glob("/dev/pts/[0-9]*")
                + glob.glob("/tmp/tty*")
                + glob.glob("/tmp/vser*")
            )
        elif "darwin" in sys_platform:  # macOS
            extra_candidates.update(
                glob.glob("/dev/tty.usbserial*")
                + glob.glob("/dev/tty.usbmodem*")
                + glob.glob("/dev/cu.usb*")
            )

        esp_ports = []
        other_hw_ports = []

        for p in ports:
            dev_path = p.device
            if dev_path.startswith("/dev/ttyS"):
                dev_name = os.path.basename(dev_path)
                sys_device = f"/sys/class/tty/{dev_name}/device"
                if os.path.exists("/sys/class/tty") and not os.path.exists(sys_device):
                    continue

            is_esp = getattr(p, "is_likely_esp32", False) or any(
                k in dev_path.lower() for k in ["usb", "acm", "cp210", "ch340", "ftdi", "esp"]
            )
            if is_esp:
                esp_ports.append(p)
            else:
                other_hw_ports.append(p)

        virtual_ports = sorted([v for v in extra_candidates if v not in known_devices])

        if not esp_ports and not other_hw_ports and not virtual_ports:
            self.port_summary_label.setText(
                "No active hardware serial ports found. Enter a custom port path or enable Simulation mode."
            )
            self.port_summary_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: none;")
            self.port_combo.setEditText("")
            self.port_combo.blockSignals(False)
            self._on_port_changed()
            return

        if esp_ports:
            self._add_category_header("── ESP32 & USB Serial Hardware ──")
            for p in esp_ports:
                reason = getattr(p, "match_reason", getattr(p, "description", "USB Serial Device"))
                self.port_combo.addItem(f"{p.device} ({reason})", p.device)

        if other_hw_ports:
            self._add_category_header("── Hardware Serial Ports ──")
            for p in other_hw_ports:
                desc = getattr(p, "description", "Serial Interface")
                self.port_combo.addItem(f"{p.device} ({desc})", p.device)

        if virtual_ports:
            self._add_category_header("── Simulation / Virtual Ports ──")
            for vport in virtual_ports:
                self.port_combo.addItem(f"{vport} (Virtual / socat)", vport)

        self.port_combo.blockSignals(False)

        if previous_device:
            idx = self.port_combo.findData(previous_device)
            if idx >= 0:
                self.port_combo.setCurrentIndex(idx)
                self.port_combo.setEditText(previous_device)
            else:
                self.port_combo.setEditText(previous_device)
        else:
            self._select_first_valid_port()

        self._on_port_changed()
        self._on_simulate_toggled(self.simulate_check.isChecked())

    def _select_first_valid_port(self) -> None:
        """Finds and selects the first valid hardware port item in the dropdown."""
        for i in range(self.port_combo.count()):
            data = self.port_combo.itemData(i)
            if data and isinstance(data, str) and not data.startswith("──"):
                self.port_combo.setCurrentIndex(i)
                self.port_combo.setEditText(data)
                break

    def _on_port_changed(self) -> None:
        """Updates summary banner and enables connection button for valid inputs."""
        if self._is_connected:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            return

        if self.simulate_check.isChecked():
            self.port_summary_label.setText("Simulation mode active — Synthetic data stream enabled.")
            self.port_summary_label.setStyleSheet("color: #38BDF8; font-size: 12px; border: none;")
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            return

        port = self._get_clean_port_path()
        if not port or port.startswith("──"):
            self.port_summary_label.setText("Please select or enter a valid serial port path.")
            self.port_summary_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: none;")
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(False)
            return

        self.port_summary_label.setText(f"Target serial port: {port}")
        self.port_summary_label.setStyleSheet("color: #38BDF8; font-size: 12px; border: none;")
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def _auto_refresh(self) -> None:
        if not self._is_connected and not self.port_combo.hasFocus():
            self.refresh_ports()

    def _on_simulate_toggled(self, checked: bool) -> None:
        if not self._is_connected:
            self.port_combo.setEnabled(not checked)
            self.baud_combo.setEnabled(not checked)
        self._on_port_changed()

    def _on_connect_clicked(self) -> None:
        """Verifies serial permissions and emits connection request."""
        if self.simulate_check.isChecked():
            self.set_connected_ui_state(True)
            self.connect_requested.emit("__SIMULATE__", 0)
            return

        port = self._get_clean_port_path()
        if not port or port.startswith("──"):
            return

        # Pre-flight permission fix attempt on Linux/macOS
        if port.startswith("/dev/"):
            if os.path.exists(port) and not os.access(port, os.R_OK | os.W_OK):
                try:
                    subprocess.run(["chmod", "666", port], check=False, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

            if os.path.exists(port) and not os.access(port, os.R_OK | os.W_OK):
                self.port_summary_label.setText(
                    f"Permission Denied accessing {port}. Run 'sudo chmod 666 {port}' or 'sudo usermod -aG dialout $USER'."
                )
                self.port_summary_label.setStyleSheet("color: #F87171; font-size: 12px; font-weight: bold; border: none;")
                self.set_connected_ui_state(False)
                return

        baud = int(self.baud_combo.currentText())
        self.set_connected_ui_state(True)
        self.connect_requested.emit(port, baud)

    def _on_disconnect_clicked(self) -> None:
        self.set_connected_ui_state(False)
        self.disconnect_requested.emit()

    def set_connected_ui_state(self, connected: bool, error_message: str = "") -> None:
        """Updates UI elements based on connection status or error state."""
        self._is_connected = connected

        if connected:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.simulate_check.setEnabled(False)
            self.port_summary_label.setText("Device connected successfully.")
            self.port_summary_label.setStyleSheet("color: #4ADE80; font-size: 12px; border: none;")
        else:
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.simulate_check.setEnabled(True)
            self.port_combo.setEnabled(not self.simulate_check.isChecked())
            self.baud_combo.setEnabled(not self.simulate_check.isChecked())
            self.port_summary_label.setText("Disconnected.")
            self.port_summary_label.setStyleSheet("color: #94A3B8; font-size: 12px; border: none;")
            if error_message:
                self.port_summary_label.setText(error_message)
                self.port_summary_label.setStyleSheet("color: #F87171; font-size: 12px; border: none;")
