"""Tests for core Instagram media extraction logic.

現行実装は関数ベース（process_instagram_url）であり、かつてテストが前提に
していた MediaExtractor クラスは存在しない。本ファイルは現行の公開関数に
対して、URL検出・API通信・レスポンス解析の各段階を検証する。
メディア抽出ヘルパー（_find_all_urls / _extract_media_info）の詳細は
test_carousel_handling.py が担当する。
"""

from unittest.mock import Mock, patch

import requests

from core.logic import process_instagram_url


def _mock_response(json_data=None, json_error=None):
    """requests.get の戻り値モックを作る。"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    if json_error is not None:
        mock_response.json.side_effect = json_error
    else:
        mock_response.json.return_value = json_data if json_data is not None else {}
    return mock_response


class TestProcessInstagramUrl:
    """process_instagram_url の振る舞い。"""

    def test_non_instagram_text_returns_none_without_api_call(self):
        """Instagram URL を含まないテキストでは API を叩かず None。"""
        with patch("core.logic.requests.get") as mock_get:
            result = process_instagram_url("Hello, this is a test message")
        assert result is None
        mock_get.assert_not_called()

    def test_missing_api_key_returns_none(self):
        """RAPID_API_KEY 未設定時は None（API は叩かない）。"""
        with patch("core.logic.RAPID_API_KEY", None), \
                patch("core.logic.requests.get") as mock_get:
            result = process_instagram_url("https://www.instagram.com/p/TEST123/")
        assert result is None
        mock_get.assert_not_called()

    @patch("core.logic.requests.get")
    def test_success_single_image(self, mock_get, mock_instagram_response):
        """単一画像の成功レスポンスを結果辞書に変換する。"""
        mock_get.return_value = _mock_response(mock_instagram_response)

        result = process_instagram_url("https://www.instagram.com/p/TEST123/")

        assert result is not None
        assert result["type"] == "single"
        assert result["media_count"] == 1
        assert result["media_url"] == "https://example.com/image1.jpg"
        assert result["media_type"] == "image"
        assert result["preview_url"] == "https://example.com/image1.jpg"

    @patch("core.logic.requests.get")
    def test_success_video_uses_thumbnail_as_preview(self, mock_get, mock_video_response):
        """動画は video_url を使い、プレビューにはサムネイルを使う。"""
        mock_get.return_value = _mock_response(mock_video_response)

        result = process_instagram_url("https://www.instagram.com/reel/VIDEO123/")

        assert result is not None
        assert result["media_url"] == "https://example.com/video.mp4"
        assert result["media_type"] == "video"
        assert result["preview_url"] == "https://example.com/thumbnail.jpg"

    @patch("core.logic.requests.get")
    def test_request_passes_url_text_and_host_header(self, mock_get):
        """API には入力テキストが url パラメータとして渡る（現行の契約）。"""
        mock_get.return_value = _mock_response({"medias": [{"url": "https://example.com/a.jpg"}]})
        text = "https://www.instagram.com/p/TEST123/"

        process_instagram_url(text)

        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"url": text}
        assert kwargs["headers"]["X-RapidAPI-Host"] == "test_api_host"
        assert kwargs["headers"]["X-RapidAPI-Key"] == "test_api_key"

    @patch("core.logic.requests.get")
    def test_http_error_returns_none(self, mock_get):
        """HTTP エラー（raise_for_status が例外）では None。"""
        mock_response = _mock_response({"medias": []})
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        result = process_instagram_url("https://www.instagram.com/p/NOTFOUND/")

        assert result is None

    @patch("core.logic.requests.get")
    def test_timeout_returns_none(self, mock_get):
        """タイムアウト等の通信例外では None。"""
        mock_get.side_effect = requests.Timeout("timed out")

        result = process_instagram_url("https://www.instagram.com/p/TEST123/")

        assert result is None

    @patch("core.logic.requests.get")
    def test_invalid_json_returns_none(self, mock_get):
        """JSON として解析できない応答では None。"""
        mock_get.return_value = _mock_response(json_error=ValueError("No JSON"))

        result = process_instagram_url("https://www.instagram.com/p/TEST123/")

        assert result is None

    @patch("core.logic.requests.get")
    def test_response_without_media_returns_none(self, mock_get):
        """メディアが抽出できない応答（空辞書）では None。"""
        mock_get.return_value = _mock_response({})

        result = process_instagram_url("https://www.instagram.com/p/TEST123/")

        assert result is None
