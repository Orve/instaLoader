#!/bin/bash
# ログがバッファリングされないように -u オプションを追加
# Discord Botをバックグラウンドで起動
python -u run_discord.py &

# RenderのPORT環境変数が設定されていない場合のデフォルト値
PORT=${PORT:-10000}

# LINE Bot (Gunicorn) をフォアグラウンドで起動
# Renderからのアクセスを受け付けるため 0.0.0.0:$PORT に明示的にバインド
exec gunicorn --bind 0.0.0.0:$PORT run_line:app
