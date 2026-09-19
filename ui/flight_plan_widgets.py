import math
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QMenu
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QAction

PANEL_STYLE = """
QFrame#plan_top_bar {
    background: rgba(11, 15, 25, 0.96);
    border-bottom: 1px solid #334155;
}
QFrame#left_plan_tools {
    background: rgba(11, 15, 25, 0.94);
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QFrame#right_mission_panel {
    background: rgba(11, 15, 25, 0.96);
    border: 1px solid #334155;
    border-radius: 6px;
}
QPushButton.tool_btn {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    color: #cbd5e1;
    font-size: 8pt;
    font-weight: bold;
    min-width: 50px;
    min-height: 44px;
    max-width: 50px;
    max-height: 44px;
}
QPushButton.tool_btn:hover {
    background-color: #1e293b;
    border-color: #0284c7;
}
QPushButton.tool_btn_active {
    background-color: #eab308;
    border: 2px solid #facc15;
    border-radius: 4px;
    color: #0b0f19;
    font-size: 8pt;
    font-weight: 900;
    min-width: 50px;
    min-height: 44px;
    max-width: 50px;
    max-height: 44px;
}
QPushButton#btn_exit_plan {
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #ffffff;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 3px 10px;
    border-radius: 4px;
}
QPushButton#btn_exit_plan:hover {
    background-color: #dc2626;
}
QPushButton#btn_upload_plan {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 3px 12px;
    border-radius: 4px;
}
QPushButton#btn_upload_plan:hover {
    background-color: #0369a1;
}
QPushButton#btn_plan_coord {
    background-color: #0f766e;
    border: 1px solid #2dd4bf;
    color: #ffffff;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 3px 10px;
    border-radius: 4px;
}
QPushButton#btn_plan_coord:hover {
    background-color: #14b8a6;
}
QPushButton#btn_start_mission {
    background-color: #15803d;
    border: 1px solid #22c55e;
    color: #ffffff;
    font-weight: bold;
    font-size: 9.5pt;
    padding: 6px 12px;
    border-radius: 4px;
}
QPushButton#btn_start_mission:hover {
    background-color: #16a34a;
}
QPushButton#btn_pause_mission {
    background-color: #d97706;
    border: 1px solid #f59e0b;
    color: #ffffff;
    font-weight: bold;
    font-size: 9.5pt;
    padding: 6px 12px;
    border-radius: 4px;
}
QPushButton#btn_pause_mission:hover {
    background-color: #b45309;
}
QLabel.stat_title {
    color: #94a3b8;
    font-size: 7.5pt;
    font-weight: bold;
}
QLabel.stat_value {
    color: #ffffff;
    font-size: 8.5pt;
    font-family: 'Consolas', monospace;
    font-weight: bold;
}
QComboBox.qgc_combo {
    background: #0f172a;
    border: 1px solid #334155;
    color: #e2e8f0;
    padding: 3px 6px;
    border-radius: 3px;
    font-size: 8pt;
}
QLineEdit.qgc_row_input {
    background: #030712;
    border: 1px solid #334155;
    color: #facc15;
    font-family: 'Consolas', monospace;
    font-size: 8pt;
    padding: 2px 2px;
    border-radius: 3px;
    max-width: 36px;
    text-align: center;
}
QLineEdit.qgc_row_input:focus {
    border-color: #38bdf8;
}
QMenu {
    background-color: #0f172a;
    border: 1px solid #38bdf8;
    color: #e2e8f0;
    font-weight: bold;
    font-size: 8.5pt;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 20px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}
"""

