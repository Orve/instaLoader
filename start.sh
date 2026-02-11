#!/bin/bash

# Discord Botを「10秒待ってから」裏でこっそり起動させる
# ( ) で囲んでバックグラウンド(&)にするのがミソです
(sleep 10 && python run_discord.py) &

# LINE Bot (Web Server) はすぐに起動して場所を確保する
gunicorn run_line:app