from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

GIMBAL_PANEL_STYLE = """
QFrame#gimbal_root {
    background: rgba(11, 17, 24, 0.94);
    border: 1px solid #1e293b;
    border-radius: 8px;
}
QPushButton.g_top_btn {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 5px;
    color: #cbd5e1;
    font-size: 8.5pt;
    font-weight: bold;
    min-width: 28px;
    max-width: 32px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton.g_top_btn:hover {
    background: #1e293b;
    border-color: #38bdf8;
    color: #ffffff;
}
QPushButton#btn_track_active {
    background: #064e3b;
    border: 1.5px solid #10b981;
    color: #34d399;
}
QPushButton.g_pad_btn {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 4px;
    color: #e2e8f0;
    font-size: 8.5pt;
    font-weight: bold;
    min-width: 34px;
    max-width: 38px;
    min-height: 28px;
    max-height: 28px;
}
QPushButton.g_pad_btn:hover {
    background: #1e293b;
    border-color: #0284c7;
    color: #ffffff;
}
QPushButton.g_rec_btn {
    background: transparent;
    border: 1px solid #475569;
    border-radius: 14px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton.g_rec_btn:hover {
    border-color: #ef4444;
}
QLabel#lbl_rec_timer {
    background: #dc2626;
    color: #ffffff;
    font-family: 'Consolas', monospace;
    font-size: 9pt;
    font-weight: bold;
    border-radius: 4px;
    padding: 3px 12px;
}
QLabel.section_lbl {
    color: #94a3b8;
    font-size: 7.5pt;
    font-weight: 800;
}
"""

