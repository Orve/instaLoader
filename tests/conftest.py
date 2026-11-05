"""Pytest configuration and shared fixtures."""

import os

# テスト用の環境変数は、アプリ側モジュール（core.config）が import される前に
# セットする必要がある。core.config は import 時点で os.environ を読むため、
# fixture（テスト実行時に呼ばれる）では間に合わない。
# conftest.py はテストモジュールより先に読み込まれるので、ここで module level
# で setdefault する。実環境の値が既にある場合は上書きしない。
_TEST_ENV_DEFAULTS = {
    "LINE_CHANNEL_ACCESS_TOKEN": "test_line_token",
    "LINE_CHANNEL_SECRET": "test_line_secret",
    "DISCORD_BOT_TOKEN": "test_discord_token",
    "RAPID_API_KEY": "test_api_key",
    "RAPID_API_HOST": "test_api_host",
}
for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)


import pytest


@pytest.fixture
def mock_instagram_response():
    """現行の RapidAPI レスポンス形式（medias リスト）のモック: 単一画像。"""
    return {
        "medias": [
            {"url": "https://example.com/image1.jpg"}
        ]
    }


@pytest.fixture
def mock_video_response():
    """現行の RapidAPI レスポンス形式のモック: 動画＋サムネイル。"""
    return {
        "medias": [
            {
                "video_url": "https://example.com/video.mp4",
                "thumbnail": "https://example.com/thumbnail.jpg",
            }
        ]
    }


@pytest.fixture
def mock_carousel_response():
    """現行の RapidAPI レスポンス形式のモック: カルーセル（画像2枚）。"""
    return {
        "medias": [
            {"url": "https://example.com/carousel1.jpg"},
            {"url": "https://example.com/carousel2.jpg"},
        ]
    }
