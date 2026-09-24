import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QFrame, QProgressBar, QTextEdit, QMessageBox,
    QSplitter, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush

# ==============================================================================
# COMPACT 16-CHANNEL PWM STICK / SWITCH BAR
# ==============================================================================
class PwmBarWidget(QWidget):
    def __init__(self, label_text, parent=None):
        super().__init__(parent)
        self.label_text = label_text
        self.val = 1500
        self.min_val = 1500
        self.max_val = 1500
        self.trim_val = 1500
        self.setFixedHeight(24)

    def set_value(self, val):
        if val <= 0:
            return
        self.val = max(900, min(2100, val))
        if self.val < self.min_val: self.min_val = self.val
        if self.val > self.max_val: self.max_val = self.val
        self.update()

    def reset_limits(self):
        self.min_val = self.val
        self.max_val = self.val
        self.trim_val = self.val
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Channel text
        p.setPen(QColor("#f1f5f9"))
        p.setFont(QFont("Consolas", 7, QFont.Bold))
        p.drawText(2, h - 8, self.label_text)

        bar_x = 72
        bar_w = w - bar_x - 100
        bar_y = 4
        bar_h = h - 8

        # Trough
        p.setPen(QPen(QColor("#334155"), 1))
        p.setBrush(QBrush(QColor("#080d14")))
        p.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)

        # 1500us Center Dash
        cx = bar_x + (bar_w / 2.0)
        p.setPen(QPen(QColor("#475569"), 1, Qt.DashLine))
        p.drawLine(cx, bar_y, cx, bar_y + bar_h)

        # Active fill
        pct = max(0.0, min(1.0, (self.val - 1000) / 1000.0))
        fill_w = int(bar_w * pct)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#0284c7") if self.val >= 1500 else QColor("#0f766e")))
        p.drawRoundedRect(bar_x + 1, bar_y + 1, fill_w, bar_h - 2, 2, 2)

        # Microsecond text
        p.setPen(QColor("#00ffcc"))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(w - 95, h - 8, f"{self.val}µs")

        # Range bounds
        p.setPen(QColor("#64748b"))
        p.setFont(QFont("Consolas", 6))
        p.drawText(w - 48, h - 8, f"{self.min_val}-{self.max_val}")


