"""Tests for Discord Bot functionality.

現行の run_discord 実装（on_message / send_media_embeds）を直接検証する。
かつてのテストは存在しない MediaExtractor クラスを前提にし、実コードの
呼び出しもコメントアウトされていたため書き直した。
pytest-asyncio に依存せず、asyncio.run でコルーチンを実行する。
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import discord

import run_discord


class _Typing:
    """channel.typing() が返す非同期コンテキストマネージャの代役。"""

    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class _FakeChannel:
    def __init__(self):
        self.send = AsyncMock()

    def typing(self):
        return _Typing()


class _FakeMessage:
    def __init__(self, content, author=None):
        self.content = content
        self.author = author if author is not None else Mock()
        self.channel = _FakeChannel()
        self.reply = AsyncMock()
        self.id = 1


def _result(media_list):
    return {
        "type": "carousel" if len(media_list) > 1 else "single",
        "media_count": len(media_list),
        "media_list": media_list,
        "media_url": media_list[0]["url"],
        "preview_url": media_list[0].get("thumbnail") or media_list[0]["url"],
        "media_type": media_list[0]["type"],
    }


_IMAGE = {"url": "https://example.com/image.jpg", "type": "image", "thumbnail": None}
_VIDEO = {
    "url": "https://example.com/video.mp4",
    "type": "video",
    "thumbnail": "https://example.com/thumb.jpg",
}


class TestOnMessage:
    """on_message の分岐。"""

    def test_ignore_own_message(self):
        """Bot 自身のメッセージは処理しない。"""
        message = _FakeMessage("https://www.instagram.com/p/TEST123/")
        # client.user はログイン前は None になり得るため、代役の都合ではなく
        # 「author が client.user と同一」を直接作る
        message.author = run_discord.client.user
        with patch("run_discord.fetch_instagram_media") as mock_process:
            asyncio.run(run_discord.on_message(message))
        mock_process.assert_not_called()
        message.reply.assert_not_called()

    def test_ignore_non_instagram_message(self):
        """Instagram URL を含まないメッセージは処理しない。"""
        message = _FakeMessage("Just a regular message")
        with patch("run_discord.fetch_instagram_media") as mock_process:
            asyncio.run(run_discord.on_message(message))
        mock_process.assert_not_called()
        message.reply.assert_not_called()

    def test_reply_image_embed_on_success(self):
        """単一画像の成功時は画像 Embed で返信する。"""
        message = _FakeMessage("https://www.instagram.com/p/TEST123/")
        with patch("run_discord.fetch_instagram_media", return_value={"status": "ok", "result": _result([_IMAGE])}):
            asyncio.run(run_discord.on_message(message))

        message.reply.assert_called_once()
        embed = message.reply.call_args.kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert embed.image.url == "https://example.com/image.jpg"

    def test_reply_video_url_on_success(self):
        """単一動画の成功時は URL をそのまま返信する。"""
        message = _FakeMessage("https://www.instagram.com/reel/VIDEO123/")
        with patch("run_discord.fetch_instagram_media", return_value={"status": "ok", "result": _result([_VIDEO])}):
            asyncio.run(run_discord.on_message(message))

        message.reply.assert_called_once()
        assert message.reply.call_args.kwargs["content"] == "https://example.com/video.mp4"

    def test_error_embed_on_failure(self):
        """取得失敗時は ❌ エラー Embed に理由に応じた文言を入れて返信する（#3）。"""
        message = _FakeMessage("https://www.instagram.com/p/TEST123/")
        outcome = {"status": "failed", "reason": "http_error", "http_status": 500}
        with patch("run_discord.fetch_instagram_media", return_value=outcome):
            asyncio.run(run_discord.on_message(message))

        message.reply.assert_called_once()
        embed = message.reply.call_args.kwargs["embed"]
        assert "エラー" in embed.title
        assert "取得できませんでした" in embed.description
        assert "制限されている投稿の可能性" in embed.description

    def test_error_embed_on_exception(self):
        """処理中の例外時は ⚠️ エラー Embed で返信する。"""
        message = _FakeMessage("https://www.instagram.com/p/TEST123/")
        with patch(
            "run_discord.fetch_instagram_media", side_effect=Exception("Network error")
        ):
            asyncio.run(run_discord.on_message(message))

        message.reply.assert_called_once()
        embed = message.reply.call_args.kwargs["embed"]
        assert "エラー" in embed.title


class TestSendMediaEmbeds:
    """send_media_embeds のカルーセル送信。"""

    def test_carousel_sends_info_and_each_media(self):
        """複数メディアでは件数 Embed のあと各メディアを送る。"""
        message = _FakeMessage("https://www.instagram.com/p/TEST123/")
        media_list = [
            {"url": "https://example.com/1.jpg", "type": "image", "thumbnail": None},
            {"url": "https://example.com/2.jpg", "type": "image", "thumbnail": None},
        ]
        asyncio.run(run_discord.send_media_embeds(message, _result(media_list)))

        # 先頭は件数通知の reply、残り2件は channel.send
        message.reply.assert_called_once()
        assert message.channel.send.call_count == 2
