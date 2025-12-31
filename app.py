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
            url = f"https://{RAPID_API_HOST}/index"
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

            # --- レスポンス解析 (APIの仕様に合わせて調整してください) ---
            # APIによってレスポンス構造が異なります。
            # 例1: {"media": "https://..."}
            # 例2: [{"url": "https://..."}]
            # 例3: {"results": [{"url": "https://..."}]}
            
            media_url = None
            preview_url = None
            is_video = False

            # 以下は一般的な構造を想定した探索ロジックです
            if isinstance(data, dict):
                if 'media' in data:
                    media_url = data['media']
                elif 'download_url' in data:
                    media_url = data['download_url']
                elif 'results' in data and isinstance(data['results'], list) and data['results']:
                    media_url = data['results'][0].get('url')
            elif isinstance(data, list) and len(data) > 0:
                media_url = data[0].get('url')

            # メディアURLが見つからなかった場合
            if not media_url:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="メディアURLを取得できませんでした😢")
                )
                return

            # 動画か画像かの判定（簡易的）
            if ".mp4" in media_url:
                is_video = True
            
            # プレビュー画像のURL（動画の場合は必須）
            # APIがサムネイルを返さない場合は、適当な画像か動画URLそのものを指定（LINE仕様による）
            preview_url = data.get('thumbnail') or media_url 
            if is_video and not data.get('thumbnail'):
                 # 動画の場合、プレビューに動画URLを指定しても表示されない場合があるため
                 # 本来はサムネイルが必要だが、今回は簡易的に設定
                 preview_url = "https://via.placeholder.com/1024x1024?text=Video"

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
