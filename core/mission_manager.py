import time
from pymavlink import mavutil
from PySide6.QtCore import QObject, Signal, QEventLoop, QTimer


class MissionManager(QObject):
    upload_progress = Signal(int, int)
    mission_uploaded = Signal(bool, str)
    mission_started = Signal(bool, str)
    mission_paused = Signal(bool, str)
    mission_resumed = Signal(bool, str)

    def __init__(self, mav_worker=None):
        super().__init__()
        self.mav_worker = mav_worker
        self._pending_msg = None
        self._loop = None

        if self.mav_worker and hasattr(self.mav_worker, "mission_msg_received"):
            self.mav_worker.mission_msg_received.connect(self._on_mission_packet)

    def _on_mission_packet(self, msg):
        self._pending_msg = msg
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    def _wait_for_packet(self, timeout_sec=2.0):
        """Safely waits for a mission packet without directly polling the busy serial port."""
        self._pending_msg = None
        self._loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self._loop.quit)
        timer.start(int(timeout_sec * 1000))
        self._loop.exec()
        return self._pending_msg

    def is_drone_armed(self) -> bool:
        if not self.mav_worker or not self.mav_worker.master:
            return False
        if hasattr(self.mav_worker, "motors_armed"):
            return bool(self.mav_worker.motors_armed)
        return bool(self.mav_worker.master.motors_armed())

    def arm_vehicle(self):
        if not self.mav_worker or not self.mav_worker.master:
            return False
        master = self.mav_worker.master
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )
        return True

    def upload_waypoint_mission(
        self,
        waypoints: list,
        default_alt: float = 30.0,
        default_speed: float = 5.0,
        finish_action: str = "RTL",
        force_bench_origin: bool = False
    ):
        """Uploads waypoints and injects an artificial EKF origin if running in bench-test mode."""
        if not self.mav_worker or not self.mav_worker.master:
            self.mission_uploaded.emit(False, "Drone not connected")
            return

        if not waypoints:
            self.mission_uploaded.emit(False, "Waypoint list is empty")
            return

        master = self.mav_worker.master
        target_sys = master.target_system
        target_comp = master.target_component

        # Determine home coordinate
        home_lat = getattr(self.mav_worker, "home_lat", None)
        home_lon = getattr(self.mav_worker, "home_lon", None)
        if not home_lat or home_lat == 0.0 or force_bench_origin:
            home_lat = waypoints[0]["lat"]
            home_lon = waypoints[0]["lon"]

        # Bench Test Override: Force EKF Origin and Home so FC accepts relative altitudes with 0 Sats
        if force_bench_origin:
            lat_int = int(home_lat * 1e7)
            lon_int = int(home_lon * 1e7)

            master.mav.set_gps_global_origin_send(
                target_sys,
                lat_int,
                lon_int,
                0
            )
            time.sleep(0.04)

            master.mav.command_long_send(
                target_sys,
                target_comp,
                mavutil.mavlink.MAV_CMD_DO_SET_HOME,
                0,
                0, 0, 0, 0,
                home_lat, home_lon, 0.0
            )
            time.sleep(0.06)

        full_mission = []
        # Sequence 0: Home / Launch reference
        full_mission.append({
            "lat": home_lat,
            "lon": home_lon,
            "alt": 0.0,
            "cmd": mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            "autocontinue": 1,
            "p1": 0.0
        })

        for wp in waypoints:
            hover_sec = float(wp.get("hover", 0.0))
            full_mission.append({
                "lat": wp["lat"],
                "lon": wp["lon"],
                "alt": float(wp.get("alt", default_alt)),
                "cmd": mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                "autocontinue": 1,
                "p1": hover_sec
            })

        # Terminal action after last waypoint
        last_wp = waypoints[-1]
        if finish_action == "RTL":
            full_mission.append({
                "lat": home_lat,
                "lon": home_lon,
                "alt": 0.0,
                "cmd": mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                "autocontinue": 1,
                "p1": 0.0
            })
        elif finish_action == "LAND":
            full_mission.append({
                "lat": last_wp["lat"],
                "lon": last_wp["lon"],
                "alt": 0.0,
                "cmd": mavutil.mavlink.MAV_CMD_NAV_LAND,
                "autocontinue": 1,
                "p1": 0.0
            })
        elif finish_action == "HOLD":
            full_mission.append({
                "lat": last_wp["lat"],
                "lon": last_wp["lon"],
                "alt": float(last_wp.get("alt", default_alt)),
                "cmd": mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
                "autocontinue": 0,
                "p1": 0.0
            })

        total_items = len(full_mission)

        # Clear existing mission
        master.mav.mission_clear_all_send(target_sys, target_comp)
        time.sleep(0.08)

        # Retry loop for initial mission handshake
        for attempt in range(4):
            master.mav.mission_count_send(
                target_sys,
                target_comp,
                total_items,
                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
            )

            start_wait = time.time()
            while time.time() - start_wait < 1.5:
                # If signal mechanism is connected, wait for packet event; otherwise fallback to recv_match
                if hasattr(self.mav_worker, "mission_msg_received"):
                    msg = self._wait_for_packet(timeout_sec=0.8)
                else:
                    msg = master.recv_match(
                        type=['MISSION_REQUEST_INT', 'MISSION_REQUEST', 'MISSION_ACK'],
                        blocking=True,
                        timeout=0.8
                    )

                if not msg:
                    continue

                m_type = msg.get_type()

                if m_type in ['MISSION_REQUEST', 'MISSION_REQUEST_INT']:
                    seq = msg.seq
                    while seq < total_items:
                        item = full_mission[seq]

                        if m_type == 'MISSION_REQUEST_INT':
                            master.mav.mission_item_int_send(
                                target_sys, target_comp, seq,
                                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                                item["cmd"], 0, item["autocontinue"],
                                float(item["p1"]), 2.0, 0.0, 0.0,
                                int(item["lat"] * 1e7), int(item["lon"] * 1e7),
                                float(item["alt"]),
                                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                            )
                        else:
                            master.mav.mission_item_send(
                                target_sys, target_comp, seq,
                                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                                item["cmd"], 0, item["autocontinue"],
                                float(item["p1"]), 2.0, 0.0, 0.0,
                                float(item["lat"]), float(item["lon"]),
                                float(item["alt"]),
                                mavutil.mavlink.MAV_MISSION_TYPE_MISSION
                            )

                        self.upload_progress.emit(seq + 1, total_items)

                        if hasattr(self.mav_worker, "mission_msg_received"):
                            next_msg = self._wait_for_packet(timeout_sec=2.0)
                        else:
                            next_msg = master.recv_match(
                                type=['MISSION_REQUEST_INT', 'MISSION_REQUEST', 'MISSION_ACK'],
                                blocking=True,
                                timeout=2.0
                            )

                        if not next_msg:
                            break

                        m_type = next_msg.get_type()
                        if m_type in ['MISSION_REQUEST', 'MISSION_REQUEST_INT']:
                            seq = next_msg.seq
                        elif m_type == 'MISSION_ACK':
                            if next_msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                                self.mission_uploaded.emit(True, f"Mission uploaded successfully ({len(waypoints)} Waypoints)")
                                return
                            else:
                                self.mission_uploaded.emit(False, f"FC Rejected Mission (Code: {next_msg.type})")
                                return

                elif m_type == 'MISSION_ACK':
                    if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        self.mission_uploaded.emit(True, f"Mission uploaded successfully ({len(waypoints)} Waypoints)")
                        return
                    else:
                        self.mission_uploaded.emit(False, f"FC Rejected Mission (Code: {msg.type})")
                        return

        self.mission_uploaded.emit(False, "Mission upload timed out. Flight controller did not respond.")

    def start_auto_mission(self):
        if not self.mav_worker or not self.mav_worker.master:
            self.mission_started.emit(False, "Drone not connected")
            return

        master = self.mav_worker.master
        mode_id = master.mode_mapping().get('AUTO', 3)
        master.set_mode(mode_id)
        master.mav.command_long_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_CMD_MISSION_START,
            0,
            0, 0, 0, 0, 0, 0, 0
        )
        self.mission_started.emit(True, "Autonomous mission started in AUTO mode")

    def pause_mission(self):
        if not self.mav_worker or not self.mav_worker.master:
            self.mission_paused.emit(False, "Drone not connected")
            return

        master = self.mav_worker.master
        mode_id = master.mode_mapping().get('LOITER', master.mode_mapping().get('BRAKE', 5))
        master.set_mode(mode_id)
        self.mission_paused.emit(True, "Mission paused: In LOITER mode. Manual control active.")

    def resume_mission(self):
        if not self.mav_worker or not self.mav_worker.master:
            self.mission_resumed.emit(False, "Drone not connected")
            return

        master = self.mav_worker.master
        mode_id = master.mode_mapping().get('AUTO', 3)
        master.set_mode(mode_id)
        self.mission_resumed.emit(True, "Mission resumed: Switched to AUTO mode")