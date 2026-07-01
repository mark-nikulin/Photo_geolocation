import math
import re
from typing import Any, Dict, List, Optional, Tuple

import structlog
from geopy.distance import geodesic

logger = structlog.get_logger(__name__)


class GeoUtils:
    @staticmethod
    def calculate_distance(
        point1: Tuple[float, float], point2: Tuple[float, float]
    ) -> float:
        try:
            return geodesic(point1, point2).kilometers
        except Exception as e:
            logger.error("Error calculating distance", error=str(e))
            return float("inf")

    @staticmethod
    def calculate_bearing(
        point1: Tuple[float, float], point2: Tuple[float, float]
    ) -> float:
        try:
            lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
            lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])

            dlon = lon2 - lon1

            y = math.sin(dlon) * math.cos(lat2)
            x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
                lat2
            ) * math.cos(dlon)

            bearing = math.atan2(y, x)
            bearing = math.degrees(bearing)

            return (bearing + 360) % 360
        except Exception as e:
            logger.error("Error calculating bearing", error=str(e))
            return 0.0

    @staticmethod
    def validate_coordinates(
        latitude: float, longitude: float
    ) -> Tuple[bool, Optional[str]]:
        try:
            lat_f = float(latitude)
            lon_f = float(longitude)

            if not (-90 <= lat_f <= 90):
                return False, f"Latitude {lat_f} out of range (-90 to 90)"

            if not (-180 <= lon_f <= 180):
                return False, f"Longitude {lon_f} out of range (-180 to 180)"

            return True, None
        except (ValueError, TypeError):
            return False, "Coordinates must be valid numbers"

    @staticmethod
    def degrees_to_decimal(
        degrees: int, minutes: int, seconds: float, direction: str
    ) -> float:
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if direction.upper() in ["S", "W"]:
            decimal = -decimal
        return decimal

    @staticmethod
    def decimal_to_dms(decimal_degrees: float) -> Dict[str, Any]:
        is_positive = decimal_degrees >= 0
        decimal_degrees = abs(decimal_degrees)

        degrees = int(decimal_degrees)
        minutes_float = (decimal_degrees - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60

        return {
            "degrees": degrees,
            "minutes": minutes,
            "seconds": round(seconds, 2),
            "direction": "N" if is_positive else "S",
        }

    @staticmethod
    def find_center_point(
        coordinates: List[Tuple[float, float]],
    ) -> Tuple[float, float]:
        if not coordinates:
            return 0.0, 0.0

        if len(coordinates) == 1:
            return coordinates[0]

        lat_sum = sum(coord[0] for coord in coordinates)
        lon_sum = sum(coord[1] for coord in coordinates)

        return lat_sum / len(coordinates), lon_sum / len(coordinates)

    @staticmethod
    def create_bounding_box(
        coordinates: List[Tuple[float, float]], padding_km: float = 1.0
    ) -> Dict[str, float]:
        if not coordinates:
            return {"north": 0, "south": 0, "east": 0, "west": 0}

        lats = [coord[0] for coord in coordinates]
        lons = [coord[1] for coord in coordinates]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        lat_padding = padding_km / 111.0
        lon_padding = padding_km / (
            111.0 * math.cos(math.radians((min_lat + max_lat) / 2))
        )

        return {
            "north": max_lat + lat_padding,
            "south": min_lat - lat_padding,
            "east": max_lon + lon_padding,
            "west": min_lon - lon_padding,
        }

    @staticmethod
    def extract_coordinates_from_text(text: str) -> List[Tuple[float, float]]:
        coordinates = []

        decimal_pattern = r"(-?\d{1,3}\.\d+),\s*(-?\d{1,3}\.\d+)"

        for match in re.finditer(decimal_pattern, text):
            try:
                lat, lon = float(match.group(1)), float(match.group(2))
                if GeoUtils.validate_coordinates(lat, lon)[0]:
                    coordinates.append((lat, lon))
            except ValueError:
                continue

        return coordinates

    @staticmethod
    def format_coordinates(
        latitude: float, longitude: float, format_type: str = "decimal"
    ) -> str:
        if format_type == "decimal":
            return f"{latitude:.6f}, {longitude:.6f}"
        elif format_type == "dms":
            lat_dms = GeoUtils.decimal_to_dms(latitude)
            lon_dms = GeoUtils.decimal_to_dms(longitude)

            lat_dir = "N" if latitude >= 0 else "S"
            lon_dir = "E" if longitude >= 0 else "W"

            return (
                f"{lat_dms['degrees']}°{lat_dms['minutes']}'{lat_dms['seconds']}\"{lat_dir}, "
                f"{lon_dms['degrees']}°{lon_dms['minutes']}'{lon_dms['seconds']}\"{lon_dir}"
            )
        else:
            return f"{latitude:.6f}, {longitude:.6f}"
