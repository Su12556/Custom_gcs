"""
Pure Python MGRS (Military Grid Reference System) Implementation.
Zero dependencies: does not require C-compilers or third-party binary packages.
Includes forward (Lat/Lon -> MGRS) and reverse (MGRS -> Lat/Lon) converters.
"""
import math
import re

_UTM_COLS = [
    "ABCDEFGH",
    "JKLMNPQR",
    "STUVWXYZ"
]
_UTM_ROWS = [
    "ABCDEFGHJKLMNPQRSTUV",
    "FGHJKLMNPQRSTUVABCDE"
]

def _lat_band(lat: float) -> str:
    bands = "CDEFGHJKLMNPQRSTUVWX"
    if -80.0 <= lat <= 84.0:
        idx = int((lat + 80.0) / 8.0)
        return bands[min(idx, len(bands) - 1)]
    return "X" if lat > 84.0 else "C"

def to_mgrs_gr(lat: float, lon: float, precision: int = 5) -> str:
    """Converts Latitude and Longitude to standard military MGRS Grid Reference."""
    try:
        zone = int((lon + 180.0) / 6.0) + 1
        band = _lat_band(lat)

        a = 6378137.0
        f = 1.0 / 298.257223563
        e2 = 2.0 * f - f * f
        e_prime2 = e2 / (1.0 - e2)

        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        lon_origin = (zone - 1) * 6 - 180 + 3
        lon_origin_rad = math.radians(lon_origin)

        k0 = 0.9996
        N = a / math.sqrt(1.0 - e2 * math.sin(lat_rad) ** 2)
        T = math.tan(lat_rad) ** 2
        C = e_prime2 * math.cos(lat_rad) ** 2
        A = math.cos(lat_rad) * (lon_rad - lon_origin_rad)

        M = a * (
            (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 * e2 * e2 / 256.0) * lat_rad
            - (3.0 * e2 / 8.0 + 3.0 * e2 * e2 / 32.0 + 45.0 * e2 * e2 * e2 / 1024.0) * math.sin(2.0 * lat_rad)
            + (15.0 * e2 * e2 / 256.0 + 45.0 * e2 * e2 * e2 / 1024.0) * math.sin(4.0 * lat_rad)
            - (35.0 * e2 * e2 * e2 / 3072.0) * math.sin(6.0 * lat_rad)
        )

        easting = k0 * N * (
            A + (1.0 - T + C) * (A ** 3) / 6.0
            + (5.0 - 18.0 * T + T * T + 72.0 * C - 58.0 * e_prime2) * (A ** 5) / 120.0
        ) + 500000.0

        northing = k0 * (
            M + N * math.tan(lat_rad) * (
                (A ** 2) / 2.0
                + (5.0 - T + 9.0 * C + 4.0 * C * C) * (A ** 4) / 24.0
                + (61.0 - 58.0 * T + T * T + 600.0 * C - 330.0 * e_prime2) * (A ** 6) / 720.0
            )
        )
        if lat < 0.0:
            northing += 10000000.0

        col_set = (zone - 1) % 3
        col_idx = int(easting / 100000.0) - 1
        col_char = _UTM_COLS[col_set][col_idx % 8]

        row_set = (zone - 1) % 2
        row_idx = int(northing / 100000.0) % 20
        row_char = _UTM_ROWS[row_set][row_idx]

        rem_e = int(easting % 100000.0)
        rem_n = int(northing % 100000.0)

        divisor = 10 ** (5 - precision)
        e_str = f"{int(rem_e / divisor):0{precision}d}"
        n_str = f"{int(rem_n / divisor):0{precision}d}"

        return f"{zone:02d}{band} {col_char}{row_char} {e_str} {n_str}"
    except Exception:
        return f"{int((lon + 180) / 6) + 1}Q --"