class GimbalControlPanel(QFrame):
    # Gimbal movement signals: pitch_delta, yaw_delta
    gimbal_command = Signal(float, float)
    gimbal_mode_command = Signal(str)  # "HOME", "NADIR_90"
    zoom_changed = Signal(float)
    snapshot_requested = Signal()
    record_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gimbal_root")
        self.setStyleSheet(GIMBAL_PANEL_STYLE)
        self.setFixedWidth(240)

        self.is_minimized = False
        self.is_recording = False
        self.record_seconds = 0
        self.current_zoom = 1.0

        # Recording stopwatch timer
        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(1000)
        self.rec_timer.timeout.connect(self._update_rec_timer)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        # -------------------------------------------------------------
        # Row 1: Camera Header Controls
        # -------------------------------------------------------------
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.btn_cam_mode = QPushButton("📹")
        self.btn_cam_mode.setProperty("class", "g_top_btn")
        self.btn_cam_mode.setToolTip("Camera Video Mode")
        top_row.addWidget(self.btn_cam_mode)

        self.btn_snap = QPushButton("📷")
        self.btn_snap.setProperty("class", "g_top_btn")
        self.btn_snap.setToolTip("Take Snapshot / Photo")
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)
        top_row.addWidget(self.btn_snap)

        self.btn_grid = QPushButton("⊞")
        self.btn_grid.setProperty("class", "g_top_btn")
        self.btn_grid.setToolTip("Toggle Crosshair / Grid")
        top_row.addWidget(self.btn_grid)

        self.btn_ir = QPushButton("IR")
        self.btn_ir.setProperty("class", "g_top_btn")
        self.btn_ir.setToolTip("IR / Thermal Palette")
        top_row.addWidget(self.btn_ir)

        self.btn_track = QPushButton("🎯")
        self.btn_track.setProperty("class", "g_top_btn")
        self.btn_track.setObjectName("btn_track_active")
        self.btn_track.setToolTip("Target Tracking Lock")
        top_row.addWidget(self.btn_track)

        self.lbl_zoom = QLabel("1.0x")
        self.lbl_zoom.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; color: #cbd5e1; font-family: Consolas; font-size: 8pt; padding: 2px 4px; border-radius: 3px;")
        top_row.addWidget(self.lbl_zoom)

        # Minimize Toggle Button (chevron)
        self.btn_minimize = QPushButton("›")
        self.btn_minimize.setProperty("class", "g_top_btn")
        self.btn_minimize.setToolTip("Minimize / Expand Gimbal Panel")
        self.btn_minimize.clicked.connect(self.toggle_minimize)
        top_row.addWidget(self.btn_minimize)

        self.main_layout.addLayout(top_row)

        # -------------------------------------------------------------
        # Expandable Body Container
        # -------------------------------------------------------------
        self.body_widget = QWidget(self)
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)

        # Row 2: Video Recording Row
        rec_row = QHBoxLayout()
        rec_row.setSpacing(8)

        self.btn_rec = QPushButton()
        self.btn_rec.setProperty("class", "g_rec_btn")
        self.btn_rec.setText("🔴")
        self.btn_rec.setToolTip("Start / Stop Screen Video Recording")
        self.btn_rec.clicked.connect(self.toggle_recording)
        rec_row.addWidget(self.btn_rec)

        self.lbl_timer = QLabel("00:00:00")
        self.lbl_timer.setObjectName("lbl_rec_timer")
        self.lbl_timer.setAlignment(Qt.AlignCenter)
        rec_row.addWidget(self.lbl_timer, stretch=1)

        body_layout.addLayout(rec_row)

        # Divider line
        div = QFrame()
        div.setStyleSheet("background: #1e293b; max-height: 1px;")
        body_layout.addWidget(div)

        # Row 3: Lens Zoom & Focus Controls
        lens_layout = QHBoxLayout()
        lens_layout.setSpacing(4)

        lbl_lens = QLabel("LENS")
        lbl_lens.setProperty("class", "section_lbl")
        lens_layout.addWidget(lbl_lens)

        lbl_z = QLabel("Z")
        lbl_z.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 8pt;")
        lens_layout.addWidget(lbl_z)

        self.btn_zoom_out = QPushButton("-")
        self.btn_zoom_out.setProperty("class", "g_pad_btn")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        lens_layout.addWidget(self.btn_zoom_out)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setProperty("class", "g_pad_btn")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        lens_layout.addWidget(self.btn_zoom_in)

        lbl_f = QLabel("F")
        lbl_f.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 8pt; margin-left: 2px;")
        lens_layout.addWidget(lbl_f)

        self.btn_focus_near = QPushButton("-")
        self.btn_focus_near.setProperty("class", "g_pad_btn")
        lens_layout.addWidget(self.btn_focus_near)

        self.btn_focus_far = QPushButton("+")
        self.btn_focus_far.setProperty("class", "g_pad_btn")
        lens_layout.addWidget(self.btn_focus_far)

        body_layout.addLayout(lens_layout)

        # Row 4: Gimbal Directional Numpad[cite: 15]
        gimbal_wrap = QHBoxLayout()
        gimbal_wrap.setSpacing(6)

        lbl_gimb = QLabel("GIMBAL")
        lbl_gimb.setProperty("class", "section_lbl")
        gimbal_wrap.addWidget(lbl_gimb)

        pad_grid = QGridLayout()
        pad_grid.setSpacing(3)

        self.btn_yaw_left = QPushButton("←")
        self.btn_yaw_left.setProperty("class", "g_pad_btn")
        self.btn_yaw_left.clicked.connect(lambda: self.gimbal_command.emit(0.0, -5.0))
        pad_grid.addWidget(self.btn_yaw_left, 0, 0)

        self.btn_pitch_up = QPushButton("↑")
        self.btn_pitch_up.setProperty("class", "g_pad_btn")
        self.btn_pitch_up.clicked.connect(lambda: self.gimbal_command.emit(5.0, 0.0))
        pad_grid.addWidget(self.btn_pitch_up, 0, 1)

        self.btn_yaw_right = QPushButton("→")
        self.btn_yaw_right.setProperty("class", "g_pad_btn")
        self.btn_yaw_right.clicked.connect(lambda: self.gimbal_command.emit(0.0, 5.0))
        pad_grid.addWidget(self.btn_yaw_right, 0, 2)

        self.btn_home = QPushButton("⌂")
        self.btn_home.setProperty("class", "g_pad_btn")
        self.btn_home.setToolTip("Recenter Gimbal Forward (0° pitch, 0° yaw)")
        self.btn_home.clicked.connect(lambda: self.gimbal_mode_command.emit("HOME"))
        pad_grid.addWidget(self.btn_home, 1, 0)

        self.btn_pitch_down = QPushButton("↓")
        self.btn_pitch_down.setProperty("class", "g_pad_btn")
        self.btn_pitch_down.clicked.connect(lambda: self.gimbal_command.emit(-5.0, 0.0))
        pad_grid.addWidget(self.btn_pitch_down, 1, 1)

        self.btn_nadir = QPushButton("90°")
        self.btn_nadir.setProperty("class", "g_pad_btn")
        self.btn_nadir.setToolTip("Point Directly Downwards (-90° Nadir)")
        self.btn_nadir.clicked.connect(lambda: self.gimbal_mode_command.emit("NADIR_90"))
        pad_grid.addWidget(self.btn_nadir, 1, 2)

        gimbal_wrap.addLayout(pad_grid)
        body_layout.addLayout(gimbal_wrap)

        self.main_layout.addWidget(self.body_widget)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.body_widget.hide()
            self.btn_minimize.setText("‹")
            self.adjustSize()
        else:
            self.body_widget.show()
            self.btn_minimize.setText("›")
            self.adjustSize()

    def toggle_recording(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.record_seconds = 0
            self.lbl_timer.setText("00:00:00")
            self.lbl_timer.setStyleSheet("background: #dc2626; color: #ffffff;")
            self.rec_timer.start()
            self.record_toggled.emit(True)
        else:
            self.rec_timer.stop()
            self.lbl_timer.setStyleSheet("background: #334155; color: #94a3b8;")
            self.record_toggled.emit(False)

    def _update_rec_timer(self):
        self.record_seconds += 1
        hrs = self.record_seconds // 3600
        mins = (self.record_seconds % 3600) // 60
        secs = self.record_seconds % 60
        self.lbl_timer.setText(f"{hrs:02d}:{mins:02d}:{secs:02d}")

    def _zoom_in(self):
        self.current_zoom = min(10.0, self.current_zoom + 0.5)
        self.lbl_zoom.setText(f"{self.current_zoom:.1f}x")
        self.zoom_changed.emit(self.current_zoom)

    def _zoom_out(self):
        self.current_zoom = max(1.0, self.current_zoom - 0.5)
        self.lbl_zoom.setText(f"{self.current_zoom:.1f}x")
        self.zoom_changed.emit(self.current_zoom)