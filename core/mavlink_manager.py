import os
import time
import math
import socket
from datetime import datetime
from PySide6.QtCore import QThread, Signal
from pymavlink import mavutil

class MavlinkWorker(QThread):
    telemetry_updated = Signal(dict)
    log_entry_received = Signal(dict)
    log_download_progress = Signal(int, int, float)  # log_id, bytes_received, percent

    def __init__(self, connection_string="udpin:0.0.0.0:14550", baud=115200):
        super().__init__()
        self.connection_string = connection_string
        self.baud = baud
        self.running = True
        self.master = None
        self.home_lat = None
        self.home_lon = None
        self.start_time = None
        self.last_heartbeat_time = 0.0
        self.connected = False

        # --- Flight Logging (.tlog & .bin) ---
        self.logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(self.logs_dir, exist_ok=True)
        self.tlog_file = None
        self.current_download_file = None
        self.current_download_id = None
        self.current_download_size = 0
        self.current_download_bytes = 0

    def run(self):
        telem = {
            "connected": False,
            "mode": "CONNECTING",
            "sub_mode": "SEARCHING",
            "voltage": 0.0,
            "sats": 0,
            "hdop": 99.9,
            "alt": 0.0,
            "speed": 0.0,
            "flight_time": "00:00",
            "home_dist": 0.0,
            "compass": 0.0,
            "temp": 0.0,
            "stat_msg": f"OPENING {self.connection_string}...",
            "lat": 0.0,
            "lon": 0.0
        }
        self.telemetry_updated.emit(telem.copy())

        # Establish connection with socket reuse
        try:
            if self.connection_string.startswith("COM") or "/dev/" in self.connection_string:
                self.master = mavutil.mavlink_connection(self.connection_string, baud=self.baud)
            else:
                self.master = mavutil.mavlink_connection(self.connection_string)
                
                try:
                    if hasattr(self.master, 'port') and hasattr(self.master.port, 'setsockopt'):
                        self.master.port.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        if hasattr(socket, 'SO_REUSEPORT'):
                            self.master.port.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass

            telem["stat_msg"] = f"LISTENING ON {self.connection_string} (AWAITING HEARTBEAT)"
            self.telemetry_updated.emit(telem.copy())

        except Exception as e:
            telem["stat_msg"] = f"BIND ERROR: {e}"
            telem["sub_mode"] = "ERROR"
            self.telemetry_updated.emit(telem.copy())
            return

        last_gcs_heartbeat = 0.0

        while self.running:
            now = time.time()

            # Broadcast GCS Heartbeat every 1 sec
            if now - last_gcs_heartbeat > 1.0:
                try:
                    if self.master:
                        self.master.mav.heartbeat_send(
                            mavutil.mavlink.MAV_TYPE_GCS,
                            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                            0, 0, 0
                        )
                except Exception:
                    pass
                last_gcs_heartbeat = now

            # Fetch incoming MAVLink packets
            try:
                msg = self.master.recv_match(blocking=False)
            except Exception:
                msg = None

            # Timeout detection
            if self.connected and (now - self.last_heartbeat_time > 4.0):
                self.connected = False
                telem["connected"] = False
                telem["mode"] = "DISCONNECTED"
                telem["sub_mode"] = "LOST LINK"
                telem["stat_msg"] = "WARNING: TELEMETRY SIGNAL LOST"
                self.telemetry_updated.emit(telem.copy())

            if msg is None:
                time.sleep(0.01)
                continue

            # --- 1. Write Packet to .tlog Flight File ---
            if self.tlog_file:
                try:
                    t_hdr = int(time.time() * 1e6).to_bytes(8, byteorder='big')
                    self.tlog_file.write(t_hdr + msg.get_msgbuf())
                except Exception:
                    pass

            msg_type = msg.get_type()

            if msg_type == 'HEARTBEAT':
                if msg.get_srcSystem() == 255:
                    continue

                self.last_heartbeat_time = now
                if not self.connected:
                    self.connected = True
                    self.start_time = time.time()
                    self._start_telemetry_logging()
                    self._request_streams()

                telem["connected"] = True
                telem["sub_mode"] = mavutil.mode_mapping_acm.get(msg.custom_mode, "STABILIZE")
                is_armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                telem["mode"] = "ARMED" if is_armed else "DISARMED"
                if telem["stat_msg"].startswith("LISTENING"):
                    telem["stat_msg"] = f"CONNECTED: SYSTEM ID {msg.get_srcSystem()}"

            elif msg_type == 'STATUSTEXT':
                telem["stat_msg"] = str(msg.text).strip()

            elif msg_type == 'SYS_STATUS':
                telem["voltage"] = msg.voltage_battery / 1000.0

            elif msg_type == 'GPS_RAW_INT':
                telem["sats"] = msg.satellites_visible
                telem["hdop"] = (msg.eph / 100.0) if hasattr(msg, 'eph') else 1.0

            elif msg_type == 'VFR_HUD':
                telem["speed"] = msg.groundspeed
                if hasattr(msg, 'heading') and msg.heading is not None:
                    telem["compass"] = float(msg.heading) % 360.0

            elif msg_type == 'GLOBAL_POSITION_INT':
                telem["lat"] = msg.lat / 1e7
                telem["lon"] = msg.lon / 1e7
                telem["alt"] = msg.relative_alt / 1000.0

                if hasattr(msg, 'hdg') and msg.hdg != 65535:
                    telem["compass"] = (float(msg.hdg) / 100.0) % 360.0

                if self.home_lat is None and telem["lat"] != 0.0:
                    self.home_lat = telem["lat"]
                    self.home_lon = telem["lon"]

                if self.home_lat is not None:
                    dlat = (telem["lat"] - self.home_lat) * 111319.5
                    dlon = (telem["lon"] - self.home_lon) * 111319.5 * math.cos(math.radians(telem["lat"]))
                    telem["home_dist"] = math.hypot(dlat, dlon)

            elif msg_type == 'SCALED_PRESSURE':
                telem["temp"] = msg.temperature / 100.0

            # --- 2. Micro-SD Onboard Logs (.bin Transfer) ---
            elif msg_type == 'LOG_ENTRY':
                self.log_entry_received.emit({
                    "id": msg.id,
                    "num_logs": msg.num_logs,
                    "last_log_num": msg.last_log_num,
                    "time_utc": msg.time_utc,
                    "size": msg.size
                })

            elif msg_type == 'LOG_DATA':
                if self.current_download_file and msg.id == self.current_download_id:
                    self.current_download_file.seek(msg.ofs)
                    self.current_download_file.write(bytes(msg.data[:msg.count]))
                    self.current_download_bytes += msg.count
                    pct = (self.current_download_bytes / float(self.current_download_size)) * 100.0 if self.current_download_size > 0 else 0.0
                    self.log_download_progress.emit(msg.id, self.current_download_bytes, min(100.0, pct))
                    
                    if self.current_download_bytes >= self.current_download_size:
                        self.current_download_file.close()
                        self.current_download_file = None
                        telem["stat_msg"] = f"DOWNLOAD COMPLETE: LOG #{msg.id}"

            if self.connected and self.start_time:
                elapsed = int(time.time() - self.start_time)
                mins, secs = divmod(elapsed, 60)
                telem["flight_time"] = f"{mins:02d}:{secs:02d}"

            self.telemetry_updated.emit(telem.copy())

        self._cleanup()

    def _start_telemetry_logging(self):
        """Initializes raw .tlog session in the logs folder."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(self.logs_dir, f"flight_telemetry_{ts}.tlog")
            self.tlog_file = open(log_path, "wb")
        except Exception:
            self.tlog_file = None

    def _request_streams(self):
        if not self.master:
            return
        try:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                4,
                1
            )
        except Exception:
            pass

    # --- Methods for Onboard Dataflash Download ---
    def request_onboard_log_list(self):
        """Sends MAVLink request to enumerate all logs on the autopilot SD card."""
        if self.master:
            self.master.mav.log_request_list_send(
                self.master.target_system,
                self.master.target_component,
                0,
                0xFFFF
            )

    def start_onboard_log_download(self, log_id: int, log_size: int):
        """Requests chunks for a specific log and prepares local .bin file."""
        if not self.master:
            return

        if self.current_download_file:
            try:
                self.current_download_file.close()
            except Exception:
                pass

        bin_path = os.path.join(self.logs_dir, f"autopilot_log_{log_id}.bin")
        self.current_download_file = open(bin_path, "wb")
        self.current_download_id = log_id
        self.current_download_size = log_size
        self.current_download_bytes = 0

        self.master.mav.log_request_data_send(
            self.master.target_system,
            self.master.target_component,
            log_id,
            0,
            0xFFFFFFFF
        )

    def _cleanup(self):
        if self.tlog_file:
            try:
                self.tlog_file.flush()
                self.tlog_file.close()
            except Exception:
                pass
            self.tlog_file = None

        if self.current_download_file:
            try:
                self.current_download_file.close()
            except Exception:
                pass
            self.current_download_file = None

        if self.master:
            try:
                self.master.close()
            except Exception:
                pass
            self.master = None

    def stop(self):
        self.running = False
        self.quit()
        self.wait(1000)