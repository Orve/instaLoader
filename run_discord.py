import discord
import asyncio
import logging
from typing import Optional, List

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

async def send_media_embeds(message: discord.Message, result: dict):
    """
    複数のメディアをEmbed形式で送信する。
    
    Args:
        message: 元のDiscordメッセージオブジェクト
        result: process_instagram_urlの戻り値
    """
    if "media_list" in result and len(result["media_list"]) > 0:
        media_list = result["media_list"]
        media_count = len(media_list)
        
        # 複数メディアの場合
        if media_count > 1:
            # まず全体の情報を送信
            info_embed = discord.Embed(
                title="📸 Instagram メディア",
                description=f"{media_count}件のメディアが見つかりました",
                color=discord.Color.blue()
            )
            await message.reply(embed=info_embed)
            
            # 各メディアを個別に送信（Discord Embedの制限を考慮）
            for i, media in enumerate(media_list[:10], 1):  # 最大10個まで
                if media["type"] == "video":
                    # 動画の場合はURLを直接送信（Discordが自動でプレイヤーを展開）
                    await message.channel.send(
                        f"**動画 {i}/{media_count}**\n{media['url']}"
                    )
                else:
                    # 画像の場合はEmbed
                    embed = discord.Embed(
                        title=f"画像 {i}/{media_count}",
                        color=discord.Color.green()
                    )
                    embed.set_image(url=media["url"])
                    await message.channel.send(embed=embed)
                
                # レート制限を避けるため少し待機
                if i < len(media_list) and i < 10:
                    await asyncio.sleep(0.5)
            
            # 10個を超える場合の通知
            if media_count > 10:
                await message.channel.send(
                    f"⚠️ 残り{media_count - 10}個のメディアがありますが、表示を省略しました。"
                )
        else:
            # 単一メディアの場合
            media = media_list[0]
            if media["type"] == "video":
                # 動画はURLを直接送信
                await message.reply(content=media["url"])
            else:
                # 画像はEmbed形式
                embed = discord.Embed(
                    title="Instagram 画像",
                    color=discord.Color.green()
                )
                embed.set_image(url=media["url"])
                await message.reply(embed=embed)
    else:
        # 後方互換性: 古い形式の場合
        media_url = result["media_url"]
        await message.reply(content=media_url)

@client.event
async def on_message(message: discord.Message):
    """
    メッセージ受信時のイベントハンドラ。
    InstagramのURLが含まれている場合、API経由でメディアURLを取得して返信する。
    複数メディア（カルーセル投稿）に対応。
    """
    # 自分自身のメッセージは無視
    if message.author == client.user:
        return

    # メッセージ本文を取得
    content = message.content
    
    # InstagramのURLが含まれているか簡易チェック (最適化のため)
    if "instagram.com/p/" not in content and "instagram.com/reel/" not in content:
        return

    # タイピング表示を開始（処理中であることを示す）
    async with message.channel.typing():
        try:
            # 同期処理である process_instagram_url を非同期スレッドで実行
            # これにより、API待ち時間中も他のイベント（他ユーザーへの応答など）をブロックしない
            result = await asyncio.to_thread(process_instagram_url, content)
            
            if result:
                logger.info(f"Found {result.get('media_count', 1)} media items for message: {message.id}")
                
                # メディアの送信
                await send_media_embeds(message, result)
            else:
                # メディアが取得できなかった場合
                error_embed = discord.Embed(
                    title="❌ エラー",
                    description="メディアの取得に失敗しました。URLを確認してください。",
                    color=discord.Color.red()
                )
                await message.reply(embed=error_embed)
                
        except Exception as e:
            logger.error(f"Error in on_message: {e}")
            # エラー通知
            error_embed = discord.Embed(
                title="⚠️ エラー",
                description="処理中にエラーが発生しました。",
                color=discord.Color.red()
            )
            await message.reply(embed=error_embed)

if __name__ == "__main__":
    if DISCORD_BOT_TOKEN:
        client.run(DISCORD_BOT_TOKEN)
    else:
        logger.error("DISCORD_BOT_TOKEN is not set in environment variables.")