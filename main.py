import os
import sys
import json

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|fflags;nobuffer|max_delay;500000|stimeout;5000000"
)

from datetime import datetime
from pymavlink import mavutil
import serial.tools.list_ports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QLabel, QComboBox, QInputDialog, QLineEdit, QMessageBox,
    QFileDialog
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl, Qt, QTimer
from PySide6.QtGui import QFont

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.mavlink_manager import MavlinkWorker
from core.mission_manager import MissionManager
from core.dooaf_engine import DOOAFEngine
from core.video_stream import GimbalCameraThread
from core.dem_manager import DemManager
from core.mgrs_helper import to_mgrs_gr
from core.dooaf_report_generator import generate_dooaf_html_report, haversine_dist
from ui.video_widget import ClickableVideoLabel
from ui.hud_overlay import TacticalOverlayHUD
from ui.report_dialog import DooafReportDialog
from ui.dooaf_setup_dialog import DooafSetupDialog
from ui.udp_config_dialog import UdpConfigDialog
from ui.target_popup_dialog import TacticalTargetPopup
from ui.coordinate_goto_dialog import CoordinateGotoDialog
from ui.flight_plan_widgets import PlanTopStatsBar, PlanLeftToolBar, PlanRightMissionPanel
from ui.gimbal_control_panel import GimbalControlPanel

MAIN_STYLE = """
QPushButton.circle_btn {
    background-color: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(180, 180, 180, 0.8);
    border-radius: 8px;
    color: #0f172a;
    font-size: 14pt;
    font-weight: bold;
    min-width: 44px;
    min-height: 44px;
    max-width: 44px;
    max-height: 44px;
}
QPushButton.circle_btn:hover {
    background-color: #ffffff;
    border: 2px solid #0284c7;
}
QFrame#control_bar_panel {
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid #334155;
    border-radius: 6px;
}
QPushButton#setup_btn {
    background-color: #b91c1c;
    border: 1px solid #dc2626;
    border-radius: 4px;
    color: white;
    font-size: 8.5pt;
    font-weight: bold;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton#setup_btn:hover { background-color: #dc2626; }
QPushButton#plan_mode_btn {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    border-radius: 4px;
    color: white;
    font-size: 8.5pt;
    font-weight: bold;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton#plan_mode_btn:hover { background-color: #0369a1; }
QPushButton#coord_btn {
    background-color: #0f766e;
    border: 1px solid #2dd4bf;
    border-radius: 4px;
    color: white;
    font-size: 8.5pt;
    font-weight: bold;
    padding: 4px 10px;
    min-height: 24px;
}
QPushButton#coord_btn:hover { background-color: #14b8a6; }
QComboBox.mav_combo_box {
    background-color: #0f172a;
    border: 1px solid #38bdf8;
    border-radius: 4px;
    color: #00ffcc;
    font-family: 'Consolas', monospace;
    font-size: 9pt;
    font-weight: bold;
    padding: 2px 6px;
    min-height: 24px;
    max-height: 24px;
}
QComboBox.mav_combo_box QLineEdit {
    background-color: #0f172a;
    color: #00ffcc;
    border: none;
    font-family: 'Consolas', monospace;
    font-size: 9pt;
    font-weight: bold;
}
QComboBox.mav_combo_box::drop-down { border: none; width: 16px; }
QComboBox.mav_combo_box QAbstractItemView {
    background-color: #0f172a;
    color: #ffffff;
    selection-background-color: #0284c7;
}
"""

