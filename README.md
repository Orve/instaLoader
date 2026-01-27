
# Multi-Platform Instagram Downloader Bot

LINEとDiscordの両方で動作する、Instagramメディア（画像・動画）ダウンロードBotの統合リポジトリです。
URLを送信するだけで、自動的にメディアを抽出して返信します。

## 特徴

*   **マルチプラットフォーム対応**: ひとつのリポジトリ、ひとつのコアロジックで LINE Bot と Discord Bot の両方を稼働。
*   **ビジネスロジックの共通化**: Instagramの解析処理を `core` モジュールに集約し、保守性を向上。
*   **サーバーレス/コンテナ最適化**:
    *   同期処理 (Flask/LINE) と 非同期処理 (discord.py) のハイブリッド構成。
    *   **コスト最適化アーキテクチャ**: Renderの無料枠 (Free Tier) の Web Service 1つだけで、HTTPサーバーとLINE Bot、Discord Botを全て同時稼働させる構成を採用。

## 技術スタック

*   **言語**: Python 3.10+
*   **フレームワーク**:
    *   **LINE**: Flask, line-bot-sdk
    *   **Discord**: discord.py (Async IO)
*   **外部API**: RapidAPI (Instagram Data)
*   **インフラ**: Render (Web Service)
    *   Gunicorn (WSGI Server)
    *   Shell Scripting (Process Management)

## ディレクトリ構成

```text
.
├── core/                  # システムの中核
│   ├── logic.py           # Instagramメディア抽出の共通ロジック
│   └── config.py          # 環境変数管理
├── run_line.py            # LINE Bot エントリーポイント (Flask)
├── run_discord.py         # Discord Bot エントリーポイント (discord.py)
├── start.sh               # Render用 複合プロセス起動スクリプト
├── Procfile               # Render 起動設定
└── requirements.txt       # 依存ライブラリ
```

## アーキテクチャのポイント

### 1. ロジックの分離と再利用 (`core/`)
プラットフォーム依存の処理（LINEの署名検証、Discordのイベントループなど）と、本質的なビジネスロジック（InstagramAPIの叩き方、データ整形）を完全に分離しました。これにより、将来的なTelegram Bot等の追加も容易です。

### 2. Render Free Tier Hack (`start.sh`)
通常、Webサーバー (LINE) と 常駐型Bot (Discord) は別々のサービスとしてデプロイする必要がありますが、本プロジェクトではシェルスクリプトを用いて単一コンテナ内で並列稼働させています。

```bash
#!/bin/bash
# Discord Botをバックグラウンドで非同期実行
python -u run_discord.py &

# LINE Bot (Web Server) をフォアグラウンドで実行し、コンテナの生存を維持
exec gunicorn --bind 0.0.0.0:$PORT run_line:app
```

## アーキテクチャについて (The "Free Tier" Hack)
PaaS (Render) の無料枠における「Web Serviceは1つしか起動できない」という制約を突破するため、コンテナのエントリーポイントをハックし、単一コンテナ内でWebサーバーとBotプロセスを並列稼働させるアーキテクチャを採用しました。

Render (Web Service) Container
```
┌──────────────────────────────────────────────┐
│  entrypoint: start.sh                        │
│                                              │
│  [Process 1: Foreground]                     │
│  🌊 Gunicorn (Flask / LINE Bot)              │ <--- HTTP Request (Keep Alive)
│       │  (Webサーバーとしてポート待受)           │
│       └─ core/logic.py (共通ロジック)          │
│                                              │
│  [Process 2: Background (&)]                 │
│  🤖 python run_discord.py (Discord Bot)      │ <--- WebSocket (Gateway)
│       │  (常駐プロセスとしてバックグラウンド起動)   │
│       └─ core/logic.py (共通ロジック)          │
└──────────────────────────────────────────────┘
```

## セットアップとデプロイ

### 必須環境変数 (.env)
*   `LINE_CHANNEL_ACCESS_TOKEN`
*   `LINE_CHANNEL_SECRET`
*   `DISCORD_BOT_TOKEN`
*   `RAPID_API_KEY`
*   `RAPID_API_HOST`

### ローカル実行
```bash
# 依存関係のインストール
pip install -r requirements.txt

# 個別に起動 (Window/Mac)
python run_line.py
python run_discord.py
```
