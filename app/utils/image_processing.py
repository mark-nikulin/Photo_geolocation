import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import exifread
import structlog
from PIL import Image
from PIL.ExifTags import TAGS

logger = structlog.get_logger(__name__)


class ImageProcessor:
    def __init__(self, max_size: int = 10 * 1024 * 1024):
        self.max_size = max_size
        self.allowed_formats = {"JPEG", "PNG", "WEBP", "TIFF"}

    def validate_image(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        if not file_path.exists():
            return False, "File does not exist"

        if file_path.stat().st_size > self.max_size:
            return False, f"File too large. Max size: {self.max_size} bytes"

        try:
            with Image.open(file_path) as img:
                if img.format not in self.allowed_formats:
                    return False, f"Unsupported format: {img.format}"
                img.verify()
            return True, None
        except Exception as e:
            return False, f"Invalid image: {str(e)}"

    def extract_metadata(self, file_path: Path) -> Dict[str, Any]:
        metadata = {
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "dimensions": {},
            "format": "",
            "has_exif": False,
            "has_gps": False,
            "exif_data": {},
        }

        try:
            with Image.open(file_path) as img:
                metadata["format"] = img.format
                metadata["dimensions"] = {"width": img.width, "height": img.height}

                exif_data = self._extract_exif_data(file_path)
                if exif_data:
                    metadata["has_exif"] = True
                    metadata["exif_data"] = exif_data
                    metadata["has_gps"] = "GPS" in exif_data

        except Exception as e:
            logger.error("Error extracting metadata", error=str(e), file=str(file_path))

        return metadata

    def _extract_exif_data(self, file_path: Path) -> Dict[str, Any]:
        exif_data: Dict[str, Any] = {}

        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, details=True)

            with Image.open(file_path) as img:
                if hasattr(img, "_getexif") and img._getexif():
                    exif = img._getexif()
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif_data[tag] = str(value)

            gps_data = self._extract_gps_coordinates(file_path)
            if gps_data:
                exif_data["GPS"] = gps_data

            camera_info = self._extract_camera_info(tags)
            exif_data.update(camera_info)

            datetime_info = self._extract_datetime_info(tags)
            if datetime_info:
                exif_data["DateTime"] = datetime_info

        except Exception as e:
            logger.error("Error extracting EXIF", error=str(e))

        return exif_data

    def _extract_gps_coordinates(self, file_path: Path) -> Optional[Dict[str, float]]:
        try:
            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, details=True)

            gps_latitude = tags.get("GPS GPSLatitude")
            gps_latitude_ref = tags.get("GPS GPSLatitudeRef")
            gps_longitude = tags.get("GPS GPSLongitude")
            gps_longitude_ref = tags.get("GPS GPSLongitudeRef")

            if not (
                gps_latitude
                and gps_latitude_ref
                and gps_longitude
                and gps_longitude_ref
            ):
                return None

            lat = self._convert_to_degrees(gps_latitude.values)
            if gps_latitude_ref.values[0] != "N":
                lat = -lat

            lon = self._convert_to_degrees(gps_longitude.values)
            if gps_longitude_ref.values[0] != "E":
                lon = -lon

            return {"latitude": lat, "longitude": lon}

        except Exception as e:
            logger.error("Error extracting GPS", error=str(e))
            return None

    def _convert_to_degrees(self, value: Any) -> float:
        d, m, s = value
        return float(d) + float(m) / 60.0 + float(s) / 3600.0

    def _extract_camera_info(self, tags: Dict) -> Dict[str, Any]:
        camera_info: Dict[str, Any] = {}

        if "Image Make" in tags:
            camera_info["make"] = str(tags["Image Make"])
        if "Image Model" in tags:
            camera_info["model"] = str(tags["Image Model"])
        if "Image Orientation" in tags:
            camera_info["orientation"] = int(str(tags["Image Orientation"]))

        return camera_info

    def _extract_datetime_info(self, tags: Dict) -> Optional[datetime]:
        datetime_tags = ["EXIF DateTimeOriginal", "EXIF DateTime", "Image DateTime"]

        for tag in datetime_tags:
            if tag in tags:
                try:
                    date_str = str(tags[tag])
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    continue

        return None

    def generate_hash(self, file_path: Path) -> str:
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def resize_if_needed(self, file_path: Path, max_dimension: int = 2048) -> Path:
        try:
            with Image.open(file_path) as img:
                if max(img.size) <= max_dimension:
                    return file_path

                ratio = max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)

                resized = img.resize(new_size, Image.Resampling.LANCZOS)

                resized_path = file_path.with_stem(f"{file_path.stem}_resized")
                resized.save(resized_path, optimize=True, quality=85)

                return resized_path
        except Exception as e:
            logger.error("Error resizing image", error=str(e))
            return file_path
