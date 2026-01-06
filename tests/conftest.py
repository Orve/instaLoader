"""Pytest configuration and shared fixtures."""

import pytest
import os
from unittest.mock import Mock


@pytest.fixture(scope="session")
def test_env_vars():
    """Set up test environment variables."""
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_line_token"
    os.environ["LINE_CHANNEL_SECRET"] = "test_line_secret"
    os.environ["DISCORD_BOT_TOKEN"] = "test_discord_token"
    os.environ["RAPID_API_KEY"] = "test_api_key"
    os.environ["RAPID_API_HOST"] = "test_api_host"
    yield
    # Cleanup after tests
    for key in ["LINE_CHANNEL_ACCESS_TOKEN", "LINE_CHANNEL_SECRET", 
                "DISCORD_BOT_TOKEN", "RAPID_API_KEY", "RAPID_API_HOST"]:
        os.environ.pop(key, None)


@pytest.fixture
def mock_instagram_response():
    """Mock Instagram API response."""
    return {
        "data": {
            "shortcode": "TEST123",
            "media_type": 1,
            "image_versions": {
                "items": [
                    {"url": "https://example.com/image1.jpg"},
                    {"url": "https://example.com/image2.jpg"}
                ]
            },
            "caption": {
                "text": "Test caption"
            },
            "owner": {
                "username": "testuser"
            }
        }
    }


@pytest.fixture
def mock_video_response():
    """Mock Instagram video response."""
    return {
        "data": {
            "shortcode": "VIDEO123",
            "media_type": 2,
            "video_versions": [
                {"url": "https://example.com/video.mp4"}
            ],
            "image_versions": {
                "items": [
                    {"url": "https://example.com/thumbnail.jpg"}
                ]
            }
        }
    }


@pytest.fixture
def mock_carousel_response():
    """Mock Instagram carousel response."""
    return {
        "data": {
            "shortcode": "CAROUSEL123",
            "media_type": 8,
            "carousel_media": [
                {
                    "media_type": 1,
                    "image_versions": {
                        "items": [{"url": "https://example.com/carousel1.jpg"}]
                    }
                },
                {
                    "media_type": 2,
                    "video_versions": [{"url": "https://example.com/carousel_video.mp4"}]
                }
            ]
        }
    }