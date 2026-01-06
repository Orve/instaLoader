"""Tests for core Instagram media extraction logic."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.logic import MediaExtractor


class TestMediaExtractor:
    """Test suite for MediaExtractor class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.api_key = "test_api_key"
        self.api_host = "test_api_host"
        self.extractor = MediaExtractor(self.api_key, self.api_host)

    def test_extract_shortcode_from_url(self):
        """Test shortcode extraction from various Instagram URLs."""
        test_cases = [
            ("https://www.instagram.com/p/ABC123/", "ABC123"),
            ("http://instagram.com/p/XYZ789/", "XYZ789"),
            ("https://www.instagram.com/p/TEST123/?utm_source=test", "TEST123"),
            ("https://www.instagram.com/reel/REEL456/", "REEL456"),
        ]
        
        for url, expected_shortcode in test_cases:
            shortcode = self.extractor._extract_shortcode(url)
            assert shortcode == expected_shortcode, f"Failed for URL: {url}"

    def test_extract_shortcode_invalid_url(self):
        """Test shortcode extraction with invalid URLs."""
        invalid_urls = [
            "https://www.google.com",
            "not_a_url",
            "https://instagram.com/username/",
            "",
            None,
        ]
        
        for url in invalid_urls:
            shortcode = self.extractor._extract_shortcode(url)
            assert shortcode is None, f"Should return None for: {url}"

    @patch('requests.get')
    def test_fetch_media_success(self, mock_get):
        """Test successful media fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "media_type": 1,
                "image_versions": {
                    "items": [
                        {"url": "https://example.com/image.jpg"}
                    ]
                }
            }
        }
        mock_get.return_value = mock_response
        
        url = "https://www.instagram.com/p/TEST123/"
        result = self.extractor.fetch_media(url)
        
        assert result["success"] is True
        assert "media_urls" in result
        assert len(result["media_urls"]) > 0

    @patch('requests.get')
    def test_fetch_media_api_error(self, mock_get):
        """Test media fetching with API error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response
        
        url = "https://www.instagram.com/p/NOTFOUND/"
        result = self.extractor.fetch_media(url)
        
        assert result["success"] is False
        assert "error" in result

    @patch('requests.get')
    def test_fetch_media_network_error(self, mock_get):
        """Test media fetching with network error."""
        mock_get.side_effect = Exception("Network error")
        
        url = "https://www.instagram.com/p/TEST123/"
        result = self.extractor.fetch_media(url)
        
        assert result["success"] is False
        assert "error" in result
        assert "Network error" in result["error"]


class TestMediaTypeDetection:
    """Test suite for media type detection."""

    def setup_method(self):
        """Setup test fixtures."""
        self.extractor = MediaExtractor("key", "host")

    def test_detect_image_type(self):
        """Test detection of image media type."""
        media_data = {
            "media_type": 1,
            "image_versions": {"items": [{"url": "test.jpg"}]}
        }
        media_type = self.extractor._detect_media_type(media_data)
        assert media_type == "image"

    def test_detect_video_type(self):
        """Test detection of video media type."""
        media_data = {
            "media_type": 2,
            "video_versions": [{"url": "test.mp4"}]
        }
        media_type = self.extractor._detect_media_type(media_data)
        assert media_type == "video"

    def test_detect_carousel_type(self):
        """Test detection of carousel media type."""
        media_data = {
            "media_type": 8,
            "carousel_media": [
                {"image_versions": {"items": [{"url": "test1.jpg"}]}},
                {"video_versions": [{"url": "test2.mp4"}]}
            ]
        }
        media_type = self.extractor._detect_media_type(media_data)
        assert media_type == "carousel"