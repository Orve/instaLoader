
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

## ログと診断（Render）

取得に失敗した投稿は、Render のログで「どの段階で止まったか」を判別できる。

### ログの見方

1. Render ダッシュボードで対象の Web Service を開き、Logs を表示する
2. 失敗した投稿を送った時刻前後のログを探す
3. `rid=` が同じ行が1リクエスト分（LINE は Webhook ごとに生成、Discord はメッセージID）。`stage=` で段階を追う

| stage | 意味 | 代表的な result |
|---|---|---|
| `url_detect` | Instagram URL の検出 | `ok`（shortcode付き）/ `not_found` |
| `config` | 設定確認 | `error reason=api_key_missing` |
| `api` | RapidAPI 通信 | `ok status=200 elapsed_ms=...` / `http_error status=...` / `timeout` / `request_error` |
| `parse` | JSON 解析 | `ok top_keys=...` / `json_error` |
| `extract` | メディア抽出 | `ok count=... types=...` / `no_media` |
| `reply`（LINE） | LINE 返信 | `ok` / `error`（配信失敗）/ `skipped`（取得失敗またはURLなし） |

判別例:
- `stage=api result=http_error` → API 側がエラーを返した
- `stage=api result=ok` のあと `stage=extract result=no_media` → 応答は200だがメディアが含まれなかった（外部参照が制限されている投稿など）
- `stage=extract result=ok` のあと `stage=reply result=error` → 取得は成功し、LINE 配信で失敗した

### ログに出ないもの

APIキー・LINEトークン・署名・Webhook本文・APIレスポンス本文・署名付きメディアURLはログに記録しない。記録するのは段階・結果・HTTPステータス・応答時間・レスポンスのトップレベルのキー名・投稿の shortcode のみ。

### タイムアウト

RapidAPI リクエストにはタイムアウトを設定している（環境変数 `RAPID_API_TIMEOUT`、デフォルト10秒）。タイムアウト時は `stage=api result=timeout` として HTTP エラーと区別して記録される。

### 再現手順（取得できない投稿の切り分け）

1. 同じ投稿 URL を LINE と Discord の両方に送る
2. Discord は共通ロジック（`core/logic.py`）を共有し、失敗時にエラーを返すため、両方で失敗すれば共通側、Discord だけ成功すれば LINE 配信側の問題と分かる
3. ログで `rid` を追い、上表のどの段階で止まったかを確認する
