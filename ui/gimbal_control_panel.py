from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QLabel, QWidget
)
from PySide6.QtCore import Qt, Signal, QTimer

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
    max-width: 30px;
    min-height: 26px;
    max-height: 26px;
}
QPushButton.g_top_btn:hover {
    background: #1e293b;
    border-color: #38bdf8;
    color: #ffffff;
}
QPushButton#btn_ir_active {
    background: #b45309;
    border: 1.5px solid #f59e0b;
    color: #ffffff;
}
QPushButton#btn_dual_active {
    background: #0369a1;
    border: 1.5px solid #38bdf8;
    color: #ffffff;
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
QPushButton.g_rec_btn:hover { border-color: #ef4444; }
QLabel#lbl_rec_timer {
    background: #dc2626;
    color: #ffffff;
    font-family: 'Consolas', monospace;
    font-size: 9pt;
    font-weight: bold;
    border-radius: 4px;
    padding: 3px 8px;
}
QLabel.section_lbl {
    color: #94a3b8;
    font-size: 7.5pt;
    font-weight: 800;
}
QPushButton#btn_floating_restore {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: white;
    font-size: 9pt;
    font-weight: bold;
    border-radius: 6px;
}
QPushButton#btn_floating_restore:hover { background-color: #0369a1; }
"""

class GimbalControlPanel(QFrame):
    gimbal_command = Signal(float, float)
    gimbal_mode_command = Signal(str)
    zoom_changed = Signal(float)
    snapshot_requested = Signal()
    record_toggled = Signal(bool)
    ir_toggled = Signal(bool)
    dual_view_toggled = Signal()
    camera_config_requested = Signal()
    panel_minimized = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gimbal_root")
        self.setStyleSheet(GIMBAL_PANEL_STYLE)

        self.is_minimized = False
        self.is_recording = False
        self.is_thermal_active = False
        self.record_seconds = 0
        self.current_zoom = 1.0

        self.rec_timer = QTimer(self)
        self.rec_timer.setInterval(1000)
        self.rec_timer.timeout.connect(self._update_rec_timer)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        # 1. Floating Minimized Pill Button
        self.btn_restore = QPushButton("📹 Gimbal Controls ‹", self)
        self.btn_restore.setObjectName("btn_floating_restore")
        self.btn_restore.setFixedSize(140, 32)
        self.btn_restore.clicked.connect(self.toggle_minimize)
        self.btn_restore.hide()
        self.outer_layout.addWidget(self.btn_restore)

        # 2. Main Full Panel Widget
        self.full_panel_widget = QWidget(self)
        self.main_layout = QVBoxLayout(self.full_panel_widget)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(6)

        # Header Row
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self.btn_cam_mode = QPushButton("📹")
        self.btn_cam_mode.setProperty("class", "g_top_btn")
        self.btn_cam_mode.setToolTip("Configure Dual Camera RTSP Streams (Day & Thermal)")
        self.btn_cam_mode.clicked.connect(self.camera_config_requested.emit)
        top_row.addWidget(self.btn_cam_mode)

        self.btn_snap = QPushButton("📷")
        self.btn_snap.setProperty("class", "g_top_btn")
        self.btn_snap.setToolTip("Take Snapshot / Photo")
        self.btn_snap.clicked.connect(self.snapshot_requested.emit)
        top_row.addWidget(self.btn_snap)

        # Grid Button = Toggle Dual Stream Split-Screen View
        self.btn_grid = QPushButton("⊞")
        self.btn_grid.setProperty("class", "g_top_btn")
        self.btn_grid.setToolTip("Toggle Day + Thermal Dual Split Screen")
        self.btn_grid.clicked.connect(self.dual_view_toggled.emit)
        top_row.addWidget(self.btn_grid)

        # IR / Thermal Button
        self.btn_ir = QPushButton("IR")
        self.btn_ir.setProperty("class", "g_top_btn")
        self.btn_ir.setToolTip("Switch Primary View between Day and Thermal (IR)")
        self.btn_ir.clicked.connect(self._toggle_ir_mode)
        top_row.addWidget(self.btn_ir)

        self.btn_track = QPushButton("🎯")
        self.btn_track.setProperty("class", "g_top_btn")
        self.btn_track.setToolTip("Target Tracking Lock")
        top_row.addWidget(self.btn_track)

        self.lbl_zoom = QLabel("1.0x")
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.lbl_zoom.setFixedWidth(36)
        self.lbl_zoom.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; color: #cbd5e1; font-family: Consolas; font-size: 8pt; border-radius: 3px; padding: 2px 0px;")
        top_row.addWidget(self.lbl_zoom)

        # Minimize Button -> Collapses panel into the small pill
        self.btn_minimize = QPushButton("›")
        self.btn_minimize.setProperty("class", "g_top_btn")
        self.btn_minimize.setToolTip("Collapse Control Panel Completely")
        self.btn_minimize.clicked.connect(self.toggle_minimize)
        top_row.addWidget(self.btn_minimize)

        self.main_layout.addLayout(top_row)

        # Body Container
        self.body_widget = QWidget(self.full_panel_widget)
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)

        # Video Recording Row
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

        div = QFrame()
        div.setStyleSheet("background: #1e293b; max-height: 1px;")
        body_layout.addWidget(div)

        # Lens Zoom & Focus Controls
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

        # Gimbal Directional Numpad
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
        self.btn_home.setToolTip("Recenter Gimbal (0° Pitch, 0° Yaw)")
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
        self.outer_layout.addWidget(self.full_panel_widget)

    def _toggle_ir_mode(self):
        self.is_thermal_active = not self.is_thermal_active
        if self.is_thermal_active:
            self.btn_ir.setStyleSheet("background: #b45309; border: 1.5px solid #f59e0b; color: #ffffff;")
        else:
            self.btn_ir.setStyleSheet("")
        self.ir_toggled.emit(self.is_thermal_active)

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        if self.is_minimized:
            self.full_panel_widget.hide()
            self.btn_restore.show()
            self.setStyleSheet("background: transparent; border: none;")
        else:
            self.btn_restore.hide()
            self.full_panel_widget.show()
            self.setStyleSheet(GIMBAL_PANEL_STYLE)
        self.panel_minimized.emit(self.is_minimized)

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