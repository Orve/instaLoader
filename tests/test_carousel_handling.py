"""Tests for carousel/multiple media handling."""

import pytest
from unittest.mock import Mock, patch
from core.logic import process_instagram_url, _find_all_urls, _extract_media_info


class TestCarouselHandling:
    """Test suite for carousel post handling."""
    
    def test_find_all_urls_single_media(self):
        """Test _find_all_urls with single media response."""
        data = {
            "medias": [
                {"url": "https://example.com/image1.jpg"}
            ]
        }
        urls = _find_all_urls(data)
        assert len(urls) == 1
        assert urls[0] == "https://example.com/image1.jpg"
    
    def test_find_all_urls_multiple_media(self):
        """Test _find_all_urls with multiple media (carousel)."""
        data = {
            "medias": [
                {"url": "https://example.com/image1.jpg"},
                {"url": "https://example.com/image2.jpg"},
                {"url": "https://example.com/image3.jpg"}
            ]
        }
        urls = _find_all_urls(data)
        assert len(urls) == 3
        assert "https://example.com/image1.jpg" in urls
        assert "https://example.com/image2.jpg" in urls
        assert "https://example.com/image3.jpg" in urls
    
    def test_find_all_urls_mixed_media(self):
        """Test _find_all_urls with mixed media types."""
        data = {
            "medias": [
                {"url": "https://example.com/image1.jpg"},
                {"video_url": "https://example.com/video1.mp4"},
                {"download_url": "https://example.com/image2.jpg"}
            ]
        }
        urls = _find_all_urls(data)
        assert len(urls) == 3
        assert "https://example.com/video1.mp4" in urls
    
    def test_find_all_urls_excludes_instagram_urls(self):
        """Test that Instagram post URLs are excluded."""
        data = {
            "medias": [
                {"url": "https://instagram.com/p/ABC123/"},
                {"url": "https://example.com/image1.jpg"},
                {"url": "https://instagram.com/reel/XYZ789/"}
            ]
        }
        urls = _find_all_urls(data)
        assert len(urls) == 1
        assert urls[0] == "https://example.com/image1.jpg"
    
    def test_extract_media_info_single_image(self):
        """Test media info extraction for single image."""
        data = {
            "medias": [
                {"url": "https://example.com/image.jpg"}
            ]
        }
        media_list = _extract_media_info(data)
        assert len(media_list) == 1
        assert media_list[0]["url"] == "https://example.com/image.jpg"
        assert media_list[0]["type"] == "image"
    
    def test_extract_media_info_video_with_thumbnail(self):
        """Test media info extraction for video with thumbnail."""
        data = {
            "medias": [
                {
                    "video_url": "https://example.com/video.mp4",
                    "thumbnail": "https://example.com/thumb.jpg"
                }
            ]
        }
        media_list = _extract_media_info(data)
        assert len(media_list) == 1
        assert media_list[0]["url"] == "https://example.com/video.mp4"
        assert media_list[0]["type"] == "video"
        assert media_list[0]["thumbnail"] == "https://example.com/thumb.jpg"
    
    def test_extract_media_info_carousel(self):
        """Test media info extraction for carousel with mixed media."""
        data = {
            "medias": [
                {"url": "https://example.com/image1.jpg"},
                {
                    "video_url": "https://example.com/video.mp4",
                    "thumbnail": "https://example.com/video_thumb.jpg"
                },
                {"download_url": "https://example.com/image2.jpg"}
            ]
        }
        media_list = _extract_media_info(data)
        assert len(media_list) == 3
        
        # Check first image
        assert media_list[0]["type"] == "image"
        
        # Check video
        video_item = next((m for m in media_list if m["type"] == "video"), None)
        assert video_item is not None
        assert video_item["thumbnail"] is not None
    
    @patch('requests.get')
    def test_process_instagram_url_carousel(self, mock_get):
        """Test process_instagram_url with carousel response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "medias": [
                {"url": "https://example.com/image1.jpg"},
                {"url": "https://example.com/image2.jpg"},
                {"url": "https://example.com/image3.jpg"}
            ]
        }
        mock_get.return_value = mock_response
        
        result = process_instagram_url("https://instagram.com/p/TEST123/")
        
        assert result is not None
        assert result["type"] == "carousel"
        assert result["media_count"] == 3
        assert len(result["media_list"]) == 3
        
        # Check backward compatibility
        assert "media_url" in result
        assert result["media_url"] == "https://example.com/image1.jpg"
    
    @patch('requests.get')
    def test_process_instagram_url_single_media(self, mock_get):
        """Test process_instagram_url with single media response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "medias": [
                {"url": "https://example.com/image.jpg"}
            ]
        }
        mock_get.return_value = mock_response
        
        result = process_instagram_url("https://instagram.com/p/TEST123/")
        
        assert result is not None
        assert result["type"] == "single"
        assert result["media_count"] == 1
        assert len(result["media_list"]) == 1
    
    @patch('requests.get')
    def test_process_instagram_url_empty_response(self, mock_get):
        """Test process_instagram_url with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response
        
        result = process_instagram_url("https://instagram.com/p/TEST123/")
        
        assert result is None
    
    def test_find_all_urls_no_duplicates(self):
        """Test that _find_all_urls doesn't return duplicate URLs."""
        data = {
            "medias": [
                {"url": "https://example.com/image.jpg"},
                {"download_url": "https://example.com/image.jpg"},  # Same URL
                {"media": "https://example.com/image.jpg"}  # Same URL again
            ]
        }
        urls = _find_all_urls(data)
        assert len(urls) == 1
        assert urls[0] == "https://example.com/image.jpg"