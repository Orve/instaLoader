
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, VideoSendMessage
)

from core.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from core.logic import process_instagram_url

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 初期化 ---
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    logger.error("LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET is not set.")
    # 起動はするが、アクセス時にエラーになる可能性がある
    # 本来はsys.exit(1)でも良い

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN if LINE_CHANNEL_ACCESS_TOKEN else "DUMMY")
handler = WebhookHandler(LINE_CHANNEL_SECRET if LINE_CHANNEL_SECRET else "DUMMY")

@app.route("/")
def health_check():
    """Render等がサービスをKillしないためのヘルスチェック用エンドポイント"""
    return "Bot is alive", 200

@app.route("/callback", methods=['POST'])
def callback():
    """LINE PlatformからのWebhookを受け取るエンドポイント"""
    # X-Line-Signatureヘッダーの検証
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
    メッセージ受信時のイベントハンドラ。
    InstagramのURLが含まれている場合、動画/画像を抽出して返信する。
    """
    text = event.message.text
    
    # 共通ロジックを使用してInstagramの情報を取得
    result = process_instagram_url(text)
    
    if result:
        try:
            logger.info(f"Sending Message -> {result}")
            
            media_url = result["media_url"]
            preview_url = result["preview_url"]
            
            # --- LINEへの返信 ---
            if result["type"] == "video":
                # 動画の場合
                line_bot_api.reply_message(
                    event.reply_token,
                    VideoSendMessage(
                        original_content_url=media_url,
                        preview_image_url=preview_url
                    )
                )
            else:
                # 画像の場合
                line_bot_api.reply_message(
                    event.reply_token,
                    ImageSendMessage(
                        original_content_url=media_url,
                        preview_image_url=media_url
                    )
                )
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました🙇‍♂️\n送信中に問題が発生しました。")
            )
    else:
        # InstagramのURLでない、または取得に失敗した場合は何もしない
        # (取得失敗時にエラーメッセージを送る仕様にする場合はここでTextSendMessageを送る)
        pass

if __name__ == "__main__":
    # ローカルでのテスト用
    # ポート番号の設定（デフォルト5000）
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
