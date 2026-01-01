#!/bin/bash
# Discord Botをバックグラウンドで起動
python run_discord.py &

# LINE Bot (Gunicorn) をフォアグラウンドで起動
gunicorn run_line:app
