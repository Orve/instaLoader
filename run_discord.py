
import discord
import asyncio
import logging
from typing import Optional

from core.config import DISCORD_BOT_TOKEN
from core.logic import process_instagram_url

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Discordクライアントの設定
intents = discord.Intents.default()
intents.message_content = True  # メッセージ内容の読み取り権限
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Bot起動時のイベント"""
    logger.info(f'Logged in as {client.user} (ID: {client.user.id})')

@client.event
async def on_message(message: discord.Message):
    """
    メッセージ受信時のイベントハンドラ。
    InstagramのURLが含まれている場合、API経由でメディアURLを取得して返信する。
    """
    # 自分自身のメッセージは無視
    if message.author == client.user:
        return

    # メッセージ本文を取得
    content = message.content
    
    # InstagramのURLが含まれているか簡易チェック (最適化のため)
    if "instagram.com/p/" not in content and "instagram.com/reel/" not in content:
        return

    # 同期処理である process_instagram_url を非同期スレッドで実行
    # これにより、API待ち時間中も他のイベント（他ユーザーへの応答など）をブロックしない
    try:
        result = await asyncio.to_thread(process_instagram_url, content)
        
        if result:
            logger.info(f"Found media for message: {message.id}")
            media_url = result["media_url"]
            
            # DiscordはURLを貼るだけで自動的にプレビュー/プレイヤーを展開するため、
            # 単純にURLを返信する実装とする。
            await message.reply(content=media_url)
            
    except Exception as e:
        logger.error(f"Error in on_message: {e}")
        # ユーザーへのエラー通知は、必要に応じて有効化してください
        # await message.reply("エラーが発生しました。")

if __name__ == "__main__":
    if DISCORD_BOT_TOKEN:
        client.run(DISCORD_BOT_TOKEN)
    else:
        logger.error("DISCORD_BOT_TOKEN is not set in environment variables.")
