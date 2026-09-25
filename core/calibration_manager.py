import time
from pymavlink import mavutil
from PySide6.QtCore import QObject, Signal

class CalibrationManager(QObject):
    accel_prompt_sig = Signal(str)
    compass_progress_sig = Signal(int)
    compass_done_sig = Signal(bool, str)
    rc_channels_sig = Signal(list)
    log_sig = Signal(str)

    def __init__(self, mav_worker=None, parent=None):
        super().__init__(parent)
        self.mav_worker = mav_worker
        self.accel_step_index = 0
        self.active_cal_type = None

    def set_worker(self, worker):
        self.mav_worker = worker
        if self.master:
            self.request_rc_stream()

    @property
    def master(self):
        return self.mav_worker.master if (self.mav_worker and getattr(self.mav_worker, 'connected', False)) else None

    # -------------------------------------------------------------
    # 0. UNIVERSAL STREAM NEGOTIATION
    # -------------------------------------------------------------
    def request_rc_stream(self):
        """Forces the flight controller to stream RC data at 20 Hz."""
        if self.mav_worker and hasattr(self.mav_worker, 'request_rc_streams_universal'):
            self.mav_worker.request_rc_streams_universal()
            return

        m = self.master
        if not m:
            return

        target_sys = m.target_system or 1
        target_comp = m.target_component or 1

        try:
            m.mav.command_long_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,
                65,       # MAVLINK_MSG_ID_RC_CHANNELS
                50000,    # 50,000 µs = 20 Hz
                0, 0, 0, 0, 0
            )
        except Exception:
            pass

        try:
            m.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS,
                20,       # 20 Hz
                1         # Start
            )
        except Exception:
            pass

    # -------------------------------------------------------------
    # 1. ACCELEROMETER CALIBRATION
    # -------------------------------------------------------------
    def start_accel_6point(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Telemetry not connected. Connect drone first.")
            return False

        self.active_cal_type = "ACCEL"
        self.accel_step_index = 1
        self.log_sig.emit("[*] Initiating 6-Axis 3D Accel Calibration...")
        try:
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
                0, 0, 0, 0, 0, 1, 0, 0
            )
            self.accel_prompt_sig.emit("Place vehicle LEVEL and press NEXT STEP.")
            return True
        except Exception as e:
            self.log_sig.emit(f"[ERROR] Failed to send Accel Cal command: {e}")
            return False

    def advance_accel_step(self):
        m = self.master
        if not m:
            return

        steps = [
            (1, "Place vehicle LEVEL and press NEXT STEP."),
            (2, "Place vehicle on its LEFT side and press NEXT STEP."),
            (3, "Place vehicle on its RIGHT side and press NEXT STEP."),
            (4, "Place vehicle NOSE DOWN and press NEXT STEP."),
            (5, "Place vehicle NOSE UP and press NEXT STEP."),
            (6, "Place vehicle on its BACK and press NEXT STEP.")
        ]

        if self.accel_step_index <= 6:
            pos_val = self.accel_step_index
            self.log_sig.emit(f"[*] Confirmed Step {pos_val}/6. Transmitting position ack...")
            try:
                m.mav.command_long_send(
                    m.target_system, m.target_component,
                    mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS,
                    0, pos_val, 0, 0, 0, 0, 0, 0
                )
            except Exception as e:
                self.log_sig.emit(f"[ERROR] Failed to send step acknowledgment: {e}")

            if self.accel_step_index < 6:
                next_prompt = steps[self.accel_step_index][1]
                self.accel_prompt_sig.emit(next_prompt)
                self.accel_step_index += 1
            else:
                self.accel_prompt_sig.emit("Calibration Completed! Writing offsets to flash...")
                self.log_sig.emit("[+] 6-Axis Accel Calibration Complete.")
                self.active_cal_type = None
                self.accel_step_index = 0

    def calibrate_simple_level(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False
        self.log_sig.emit("[*] Calibrating Horizon Level (Keep vehicle flat)...")
        try:
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
                0, 0, 0, 0, 0, 2, 0, 0
            )
            self.log_sig.emit("[+] Horizon level set successfully.")
            return True
        except Exception as e:
            self.log_sig.emit(f"[ERROR] Level calibration failed: {e}")
            return False

    # -------------------------------------------------------------
    # 2. COMPASS CALIBRATION
    # -------------------------------------------------------------
    def start_compass_cal(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.active_cal_type = "COMPASS"
        self.log_sig.emit("[*] Starting Onboard Compass Calibration. Rotate drone slowly around all axes...")
        try:
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_DO_START_MAG_CAL,
                0, 0, 0, 1, 0, 0, 0, 0
            )
            return True
        except Exception as e:
            self.log_sig.emit(f"[ERROR] Could not start compass calibration: {e}")
            return False

    def cancel_compass_cal(self):
        m = self.master
        if not m:
            return
        try:
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_DO_CANCEL_MAG_CAL,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            self.log_sig.emit("[!] Compass Calibration Cancelled.")
        except Exception:
            pass
        self.active_cal_type = None

    # -------------------------------------------------------------
    # 3. ESC CALIBRATION (Type-Safe Parameter Writing)
    # -------------------------------------------------------------
    def trigger_esc_calibration(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.log_sig.emit("[*] Writing parameter: ESC_CALIBRATION = 3 (Auto ESC on boot)...")
        try:
            param_key = "ESC_CALIBRATION"
            param_bytes = param_key.encode('utf-8') if isinstance(param_key, str) else param_key

            m.param_set_send(
                param_bytes,
                float(3.0),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            time.sleep(0.3)
            self.log_sig.emit("[*] Sending preflight reboot command to flight controller...")
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
                0, 1, 0, 0, 0, 0, 0, 0
            )
            self.log_sig.emit("[+] Target rebooting. Disconnect battery and reconnect when tone sounds to set throttle endpoints.")
            return True
        except Exception as e:
            self.log_sig.emit(f"[ERROR] ESC Calibration setup failed: {e}")
            return False

    # -------------------------------------------------------------
    # 4. RC LIMITS COMMIT (Type-Safe Parameter Writing)
    # -------------------------------------------------------------
    def save_rc_limits(self, limits_dict):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.log_sig.emit(f"[*] Committing {len(limits_dict)//3} active RC channel limits to flight controller...")
        try:
            for param_name, val in limits_dict.items():
                param_bytes = param_name.encode('utf-8') if isinstance(param_name, str) else param_name
                m.param_set_send(
                    param_bytes,
                    float(val),
                    mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                )
                time.sleep(0.02)
            self.log_sig.emit("[+] Active RC limits committed successfully.")
            return True
        except Exception as e:
            self.log_sig.emit(f"[ERROR] Failed to save RC limits: {e}")
            return False

    # -------------------------------------------------------------
    # 5. DYNAMIC ACTIVE RC CHANNELS DETECTOR
    # -------------------------------------------------------------
    def process_raw_mavlink_msg(self, msg):
        msg_type = msg.get_type()

        if msg_type == "MAG_CAL_PROGRESS":
            pct = int(getattr(msg, "completion_pct", 0))
            self.compass_progress_sig.emit(pct)

        elif msg_type == "MAG_CAL_REPORT":
            status = getattr(msg, "cal_status", 0)
            success = (status in [1, 4])
            self.compass_done_sig.emit(success, f"Report status code: {status}")

        elif msg_type == "STATUSTEXT":
            txt = getattr(msg, "text", "")
            if any(k in txt.lower() for k in ["place", "accel", "calibration", "holding"]):
                self.accel_prompt_sig.emit(txt)
                self.log_sig.emit(f"[FC] {txt}")

        elif msg_type in ["RC_CHANNELS", "RC_CHANNELS_RAW"]:
            # Auto-detect total channel capacity
            if msg_type == "RC_CHANNELS":
                reported_count = getattr(msg, "chancount", 0)
                max_inspect = max(4, min(16, reported_count if reported_count > 0 else 16))
            else:
                max_inspect = 8

            # Scan raw pulses and determine highest active channel index
            temp_channels = []
            highest_active_channel = 4  # Standard minimum (Roll, Pitch, Thr, Yaw)

            for i in range(1, max_inspect + 1):
                raw_val = getattr(msg, f"chan{i}_raw", 0)
                # Valid RC PWM range is between 800 us and 2200 us
                if 800 <= raw_val <= 2200:
                    temp_channels.append(raw_val)
                    highest_active_channel = i
                else:
                    # Inactive or default
                    temp_channels.append(1500)

            # Slice only up to the highest active channel
            # Example: 6-CH FlySky yields 6 items; 12-CH yields 12 items; 16-CH yields 16 items
            active_pwm_list = temp_channels[:highest_active_channel]
            self.rc_channels_sig.emit(active_pwm_list)