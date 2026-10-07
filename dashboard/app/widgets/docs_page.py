"""
Documentation Page: Firmware Integrity Monitor v2.0
Dark engineering specification manual with section navigation and system protocol reference.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

C_BG_APP = "#070A10"
C_BG_PANEL = "#0B0F19"
C_BG_SURFACE = "#1E293B"
C_BORDER = "#334155"
C_BORDER_LT = "#475569"
C_TEXT_PRI = "#F8FAFC"
C_TEXT_SEC = "#94A3B8"
C_TEXT_DIM = "#64748B"
C_ACCENT = "#38BDF8"
C_ACCENT_LT = "#7DD3FC"
C_TEAL = "#34D399"
C_ORANGE = "#FBBF24"
C_RED = "#F87171"
C_PURPLE = "#A78BFA"

FONT_MONO = "JetBrains Mono, SFMono-Regular, Consolas, monospace"
FONT_UI = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

QSS_BASE = f"""
    QWidget {{
        background: {C_BG_APP};
        color: {C_TEXT_PRI};
    }}
"""


class DocumentationPage(QWidget):
    """
    In-app engineering manual rendering system architecture, hardware wiring topologies,
    and wire protocol command specifications.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(QSS_BASE)

        self._active_key: str | None = None
        self._section_widgets: dict[str, tuple[QWidget, QPushButton | None]] = {}
        self._pending_sidebar_btns: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top Navigation Bar ──────────────────────────────────────────────
        topbar = QFrame()
        topbar.setFixedHeight(50)
        topbar.setStyleSheet(f"background: {C_BG_PANEL}; border-bottom: 2px solid {C_ACCENT};")
        topbar_lay = QHBoxLayout(topbar)
        topbar_lay.setContentsMargins(28, 0, 28, 0)
        topbar_lay.setSpacing(16)

        brand = QLabel("📖 FIRMWARE INTEGRITY MONITOR — ENGINEERING SPECIFICATION")
        brand.setStyleSheet(
            f"color: {C_TEXT_PRI}; font-family: {FONT_MONO}; font-size: 12px; "
            f"font-weight: 700; letter-spacing: 0.8px; background: transparent;"
        )
        topbar_lay.addWidget(brand)
        topbar_lay.addStretch()

        meta = QLabel("DOCS v2.0 · HARDWARE & SOFTWARE SPECIFICATION")
        meta.setStyleSheet(
            f"color: {C_TEXT_DIM}; font-family: {FONT_MONO}; font-size: 11px; "
            f"font-weight: 600; background: transparent;"
        )
        topbar_lay.addWidget(meta)
        root.addWidget(topbar)

        # ── Body Layout (Sidebar + Scroll Canvas) ───────────────────────────
        body_widget = QWidget()
        body_widget.setStyleSheet(f"background: {C_BG_APP};")
        body_lay = QHBoxLayout(body_widget)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Sidebar Panel
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet(f"background: {C_BG_PANEL}; border-right: 1px solid {C_BORDER};")
        sidebar_scroll = QScrollArea(sidebar)
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setStyleSheet("background: transparent; border: none;")
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        sidebar_content = QWidget()
        sidebar_content.setStyleSheet("background: transparent;")
        self._sidebar_lay = QVBoxLayout(sidebar_content)
        self._sidebar_lay.setContentsMargins(0, 24, 0, 24)
        self._sidebar_lay.setSpacing(18)

        self._add_sidebar_group("1. System Guide", [
            ("Overview", "overview"),
            ("Architecture", "architecture"),
            ("Wire Protocol", "protocol"),
            ("App Views", "pages"),
        ])
        self._add_sidebar_group("2. Implementation", [
            ("Running Locally", "local_run"),
            ("Docker Deployment", "docker"),
            ("Hardware Wiring", "wiring"),
        ])
        self._add_sidebar_group("3. Reference", [
            ("Troubleshooting", "troubleshoot"),
            ("Known Limitations", "limitations"),
        ])

        self._sidebar_lay.addStretch()
        sidebar_scroll.setWidget(sidebar_content)

        sidebar_lay = QVBoxLayout(sidebar)
        sidebar_lay.setContentsMargins(0, 0, 0, 0)
        sidebar_lay.addWidget(sidebar_scroll)
        body_lay.addWidget(sidebar)

        # Main Scrollable Documentation Canvas
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: {C_BG_APP}; border: none; }}
            QScrollBar:vertical {{
                background: {C_BG_SURFACE}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER_LT}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {C_ACCENT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {C_BG_APP};")
        self._lay = QVBoxLayout(self._content)
        self._lay.setContentsMargins(56, 48, 56, 72)
        self._lay.setSpacing(0)

        # Build Sections
        self._build_hero()

        for key, builder in [
            ("overview", self._build_section_overview),
            ("architecture", self._build_section_architecture),
            ("protocol", self._build_section_protocol),
            ("pages", self._build_section_pages),
            ("local_run", self._build_section_local_run),
            ("docker", self._build_section_docker),
            ("wiring", self._build_section_wiring),
            ("troubleshoot", self._build_section_troubleshoot),
            ("limitations", self._build_section_limitations),
        ]:
            self._begin_section(key)
            builder()
            self._end_section()

        self._lay.addStretch()
        self.scroll.setWidget(self._content)
        body_lay.addWidget(self.scroll)
        root.addWidget(body_widget)

        self._patch_sidebar_refs()

    def _begin_section(self, key: str):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setObjectName(f"sec_{key}")
        container_lay = QVBoxLayout(container)
        container_lay.setContentsMargins(0, 0, 0, 0)
        container_lay.setSpacing(0)
        self._outer_lay = self._lay
        self._lay.addWidget(container)
        self._lay = container_lay
        self._pending_key = key
        self._pending_container = container

    def _end_section(self):
        self._section_widgets[self._pending_key] = (self._pending_container, None)
        self._lay = self._outer_lay

    def _scroll_to_section(self, key: str):
        if key not in self._section_widgets:
            return
        container, _ = self._section_widgets[key]

        def _do_scroll():
            pos = container.mapTo(self._content, container.rect().topLeft())
            self.scroll.verticalScrollBar().setValue(pos.y())

        QTimer.singleShot(0, _do_scroll)
        self._set_active(key)

    def _set_active(self, key: str):
        for _, (_, btn) in self._section_widgets.items():
            if btn:
                btn.setStyleSheet(self._sidebar_btn_qss(False))
        _, sidebar_btn = self._section_widgets.get(key, (None, None))
        if sidebar_btn:
            sidebar_btn.setStyleSheet(self._sidebar_btn_qss(True))
        self._active_key = key

    def _patch_sidebar_refs(self):
        for key, btn in self._pending_sidebar_btns.items():
            if key in self._section_widgets:
                container, _ = self._section_widgets[key]
                self._section_widgets[key] = (container, btn)

    def _sidebar_btn_qss(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{"
                f"  color: {C_ACCENT}; background: #0B2341; border: none; "
                f"  border-left: 4px solid {C_ACCENT}; text-align: left; "
                f"  padding: 8px 20px; font-family: {FONT_UI}; font-size: 13px; font-weight: 700;"
                f"}}"
            )
        return (
            f"QPushButton {{"
            f"  color: {C_TEXT_SEC}; background: transparent; border: none; "
            f"  border-left: 4px solid transparent; text-align: left; "
            f"  padding: 8px 20px; font-family: {FONT_UI}; font-size: 13px; font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"  color: {C_ACCENT}; background: {C_BG_SURFACE}; "
            f"  border-left: 4px solid {C_BORDER_LT};"
            f"}}"
        )

    def _add_sidebar_group(self, title: str, links: list):
        group = QWidget()
        group.setStyleSheet("background: transparent;")
        gl = QVBoxLayout(group)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(4)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color: {C_TEXT_DIM}; font-family: {FONT_MONO}; font-size: 10px; "
            f"font-weight: 700; letter-spacing: 1.5px; padding: 0 20px 8px;"
        )
        gl.addWidget(lbl)

        for text, key in links:
            btn = QPushButton(text)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._sidebar_btn_qss(False))
            btn.clicked.connect(lambda checked=False, k=key: self._scroll_to_section(k))
            gl.addWidget(btn)
            self._pending_sidebar_btns[key] = btn

        self._sidebar_lay.addWidget(group)

    def _div(self, spacing_before: int = 36):
        self._lay.addSpacing(spacing_before)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {C_BORDER}; border: none;")
        self._lay.addWidget(line)

    def _eyebrow(self, text: str):
        self._lay.addSpacing(16)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C_ACCENT}; font-family: {FONT_MONO}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1.5px;"
        )
        self._lay.addWidget(lbl)
        self._lay.addSpacing(6)

    def _h2(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C_TEXT_PRI}; font-family: {FONT_UI}; font-size: 24px; "
            f"font-weight: 800; border-bottom: 2px solid {C_BORDER}; padding-bottom: 12px;"
        )
        self._lay.addWidget(lbl)
        self._lay.addSpacing(16)

    def _h3(self, text: str, color: str = None):
        color = color or C_ACCENT_LT
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-family: {FONT_UI}; font-size: 16px; font-weight: 700; margin-top: 20px;")
        self._lay.addWidget(lbl)
        self._lay.addSpacing(8)

    def _para(self, text: str):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(f"color: {C_TEXT_SEC}; font-family: {FONT_UI}; font-size: 14px; line-height: 1.8; margin-bottom: 10px;")
        self._lay.addWidget(lbl)

    def _code(self, text: str):
        frame = QFrame()
        frame.setStyleSheet(f"background: {C_BG_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 6px;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(20, 16, 20, 16)
        lbl = QLabel(text)
        lbl.setWordWrap(False)
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet(f"color: {C_TEXT_PRI}; font-family: {FONT_MONO}; font-size: 12px; background: transparent; line-height: 1.7;")
        fl.addWidget(lbl)
        self._lay.addWidget(frame)
        self._lay.addSpacing(16)

    def _card_grid(self, cards: list, cols: int = 2):
        gw = QWidget()
        gw.setStyleSheet("background: transparent;")
        grid = QGridLayout(gw)
        grid.setSpacing(16)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, (title, color, body) in enumerate(cards):
            card = QFrame()
            card.setStyleSheet(f"background: {C_BG_PANEL}; border: 1px solid {C_BORDER}; border-top: 4px solid {color}; border-radius: 8px;")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(22, 20, 22, 20)
            cl.setSpacing(10)
            t = QLabel(title)
            t.setStyleSheet(f"color: {C_TEXT_PRI}; font-family: {FONT_UI}; font-size: 15px; font-weight: 700; background: transparent;")
            cl.addWidget(t)
            b = QLabel(body)
            b.setWordWrap(True)
            b.setStyleSheet(f"color: {C_TEXT_SEC}; font-family: {FONT_UI}; font-size: 13px; line-height: 1.7; background: transparent;")
            cl.addWidget(b)
            grid.addWidget(card, i // cols, i % cols)
        self._lay.addWidget(gw)
        self._lay.addSpacing(16)

    def _table(self, headers: list, rows: list):
        t = QFrame()
        t.setStyleSheet(f"background: {C_BG_PANEL}; border: 1px solid {C_BORDER}; border-radius: 8px;")
        tl = QVBoxLayout(t)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        hrow = QFrame()
        hrow.setStyleSheet(f"background: {C_BG_SURFACE}; border-bottom: 2px solid {C_BORDER};")
        hrl = QHBoxLayout(hrow)
        hrl.setContentsMargins(18, 12, 18, 12)
        hrl.setSpacing(0)
        for i, h in enumerate(headers):
            hl = QLabel(h.upper())
            hl.setStyleSheet(f"color: {C_TEXT_PRI}; font-family: {FONT_MONO}; font-size: 11px; font-weight: 700; letter-spacing: 1px;")
            hrl.addWidget(hl, 1 if i > 0 else 0)
            if i == 0:
                hl.setFixedWidth(220)
        tl.addWidget(hrow)
        for ri, row in enumerate(rows):
            rframe = QFrame()
            rframe.setStyleSheet(f"background: {C_BG_PANEL if ri % 2 == 0 else C_BG_SURFACE}; border-bottom: 1px solid {C_BORDER};")
            rl = QHBoxLayout(rframe)
            rl.setContentsMargins(18, 12, 18, 12)
            rl.setSpacing(0)
            for ci, cell in enumerate(row):
                cl = QLabel(str(cell))
                cl.setWordWrap(True)
                if ci == 0:
                    cl.setStyleSheet(f"color: {C_ACCENT_LT}; font-family: {FONT_MONO}; font-size: 12px; font-weight: 600;")
                    cl.setFixedWidth(220)
                    rl.addWidget(cl)
                else:
                    cl.setStyleSheet(f"color: {C_TEXT_SEC}; font-family: {FONT_UI}; font-size: 13px;")
                    rl.addWidget(cl, 1)
            tl.addWidget(rframe)
        self._lay.addWidget(t)
        self._lay.addSpacing(16)

    # ── Section Content Builders ──────────────────────────────────────────

    def _build_hero(self):
        hero = QFrame()
        hero.setStyleSheet(f"background: {C_BG_PANEL}; border: 1px solid {C_BORDER}; border-top: 4px solid {C_ACCENT}; border-radius: 10px;")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(40, 36, 40, 36)
        hl.setSpacing(14)

        eye = QLabel("ESP32 MICROCONTROLLER SECURITY · RUNTIME INTEGRITY SPECIFICATION")
        eye.setStyleSheet(f"color: {C_ACCENT}; font-family: {FONT_MONO}; font-size: 11px; font-weight: 700; letter-spacing: 1.5px;")
        hl.addWidget(eye)

        title = QLabel("Firmware Integrity Monitor & Sentinel Console")
        title.setStyleSheet(f"color: {C_TEXT_PRI}; font-family: {FONT_UI}; font-size: 28px; font-weight: 800;")
        hl.addWidget(title)

        desc = QLabel(
            "Continuous runtime SHA-256 integrity verification suite for ESP32 microcontrollers. "
            "Computes live hash calculations of running flash segments, validates baseline signatures, "
            "and transmits security alerts and rehash data over isolated serial UART."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {C_TEXT_SEC}; font-family: {FONT_UI}; font-size: 14px; line-height: 1.8;")
        hl.addWidget(desc)

        self._lay.addWidget(hero)
        self._lay.addSpacing(36)

    def _build_section_overview(self):
        self._eyebrow("01 — SYSTEM OVERVIEW")
        self._h2("Operational Profile")
        self._para("The Firmware Integrity Monitor continuously audits device flash memory and security anti-rollback counters.")
        self._card_grid([
            ("Continuous Rehash Telemetry", C_ACCENT, "Live SHA-256 calculation streams streamed over serial UART."),
            ("Custom Event Timeline", C_PURPLE, "Visual rolling strip chart for real-time alert classification."),
            ("Serial Command Control", C_ORANGE, "Manual command execution for polling, rehash triggers, and firmware reset."),
            ("Audit Logging & CSV", C_TEAL, "Searchable audit trail with persistent CSV export capabilities."),
        ])

    def _build_section_architecture(self):
        self._div()
        self._eyebrow("02 — ARCHITECTURE")
        self._h2("Module Layout")
        self._code(
            "esp32-integrity-project/\n"
            "├── dashboard/app/\n"
            "│   ├── main_window.py      # Main PySide6 Application Window\n"
            "│   ├── device_link.py      # Serial UART Threading Worker\n"
            "│   ├── models.py           # Alert & Rehash Data Models\n"
            "│   ├── protocol.py         # Wire Protocol Definitions\n"
            "│   └── widgets/            # Dashboard Views & Custom Painting Components\n"
            "└── firmware/main/\n"
            "    ├── crypto.c/h          # SHA-256 Flash Calculation Logic\n"
            "    ├── serial_comm.c/h     # Serial Framing Transceiver\n"
            "    └── main.c              # Firmware Entry Point"
        )

    def _build_section_protocol(self):
        self._div()
        self._eyebrow("03 — WIRE PROTOCOL")
        self._h2("Command & Frame Specifications")
        self._code(
            "Incoming Telemetry Frames:\n"
            "::STATUS:<version>:<rev>::          Boot notification\n"
            "::REHASH:<full_sha256_hash>::       Continuous rehash calculation payload\n"
            "::ALERT:<LEVEL>:<EVENT_CODE>::      Hardware/firmware tamper alert\n\n"
            "Outgoing Serial Commands:\n"
            "::POLL::                            Request immediate integrity sweep\n"
            "::REHASH::                          Trigger manual firmware SHA-256 calculation\n"
            "::TAMPER::                          Simulate hardware tamper signal (debug builds)\n"
            "::RESET_FIRMWARE::                  Restore baseline golden firmware image"
        )
        self._table(
            ["Command / Event Code", "Direction", "Description"],
            [
                ["::REHASH::", "Outgoing → Device", "Triggers immediate firmware SHA-256 recalculation."],
                ["::RESET_FIRMWARE::", "Outgoing → Device", "Dispatches firmware restoration signal over UART."],
                ["STATUS_SAFE", "Incoming ← Device", "Runtime hash matches baseline golden signature."],
                ["FIRMWARE_TAMPERED", "Incoming ← Device", "Critical alert: runtime hash mismatch detected."],
            ],
        )

    def _build_section_pages(self):
        self._div()
        self._eyebrow("04 — APP VIEWS")
        self._h2("View Structure")
        self._para("• <b>Dashboard:</b> Real-time status cards and rolling timeline chart.")
        self._para("• <b>Alert Log:</b> Immutable audit log displaying full SHA-256 hashes and export tools.")
        self._para("• <b>Device Console:</b> Interactive UART terminal with command dispatch buttons.")
        self._para("• <b>Settings:</b> Port auto-detection, baud rate controls, and simulation mode.")

    def _build_section_local_run(self):
        self._div()
        self._eyebrow("05 — DEPLOYMENT")
        self._h2("Local Execution")
        self._code("python3 -m venv venv\nsource venv/bin/activate\npip install -r requirements.txt\npython main.py")

    def _build_section_docker(self):
        self._div()
        self._eyebrow("06 — DOCKER")
        self._h2("Containerized Execution")
        self._code("xhost +local:docker\ndocker compose up --build")

    def _build_section_wiring(self):
        self._div()
        self._eyebrow("07 — HARDWARE WIRING")
        self._h2("Serial Connections")
        self._para("Connect the ESP32 UART pins (GPIO17 TX, GPIO18 RX, GND) to your USB-to-UART bridge adapter.")

    def _build_section_troubleshoot(self):
        self._div()
        self._eyebrow("08 — TROUBLESHOOTING")
        self._h2("Diagnostic Guide")
        self._table(
            ["Issue", "Remediation"],
            [
                ["Serial Port Missing", "Verify USB connection or review permissions (usermod -a -G dialout $USER)."],
                ["Hash Mismatch Alerts", "Firmware binary modified or corrupted; issue ::RESET_FIRMWARE:: to restore."],
            ],
        )

    def _build_section_limitations(self):
        self._div()
        self._eyebrow("09 — LIMITATIONS")
        self._h2("Known Constraints")
        self._para("Requires direct point-to-point UART connectivity or USB serial bridging.")