class PlanTopStatsBar(QFrame):
    exit_clicked = Signal()
    upload_clicked = Signal()
    add_coord_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("plan_top_bar")
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # 1. Exit Button
        self.btn_exit = QPushButton("< Exit Plan")
        self.btn_exit.setObjectName("btn_exit_plan")
        self.btn_exit.clicked.connect(self.exit_clicked.emit)
        layout.addWidget(self.btn_exit)

        # 2. Upload Button
        self.btn_upload = QPushButton("Upload")
        self.btn_upload.setObjectName("btn_upload_plan")
        self.btn_upload.clicked.connect(self.upload_clicked.emit)
        layout.addWidget(self.btn_upload)

        # 3. Dedicated Coordinates Entry Button inside Plan Mode
        self.btn_coord = QPushButton("📍 + Coord WP")
        self.btn_coord.setObjectName("btn_plan_coord")
        self.btn_coord.setToolTip("Enter Latitude and Longitude to place a Waypoint automatically")
        self.btn_coord.clicked.connect(self.add_coord_clicked.emit)
        layout.addWidget(self.btn_coord)

        layout.addSpacing(6)

        # Selected Waypoint Stats
        sel_box = QVBoxLayout()
        lbl_sel = QLabel("Selected Waypoint")
        lbl_sel.setProperty("class", "stat_title")
        self.lbl_sel_val = QLabel("Alt diff: 0.0 m | Gradient: -- | Azimuth: -- | Dist prev WP: 0.0 m")
        self.lbl_sel_val.setProperty("class", "stat_value")
        sel_box.addWidget(lbl_sel)
        sel_box.addWidget(self.lbl_sel_val)
        layout.addLayout(sel_box)

        layout.addSpacing(8)

        # Total Mission Stats
        tot_box = QVBoxLayout()
        lbl_tot = QLabel("Total Mission (incl. return)")
        lbl_tot.setProperty("class", "stat_title")
        self.lbl_tot_val = QLabel("Distance: 0 m | Time: 00:00:00")
        self.lbl_tot_val.setProperty("class", "stat_value")
        tot_box.addWidget(lbl_tot)
        tot_box.addWidget(self.lbl_tot_val)
        layout.addLayout(tot_box)

        layout.addSpacing(8)

        # Max Telem Distance
        max_box = QVBoxLayout()
        lbl_max = QLabel("Max telem dist")
        lbl_max.setProperty("class", "stat_title")
        self.lbl_max_val = QLabel("0 m")
        self.lbl_max_val.setProperty("class", "stat_value")
        max_box.addWidget(lbl_max)
        max_box.addWidget(self.lbl_max_val)
        layout.addLayout(max_box)

        layout.addStretch()

    def update_stats(self, waypoints: list, home_lat=None, home_lon=None):
        if not waypoints:
            self.lbl_sel_val.setText("Alt diff: 0.0 m | Gradient: -- | Azimuth: -- | Dist prev WP: 0.0 m")
            self.lbl_tot_val.setText("Distance: 0 m | Time: 00:00:00")
            self.lbl_max_val.setText("0 m")
            return

        total_dist = 0.0
        max_dist_home = 0.0
        total_hover_time = 0.0

        for i in range(len(waypoints)):
            wp = waypoints[i]
            total_hover_time += float(wp.get("hover", 0.0))
            if i > 0:
                prev = waypoints[i - 1]
                d = self._calc_dist(prev["lat"], prev["lon"], wp["lat"], wp["lon"])
                total_dist += d

            if home_lat and home_lon:
                dh = self._calc_dist(home_lat, home_lon, wp["lat"], wp["lon"])
                if dh > max_dist_home:
                    max_dist_home = dh

        if home_lat and home_lon and len(waypoints) > 0:
            last = waypoints[-1]
            total_dist += self._calc_dist(last["lat"], last["lon"], home_lat, home_lon)

        avg_speed = float(waypoints[0].get("speed", 5.0)) if waypoints else 5.0
        flight_sec = int(total_dist / avg_speed) if avg_speed > 0 else 0
        total_sec = flight_sec + int(total_hover_time)

        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60

        self.lbl_tot_val.setText(f"Distance: {total_dist:.0f} m | Time: {hrs:02d}:{mins:02d}:{secs:02d}")
        self.lbl_max_val.setText(f"{max_dist_home:.0f} m")

        last_wp = waypoints[-1]
        prev_dist = 0.0
        azimuth = 0.0
        if len(waypoints) > 1:
            penult = waypoints[-2]
            prev_dist = self._calc_dist(penult["lat"], penult["lon"], last_wp["lat"], last_wp["lon"])
            azimuth = self._calc_bearing(penult["lat"], penult["lon"], last_wp["lat"], last_wp["lon"])

        alt_diff = float(last_wp.get("alt", 30.0))
        grad = (alt_diff / prev_dist * 100.0) if prev_dist > 0 else 0.0
        self.lbl_sel_val.setText(
            f"Alt diff: {alt_diff:+.1f} m | Gradient: {grad:+.1f}% | Azimuth: {azimuth:.0f}° | Dist prev WP: {prev_dist:.1f} m"
        )

    def _calc_dist(self, lat1, lon1, lat2, lon2):
        r = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    def _calc_bearing(self, lat1, lon1, lat2, lon2):
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlon = math.radians(lon2 - lon1)
        y = math.sin(dlon) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