def from_mgrs_gr(mgrs_str: str):
    """
    Decodes an MGRS / Grid Reference string into (lat, lon) in decimal degrees.
    Accepts formatted or unformatted inputs:
      e.g., '43P GQ 80325 35703' or '43PGQ8032535703'
    """
    cleaned = re.sub(r'\s+', '', mgrs_str).upper()
    match = re.match(r'^(\d{1,2})([C-X])([A-Z])([A-Z])(\d+)$', cleaned)
    if not match:
        return None

    zone = int(match.group(1))
    band = match.group(2)
    col_char = match.group(3)
    row_char = match.group(4)
    digits = match.group(5)

    if len(digits) % 2 != 0:
        return None

    half = len(digits) // 2
    e_str = digits[:half]
    n_str = digits[half:]

    precision = half
    e_val = float(e_str) * (10 ** (5 - precision))
    n_val = float(n_str) * (10 ** (5 - precision))

    # Center within grid cell
    half_cell = (10 ** (5 - precision)) / 2.0
    e_val += half_cell
    n_val += half_cell

    col_set = (zone - 1) % 3
    if col_char not in _UTM_COLS[col_set]:
        return None
    col_idx = _UTM_COLS[col_set].index(col_char) + 1
    easting = col_idx * 100000.0 + e_val

    row_set = (zone - 1) % 2
    if row_char not in _UTM_ROWS[row_set]:
        return None
    row_idx = _UTM_ROWS[row_set].index(row_char)

    bands = "CDEFGHJKLMNPQRSTUVWX"
    band_idx = bands.index(band)
    approx_lat = -80.0 + band_idx * 8.0 + 4.0
    approx_northing = (approx_lat / 90.0) * 10000000.0 if approx_lat >= 0 else (10000000.0 + (approx_lat / 90.0) * 10000000.0)

    base_northing = round((approx_northing - (row_idx * 100000.0)) / 2000000.0) * 2000000.0
    northing = base_northing + row_idx * 100000.0 + n_val

    # Inverse UTM Projection to WGS-84 Lat/Lon
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f * f
    e_prime2 = e2 / (1.0 - e2)
    k0 = 0.9996

    x = easting - 500000.0
    y = northing

    M = y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * e2 * e2 / 64.0 - 5.0 * e2 * e2 * e2 / 256.0))

    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    J1 = 3.0 * e1 / 2.0 - 27.0 * (e1 ** 3) / 32.0
    J2 = 21.0 * (e1 ** 2) / 16.0 - 55.0 * (e1 ** 4) / 32.0
    J3 = 151.0 * (e1 ** 3) / 96.0
    J4 = 1097.0 * (e1 ** 4) / 512.0

    fp = mu + J1 * math.sin(2.0 * mu) + J2 * math.sin(4.0 * mu) + J3 * math.sin(6.0 * mu) + J4 * math.sin(8.0 * mu)

    C1 = e_prime2 * math.cos(fp) ** 2
    T1 = math.tan(fp) ** 2
    R1 = a * (1.0 - e2) / ((1.0 - e2 * math.sin(fp) ** 2) ** 1.5)
    N1 = a / math.sqrt(1.0 - e2 * math.sin(fp) ** 2)

    D = x / (N1 * k0)

    lat = fp - (N1 * math.tan(fp) / R1) * (
        (D ** 2) / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 * C1 - 9.0 * e_prime2) * (D ** 4) / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 * T1 - 252.0 * e_prime2 - 3.0 * C1 * C1) * (D ** 6) / 720.0
    )
    lat_deg = math.degrees(lat)

    lon_origin = (zone - 1) * 6 - 180 + 3
    lon = (
        D
        - (1.0 + 2.0 * T1 + C1) * (D ** 3) / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 * C1 + 8.0 * e_prime2 + 24.0 * T1 * T1) * (D ** 5) / 120.0
    ) / math.cos(fp)
    lon_deg = lon_origin + math.degrees(lon)

    return round(lat_deg, 6), round(lon_deg, 6)