# ==============================================================================
# SENSOR CALIBRATION WIZARD (UP TO 16-CH RADIO & 6-AXIS VISUALS)
# ==============================================================================
class SensorCalibrationView(QWidget):
    back_to_home = Signal()

    def __init__(self, cal_mgr, parent=None):
        super().__init__(parent)
        self.cal_mgr = cal_mgr
        self.rc_is_calibrating = False
        self.init_ui()
        self.wire_signals()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #0b111a; color: #f1f5f9; font-family: 'Segoe UI', monospace; }
            QFrame.card {
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton.cal_btn {
                background-color: #0284c7; border: 1px solid #38bdf8;
                border-radius: 4px; color: #ffffff; font-weight: bold;
                font-size: 8.5pt; padding: 5px 12px; min-height: 24px;
            }
            QPushButton.cal_btn:hover { background-color: #0369a1; }
            QPushButton.danger_btn {
                background-color: #b91c1c; border: 1px solid #ef4444;
                border-radius: 4px; color: #ffffff; font-weight: bold;
                font-size: 8.5pt; padding: 5px 12px; min-height: 24px;
            }
            QPushButton.danger_btn:hover { background-color: #dc2626; }
            QProgressBar {
                background: #060b13; border: 1px solid #334155; border-radius: 4px;
                text-align: center; color: #ffffff; font-weight: bold; height: 18px; font-size: 8.5pt;
            }
            QProgressBar::chunk { background: #10b981; }
            QTextEdit#console_output {
                background-color: #05080e;
                border: 1px solid #00ffcc;
                border-radius: 6px;
                color: #00ffcc;
                font-family: 'Consolas', monospace;
                font-size: 9pt;
                padding: 6px 10px;
            }
            QSplitter::handle { background-color: #1e293b; }
            QSplitter::handle:hover { background-color: #00ffcc; }
            QSplitter::handle:horizontal { width: 5px; }
            QSplitter::handle:vertical { height: 5px; }
        """)

        master_layout = QVBoxLayout(self)
        master_layout.setContentsMargins(14, 10, 14, 10)
        master_layout.setSpacing(8)

        # Header Strip
        top_bar = QHBoxLayout()
        btn_back = QPushButton("◀ FLIGHT MAP (HOME)")
        btn_back.setStyleSheet("""
            background: #0284c7; border: 1px solid #38bdf8; color: white;
            font-weight: 900; font-size: 8.5pt; padding: 5px 12px; border-radius: 4px;
        """)
        btn_back.clicked.connect(self.back_to_home.emit)
        top_bar.addWidget(btn_back)

        title = QLabel("🛠 SENSOR HARDWARE CALIBRATION WIZARD")
        title.setStyleSheet("font-size: 12pt; font-weight: 900; color: #00ffcc; letter-spacing: 1px;")
        top_bar.addWidget(title)
        top_bar.addStretch()
        master_layout.addLayout(top_bar)

        # Master Vertical Splitter (Panels vs Console)
        self.v_master_splitter = QSplitter(Qt.Vertical)
        self.h_panels_splitter = QSplitter(Qt.Horizontal)

        # -------------------------------------------------------------
        # LEFT COLUMN (Accel & 16-Channel Radio)
        # -------------------------------------------------------------
        self.left_v_splitter = QSplitter(Qt.Vertical)

        # 1. Accelerometer Card with 6 visual position indicator badges
        accel_card = QFrame()
        accel_card.setProperty("class", "card")
        ac_layout = QVBoxLayout(accel_card)
        ac_layout.setSpacing(6)

        ac_title = QLabel("1. ACCELEROMETER / LEVEL CALIBRATION")
        ac_title.setStyleSheet("font-weight: 900; font-size: 9.5pt; color: #38bdf8;")
        ac_layout.addWidget(ac_title)

        self.lbl_accel_step = QLabel("Status: Standby. Ready for 6-axis 3D calibration.")
        self.lbl_accel_step.setStyleSheet("""
            background: #060b13; border: 1px dashed #38bdf8; padding: 8px;
            color: #facc15; font-weight: bold; border-radius: 4px; font-size: 9pt;
        """)
        self.lbl_accel_step.setWordWrap(True)
        ac_layout.addWidget(self.lbl_accel_step)

        # Visual orientation step badges
        self.step_badges = []
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        for name in ["LEVEL", "LEFT", "RIGHT", "NOSE DN", "NOSE UP", "BACK"]:
            b = QLabel(name)
            b.setAlignment(Qt.AlignCenter)
            b.setStyleSheet("background: #1e293b; color: #94a3b8; font-size: 7.5pt; font-weight: bold; border-radius: 3px; padding: 4px;")
            self.step_badges.append(b)
            badge_row.addWidget(b)
        ac_layout.addLayout(badge_row)

        ac_btns = QHBoxLayout()
        self.btn_accel_start = QPushButton("CALIBRATE 3D ACCEL")
        self.btn_accel_start.setProperty("class", "cal_btn")
        self.btn_accel_start.clicked.connect(self.start_accel)
        ac_btns.addWidget(self.btn_accel_start)

        self.btn_accel_next = QPushButton("NEXT STEP (ACK) ▶")
        self.btn_accel_next.setProperty("class", "cal_btn")
        self.btn_accel_next.setEnabled(False)
        self.btn_accel_next.clicked.connect(self.next_accel)
        ac_btns.addWidget(self.btn_accel_next)

        btn_level = QPushButton("CALIBRATE LEVEL ONLY")
        btn_level.setStyleSheet("background: #1e293b; border: 1px solid #475569; color: #cbd5e1; font-weight: bold; padding: 5px 10px; border-radius: 4px; font-size: 8pt;")
        btn_level.clicked.connect(self.cal_mgr.calibrate_simple_level)
        ac_btns.addWidget(btn_level)
        ac_btns.addStretch()

        ac_layout.addLayout(ac_btns)
        self.left_v_splitter.addWidget(accel_card)

        # 2. Radio Card (Supports 16 Channels in 2 Columns: Skydroid, MK15, MK32)
        rc_card = QFrame()
        rc_card.setProperty("class", "card")
        rc_layout = QVBoxLayout(rc_card)
        rc_layout.setSpacing(6)

        rc_title_row = QHBoxLayout()
        rc_title = QLabel("3. RADIO / RC STICKS (16-CHANNELS: T12 / MK15 / MK32)")
        rc_title.setStyleSheet("font-weight: 900; font-size: 9.5pt; color: #38bdf8;")
        rc_title_row.addWidget(rc_title)
        rc_title_row.addStretch()

        self.btn_rc_cal = QPushButton("CALIBRATE RADIO")
        self.btn_rc_cal.setProperty("class", "cal_btn")
        self.btn_rc_cal.clicked.connect(self.toggle_rc_calibration)
        rc_title_row.addWidget(self.btn_rc_cal)
        rc_layout.addLayout(rc_title_row)

        # 2-column scrollable grid for all 16 channels
        rc_grid_widget = QWidget()
        rc_grid = QGridLayout(rc_grid_widget)
        rc_grid.setContentsMargins(0, 0, 0, 0)
        rc_grid.setSpacing(4)

        channel_names = [
            "CH1 (Roll)", "CH2 (Pitch)", "CH3 (Thr)", "CH4 (Yaw)",
            "CH5 (Mode)", "CH6 (Aux1)", "CH7 (Aux2)", "CH8 (Aux3)",
            "CH9 (Cam P)", "CH10 (Cam Y)", "CH11 (Aux4)", "CH12 (Aux5)",
            "CH13 (Aux6)", "CH14 (Aux7)", "CH15 (Aux8)", "CH16 (Aux9)"
        ]

        self.bars = []
        for i, name in enumerate(channel_names):
            bar = PwmBarWidget(name)
            self.bars.append(bar)
            row = i % 8
            col = i // 8
            rc_grid.addWidget(bar, row, col)

        rc_scroll = QScrollArea()
        rc_scroll.setWidgetResizable(True)
        rc_scroll.setWidget(rc_grid_widget)
        rc_scroll.setStyleSheet("background: transparent; border: none;")
        rc_layout.addWidget(rc_scroll)

        self.left_v_splitter.addWidget(rc_card)
        self.h_panels_splitter.addWidget(self.left_v_splitter)

        # -------------------------------------------------------------
        # RIGHT COLUMN (Compass & ESC)
        # -------------------------------------------------------------
        self.right_v_splitter = QSplitter(Qt.Vertical)

        # 3. Compass Card
        mag_card = QFrame()
        mag_card.setProperty("class", "card")
        mc_layout = QVBoxLayout(mag_card)
        mc_layout.setSpacing(8)

        mc_title = QLabel("2. ONBOARD COMPASS (MAGNETOMETER)")
        mc_title.setStyleSheet("font-weight: 900; font-size: 9.5pt; color: #38bdf8;")
        mc_layout.addWidget(mc_title)

        mc_desc = QLabel("Rotate drone in slow continuous spheres away from metal:")
        mc_desc.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        mc_layout.addWidget(mc_desc)

        self.mag_pbar = QProgressBar()
        self.mag_pbar.setValue(0)
        self.mag_pbar.setFixedHeight(22)
        mc_layout.addWidget(self.mag_pbar)

        mc_btns = QHBoxLayout()
        self.btn_mag_start = QPushButton("START COMPASS CAL")
        self.btn_mag_start.setProperty("class", "cal_btn")
        self.btn_mag_start.setFixedWidth(180)
        self.btn_mag_start.clicked.connect(self.start_compass)
        mc_btns.addWidget(self.btn_mag_start)

        self.btn_mag_cancel = QPushButton("CANCEL")
        self.btn_mag_cancel.setProperty("class", "danger_btn")
        self.btn_mag_cancel.setFixedWidth(100)
        self.btn_mag_cancel.clicked.connect(self.cancel_compass)
        mc_btns.addWidget(self.btn_mag_cancel)
        mc_btns.addStretch()

        mc_layout.addLayout(mc_btns)
        mc_layout.addStretch()
        self.right_v_splitter.addWidget(mag_card)

        # 4. ESC Card
        esc_card = QFrame()
        esc_card.setProperty("class", "card")
        ec_layout = QVBoxLayout(esc_card)
        ec_layout.setSpacing(8)

        ec_title = QLabel("4. ESC AUTOMATIC CALIBRATION")
        ec_title.setStyleSheet("font-weight: 900; font-size: 9.5pt; color: #ef4444;")
        ec_layout.addWidget(ec_title)

        ec_desc = QLabel(
            "<b>DANGER: REMOVE ALL PROPELLERS!</b><br>"
            "Sets <code>ESC_CALIBRATION=3</code> and reboots the board.<br>"
            "Disconnect battery, plug in when tone sounds to set throttle endpoints."
        )
        ec_desc.setStyleSheet("color: #fca5a5; font-size: 8.5pt; line-height: 1.3;")
        ec_layout.addWidget(ec_desc)

        btn_esc = QPushButton("TRIGGER ESC CALIBRATION REBOOT")
        btn_esc.setProperty("class", "danger_btn")
        btn_esc.setFixedWidth(240)
        btn_esc.clicked.connect(self.confirm_esc_trigger)
        ec_layout.addWidget(btn_esc)
        ec_layout.addStretch()

        self.right_v_splitter.addWidget(esc_card)
        self.h_panels_splitter.addWidget(self.right_v_splitter)

        # Set balanced default widths (Left: 60%, Right: 40%)
        self.h_panels_splitter.setSizes([850, 550])
        self.left_v_splitter.setSizes([200, 380])
        self.right_v_splitter.setSizes([240, 240])

        self.v_master_splitter.addWidget(self.h_panels_splitter)

        # -------------------------------------------------------------
        # 5. EXPANDED, DRAGGABLE TELEMETRY CONSOLE
        # -------------------------------------------------------------
        console_container = QFrame()
        console_container.setStyleSheet("background: #080d14; border: 1px solid #1e293b; border-radius: 6px; padding: 4px;")
        cc_layout = QVBoxLayout(console_container)
        cc_layout.setContentsMargins(4, 2, 4, 4)
        cc_layout.setSpacing(4)

        console_hdr = QLabel("📟 REAL-TIME CALIBRATION LOGS & MAVLINK TELEMETRY CONSOLE (DRAG DIVIDER BAR TO RESIZE)")
        console_hdr.setStyleSheet("font-weight: 900; font-size: 8.5pt; color: #38bdf8; letter-spacing: 0.5px;")
        cc_layout.addWidget(console_hdr)

        self.console = QTextEdit()
        self.console.setObjectName("console_output")
        self.console.setReadOnly(True)
        self.console.append("[System] Sensor hardware calibration wizard ready. 16-channel radio monitoring active.")
        cc_layout.addWidget(self.console)

        self.v_master_splitter.addWidget(console_container)
        self.v_master_splitter.setSizes([580, 180])

        master_layout.addWidget(self.v_master_splitter)

    # -------------------------------------------------------------
    # MAVLink Signal Routing & Interaction
    # -------------------------------------------------------------
    def wire_signals(self):
        self.cal_mgr.log_sig.connect(self.log_message)
        self.cal_mgr.accel_prompt_sig.connect(self.on_accel_prompt)
        self.cal_mgr.compass_progress_sig.connect(self.mag_pbar.setValue)
        self.cal_mgr.compass_done_sig.connect(self.on_compass_finished)
        self.cal_mgr.rc_channels_sig.connect(self.on_rc_raw_received)

    def log_message(self, text):
        self.console.append(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def start_accel(self):
        if self.cal_mgr.start_accel_6point():
            self.btn_accel_next.setEnabled(True)
            self.btn_accel_start.setEnabled(False)
            self.update_step_badges(1)

    def next_accel(self):
        step = self.cal_mgr.accel_step_index
        self.cal_mgr.advance_accel_step()
        self.update_step_badges(self.cal_mgr.accel_step_index)
        if self.cal_mgr.accel_step_index == 0:
            self.btn_accel_next.setEnabled(False)
            self.btn_accel_start.setEnabled(True)

    def update_step_badges(self, current_step):
        for idx, b in enumerate(self.step_badges):
            if idx + 1 < current_step:
                b.setStyleSheet("background: #166534; color: #4ade80; font-size: 7.5pt; font-weight: bold; border-radius: 3px; padding: 4px;")
            elif idx + 1 == current_step:
                b.setStyleSheet("background: #0284c7; color: white; font-size: 7.5pt; font-weight: 900; border-radius: 3px; padding: 4px;")
            else:
                b.setStyleSheet("background: #1e293b; color: #64748b; font-size: 7.5pt; font-weight: bold; border-radius: 3px; padding: 4px;")

    def on_accel_prompt(self, msg):
        self.lbl_accel_step.setText(f"Instruction: {msg}")

    def start_compass(self):
        self.mag_pbar.setValue(0)
        self.cal_mgr.start_compass_cal()

    def cancel_compass(self):
        self.cal_mgr.cancel_compass_cal()
        self.mag_pbar.setValue(0)

    def on_compass_finished(self, success, text):
        if success:
            QMessageBox.information(self, "Compass Success", "Compass calibration successful! Offsets committed.")
        else:
            QMessageBox.warning(self, "Compass Notice", f"Compass calibration status:\n{text}")

    def toggle_rc_calibration(self):
        if not self.rc_is_calibrating:
            self.rc_is_calibrating = True
            for b in self.bars: b.reset_limits()
            self.btn_rc_cal.setText("SAVE LIMITS (FINISH)")
            self.btn_rc_cal.setStyleSheet("background: #16a34a; border: 1px solid #4ade80; color: white; font-weight: bold; border-radius: 4px; padding: 5px 12px;")
            self.log_message("[*] Move all sticks, dials, and switches on your remote in full circles...")
        else:
            self.rc_is_calibrating = False
            self.btn_rc_cal.setText("CALIBRATE RADIO")
            self.btn_rc_cal.setStyleSheet("")
            limits = {}
            for i in range(16):
                limits[f"RC{i+1}_MIN"] = self.bars[i].min_val
                limits[f"RC{i+1}_MAX"] = self.bars[i].max_val
                limits[f"RC{i+1}_TRIM"] = self.bars[i].trim_val
            self.cal_mgr.save_rc_limits(limits)

    def on_rc_raw_received(self, pwm_list):
        for i in range(min(16, len(pwm_list))):
            self.bars[i].set_value(pwm_list[i])

    def confirm_esc_trigger(self):
        reply = QMessageBox.critical(
            self, "DANGER: ESC CALIBRATION",
            "Are all propellers REMOVED from the drone?\n\n"
            "Motors may spin during calibration.\n\nProceed with calibration?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.cal_mgr.trigger_esc_calibration()