class PlanLeftToolBar(QFrame):
    tool_triggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("left_plan_tools")
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedWidth(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 6, 5, 6)
        layout.setSpacing(6)

        self.btn_file = QPushButton("📁\nFile")
        self.btn_file.setProperty("class", "tool_btn")
        self.btn_file.clicked.connect(self._show_file_menu)
        layout.addWidget(self.btn_file)

        self.btn_takeoff = QPushButton("🛫\nTakeoff")
        self.btn_takeoff.setProperty("class", "tool_btn")
        self.btn_takeoff.clicked.connect(lambda: self.tool_triggered.emit("TAKEOFF"))
        layout.addWidget(self.btn_takeoff)

        self.btn_wp = QPushButton("📍\nWaypoint")
        self.btn_wp.setProperty("class", "tool_btn_active")
        self.btn_wp.clicked.connect(lambda: self.tool_triggered.emit("WAYPOINT"))
        layout.addWidget(self.btn_wp)

        self.btn_roi = QPushButton("🎯\nROI")
        self.btn_roi.setProperty("class", "tool_btn")
        self.btn_roi.clicked.connect(lambda: self.tool_triggered.emit("ROI"))
        layout.addWidget(self.btn_roi)

        self.btn_pattern = QPushButton("▤\nPattern")
        self.btn_pattern.setProperty("class", "tool_btn")
        self.btn_pattern.clicked.connect(lambda: self.tool_triggered.emit("PATTERN"))
        layout.addWidget(self.btn_pattern)

        self.btn_center = QPushButton("⊕\nCenter")
        self.btn_center.setProperty("class", "tool_btn")
        self.btn_center.clicked.connect(lambda: self.tool_triggered.emit("CENTER"))
        layout.addWidget(self.btn_center)

        layout.addStretch()

        self.file_menu = QMenu(self)
        self.file_menu.setStyleSheet(PANEL_STYLE)
        
        act_save = self.file_menu.addAction("💾 Save Plan to PC...")
        act_save.triggered.connect(lambda: self.tool_triggered.emit("FILE_SAVE"))

        act_load = self.file_menu.addAction("📂 Open Plan from PC...")
        act_load.triggered.connect(lambda: self.tool_triggered.emit("FILE_OPEN"))

        self.file_menu.addSeparator()

        act_clear = self.file_menu.addAction("🗑 Clear Mission")
        act_clear.triggered.connect(lambda: self.tool_triggered.emit("FILE_CLEAR"))

    def _show_file_menu(self):
        pos = self.btn_file.mapToGlobal(QPoint(self.btn_file.width() + 4, 0))
        self.file_menu.exec(pos)


