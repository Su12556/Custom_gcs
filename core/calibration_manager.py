import time
from pymavlink import mavutil
from PySide6.QtCore import QObject, Signal

class CalibrationManager(QObject):
    # Signals for UI Updates
    accel_prompt_sig = Signal(str)           # Prompts like "Place level", "Nose Up", etc.
    compass_progress_sig = Signal(int)       # 0 - 100% completion
    compass_done_sig = Signal(bool, str)     # Pass/Fail + report string
    rc_channels_sig = Signal(list)           # List of RAW PWM values [ch1, ch2, ..., ch8]
    log_sig = Signal(str)                    # Generic status console logging

    def __init__(self, mav_worker=None, parent=None):
        super().__init__(parent)
        self.mav_worker = mav_worker
        self.accel_step_index = 0
        self.active_cal_type = None

    def set_worker(self, mav_worker):
        self.mav_worker = mav_worker

    @property
    def master(self):
        return self.mav_worker.master if (self.mav_worker and self.mav_worker.connected) else None

    # -------------------------------------------------------------
    # 1. ACCELEROMETER CALIBRATION (6-Point & Simple Level)
    # -------------------------------------------------------------
    def start_accel_6point(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Telemetry not connected. Connect drone first.")
            return False

        self.active_cal_type = "ACCEL"
        self.accel_step_index = 1
        self.log_sig.emit("[*] Initiating 6-Axis 3D Accel Calibration...")
        
        # MAV_CMD_PREFLIGHT_CALIBRATION (param5 = 1 => 3D Accel calibration)
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
            0, 0, 0, 0, 1, 0, 0
        )
        self.accel_prompt_sig.emit("Place vehicle LEVEL and press NEXT.")
        return True

    def advance_accel_step(self):
        m = self.master
        if not m: return

        # ArduPilot vehicle orientation positions:
        # 1: Level, 2: Left, 3: Right, 4: Nose Down, 5: Nose Up, 6: Back
        steps = [
            (1, "Place vehicle LEVEL and press NEXT."),
            (2, "Place vehicle on its LEFT side and press NEXT."),
            (3, "Place vehicle on its RIGHT side and press NEXT."),
            (4, "Place vehicle NOSE DOWN and press NEXT."),
            (5, "Place vehicle NOSE UP and press NEXT."),
            (6, "Place vehicle on its BACK and press NEXT.")
        ]

        if self.accel_step_index <= 6:
            pos_val = self.accel_step_index
            self.log_sig.emit(f"[*] Confirmed Step {pos_val}/6. Transmitting pos ack...")
            
            # Send vehicle position response
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_ACCELCAL_VEHICLE_POS,
                0,
                pos_val, 0, 0, 0, 0, 0, 0
            )

            if self.accel_step_index < 6:
                next_prompt = steps[self.accel_step_index][1]
                self.accel_prompt_sig.emit(next_prompt)
                self.accel_step_index += 1
            else:
                self.accel_prompt_sig.emit("Calibration Completed! Writing offsets...")
                self.log_sig.emit("[+] 6-Axis Accel Calibration Complete.")
                self.active_cal_type = None
                self.accel_step_index = 0

    def calibrate_simple_level(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False
        self.log_sig.emit("[*] Calibrating Horizon Level (Keep flat)...")
        # param5 = 2 is level calibration
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_CALIBRATION,
            0,
            0, 0, 0, 0, 2, 0, 0
        )
        self.log_sig.emit("[+] Horizon level set successfully.")
        return True

    # -------------------------------------------------------------
    # 2. COMPASS CALIBRATION (Onboard Mag Routine)
    # -------------------------------------------------------------
    def start_compass_cal(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.active_cal_type = "COMPASS"
        self.log_sig.emit("[*] Starting Onboard Compass Calibration. Rotate drone slowly on all axes...")
        # MAV_CMD_DO_START_MAG_CAL: param1 = 0 (All compasses), param2 = 0 (normal), param3 = 1 (auto-reboot/save)
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_DO_START_MAG_CAL,
            0,
            0, 0, 1, 0, 0, 0, 0
        )
        return True

    def cancel_compass_cal(self):
        m = self.master
        if not m: return
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_DO_CANCEL_MAG_CAL,
            0, 0, 0, 0, 0, 0, 0, 0
        )
        self.log_sig.emit("[!] Compass Calibration Cancelled.")
        self.active_cal_type = None

    # -------------------------------------------------------------
    # 3. ESC CALIBRATION (Set ESC_CALIBRATION = 3 & Reboot)
    # -------------------------------------------------------------
    def trigger_esc_calibration(self):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.log_sig.emit("[*] Writing parameter: ESC_CALIBRATION = 3 (Auto on next reboot)...")
        m.param_set_send(
            b"ESC_CALIBRATION",
            3.0,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        time.sleep(0.3)
        self.log_sig.emit("[*] Sending reboot command to FC...")
        # MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN (param1 = 1: reboot autopilot)
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
            0,
            1, 0, 0, 0, 0, 0, 0
        )
        self.log_sig.emit("[+] Target rebooting. Plug in battery when tone sounds to calibrate ESCs.")
        return True

    # -------------------------------------------------------------
    # 4. RADIO / RC CHANNELS PARSING & SAVING
    # -------------------------------------------------------------
    def save_rc_limits(self, limits_dict):
        m = self.master
        if not m:
            self.log_sig.emit("[!] Drone not connected.")
            return False

        self.log_sig.emit("[*] Committing RC Stick Min/Max/Trim parameters to FC...")
        for param_name, val in limits_dict.items():
            m.param_set_send(
                param_name.encode('ascii'),
                float(val),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            time.sleep(0.04)
        self.log_sig.emit("[+] RC Limits committed successfully.")
        return True

    # -------------------------------------------------------------
    # MAVLink Feed Processor Hook
    # -------------------------------------------------------------
    def process_raw_mavlink_msg(self, msg):
        msg_type = msg.get_type()

        # Parse Compass Progress
        if msg_type == "MAG_CAL_PROGRESS":
            pct = int(getattr(msg, "completion_pct", 0))
            self.compass_progress_sig.emit(pct)

        elif msg_type == "MAG_CAL_REPORT":
            status = getattr(msg, "cal_status", 0)
            success = (status == 1 or status == 4)  # 1 = Completed, 4 = Successful
            self.compass_done_sig.emit(success, f"Report status code: {status}")

        # Parse Accel Status Messages
        elif msg_type == "STATUSTEXT":
            txt = getattr(msg, "text", "")
            if any(k in txt.lower() for k in ["place", "accel", "calibration", "holding"]):
                self.accel_prompt_sig.emit(txt)
                self.log_sig.emit(f"[FC] {txt}")

        # Parse Live Radio Channels
        elif msg_type == "RC_CHANNELS":
            pwm_list = [
                getattr(msg, f"chan{i}_raw", 1500)
                for i in range(1, 9)
            ]
            self.rc_channels_sig.emit(pwm_list)