
import os
from dotenv import load_dotenv
from typing import Optional

# .envファイルを読み込む
load_dotenv()

# --- 環境変数の読み込み ---

# LINE Configuration
LINE_CHANNEL_ACCESS_TOKEN: Optional[str] = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET: Optional[str] = os.environ.get('LINE_CHANNEL_SECRET')

# Discord Configuration
DISCORD_BOT_TOKEN: Optional[str] = os.environ.get('DISCORD_BOT_TOKEN')

# API Key Configuration
RAPID_API_KEY: Optional[str] = os.environ.get('RAPID_API_KEY')
RAPID_API_HOST: str = os.environ.get(
    'RAPID_API_HOST',
    'instagram-downloader-download-instagram-videos-stories.p.rapidapi.com'
)

# RapidAPI リクエストのタイムアウト（秒）。未設定・不正値の場合はデフォルト10秒。
# gunicorn のデフォルト timeout（30秒）より短くし、ワーカーごと止まる前に
# タイムアウトとして検出できるようにする。
try:
    RAPID_API_TIMEOUT: float = float(os.environ.get('RAPID_API_TIMEOUT', '10'))
except ValueError:
    RAPID_API_TIMEOUT = 10.0
