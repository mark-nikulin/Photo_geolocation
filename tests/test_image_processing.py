from pathlib import Path
from unittest.mock import Mock, patch

from app.utils.image_processing import ImageProcessor


class TestImageProcessor:
    def setup_method(self):
        self.processor = ImageProcessor()

    def test_validate_image_file_not_exists(self):
        result, error = self.processor.validate_image(Path("nonexistent.jpg"))
        assert result is False
        assert "does not exist" in error

    @patch("app.utils.image_processing.Image.open")
    def test_validate_image_success(self, mock_open):
        mock_img = Mock()
        mock_img.format = "JPEG"
        mock_open.return_value.__enter__.return_value = mock_img

        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000

                result, error = self.processor.validate_image(Path("test.jpg"))
                assert result is True
                assert error is None

    def test_generate_hash(self):
        with patch("builtins.open", mock_open(read_data=b"test data")):
            hash_result = self.processor.generate_hash(Path("test.jpg"))
            assert len(hash_result) == 64

    def test_extract_metadata_basic(self):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_size = 1000

                with patch("app.utils.image_processing.Image.open") as mock_open:
                    mock_img = Mock()
                    mock_img.format = "JPEG"
                    mock_img.width = 1920
                    mock_img.height = 1080
                    mock_open.return_value.__enter__.return_value = mock_img

                    metadata = self.processor.extract_metadata(Path("test.jpg"))

                    assert metadata["format"] == "JPEG"
                    assert metadata["dimensions"]["width"] == 1920
                    assert metadata["dimensions"]["height"] == 1080

    def test_convert_to_degrees(self):
        value = [40, 45, 30]
        result = self.processor._convert_to_degrees(value)
        expected = 40 + 45 / 60.0 + 30 / 3600.0
        assert abs(result - expected) < 0.0001


def mock_open(read_data=b""):
    from unittest.mock import mock_open as original_mock_open

    return original_mock_open(read_data=read_data)