class VikasFlyViewGCS(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VIKAS GCS - DOOAF Artillery & Autonomous Flight Control")
        self.resize(1600, 900)
        self.setStyleSheet(MAIN_STYLE)

        self.dooaf = DOOAFEngine(gun_default_facing=180.0)
        default_dem = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "elevation.tif"))
        self.dem = DemManager(default_dem if os.path.exists(default_dem) else None)

        self.cam_worker = None
        self.current_rtsp_url = ""
        self.mav_worker = None
        self.mission_mgr = None
        self.target_pt = None
        self.impact_pt = None
        self.latest_sol = None
        self.latest_corr = None
        self.map_is_primary = True
        self.custom_udp_conn = "udpin:0.0.0.0:14550"

        # Gimbal orientation tracking (degrees)
        self.gimbal_pitch = -45.0
        self.gimbal_yaw = 0.0

        self.current_view_mode = "FLY"
        self.planned_waypoints = []
        self.mission_execution_state = "IDLE"

        self.artillery_auth_pin = "1234"
        self.active_pick_entity = None
        self.active_pick_source = None

        self.canvas = QWidget(self)
        self.setCentralWidget(self.canvas)

        self.primary_host = QWidget(self.canvas)
        self.pip_host = QFrame(self.canvas)
        self.pip_host.setStyleSheet("border: 2px solid #00ffcc; border-radius: 6px; background-color: #000;")

        self.video_view = ClickableVideoLabel()
        self.video_view.pixel_clicked.connect(self.on_video_target_selected)

        self.web_map = QWebEngineView()
        self.web_map.setStyleSheet("background-color: #0b0f19;")
        settings = self.web_map.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)

        map_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "ui", "map_view.html"))
        self.web_map.load(QUrl.fromLocalFile(map_path))
        self.web_map.titleChanged.connect(self.on_map_event)
        self.web_map.loadFinished.connect(lambda ok: QTimer.singleShot(400, self.safe_fix_map))

        self.primary_layout = QVBoxLayout(self.primary_host)
        self.primary_layout.setContentsMargins(0, 0, 0, 0)
        self.primary_layout.addWidget(self.web_map)

        self.pip_layout = QVBoxLayout(self.pip_host)
        self.pip_layout.setContentsMargins(0, 0, 0, 0)
        self.pip_layout.addWidget(self.video_view)

        self.btn_swap_pip = QPushButton("⇄ SWAP", self.pip_host)
        self.btn_swap_pip.setGeometry(6, 6, 64, 22)
        self.btn_swap_pip.setStyleSheet("background: rgba(0,0,0,0.85); color: #00ffcc; font-size: 9pt; font-weight: bold; border-radius: 3px;")
        self.btn_swap_pip.clicked.connect(self.swap_views)

        # Top Telemetry Dashboard
        self.top_dashboard = QFrame(self.canvas)
        self.top_dashboard.setObjectName("top_dashboard")
        self.top_dashboard.setStyleSheet("""
            QFrame#top_dashboard { background-color: #dc2626; border-bottom: 2px solid rgba(0,0,0,0.4); }
            QLabel { color: #ffffff; font-family: 'Segoe UI', 'Consolas', monospace; font-weight: bold; font-size: 10pt; }
        """)
        td_layout = QHBoxLayout(self.top_dashboard)
        td_layout.setContentsMargins(10, 3, 10, 3)
        td_layout.setSpacing(8)

        self.lbl_conn_status = QLabel("DRONE DISCONNECTED")
        self.lbl_conn_status.setFont(QFont("Segoe UI", 10, QFont.Bold))
        td_layout.addWidget(self.lbl_conn_status)

        self.lbl_veh_msg = QLabel("MSG: TELEMETRY DISCONNECTED")
        self.lbl_veh_msg.setStyleSheet("color: #fef08a; font-size: 10pt; max-width: 280px;")
        td_layout.addWidget(self.lbl_veh_msg, stretch=1)

        self.lbl_flight_mode = QLabel("MODE: --")
        self.lbl_flight_mode.setStyleSheet("color: #ffffff; font-size: 10pt; padding: 2px 10px; background: rgba(0,0,0,0.3); border-radius: 3px;")
        td_layout.addWidget(self.lbl_flight_mode)

        self.lbl_voltage = QLabel("🔋 -- V")
        td_layout.addWidget(self.lbl_voltage)

        self.lbl_gps_hdop = QLabel("🛰 0 Sats (HDOP: --)")
        td_layout.addWidget(self.lbl_gps_hdop)

        self.cmb_conn_type = QComboBox()
        self.cmb_conn_type.setProperty("class", "mav_combo_box")
        self.cmb_conn_type.setEditable(True)
        self.cmb_conn_type.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_conn_type.setFixedWidth(145)
        self.cmb_conn_type.activated.connect(self.on_conn_type_selected)
        td_layout.addWidget(self.cmb_conn_type)

        self.cmb_baud = QComboBox()
        self.cmb_baud.setProperty("class", "mav_combo_box")
        self.cmb_baud.setEditable(True)
        self.cmb_baud.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_baud.addItems(["115200", "57600", "9600", "38400", "921600", "1500000"])
        self.cmb_baud.setFixedWidth(90)
        td_layout.addWidget(self.cmb_baud)

        self.btn_mav_connect = QPushButton("CONNECT")
        self.btn_mav_connect.setStyleSheet("background-color: #0f172a; color: #00ffcc; border: 1px solid #38bdf8; border-radius: 4px; font-size: 9pt; font-weight: bold; padding: 3px 8px;")
        self.btn_mav_connect.clicked.connect(self.toggle_drone_connection)
        td_layout.addWidget(self.btn_mav_connect)

        self.hud_overlay = TacticalOverlayHUD(self.canvas)

        # Unified Control Panel (DOOAF + FLIGHT PLAN + PLOT COORD)
        self.unified_control_panel = QFrame(self.canvas)
        self.unified_control_panel.setObjectName("control_bar_panel")
        cp_layout = QHBoxLayout(self.unified_control_panel)
        cp_layout.setContentsMargins(6, 4, 6, 4)
        cp_layout.setSpacing(6)

        self.btn_dooaf_setup = QPushButton("🎯 DOOAF SETUP", self.unified_control_panel)
        self.btn_dooaf_setup.setObjectName("setup_btn")
        self.btn_dooaf_setup.clicked.connect(self.open_dooaf_setup)
        cp_layout.addWidget(self.btn_dooaf_setup)

        self.btn_flight_plan = QPushButton("✈ FLIGHT PLAN", self.unified_control_panel)
        self.btn_flight_plan.setObjectName("plan_mode_btn")
        self.btn_flight_plan.clicked.connect(self.enter_flight_plan_mode)
        cp_layout.addWidget(self.btn_flight_plan)

        self.btn_coord_plot = QPushButton("📍 PLOT COORD", self.unified_control_panel)
        self.btn_coord_plot.setObjectName("coord_btn")
        self.btn_coord_plot.clicked.connect(self.open_coordinate_dialog)
        cp_layout.addWidget(self.btn_coord_plot)

        # Left Toolbar: Camera & Report
        self.left_toolbar = QWidget(self.canvas)
        lt_layout = QVBoxLayout(self.left_toolbar)
        lt_layout.setContentsMargins(0, 0, 0, 0)
        lt_layout.setSpacing(12)

        self.btn_cam = QPushButton("📹")
        self.btn_cam.setProperty("class", "circle_btn")
        self.btn_cam.setToolTip("Toggle Gimbal Feed")
        self.btn_cam.clicked.connect(self.toggle_camera)

        self.btn_report = QPushButton("📄")
        self.btn_report.setProperty("class", "circle_btn")
        self.btn_report.setToolTip("Export DOOAF Fire Correction Report")
        self.btn_report.clicked.connect(self.show_mission_report)

        lt_layout.addWidget(self.btn_cam)
        lt_layout.addWidget(self.btn_report)

        # Gimbal Camera & Video Recording Control Panel (Top-Right Map Placement)
        self.gimbal_panel = GimbalControlPanel(self.canvas)
        self.gimbal_panel.gimbal_command.connect(self.handle_gimbal_delta)
        self.gimbal_panel.gimbal_mode_command.connect(self.handle_gimbal_mode)
        self.gimbal_panel.zoom_changed.connect(self.handle_zoom_changed)
        self.gimbal_panel.snapshot_requested.connect(self.handle_snapshot)
        self.gimbal_panel.record_toggled.connect(self.handle_recording_toggled)

        # QGC Flight Plan Panels
        self.plan_top_bar = PlanTopStatsBar(self.canvas)
        self.plan_top_bar.exit_clicked.connect(self.exit_flight_plan_mode)
        self.plan_top_bar.upload_clicked.connect(self.upload_planned_mission)
        self.plan_top_bar.add_coord_clicked.connect(self.open_coordinate_dialog)
        self.plan_top_bar.hide()

        self.plan_tools = PlanLeftToolBar(self.canvas)
        self.plan_tools.tool_triggered.connect(self.handle_plan_tool)
        self.plan_tools.hide()

        self.plan_side_panel = PlanRightMissionPanel(self.canvas)
        self.plan_side_panel.action_clicked.connect(self.handle_mission_action_clicked)
        self.plan_side_panel.clear_mission_clicked.connect(self.clear_mission_plan)
        self.plan_side_panel.waypoint_deleted.connect(self.delete_waypoint)
        self.plan_side_panel.waypoint_param_changed.connect(self.handle_waypoint_param_update)
        self.plan_side_panel.finish_action_changed.connect(self.handle_finish_action_update)
        self.plan_side_panel.hide()

        # Dialogs
        self.setup_dialog = DooafSetupDialog(self)
        self.setup_dialog.pick_requested.connect(self.handle_dialog_pick_request)
        self.setup_dialog.setup_applied.connect(self.handle_setup_applied)
        self.setup_dialog.reset_requested.connect(self.reset_mission_targets)
        self.setup_dialog.dem_uploaded.connect(self.handle_dem_uploaded)

        if self.dem.dataset:
            self.setup_dialog.set_dem_status(os.path.basename(self.dem.dem_path), True)

        self.goto_dialog = CoordinateGotoDialog(self)
        self.goto_dialog.coordinate_selected.connect(self.handle_unified_coordinate_input)

        self.udp_dialog = UdpConfigDialog(self)
        self.udp_dialog.udp_configured.connect(self.on_udp_configured)

        self.scan_serial_ports()
        self.port_scan_timer = QTimer(self)
        self.port_scan_timer.timeout.connect(self.scan_serial_ports)
        self.port_scan_timer.start(1500)

    # -----------------------------------------------------------------
    # Gimbal & Recording Handlers
    # -----------------------------------------------------------------
    def handle_gimbal_delta(self, pitch_delta: float, yaw_delta: float):
        self.gimbal_pitch = max(-90.0, min(20.0, self.gimbal_pitch + pitch_delta))
        self.gimbal_yaw = (self.gimbal_yaw + yaw_delta) % 360.0
        self._send_mavlink_gimbal(self.gimbal_pitch, self.gimbal_yaw)

    def handle_gimbal_mode(self, mode: str):
        if mode == "HOME":
            self.gimbal_pitch = 0.0
            self.gimbal_yaw = 0.0
        elif mode == "NADIR_90":
            self.gimbal_pitch = -90.0
            self.gimbal_yaw = 0.0
        self._send_mavlink_gimbal(self.gimbal_pitch, self.gimbal_yaw)

    def _send_mavlink_gimbal(self, pitch: float, yaw: float):
        if self.mav_worker and self.mav_worker.master:
            master = self.mav_worker.master
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOUNT_CONTROL,
                0,
                pitch * 100.0, 0.0, yaw * 100.0,
                0, 0, 0,
                mavutil.mavlink.MAV_MOUNT_MODE_MAVLINK_TARGETING
            )
            self.lbl_veh_msg.setText(f"MSG: GIMBAL PITCH {pitch:.0f}° | YAW {yaw:.0f}°")

    def handle_zoom_changed(self, zoom: float):
        if self.cam_worker:
            self.cam_worker.set_zoom(zoom)

    def handle_snapshot(self):
        if self.cam_worker and self.cam_worker.isRunning():
            self.cam_worker.trigger_snapshot()
            self.lbl_veh_msg.setText("MSG: SNAPSHOT CAPTURED TO /snapshots")
        else:
            QMessageBox.information(self, "Camera Inactive", "Start gimbal camera feed to capture snapshot.")
    def handle_recording_toggled(self, is_recording: bool):
        if is_recording:
            if self.cam_worker and self.cam_worker.isRunning():
                self.cam_worker.start_recording("recordings")
                self.lbl_veh_msg.setText("MSG: 🔴 RECORDING VIDEO FEED...")
            else:
                QMessageBox.warning(self, "No Video Feed", "Connect camera feed first to record.")
                self.gimbal_panel.toggle_recording()
        else:
            if self.cam_worker:
                saved_path = getattr(self.cam_worker, "record_filename", None)
                self.cam_worker.stop_recording()
                self.lbl_veh_msg.setText("MSG: VIDEO RECORDING SAVED TO /recordings")

                # Optional: Automatically open Windows File Explorer to the saved file
                if saved_path and os.path.exists(saved_path):
                    import subprocess
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(saved_path)}"')
    def open_coordinate_dialog(self):
        is_plan = (self.current_view_mode == "PLAN")
        self.goto_dialog.set_mode_hint(is_plan)
        self.goto_dialog.show()
        self.goto_dialog.raise_()

    def handle_unified_coordinate_input(self, lat: float, lon: float, coord_str: str, alt: float):
        if not self.map_is_primary:
            self.swap_views()

        if self.current_view_mode == "PLAN":
            speed = 5.0
            hover = 0.0
            self.web_map.page().runJavaScript(
                f"if (typeof addWaypoint === 'function') {{{{ addWaypoint({lat}, {lon}, {alt}, {speed}, {hover}); }}}}"
            )
            self.lbl_veh_msg.setText(f"MSG: ADDED WAYPOINT AT {lat:.6f}, {lon:.6f}")
        else:
            mgrs_val = to_mgrs_gr(lat, lon)
            self.web_map.page().runJavaScript(
                f"if (typeof panAndHighlightLocation === 'function') {{{{ panAndHighlightLocation({lat}, {lon}, '{mgrs_val}'); }}}}"
            )
            self.lbl_veh_msg.setText(f"MSG: PLOTTED LOCATION -> {mgrs_val}")

    def enter_flight_plan_mode(self):
        self.current_view_mode = "PLAN"
        if not self.map_is_primary:
            self.swap_views()

        self.unified_control_panel.hide()
        self.left_toolbar.hide()

        self.plan_top_bar.show()
        self.plan_tools.show()
        self.plan_side_panel.show()

        self.web_map.page().runJavaScript("if (typeof setSelectionMode === 'function') { setSelectionMode('WAYPOINT'); }")
        self.lbl_veh_msg.setText("MSG: FLIGHT PLAN MODE - CLICK MAP TO DROP WAYPOINTS")
        self.resizeEvent(None)

    def exit_flight_plan_mode(self):
        self.current_view_mode = "FLY"
        self.plan_top_bar.hide()
        self.plan_tools.hide()
        self.plan_side_panel.hide()

        self.unified_control_panel.show()
        self.left_toolbar.show()

        self.web_map.page().runJavaScript("if (typeof setSelectionMode === 'function') { setSelectionMode('NONE'); }")
        self.lbl_veh_msg.setText("MSG: RETURNED TO FLY VIEW")
        self.resizeEvent(None)

    def handle_plan_tool(self, tool_name):
        if tool_name == "WAYPOINT":
            self.web_map.page().runJavaScript("if (typeof setSelectionMode === 'function') { setSelectionMode('WAYPOINT'); }")
            self.lbl_veh_msg.setText("MSG: CLICK MAP TO ADD WAYPOINTS")
        elif tool_name == "TAKEOFF":
            home_lat = self.hud_overlay.telem.get("lat", 20.5937)
            home_lon = self.hud_overlay.telem.get("lon", 78.9629)
            self.web_map.page().runJavaScript(
                f"if (typeof addWaypoint === 'function') {{{{ addWaypoint({home_lat}, {home_lon}, 20.0, 5.0, 0.0); }}}}"
            )
        elif tool_name == "CENTER":
            lat = self.hud_overlay.telem.get("lat")
            lon = self.hud_overlay.telem.get("lon")
            if lat and lon:
                self.web_map.page().runJavaScript(
                    f"if (typeof map !== 'undefined' && map) {{{{ map.setView([{lat}, {lon}], 17); }}}}"
                )
        elif tool_name == "FILE_SAVE":
            self.save_mission_to_file()
        elif tool_name == "FILE_OPEN":
            self.open_mission_from_file()
        elif tool_name == "FILE_CLEAR":
            self.clear_mission_plan()

    def scan_serial_ports(self):
        current_text = self.cmb_conn_type.currentText().strip()
        ports = list(serial.tools.list_ports.comports())

        available_items = []
        for p in ports:
            dev = p.device
            desc = p.description or ""
            if desc and desc != dev and "n/a" not in desc.lower():
                short_desc = desc.split("(")[0].strip()
                item_label = f"{dev} ({short_desc})"
            else:
                item_label = dev
            available_items.append((dev, item_label))

        available_items.append(("UDP", f"UDP ({self.custom_udp_conn})"))
        available_items.append(("TCP", "TCP (127.0.0.1:5760)"))

        existing_items = [self.cmb_conn_type.itemText(i) for i in range(self.cmb_conn_type.count())]
        new_labels = [item[1] for item in available_items]

        if existing_items != new_labels:
            self.cmb_conn_type.blockSignals(True)
            self.cmb_conn_type.clear()
            for dev, label in available_items:
                self.cmb_conn_type.addItem(label, userData=dev)

            if current_text:
                idx = self.cmb_conn_type.findText(current_text, Qt.MatchContains)
                if idx != -1:
                    self.cmb_conn_type.setCurrentIndex(idx)
                else:
                    self.cmb_conn_type.setEditText(current_text)
            elif ports:
                self.cmb_conn_type.setCurrentIndex(0)

            self.cmb_conn_type.blockSignals(False)

    def on_conn_type_selected(self, index):
        text = self.cmb_conn_type.itemText(index)
        if text.startswith("UDP"):
            self.udp_dialog.show()

    def on_udp_configured(self, conn_str, port):
        self.custom_udp_conn = conn_str
        self.scan_serial_ports()
        idx = self.cmb_conn_type.findText("UDP", Qt.MatchContains)
        if idx != -1:
            self.cmb_conn_type.setCurrentIndex(idx)
        self.start_mav_worker(self.custom_udp_conn, int(self.cmb_baud.currentText().strip() or 115200))

    def get_connection_string(self):
        raw_text = self.cmb_conn_type.currentText().strip()
        if raw_text.upper().startswith("UDP"): return self.custom_udp_conn
        if raw_text.upper().startswith("TCP"): return "tcp:127.0.0.1:5760"

        current_data = self.cmb_conn_type.currentData()
        if current_data and current_data.startswith("COM"): return current_data

        if "COM" in raw_text.upper():
            for p in raw_text.upper().split():
                cleaned = p.replace("(", "").replace(")", "").replace(":", "").strip()
                if cleaned.startswith("COM") and any(ch.isdigit() for ch in cleaned):
                    return cleaned

        return raw_text if raw_text else "COM1"

    def start_mav_worker(self, conn_str, baud):
        self.lbl_conn_status.setText("CONNECTING...")
        self.btn_mav_connect.setText("DISCONNECT")
        self.lbl_veh_msg.setText(f"MSG: OPENING {conn_str} @ {baud}...")

        self.mav_worker = MavlinkWorker(connection_string=conn_str, baud=baud)
        self.mav_worker.telemetry_updated.connect(self.on_telemetry_updated)
        self.mav_worker.start()

    def toggle_drone_connection(self):
        if self.mav_worker and self.mav_worker.isRunning():
            self.mav_worker.stop()
            self.mav_worker = None
            self.btn_mav_connect.setText("CONNECT")
            self.lbl_conn_status.setText("DRONE DISCONNECTED")
            self.top_dashboard.setStyleSheet("QFrame#top_dashboard { background-color: #dc2626; } QLabel { color: #fff; }")
            self.mission_execution_state = "IDLE"
            self.plan_side_panel.set_button_state("START")
            self.lbl_veh_msg.setText("MSG: TELEMETRY DISCONNECTED")
        else:
            conn_str = self.get_connection_string()
            baud_text = self.cmb_baud.currentText().strip()
            baud = int(baud_text) if baud_text.isdigit() else 115200
            self.start_mav_worker(conn_str, baud)

    def on_telemetry_updated(self, t):
        self.hud_overlay.update_telemetry(t)
        if t.get("connected"):
            self.top_dashboard.setStyleSheet("QFrame#top_dashboard { background-color: #16a34a; } QLabel { color: #fff; }")
            self.lbl_conn_status.setText("DRONE CONNECTED")
            self.lbl_flight_mode.setText(f"MODE: {t.get('sub_mode', '--')}")
            self.lbl_voltage.setText(f"🔋 {t.get('voltage', 0.0):.2f}V")
            self.lbl_gps_hdop.setText(f"🛰 {t.get('sats', 0)} Sats (HDOP: {t.get('hdop', 1.0):.1f})")
            if "stat_msg" in t and t["stat_msg"]:
                self.lbl_veh_msg.setText(f"MSG: {t['stat_msg']}")

        lat = t.get("lat")
        lon = t.get("lon")
        compass = t.get("compass", 0.0)
        if lat and lon:
            self.web_map.page().runJavaScript(
                f"if (typeof updatePosition === 'function') {{{{ updatePosition({lat}, {lon}, {compass}); }}}}"
            )

    def save_mission_to_file(self):
        if not self.planned_waypoints:
            QMessageBox.warning(self, "Empty Plan", "There are no waypoints to save.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Flight Plan",
            os.path.expanduser("~/Documents/mission.plan"),
            "QGC Plan Files (*.plan);;JSON Mission Files (*.json);;All Files (*.*)"
        )
        if not file_path: return

        try:
            plan_data = {
                "fileType": "Plan",
                "version": 1,
                "groundStation": "VIKAS GCS",
                "mission": {
                    "cruiseSpeed": 5.0,
                    "hoverDelayDefault": 0.0,
                    "finishAction": self.plan_side_panel.get_selected_finish_action(),
                    "items": self.planned_waypoints
                }
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(plan_data, f, indent=4)

            QMessageBox.information(self, "Plan Saved", f"Mission saved to:\n{os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save plan:\n{e}")

    def open_mission_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Flight Plan",
            os.path.expanduser("~/Documents"),
            "Mission Files (*.plan *.json);;All Files (*.*)"
        )
        if not file_path or not os.path.exists(file_path): return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            waypoints_loaded = []
            finish_act = "RTL"

            if "mission" in data and "items" in data["mission"]:
                finish_act = data["mission"].get("finishAction", "RTL")
                for itm in data["mission"]["items"]:
                    waypoints_loaded.append({
                        "lat": float(itm.get("lat")),
                        "lon": float(itm.get("lon")),
                        "alt": float(itm.get("alt", 30.0)),
                        "speed": float(itm.get("speed", 5.0)),
                        "hover": float(itm.get("hover", 0.0))
                    })
            elif isinstance(data, list):
                for itm in data:
                    waypoints_loaded.append({
                        "lat": float(itm["lat"]),
                        "lon": float(itm["lon"]),
                        "alt": float(itm.get("alt", 30.0)),
                        "speed": float(itm.get("speed", 5.0)),
                        "hover": float(itm.get("hover", 0.0))
                    })

            if not waypoints_loaded:
                QMessageBox.warning(self, "Empty Plan", "The file contains no valid waypoints.")
                return

            self.plan_side_panel.set_selected_finish_action(finish_act)
            js_payload = json.dumps(waypoints_loaded)
            self.web_map.page().runJavaScript(f"loadWaypointsBatch({js_payload});")

            self.planned_waypoints = waypoints_loaded
            self.plan_side_panel.update_waypoint_items(self.planned_waypoints)
            self.mission_execution_state = "IDLE"
            self.plan_side_panel.set_button_state("START")

            home_lat = self.hud_overlay.telem.get("lat")
            home_lon = self.hud_overlay.telem.get("lon")
            self.plan_top_bar.update_stats(self.planned_waypoints, home_lat, home_lon)

            QMessageBox.information(self, "Plan Loaded", f"Loaded {len(waypoints_loaded)} waypoints.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load plan:\n{e}")

    def handle_waypoint_param_update(self, idx, new_alt, new_spd, new_hov):
        self.web_map.page().runJavaScript(
            f"if (typeof updateWaypointParams === 'function') {{{{ updateWaypointParams({idx}, {new_alt}, {new_spd}, {new_hov}); }}}}"
        )

    def delete_waypoint(self, idx):
        self.web_map.page().runJavaScript(
            f"if (typeof deleteWaypointByIndex === 'function') {{{{ deleteWaypointByIndex({idx}); }}}}"
        )

    def handle_finish_action_update(self, action_code: str):
        self.web_map.page().runJavaScript("if (typeof redrawMissionRoute === 'function') { redrawMissionRoute(); }")

    def upload_planned_mission(self):
        if not self.planned_waypoints:
            QMessageBox.warning(self, "No Waypoints", "Please add waypoints first.")
            return

        if not self.mav_worker or not self.mav_worker.connected:
            QMessageBox.warning(self, "Drone Offline", "Connect the drone to upload waypoint mission.")
            return

        t = self.hud_overlay.telem
        sats = int(t.get("sats", 0))
        hdop = float(t.get("hdop", 99.0))
        force_bench = False

        if sats < 4 or hdop > 5.0:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("GPS / Sats Not Available")
            msg_box.setText(
                f"<b>GPS / Satellite lock not available!</b><br><br>"
                f"Current status: <b>{sats} Sats</b> (HDOP: <b>{hdop:.1f}</b>).<br><br>"
                f"ArduPilot / PX4 requires a 3D GPS fix to initialize EKF Home for relative waypoint navigation.<br><br>"
                f"<b>Would you like to inject a simulated Bench-Test Origin to test the upload indoors?</b>"
            )
            btn_yes = msg_box.addButton("Yes (Bench Test)", QMessageBox.YesRole)
            btn_no = msg_box.addButton("Cancel Upload", QMessageBox.NoRole)
            msg_box.exec()

            if msg_box.clickedButton() == btn_yes:
                force_bench = True
            else:
                self.lbl_veh_msg.setText("MSG: UPLOAD CANCELLED (WAITING FOR GPS)")
                return

        finish_action = self.plan_side_panel.get_selected_finish_action()
        self.lbl_veh_msg.setText(f"MSG: UPLOADING MISSION ({len(self.planned_waypoints)} WPs)...")

        self.mission_mgr = MissionManager(self.mav_worker)
        self.mission_mgr.mission_uploaded.connect(self._on_mission_upload_result)
        self.mission_mgr.upload_waypoint_mission(
            self.planned_waypoints,
            default_alt=30.0,
            default_speed=5.0,
            finish_action=finish_action,
            force_bench_origin=force_bench
        )

    def _on_mission_upload_result(self, success: bool, msg: str):
        if success:
            QMessageBox.information(self, "Mission Upload", "Mission uploaded successfully.")
            self.lbl_veh_msg.setText("MSG: MISSION UPLOADED SUCCESSFULLY")
            self.mission_execution_state = "IDLE"
            self.plan_side_panel.set_button_state("START")
        else:
            QMessageBox.warning(self, "Upload Failed", msg)
            self.lbl_veh_msg.setText(f"MSG: {msg}")

    def handle_mission_action_clicked(self):
        if not self.mav_worker or not self.mav_worker.connected:
            QMessageBox.warning(self, "Drone Offline", "Connect drone telemetry before starting mission.")
            return

        if not self.planned_waypoints:
            QMessageBox.warning(self, "No Mission", "Please plan and upload waypoints first.")
            return

        if not self.mission_mgr:
            self.mission_mgr = MissionManager(self.mav_worker)

        if self.mission_execution_state == "IDLE":
            if not self.mission_mgr.is_drone_armed():
                reply = QMessageBox.warning(
                    self,
                    "Drone Not Armed",
                    "Drone is not Armed!\n\nPlease arm the drone to start autonomous flight.\n\n"
                    "Would you like to send the ARM command now?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.mission_mgr.arm_vehicle()
                    self.lbl_veh_msg.setText("MSG: ARM COMMAND SENT TO DRONE")
                return

            self.mission_mgr.start_auto_mission()
            self.mission_execution_state = "RUNNING"
            self.plan_side_panel.set_button_state("PAUSE")
            self.lbl_veh_msg.setText("MSG: AUTONOMOUS MISSION RUNNING (MODE: AUTO)")

        elif self.mission_execution_state == "RUNNING":
            self.mission_mgr.pause_mission()
            self.mission_execution_state = "PAUSED"
            self.plan_side_panel.set_button_state("RESUME")
            self.lbl_veh_msg.setText("MSG: MISSION PAUSED (LOITER). MANUAL CONTROL ACTIVE.")

        elif self.mission_execution_state == "PAUSED":
            self.mission_mgr.resume_mission()
            self.mission_execution_state = "RUNNING"
            self.plan_side_panel.set_button_state("PAUSE")
            self.lbl_veh_msg.setText("MSG: MISSION RESUMED (MODE: AUTO)")

    def clear_mission_plan(self):
        self.planned_waypoints = []
        self.web_map.page().runJavaScript("if (typeof clearMissionWaypoints === 'function') { clearMissionWaypoints(); }")
        self.plan_side_panel.update_waypoint_items([])
        self.plan_top_bar.update_stats([])
        self.mission_execution_state = "IDLE"
        self.plan_side_panel.set_button_state("START")
        self.lbl_veh_msg.setText("MSG: CLEARED MISSION")

    def handle_dem_uploaded(self, file_path):
        success = self.dem.load_dem(file_path)
        self.setup_dialog.set_dem_status(os.path.basename(file_path), success)

    def resizeEvent(self, event):
        if event:
            super().resizeEvent(event)
        w, h = self.width(), self.height()
        self.canvas.setGeometry(0, 0, w, h)
        self.primary_host.setGeometry(0, 0, w, h)

        self.top_dashboard.setGeometry(0, 0, w, 36)
        self.hud_overlay.setGeometry(0, 0, w, h)

        # Bottom Left: PIP Video Window
        pip_w, pip_h = 280, 200
        pip_x, pip_y = 20, h - (pip_h + 30)
        self.pip_host.setGeometry(pip_x, pip_y, pip_w, pip_h)

        # Top-Right Corner Gimbal Control Panel:
        gimbal_w = 240
        gimbal_h = 36 if self.gimbal_panel.is_minimized else 160

        if self.current_view_mode == "FLY":
            self.unified_control_panel.setGeometry(10, 44, 340, 36)
            self.left_toolbar.setGeometry(20, 92, 50, 110)
            # Anchored at top-right corner
            self.gimbal_panel.setGeometry(w - gimbal_w - 20, 46, gimbal_w, gimbal_h)
        else:
            self.plan_top_bar.setGeometry(0, 36, w, 46)
            self.plan_tools.setGeometry(12, 90, 60, 330)
            self.plan_side_panel.setGeometry(w - 350, 42, 340, h - 50)
            # In Plan Mode, place immediately to the left of the Mission Settings panel
            self.gimbal_panel.setGeometry(w - 350 - gimbal_w - 15, 46, gimbal_w, gimbal_h)

        self.primary_host.lower()
        self.hud_overlay.raise_()
        self.top_dashboard.raise_()
        self.pip_host.raise_()
        self.btn_swap_pip.raise_()
        self.gimbal_panel.raise_()

        if self.current_view_mode == "FLY":
            self.unified_control_panel.raise_()
            self.left_toolbar.raise_()
        else:
            self.plan_top_bar.raise_()
            self.plan_tools.raise_()
            self.plan_side_panel.raise_()

        self.safe_fix_map()

    def swap_views(self):
        self.primary_layout.removeWidget(self.web_map if self.map_is_primary else self.video_view)
        self.pip_layout.removeWidget(self.video_view if self.map_is_primary else self.web_map)

        if self.map_is_primary:
            self.primary_layout.addWidget(self.video_view)
            self.pip_layout.addWidget(self.web_map)
            self.map_is_primary = False
        else:
            self.primary_layout.addWidget(self.web_map)
            self.pip_layout.addWidget(self.video_view)
            self.map_is_primary = True

        self.btn_swap_pip.raise_()
        self.safe_fix_map()

    def open_dooaf_setup(self):
        self.setup_dialog.show()

    def reset_mission_targets(self):
        self.target_pt = None
        self.impact_pt = None

    def handle_dialog_pick_request(self, entity_type, source_type):
        self.active_pick_entity = entity_type
        if source_type == "MAP":
            self.web_map.page().runJavaScript(
                f"if (typeof setSelectionMode === 'function') {{{{ setSelectionMode('{entity_type}'); }}}}"
            )
        elif source_type == "VIDEO":
            if self.map_is_primary:
                self.swap_views()
            self.video_view.set_selection_mode(True, entity=entity_type)

    def on_video_target_selected(self, px, py, w, h):
        t = self.hud_overlay.telem
        d_lat = t.get("lat", 20.5937)
        d_lon = t.get("lon", 78.9629)
        d_alt = t.get("alt", 0.0)
        effective_alt = d_alt if d_alt > 0.5 else 1.5

        pt_lat, pt_lon = self.dooaf.video_pixel_to_coord(
            px, py, w, h, d_lat, d_lon, effective_alt, self.gimbal_pitch, t.get("compass", 0.0)
        )
        pt_elev = self.dem.get_elevation(pt_lat, pt_lon, default=0.0)
        pt_mgrs = to_mgrs_gr(pt_lat, pt_lon)

        entity = self.active_pick_entity
        self.active_pick_entity = None

        if entity == "TARGET":
            self.target_pt = (pt_lat, pt_lon, pt_elev)
            self.setup_dialog.receive_picked_coord("TARGET", pt_lat, pt_lon, pt_elev)
            self.web_map.page().runJavaScript(
                f"if (typeof setTargetPosition === 'function') {{{{ setTargetPosition({pt_lat}, {pt_lon}); }}}}"
            )
            TacticalTargetPopup("TARGET", {"lat": pt_lat, "lon": pt_lon, "alt": pt_elev, "mgrs": pt_mgrs}, self).exec()
        elif entity == "IMPACT":
            self.impact_pt = (pt_lat, pt_lon, pt_elev)
            self.setup_dialog.receive_picked_coord("IMPACT", pt_lat, pt_lon, pt_elev)
            self.web_map.page().runJavaScript(
                f"if (typeof setImpactPosition === 'function') {{{{ setImpactPosition({pt_lat}, {pt_lon}); }}}}"
            )

    def on_map_event(self, title):
        if title.startswith("WP_SYNC:"):
            raw_data = title.replace("WP_SYNC:", "").strip()
            self.planned_waypoints = []
            if raw_data:
                for item in raw_data.split(";"):
                    parts = item.split(":")
                    if len(parts) >= 6:
                        self.planned_waypoints.append({
                            "wp_num": int(parts[0]),
                            "lat": float(parts[1]),
                            "lon": float(parts[2]),
                            "alt": float(parts[3]),
                            "speed": float(parts[4]),
                            "hover": float(parts[5])
                        })
                    elif len(parts) >= 4:
                        self.planned_waypoints.append({
                            "wp_num": int(parts[0]),
                            "lat": float(parts[1]),
                            "lon": float(parts[2]),
                            "alt": float(parts[3]),
                            "speed": float(parts[4]) if len(parts) > 4 else 5.0,
                            "hover": 0.0
                        })
            self.plan_side_panel.update_waypoint_items(self.planned_waypoints)
            home_lat = self.hud_overlay.telem.get("lat")
            home_lon = self.hud_overlay.telem.get("lon")
            self.plan_top_bar.update_stats(self.planned_waypoints, home_lat, home_lon)
            return

        if title.startswith("INSPECT:"):
            parts = title.replace("INSPECT:", "").split(",")
            lat, lon = float(parts[0]), float(parts[1])
            mgrs_val = to_mgrs_gr(lat, lon)
            self.web_map.page().runJavaScript(
                f"if (typeof showInspectPopup === 'function') {{{{ showInspectPopup({lat}, {lon}, '{mgrs_val}'); }}}}"
            )

    def handle_setup_applied(self, data):
        self.dooaf.battery_lat = data["gun_lat"]
        self.dooaf.battery_lon = data["gun_lon"]

    def show_mission_report(self):
        if not (self.target_pt and self.impact_pt and self.latest_corr): return
        html_content = generate_dooaf_html_report(
            battery_lat=self.dooaf.battery_lat, battery_lon=self.dooaf.battery_lon,
            target_pt=self.target_pt, impact_pt=self.impact_pt,
            drone_pt=(self.hud_overlay.telem.get("lat"), self.hud_overlay.telem.get("lon"), self.hud_overlay.telem.get("alt", 30.0)),
            corr_data=self.latest_corr, telem_data=self.hud_overlay.telem
        )
        DooafReportDialog(html_content, self).exec()

    def safe_fix_map(self):
        if hasattr(self, 'web_map') and self.web_map:
            self.web_map.page().runJavaScript("if (typeof fixMapSize === 'function') { fixMapSize(); }")

    def toggle_camera(self):
        if self.cam_worker:
            self.cam_worker.stop()
            self.cam_worker = None
            self.btn_cam.setStyleSheet("")
            self.video_view.setText("NO GIMBAL CAMERA FEED\n[Click 📹 on Left Toolbar]")
        else:
            url, ok = QInputDialog.getText(self, "Gimbal Camera Setup", "Enter RTSP URL:", QLineEdit.Normal, self.current_rtsp_url)
            if ok and url.strip():
                self.current_rtsp_url = url.strip()
                self.btn_cam.setStyleSheet("border: 2px solid #00ffcc; background: #0369a1; color: white;")
                self.cam_worker = GimbalCameraThread(source=self.current_rtsp_url, parent=self)
                self.cam_worker.frame_received.connect(self.video_view.update_frame)
                self.cam_worker.start()

    def closeEvent(self, event):
        self.port_scan_timer.stop()
        if self.cam_worker: self.cam_worker.stop()
        if self.mav_worker: self.mav_worker.stop()
        if self.dem: self.dem.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VikasFlyViewGCS()
    window.show()
    sys.exit(app.exec())