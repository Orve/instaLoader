"""Tests for LINE Bot functionality.

現行の run_line 実装（create_media_messages / handle_message / callback）を
直接検証する。かつてのテストは存在しない MediaExtractor クラスと、
実コードを呼ばない自作ヘルパーを前提にしていたため書き直した。
取得失敗時に無言になるのは現行仕様であり、その変更は #3 で扱う。
"""

import logging
from unittest.mock import Mock, patch

from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    ImageSendMessage,
    MessageEvent,
    SourceUser,
    TextMessage,
    TextSendMessage,
    VideoSendMessage,
)

import run_line
from run_line import create_media_messages


def _single_result(media_type="image"):
    """process_instagram_url の戻り値（単一メディア）の形を作る。"""
    if media_type == "video":
        media = {
            "url": "https://example.com/video.mp4",
            "type": "video",
            "thumbnail": "https://example.com/thumb.jpg",
        }
    else:
        media = {
            "url": "https://example.com/image.jpg",
            "type": "image",
            "thumbnail": None,
        }
    return {
        "type": "single",
        "media_count": 1,
        "media_list": [media],
        "media_url": media["url"],
        "preview_url": media["thumbnail"] or media["url"],
        "media_type": media["type"],
    }


def _carousel_result(count):
    """process_instagram_url の戻り値（カルーセル、画像 count 枚）の形を作る。"""
    media_list = [
        {"url": f"https://example.com/image{i}.jpg", "type": "image", "thumbnail": None}
        for i in range(count)
    ]
    return {
        "type": "carousel",
        "media_count": count,
        "media_list": media_list,
        "media_url": media_list[0]["url"],
        "preview_url": media_list[0]["url"],
        "media_type": "image",
    }


def _text_event(text):
    """テキストメッセージの MessageEvent を作る。"""
    return MessageEvent(
        reply_token="test_reply_token",
        source=SourceUser(user_id="U_test"),
        message=TextMessage(id="1", text=text),
    )


class TestCreateMediaMessages:
    """create_media_messages のメッセージ構築。"""

    def test_single_image(self):
        messages = create_media_messages(_single_result("image"))
        assert len(messages) == 1
        assert isinstance(messages[0], ImageSendMessage)
        assert messages[0].original_content_url == "https://example.com/image.jpg"

    def test_single_video(self):
        messages = create_media_messages(_single_result("video"))
        assert len(messages) == 1
        assert isinstance(messages[0], VideoSendMessage)
        assert messages[0].original_content_url == "https://example.com/video.mp4"
        assert messages[0].preview_image_url == "https://example.com/thumb.jpg"

    def test_carousel_starts_with_count_text(self):
        messages = create_media_messages(_carousel_result(3))
        assert isinstance(messages[0], TextSendMessage)
        assert "3件" in messages[0].text
        assert sum(isinstance(m, ImageSendMessage) for m in messages) == 3

    def test_messages_capped_at_five(self):
        """LINE の上限により、返信メッセージは最大5個に切り詰められる。"""
        messages = create_media_messages(_carousel_result(8))
        assert len(messages) == 5


class TestHandleMessage:
    """handle_message の返信分岐。"""

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_reply_on_success(self, mock_process, mock_api):
        mock_process.return_value = _single_result("image")

        run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        mock_api.reply_message.assert_called_once()
        reply_token, messages = mock_api.reply_message.call_args[0]
        assert reply_token == "test_reply_token"
        assert isinstance(messages[0], ImageSendMessage)

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_no_reply_on_failure(self, mock_process, mock_api):
        """取得失敗時は現行仕様として何も返信しない（#3 で変更予定）。"""
        mock_process.return_value = None

        run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        mock_api.reply_message.assert_not_called()

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_error_text_on_send_failure(self, mock_process, mock_api):
        """送信に失敗したらエラーテキストでの再返信を試みる。"""
        mock_process.return_value = _single_result("image")
        mock_api.reply_message.side_effect = [Exception("send failed"), None]

        run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        assert mock_api.reply_message.call_count == 2
        _, second_messages = mock_api.reply_message.call_args[0]
        assert isinstance(second_messages, TextSendMessage)
        assert "エラーが発生しました" in second_messages.text


class TestCallback:
    """Webhook エンドポイント /callback。"""

    def test_invalid_signature_returns_400(self):
        client = run_line.app.test_client()
        with patch.object(run_line.handler, "handle", side_effect=InvalidSignatureError("bad")):
            response = client.post(
                "/callback",
                data='{"events":[]}',
                headers={"X-Line-Signature": "invalid", "Content-Type": "application/json"},
            )
        assert response.status_code == 400

    def test_health_check(self):
        client = run_line.app.test_client()
        response = client.get("/")
        assert response.status_code == 200

    def test_callback_does_not_log_request_body(self, caplog):
        """Webhook 本文（ユーザーIDやメッセージ本文）はログに残さない。"""
        client = run_line.app.test_client()
        body = '{"events":[{"source":{"userId":"U_SECRET"},"message":{"text":"SECRET_BODY_MARKER"}}]}'
        with patch.object(run_line.handler, "handle", return_value=None):
            with caplog.at_level(logging.INFO):
                response = client.post(
                    "/callback",
                    data=body,
                    headers={"X-Line-Signature": "dummy", "Content-Type": "application/json"},
                )
        assert response.status_code == 200
        assert "SECRET_BODY_MARKER" not in caplog.text
        assert "U_SECRET" not in caplog.text


class TestHandleMessageObservability:
    """handle_message の request_id 伝播と段階ログ（Issue #2）。"""

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_request_id_is_passed_to_logic(self, mock_process, mock_api):
        mock_process.return_value = _single_result("image")

        run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        request_id = mock_process.call_args.kwargs.get("request_id")
        assert isinstance(request_id, str) and request_id

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_fetch_failure_is_logged_as_skipped(self, mock_process, mock_api, caplog):
        """取得失敗は配信失敗と区別できる形でログに残る。"""
        mock_process.return_value = None

        with caplog.at_level(logging.INFO, logger="run_line"):
            run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        assert "stage=reply result=skipped" in caplog.text

    @patch("run_line.line_bot_api")
    @patch("run_line.process_instagram_url")
    def test_send_failure_is_logged_as_reply_error(self, mock_process, mock_api, caplog):
        """取得成功後の送信失敗は stage=reply のエラーとして残る。"""
        mock_process.return_value = _single_result("image")
        mock_api.reply_message.side_effect = [Exception("send failed"), None]

        with caplog.at_level(logging.INFO, logger="run_line"):
            run_line.handle_message(_text_event("https://www.instagram.com/p/TEST123/"))

        assert "stage=reply result=error" in caplog.text
