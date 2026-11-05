import logging
import uuid

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, VideoSendMessage,
    TemplateSendMessage, ImageCarouselTemplate, ImageCarouselColumn, URIAction
)

from core.config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from core.logic import fetch_instagram_media, failure_message

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

    # Webhook 本文はログに残さない（ユーザーIDやメッセージ本文が含まれるため）。
    # 追跡に必要なのはリクエストを受けた事実とサイズだけとする。
    logger.info("stage=webhook result=received body_bytes=%d", len(body.encode("utf-8")))

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

def create_media_messages(result):
    """
    取得したメディア情報からLINE用のメッセージオブジェクトを作成する。
    
    Args:
        result: process_instagram_urlの戻り値
        
    Returns:
        list: 送信するメッセージオブジェクトのリスト
    """
    messages = []
    
    if "media_list" in result and len(result["media_list"]) > 0:
        media_list = result["media_list"]
        
        # 複数メディアの場合
        if len(media_list) > 1:
            # まず件数を通知
            messages.append(
                TextSendMessage(text=f"📸 {len(media_list)}件のメディアが見つかりました！")
            )
            
            # LINEの制限: 一度に送れるメッセージは最大5個まで
            # 画像と動画を分けて処理
            images = [m for m in media_list if m["type"] == "image"]
            videos = [m for m in media_list if m["type"] == "video"]
            
            # 画像をまとめて送信（最大4枚、残り1枠はテキスト用）
            for i in range(0, len(images), 4):
                batch = images[i:i+4]
                for img in batch:
                    messages.append(
                        ImageSendMessage(
                            original_content_url=img["url"],
                            preview_image_url=img["url"]
                        )
                    )
                # 5個制限に達したら一旦送信するため、ここでbreak
                if len(messages) >= 5:
                    break
            
            # 動画は個別に処理（5個制限があるため、画像の後に送れない可能性がある）
            # 実際の運用では、別のreplyとして送るか、ユーザーに「動画もあります」と通知
            if videos and len(messages) < 5:
                for video in videos[:5-len(messages)]:
                    preview = video["thumbnail"] or "https://via.placeholder.com/1024x1024.png?text=Video"
                    messages.append(
                        VideoSendMessage(
                            original_content_url=video["url"],
                            preview_image_url=preview
                        )
                    )
        else:
            # 単一メディアの場合（従来の処理）
            media = media_list[0]
            if media["type"] == "video":
                preview = media["thumbnail"] or "https://via.placeholder.com/1024x1024.png?text=Video"
                messages.append(
                    VideoSendMessage(
                        original_content_url=media["url"],
                        preview_image_url=preview
                    )
                )
            else:
                messages.append(
                    ImageSendMessage(
                        original_content_url=media["url"],
                        preview_image_url=media["url"]
                    )
                )
    else:
        # 後方互換性: 古い形式の場合
        media_url = result["media_url"]
        preview_url = result.get("preview_url", media_url)
        
        if result.get("media_type") == "video" or result.get("type") == "video":
            messages.append(
                VideoSendMessage(
                    original_content_url=media_url,
                    preview_image_url=preview_url
                )
            )
        else:
            messages.append(
                ImageSendMessage(
                    original_content_url=media_url,
                    preview_image_url=media_url
                )
            )
    
    # LINEの制限により最大5個まで
    return messages[:5]

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
    メッセージ受信時のイベントハンドラ。
    InstagramのURLが含まれている場合、動画/画像を抽出して返信する。
    複数メディア（カルーセル投稿）に対応。
    """
    text = event.message.text

    # Webhook から共通ロジック、返信までを1つのIDで追跡する
    request_id = uuid.uuid4().hex[:12]
    logger.info("rid=%s stage=handle result=start", request_id)

    # 共通ロジックを使用してInstagramの情報を取得
    outcome = fetch_instagram_media(text, request_id=request_id)

    if outcome.get("status") == "no_url":
        # InstagramのURLを含まない通常メッセージには反応しない（現行仕様を維持）
        logger.info("rid=%s stage=reply result=skipped reason=no_url", request_id)
        return

    if outcome.get("status") == "failed":
        # 取得失敗を利用者へ伝える（#3）。文言は理由に応じて core.logic 側で選ぶ
        reason = outcome.get("reason")
        logger.info(
            "rid=%s stage=reply result=failure_notice reason=%s",
            request_id, reason,
        )
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=failure_message(reason)),
            )
        except Exception as e:
            logger.error(
                "rid=%s stage=reply result=error error_type=%s",
                request_id, type(e).__name__,
            )
        return

    result = outcome.get("result")

    if result:
        try:
            # メッセージオブジェクトの作成
            messages = create_media_messages(result)

            if messages:
                logger.info(
                    "rid=%s stage=reply result=attempt messages=%d media_count=%d",
                    request_id, len(messages), result.get('media_count', 1),
                )
                # 複数メディアの送信
                line_bot_api.reply_message(event.reply_token, messages)
                logger.info("rid=%s stage=reply result=ok", request_id)

                # 5個を超えるメディアがある場合の追加通知
                if "media_list" in result and len(result["media_list"]) > 5:
                    # Note: reply_tokenは一度しか使えないため、pushメッセージを使用する必要がある
                    # ただし、push APIは有料プランが必要な場合がある
                    logger.info(f"Total {len(result['media_list'])} media found, but only first 5 can be sent due to LINE limitation")
            else:
                raise Exception("No messages created")

        except Exception as e:
            # 取得は成功しているため、ここでの失敗は配信側の失敗として区別する
            logger.error(
                "rid=%s stage=reply result=error error_type=%s",
                request_id, type(e).__name__,
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました🙇‍♂️\n送信中に問題が発生しました。")
            )
    else:
        # status=ok だが結果が空という想定外の形。呼び出し側は落とさず記録だけ残す
        logger.info("rid=%s stage=reply result=skipped reason=empty_result", request_id)

if __name__ == "__main__":
    # ローカルでのテスト用
    # ポート番号の設定（デフォルト5000）
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)