class PlanRightMissionPanel(QFrame):
    action_clicked = Signal()
    clear_mission_clicked = Signal()
    waypoint_deleted = Signal(int)
    waypoint_param_changed = Signal(int, float, float, float)
    finish_action_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("right_mission_panel")
        self.setStyleSheet(PANEL_STYLE)
        self.setFixedWidth(340)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        hdr_box = QHBoxLayout()
        for tab_name, active in [("Mission", True), ("Fence", False), ("Rally", False)]:
            lbl = QLabel(tab_name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "background: #0284c7; color: white; font-weight: bold; border-radius: 3px; padding: 4px;"
                if active else
                "background: #1e293b; color: #94a3b8; font-weight: bold; border-radius: 3px; padding: 4px;"
            )
            hdr_box.addWidget(lbl)
        main_layout.addLayout(hdr_box)

        lbl_sec = QLabel("Mission Settings")
        lbl_sec.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 8.5pt; margin-top: 2px;")
        main_layout.addWidget(lbl_sec)

        lbl_finish = QLabel("After last waypoint:")
        lbl_finish.setStyleSheet("color: #94a3b8; font-size: 8pt; font-weight: bold;")
        main_layout.addWidget(lbl_finish)

        self.cmb_finish_action = QComboBox()
        self.cmb_finish_action.setProperty("class", "qgc_combo")
        self.cmb_finish_action.addItems([
            "Return to launch (RTL)",
            "Land at last point",
            "Hold position (Loiter)"
        ])
        self.cmb_finish_action.currentIndexChanged.connect(self._handle_finish_change)
        main_layout.addWidget(self.cmb_finish_action)

        self.btn_action = QPushButton("▶ Start Mission")
        self.btn_action.setObjectName("btn_start_mission")
        self.btn_action.clicked.connect(self.action_clicked.emit)
        main_layout.addWidget(self.btn_action)

        lbl_wp_list = QLabel("Waypoints & start (Alt | Speed | Hover)")
        lbl_wp_list.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 8pt; margin-top: 4px;")
        main_layout.addWidget(lbl_wp_list)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: #040810; border: 1px solid #1e293b; border-radius: 4px;")

        self.wp_list_container = QWidget()
        self.wp_list_layout = QVBoxLayout(self.wp_list_container)
        self.wp_list_layout.setContentsMargins(4, 4, 4, 4)
        self.wp_list_layout.setSpacing(4)
        self.wp_list_layout.addStretch()

        self.scroll.setWidget(self.wp_list_container)
        main_layout.addWidget(self.scroll, stretch=1)

        v_card = QFrame()
        v_card.setStyleSheet("background: #0b1118; border: 1px solid #1e293b; border-radius: 4px; padding: 4px;")
        vc_layout = QVBoxLayout(v_card)
        vc_layout.setContentsMargins(4, 4, 4, 4)
        vc_layout.setSpacing(2)

        lbl_v_info = QLabel("<b>Vehicle info:</b> ArduPilot Quad / Multirotor")
        lbl_v_info.setStyleSheet("color: #94a3b8; font-size: 7.5pt;")
        lbl_v_hint = QLabel("Adjust WP Alt (m), Speed (m/s), and Hover Delay (s).")
        lbl_v_hint.setStyleSheet("color: #64748b; font-size: 7pt; font-style: italic;")
        vc_layout.addWidget(lbl_v_info)
        vc_layout.addWidget(lbl_v_hint)
        main_layout.addWidget(v_card)

        btn_clear = QPushButton("Clear Waypoints")
        btn_clear.setStyleSheet("background: #7f1d1d; border: 1px solid #ef4444; color: white; padding: 3px; font-weight: bold; border-radius: 3px; font-size: 8pt;")
        btn_clear.clicked.connect(self.clear_mission_clicked.emit)
        main_layout.addWidget(btn_clear)

    def _handle_finish_change(self, index):
        code_map = {0: "RTL", 1: "LAND", 2: "HOLD"}
        self.finish_action_changed.emit(code_map.get(index, "RTL"))

    def get_selected_finish_action(self) -> str:
        idx = self.cmb_finish_action.currentIndex()
        return {0: "RTL", 1: "LAND", 2: "HOLD"}.get(idx, "RTL")

    def set_selected_finish_action(self, action: str):
        rev_map = {"RTL": 0, "LAND": 1, "HOLD": 2}
        idx = rev_map.get(action.upper(), 0)
        self.cmb_finish_action.setCurrentIndex(idx)

    def set_button_state(self, state: str):
        if state == "PAUSE":
            self.btn_action.setText("⏸ Pause Mission")
            self.btn_action.setObjectName("btn_pause_mission")
        elif state == "RESUME":
            self.btn_action.setText("▶ Resume Mission")
            self.btn_action.setObjectName("btn_start_mission")
        else:
            self.btn_action.setText("▶ Start Mission")
            self.btn_action.setObjectName("btn_start_mission")
        self.btn_action.setStyle(self.btn_action.style())

    def update_waypoint_items(self, waypoints: list):
        while self.wp_list_layout.count() > 1:
            item = self.wp_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        card_start = QFrame()
        card_start.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 3px;")
        cs_layout = QHBoxLayout(card_start)
        cs_layout.setContentsMargins(6, 4, 6, 4)
        lbl_s = QLabel("<b>Start</b>")
        lbl_s.setStyleSheet("color: #10b981; font-size: 8pt;")
        cs_layout.addWidget(lbl_s)
        cs_layout.addStretch()
        lbl_sh = QLabel("0.0 m | Launch")
        lbl_sh.setStyleSheet("color: #64748b; font-size: 7.5pt;")
        cs_layout.addWidget(lbl_sh)
        self.wp_list_layout.insertWidget(0, card_start)

        for idx, wp in enumerate(waypoints):
            card = QFrame()
            card.setStyleSheet("background: #0b1118; border: 1px solid #1e293b; border-radius: 3px;")
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(4, 3, 4, 3)
            c_layout.setSpacing(3)

            lbl_num = QLabel(f"<b>W{idx + 1}</b>")
            lbl_num.setStyleSheet("color: #facc15; font-size: 8pt; font-family: Consolas;")
            c_layout.addWidget(lbl_num)

            txt_alt = QLineEdit(f"{float(wp.get('alt', 30.0)):.0f}")
            txt_alt.setProperty("class", "qgc_row_input")
            txt_alt.setToolTip("Altitude (m)")
            c_layout.addWidget(txt_alt)
            lbl_m = QLabel("m")
            lbl_m.setStyleSheet("color: #64748b; font-size: 7pt;")
            c_layout.addWidget(lbl_m)

            txt_spd = QLineEdit(f"{float(wp.get('speed', 5.0)):.1f}")
            txt_spd.setProperty("class", "qgc_row_input")
            txt_spd.setToolTip("Speed (m/s)")
            c_layout.addWidget(txt_spd)
            lbl_ms = QLabel("m/s")
            lbl_ms.setStyleSheet("color: #64748b; font-size: 7pt;")
            c_layout.addWidget(lbl_ms)

            txt_hov = QLineEdit(f"{float(wp.get('hover', 0.0)):.0f}")
            txt_hov.setProperty("class", "qgc_row_input")
            txt_hov.setToolTip("Hover / Hold time at this WP (seconds)")
            c_layout.addWidget(txt_hov)
            lbl_s_unit = QLabel("s")
            lbl_s_unit.setStyleSheet("color: #38bdf8; font-size: 7.5pt; font-weight: bold;")
            c_layout.addWidget(lbl_s_unit)

            def make_change_handler(wp_index, alt_edit, spd_edit, hov_edit):
                def handler():
                    try:
                        new_alt = float(alt_edit.text().strip())
                        new_spd = float(spd_edit.text().strip())
                        new_hov = float(hov_edit.text().strip())
                        self.waypoint_param_changed.emit(wp_index, new_alt, new_spd, new_hov)
                    except ValueError:
                        pass
                return handler

            ch_handler = make_change_handler(idx, txt_alt, txt_spd, txt_hov)
            txt_alt.editingFinished.connect(ch_handler)
            txt_spd.editingFinished.connect(ch_handler)
            txt_hov.editingFinished.connect(ch_handler)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(16, 16)
            btn_del.setStyleSheet("background: transparent; color: #ef4444; border: none; font-weight: bold;")
            btn_del.clicked.connect(lambda checked=False, i=idx: self.waypoint_deleted.emit(i))
            c_layout.addWidget(btn_del)

            self.wp_list_layout.insertWidget(idx + 1, card)