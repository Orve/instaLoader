import os
import sys
import json
import logging
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, VideoSendMessage
)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 環境変数の読み込み ---
# Renderなどのホスティングサービスで環境変数を設定してください
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
RAPID_API_KEY = os.environ.get('RAPID_API_KEY')
RAPID_API_HOST = os.environ.get('RAPID_API_HOST', 'instagram-downloader-download-instagram-videos-stories.p.rapidapi.com')

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    logger.error("LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET is not set.")
    # 起動時に環境変数がない場合はエラーにするか、あるいはデプロイ後の設定待ちとして走らせるか
    # ここではログを出して続行

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

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
    text = event.message.text
    
    # InstagramのURLが含まれているかチェック
    if "instagram.com/p/" in text or "instagram.com/reel/" in text:
        try:
            # ユーザーに確認メッセージを送る（UX向上）や既読をつける等の処理も可能だが
            # ここでは直接APIを叩いて結果を返す
            
            # --- RapidAPI呼び出しロジック ---
            # APIの仕様変更に合わせてエンドポイントを /download に変更
            url = f"https://{RAPID_API_HOST}/download"
            querystring = {"url": text}
            headers = {
                "X-RapidAPI-Key": RAPID_API_KEY,
                "X-RapidAPI-Host": RAPID_API_HOST
            }

            logger.info(f"Fetching media from RapidAPI for URL: {text}")
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"RapidAPI Response: {data}")

            # --- レスポンス解析 (APIの仕様に合わせて調整) ---
            media_url = None
            preview_url = None
            is_video = False

            # 様々なパターンを探索
            def find_url(obj):
                if isinstance(obj, dict):
                    # パターンA: このAPI特有の 'medias' リストがある場合（ここが本命）
                    if 'medias' in obj and isinstance(obj['medias'], list) and len(obj['medias']) > 0:
                        return find_url(obj['medias'][0])

                    # パターンB: キー名探索
                    # 'url' は投稿ページ自体のURLが入っていることがあるので優先度を下げる
                    for key in ['video_url', 'download_url', 'media', 'url']:
                        if key in obj and isinstance(obj[key], str) and obj[key].startswith('http'):
                            # ★重要: Instagramの投稿URLそのもの（HTML）は除外する
                            if "instagram.com/p/" in obj[key] or "instagram.com/reel/" in obj[key]:
                                continue
                            return obj[key]

                    # パターンC: ネストされている場合（body, data, resultsなど）
                    for key in ['body', 'data', 'results', 'items', '0']:
                        if key in obj:
                            res = find_url(obj[key])
                            if res: return res
                elif isinstance(obj, list) and len(obj) > 0:
                    for item in obj:
                        res = find_url(item)
                        if res: return res
                return None

            media_url = find_url(data)

            # メディアURLが見つからなかった場合
            if not media_url:
                logger.error(f"Media URL extraction failed. Response data: {json.dumps(data)}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"メディアURLが見つかりませんでした😢\n解析不能なレスポンスです。")
                )
                return

            # 動画か画像かの判定
            if ".mp4" in media_url or "video" in str(data).lower():
                is_video = True
            
            # プレビュー画像のURL
            # json内からサムネイルを探す、なければプレースホルダー
            preview_url = find_url({k: v for k, v in data.items() if 'thumb' in k or 'cover' in k})
            if not preview_url:
                # 動画の場合はメディアURLをそのまま使ってみる（LINEが自動取得してくれることに期待）
                # ※本来は静止画URL必須
                 preview_url = "https://via.placeholder.com/1024x1024.png?text=No+Preview" if is_video else media_url

            logger.info(f"Extracted Media URL: {media_url}")

            # --- LINEへの返信 ---
            if is_video:
                line_bot_api.reply_message(
                    event.reply_token,
                    VideoSendMessage(
                        original_content_url=media_url,
                        preview_image_url=preview_url # 動画にはプレビュー画像必須
                    )
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    ImageSendMessage(
                        original_content_url=media_url,
                        preview_image_url=media_url
                    )
                )
                
        except Exception as e:
            logger.error(f"Error: {e}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="エラーが発生しました🙇‍♂️\nAPI制限または予期せぬエラーです。")
            )
    else:
        # インスタのURL以外は無視、またはヘルプメッセージを返す
        pass

if __name__ == "__main__":
    # ローカルでのテスト用
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
