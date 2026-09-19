import os

try:
    import rasterio
    from rasterio.warp import transform
except ImportError:
    rasterio = None


class DemManager:
    """Manages dynamic elevation queries from local Digital Elevation Model (GeoTIFF) rasters."""

    def __init__(self, dem_path=None):
        self.dem_path = None
        self.dataset = None
        if dem_path and os.path.exists(dem_path):
            self.load_dem(dem_path)

    def load_dem(self, dem_path: str) -> bool:
        """Loads or swaps a GeoTIFF raster file."""
        if not rasterio:
            print("[DEM] rasterio library not installed. Run 'pip install rasterio'")
            return False

        if not os.path.exists(dem_path):
            print(f"[DEM] File not found: {dem_path}")
            return False

        try:
            if self.dataset:
                self.dataset.close()

            self.dataset = rasterio.open(dem_path)
            self.dem_path = dem_path
            print(f"[DEM] Loaded elevation raster successfully: {os.path.basename(dem_path)} (CRS: {self.dataset.crs})")
            return True
        except Exception as e:
            print(f"[DEM] Failed to load raster: {e}")
            self.dataset = None
            return False

    def get_elevation(self, lat: float, lon: float, default: float = 0.0) -> float:
        """Returns elevation in meters MSL for a given Lat/Lon coordinate."""
        if not self.dataset:
            return default

        try:
            # Transform WGS84 (EPSG:4326) into raster CRS if different
            if self.dataset.crs and str(self.dataset.crs).upper() != "EPSG:4326":
                xs, ys = transform("EPSG:4326", self.dataset.crs, [lon], [lat])
                sample_coords = [(xs[0], ys[0])]
            else:
                sample_coords = [(lon, lat)]

            sampled = list(self.dataset.sample(sample_coords))
            if sampled and len(sampled[0]) > 0:
                elev = float(sampled[0][0])
                if elev < -500.0 or elev > 9000.0:
                    return default
                return round(elev, 2)
        except Exception:
            pass

        return default

    def close(self):
        if self.dataset:
            try:
                self.dataset.close()
            except Exception:
                pass
            self.dataset = None