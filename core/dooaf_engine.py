import math

class DOOAFEngine:
    """Direction of Artillery Fire (DOOAF) Engine.
    Handles raycasting from camera pixels to ground coordinates and ballistic corrections.
    """

    def __init__(self, battery_lat=12.970978, battery_lon=77.579739, gun_default_facing=180.0):
        self.battery_lat = battery_lat
        self.battery_lon = battery_lon
        self.gun_default_facing = gun_default_facing

        # Default camera field-of-view for drone payload gimbals (degrees)
        self.hfov_deg = 60.0
        self.vfov_deg = 35.0

    def video_pixel_to_coord(self, px, py, img_w, img_h, drone_lat, drone_lon, drone_alt_m, gimbal_pitch_deg, drone_heading_deg):
        """Projects a video pixel click onto the ground plane to derive Lat/Lon.
        
        px, py: Clicked pixel coordinates in the video
        img_w, img_h: Width and height of the video frame
        drone_lat, drone_lon: Current UAV GPS position
        drone_alt_m: Drone altitude above ground (AGL) in meters
        gimbal_pitch_deg: Camera pitch (-90 is straight down, -45 is looking forward/down)
        drone_heading_deg: UAV / gimbal yaw heading (0-360 deg TN)
        """
        if img_w <= 0 or img_h <= 0 or drone_alt_m <= 0:
            return drone_lat, drone_lon

        # Normalize pixel offset from center of frame [-0.5 to +0.5]
        norm_x = (px - (img_w / 2.0)) / float(img_w)
        norm_y = ((img_h / 2.0) - py) / float(img_h)  # Invert Y so up is positive

        # Angular offsets relative to optical boresight
        azimuth_offset_deg = norm_x * self.hfov_deg
        elevation_offset_deg = norm_y * self.vfov_deg

        # Total line-of-sight elevation depression angle
        # gimbal_pitch_deg is usually negative when pitched down (e.g., -45°)
        effective_pitch = abs(gimbal_pitch_deg) - elevation_offset_deg
        effective_pitch = max(5.0, min(89.0, effective_pitch))  # Avoid divide by zero / tangent singularity

        # Slant range & horizontal ground distance
        pitch_rad = math.radians(effective_pitch)
        ground_distance_m = drone_alt_m / math.tan(pitch_rad)

        # True bearing of optical ray
        ray_bearing_deg = (drone_heading_deg + azimuth_offset_deg) % 360.0
        ray_bearing_rad = math.radians(ray_bearing_deg)

        # Flat earth delta to Lat/Lon
        delta_north = ground_distance_m * math.cos(ray_bearing_rad)
        delta_east = ground_distance_m * math.sin(ray_bearing_rad)

        earth_radius = 6378137.0
        d_lat = (delta_north / earth_radius) * (180.0 / math.pi)
        d_lon = (delta_east / (earth_radius * math.cos(math.radians(drone_lat)))) * (180.0 / math.pi)

        target_lat = drone_lat + d_lat
        target_lon = drone_lon + d_lon

        return round(target_lat, 6), round(target_lon, 6)

    def compute_artillery_solution(self, target_lat, target_lon):
        """Calculates Gun-Target Line (GTL) bearing and range from artillery battery."""
        d_lat = target_lat - self.battery_lat
        d_lon = target_lon - self.battery_lon

        lat_m = d_lat * 111319.5
        lon_m = d_lon * 111319.5 * math.cos(math.radians(self.battery_lat))

        range_m = math.hypot(lat_m, lon_m)
        gtl_rad = math.atan2(lon_m, lat_m)
        gtl_deg = (math.degrees(gtl_rad) + 360.0) % 360.0

        return {
            "gtl_bearing_tn": round(gtl_deg, 2),
            "range_m": round(range_m, 2)
        }

    def compute_fall_of_shot_correction(self, t_lat, t_lon, t_alt, i_lat, i_lon, i_alt):
        """Calculates Range (Add/Drop), Deflection (Left/Right), and Height shifts along GTL."""
        # Baseline Gun to Target Line (GTL)
        sol = self.compute_artillery_solution(t_lat, t_lon)
        gtl_deg = sol["gtl_bearing_tn"]
        gtl_rad = math.radians(gtl_deg)
        gun_range = sol["range_m"]

        # Vector from Target to Impact
        d_north = (i_lat - t_lat) * 111319.5
        d_east = (i_lon - t_lon) * 111319.5 * math.cos(math.radians(t_lat))

        # Project miss vector onto GTL:
        # Range component along GTL (positive = landed beyond target -> Drop)
        miss_range = d_north * math.cos(gtl_rad) + d_east * math.sin(gtl_rad)

        # Lateral deflection component perpendicular to GTL (positive = landed right -> Left)
        miss_lateral = -d_north * math.sin(gtl_rad) + d_east * math.cos(gtl_rad)

        # Gun Fire Correction Orders (Invert miss vectors to correct back to target)
        range_correction = -miss_range
        lateral_correction = -miss_lateral

        # Deflection in military mils (6400 NATO mils in 360 degrees)
        if gun_range > 0:
            deflection_mils = (lateral_correction / float(gun_range)) * (6400.0 / (2.0 * math.pi))
        else:
            deflection_mils = 0.0

        return {
            "range_correction_m": round(range_correction, 1),
            "lateral_correction_m": round(lateral_correction, 1),
            "deflection_mils": round(deflection_mils, 1),
            "gtl_bearing_tn": round(gtl_deg, 1),
            "height_correction_m": round(t_alt - i_alt, 1)
        }