import discord
from discord import app_commands
import instaloader
import os
import shutil
import re
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# --- 設定 ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DOWNLOAD_DIR_BASE = "./temp_downloads"
TARGET_EXTENSIONS = ('.jpg', '.png', '.mp4')
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

# --- Botのセットアップ ---
class InstaBotClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        # コマンドツリーの作成
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # コマンドをサーバーに同期（グローバル同期には時間がかかるため、開発中はGuild指定推奨だが今回は簡易化）
        await self.tree.sync()
        print("Commands synced!")

client = InstaBotClient()

# Instaloader初期化
L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False
)

def download_instagram_content(shortcode):
    """Instaloaderでダウンロードを実行する（ブロッキング処理）"""
    target_dir = os.path.join(DOWNLOAD_DIR_BASE, shortcode)
    
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    current_wd = os.getcwd()
    try:
        os.chdir(DOWNLOAD_DIR_BASE)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=shortcode)
    finally:
        os.chdir(current_wd)
    
    return target_dir

def extract_shortcode(url: str):
    match = re.search(r'instagram\.com/(?:p|reel|reels)/([^/?#&]+)', url)
    return match.group(1) if match else None

# --- スラッシュコマンド定義 ---
@client.tree.command(name="insta", description="Instagramの画像を保存します（他の人には見えません🤫）")
@app_commands.describe(url="Instagramの投稿URL")
async def insta(interaction: discord.Interaction, url: str):
    # まずは「考え中...」を表示（ephemeral=True で自分だけに見えるようにする）
    await interaction.response.defer(ephemeral=True)
    
    shortcode = extract_shortcode(url)
    if not shortcode:
        await interaction.followup.send("URLが正しくないみたいです🥺 `https://www.instagram.com/p/...` の形式を確認してください。", ephemeral=True)
        return

    try:
        # ダウンロード処理
        target_dir = download_instagram_content(shortcode)
        
        files_to_upload = []
        skipped_files = []

        if os.path.exists(target_dir):
            for filename in os.listdir(target_dir):
                file_path = os.path.join(target_dir, filename)
                if filename.lower().endswith(TARGET_EXTENSIONS):
                    if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                        skipped_files.append(filename)
                    else:
                        files_to_upload.append(discord.File(file_path))

        # 送信処理
        if files_to_upload:
            msg = "保存しました！📸"
            if skipped_files:
                msg += f"\n（サイズオーバーでスキップ: {', '.join(skipped_files)}）"
            
            # ephemeral=True なので、この画像は実行した人にしか見えない
            await interaction.followup.send(content=msg, files=files_to_upload, ephemeral=True)
        else:
            await interaction.followup.send("画像や動画が見つかりませんでした😢", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"エラーが発生しました: {str(e)}", ephemeral=True)
    
    finally:
        # クリーンアップ
        try:
            target_dir_path = os.path.join(DOWNLOAD_DIR_BASE, shortcode)
            if os.path.exists(target_dir_path):
                shutil.rmtree(target_dir_path)
        except Exception:
            pass

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

if __name__ == '__main__':
    if DISCORD_TOKEN:
        client.run(DISCORD_TOKEN)
    else:
        print("エラー: DISCORD_TOKEN が設定されていません。")
